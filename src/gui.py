try:
    import audioop
except ImportError:
    import audioop_lts as audioop
    import sys
    sys.modules["audioop"] = audioop
import os
import ctypes
import threading
import time
import tkinter as tk
from collections import deque
import customtkinter as ctk
from customtkinter import filedialog
from src.supabase_client import SupabaseClientManager
from src.cloud_sync_worker import CloudSyncWorker
from grid_panel import GridPanel
from audio_manager import AudioManager
from cache_manager import CacheManager
from detail_panel import DetailPanel
from format_filename import FilenameFormatter
from discogs_client import DiscogsClient
from catalog_manager import CatalogManager
from dialogs import DialogManager
from ui_utils import UiUtils
from log_handler import LogManager
from tool_panel import ToolPanel
from search_manager import SearchManager
from process_manager import ProcessManager
from header_panel import HeaderPanel
from undo_manager import UndoManager
import theme


class App(ctk.CTk):
    CORP_COLOR = theme.PRIMARY
    CORP_HOVER = theme.PRIMARY_HOVER
    DANGER_COLOR = theme.STATUS_DANGER
    DANGER_HOVER = "#DC2626"
    CLEAR_OPTION = "<Limpiar>"
    KEEP_VALUE = "<Mantener>"

    PANEL_FIELD_COL_MAP = {
        "entry_artist":    ("Artist", "Artist"),
        "entry_title":     ("Title", "Title"),
        "entry_mixartist": ("MixArtist", "MixArtist"),
        "entry_album":     ("Album", "Album"),
        "entry_genre":     ("Genre", "Genre"),
        "entry_publisher": ("Publisher", "Publisher"),
        "entry_year":      ("Year", "Year"),
        "entry_comment":   ("Comment", "Comment"),
    }

    CATALOG_KEYS = ("Album", "Genre", "Publisher", "Comment")

    def __init__(self):
        super().__init__()

        # Estado de la aplicación
        self.folder_path = ""
        self.sort_directions = {}
        self.file_paths_map = {}
        self.log_history = deque(maxlen=5000)
        self._multi_select_mode = False

        # 'Ver detalles' visible por defecto al abrir la aplicación
        self.show_detail_panel_var = tk.BooleanVar(value=True)
        self.detail_panel_visible = True

        self.log_window = None
        self.log_textbox = None
        self._is_loading_audio = False
        self._load_job_id = 0
        self._progress_dialog = None

        self._configure_window()
        self._init_services()
        self._load_app_resources()
        self._setup_ui()
        self._bind_shortcuts()
        self._check_initial_status()

    def _configure_window(self):
        self.title("Sonometa v2.0 - Audio Tag Suite")
        self.configure(fg_color=theme.BG_MAIN)
        self.geometry("1180x780")
        self.minsize(1000, 680)
        self.after(100, lambda: UiUtils.maximize_window(self))
        self.after(10, lambda: DialogManager.apply_dark_title_bar(self))

    def _init_services(self):
        self.logger = LogManager.setup_logger(self)
        self.undo_manager = UndoManager(self)

        # Inicializar CacheManager antes de otros servicios
        self.cache_manager = CacheManager()

        # Inicializar cliente de Supabase y motor de sincronización
        self.supabase_manager = SupabaseClientManager()
        self.sync_worker = None
        self.sync_diagnostic_mode = os.getenv("SONOMETA_SYNC_DIAGNOSTIC", "0").strip().lower() in ("1", "true", "yes", "on")

        self.audio_manager = AudioManager(cache_manager=self.cache_manager)
        self.filename_formatter = FilenameFormatter()

        self.DEFAULT_COVER_PATH = UiUtils.get_resource_path("assets/no_cover_art.jpg")

        self.discogs_token = os.getenv("DISCOGS_TOKEN", "").strip()

        self.catalog_manager = CatalogManager(self)
        self.catalog_manager.load_catalog_values()
        self.catalog_manager.load_settings()

        # 'Revisar carátulas' activado por defecto
        manual_rev = getattr(self.catalog_manager, "manual_cover_selection", True)
        self.review_covers_var = tk.BooleanVar(value=manual_rev)

        self.discogs_client = DiscogsClient(
            token_getter=lambda: self.discogs_token,
            cache_manager=self.cache_manager
        )
        self.process_manager = ProcessManager(self)

    def _load_app_resources(self):
        self.app_icon_photo = None
        self.logo_pil, self.header_logo_pil, self.broom_icon, self.process_icon = UiUtils.load_app_icons(self)

        if self.logo_pil:
            try:
                icon_path = UiUtils.get_resource_path("app_icon_temp.ico")
                if not os.path.exists(icon_path):
                    self.logo_pil.save(icon_path, format="ICO", sizes=[(32, 32), (48, 48), (64, 64)])

                self.app_icon_ico = icon_path
                self.iconbitmap(self.app_icon_ico)
            except Exception as e:
                self.logger.warning(f"No se pudo establecer el icono de la app: {e}")

    def _setup_ui(self):
        self.tool_panel = ToolPanel(self)
        self.tool_panel.pack(side="top", fill="x")

        self.header_panel = HeaderPanel(parent=self, app=self, logo_pil=self.header_logo_pil)

        self.frame_main = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        # 1. Panel Lateral Izquierdo (DetailPanel)
        self.detail_panel = DetailPanel(
            app=self,
            parent=self.frame_main,
            logger=self.logger,
            get_resource_path=UiUtils.get_resource_path
        )
        self.detail_panel.frame_sidebar.pack(side="left", fill="y", padx=(0, 10))

        # 2. Contenedor Derecho (Estructura Vertical)
        self.frame_right = ctk.CTkFrame(self.frame_main, fg_color="transparent")
        self.frame_right.pack(side="left", fill="both", expand=True)

        # 3. Instanciar tabla (Padre: self.frame_right)
        self.grid_panel = GridPanel(app=self, parent=self.frame_right, logger=self.logger)

        # Reusar la instancia de filtro que vive dentro de GridPanel.
        self.advanced_filter_panel = self.grid_panel.filter_panel

        self._setup_footer()

        # SearchManager
        self.search_manager = SearchManager(
            app=self,
            tree=self.grid_panel.tree,
            frame_bottom_ref=self.frame_bottom,
            detail_panel=self.detail_panel,
            grid_panel=self.grid_panel
        )

    def open_login_modal(self):
        """Abre el diálogo modal de autenticación desde DialogManager."""
        DialogManager.show_login_dialog(
            self,
            supabase_client=self.supabase_manager,
            on_success_callback=self.on_login_success
        )

    def on_login_success(self):
        self.logger.info("[GUI] Login correcto. Iniciando servicios Cloud...")
        # Diferir la transición para que el cierre del modal termine antes de iniciar tareas cloud.
        self.after(300, self.on_user_logged_in)

    def on_user_logged_in(self):
        if not self.supabase_manager.is_authenticated():
            self.logger.warning("Login cloud inválido: no se inicia la sincronización.")
            return

        if self.sync_worker and self.sync_worker.is_alive():
            self.logger.info("Sincronización Cloud ya está activa.")
            return

        # Instanciar el worker sin lanzarlo todavía
        self.sync_worker = CloudSyncWorker(
            self.cache_manager,
            self.supabase_manager,
            diagnostic_mode=self.sync_diagnostic_mode,
        )

        # Dejar que el bucle de eventos principal (mainloop) respire antes de iniciar el hilo secundario
        self.after(300, self._start_cloud_sync_worker)

    def _start_cloud_sync_worker(self):
        """Arranca CloudSyncWorker de forma totalmente desacoplada de la UI."""
        if not self.sync_worker or self.sync_worker.is_alive():
            return

        try:
            self.sync_worker.start()
        except Exception as e:
            self.logger.error(f"Error iniciando CloudSyncWorker: {e}")

    def _on_toggle_manual_cover_review(self):
        """Callback directo al cambiar la opción 'revisar carátulas manualmente'."""
        val = self.review_covers_var.get()
        self.catalog_manager.manual_cover_selection = val
        self.catalog_manager.save_settings()
        msg = "Activada" if val else "Desactivada"
        self.logger.info(f"Revisión manual de carátulas: {msg}")

    def _setup_footer(self):
        self.frame_bottom = ctk.CTkFrame(self)
        self.frame_bottom.pack(fill="x", padx=15, pady=(5, 10))

        self.progress_bar = ctk.CTkProgressBar(self.frame_bottom, progress_color=self.CORP_COLOR)
        self.progress_bar.pack(fill="x", padx=10, pady=2)
        self.progress_bar.set(0)

        self.label_status = ctk.CTkLabel(
            self.frame_bottom,
            text="Listo",
            anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11),
            text_color=theme.TEXT_MUTED
        )
        self.label_status.pack(fill="x", padx=12, pady=(2, 6))

    def toggle_detail_panel(self):
        """Alterna la visibilidad del panel de detalles lateral según la variable del check."""
        should_show = self.show_detail_panel_var.get()

        if should_show:
            self.detail_panel.frame_sidebar.pack(side="left", fill="y", padx=(0, 10))
            self.detail_panel_visible = True
            self.logger.info("Panel lateral expandido.")
        else:
            self.detail_panel.frame_sidebar.pack_forget()
            self.detail_panel_visible = False
            self.logger.info("Panel lateral colapsado.")

    @property
    def tree(self):
        return self.grid_panel.tree

    def get_tree_columns(self):
        if hasattr(self, "grid_panel") and hasattr(self.grid_panel, "tree"):
            return list(self.grid_panel.tree["columns"])
        return []

    def get_tree_column_index(self, column_name):
        columns = self.get_tree_columns()
        return columns.index(column_name) if column_name in columns else None

    def map_tree_values(self, values):
        columns = self.get_tree_columns()
        row_map = {}
        for idx, col_name in enumerate(columns):
            row_map[col_name] = values[idx] if idx < len(values) else ""
        return row_map

    def get_tree_value(self, values, column_name, default=""):
        idx = self.get_tree_column_index(column_name)
        if idx is None or idx >= len(values):
            return default
        val = values[idx]
        return default if val is None else val

    @property
    def catalog_values(self):
        return self.catalog_manager.catalog_values

    def _on_space_key(self, event):
        """Garantiza que la tecla espacio controle la reproducción solo si no se está editando texto."""
        try:
            focused = self.focus_get()
        except Exception:
            focused = None

        if focused is not None:
            w_class = focused.winfo_class().lower()
            if any(k in w_class for k in ["entry", "text", "spinbox", "combobox"]):
                return

            if getattr(focused, "_is_cell_editing", False):
                return

        if hasattr(self, "grid_panel") and getattr(self.grid_panel, "cell_entry", None):
            return

        if hasattr(self, "detail_panel"):
            self.detail_panel.handle_space_toggle()
            return "break"

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<Control-O>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.refresh_folder())
        self.bind("<Control-q>", lambda e: self.on_close())
        self.bind("<Control-Q>", lambda e: self.on_close())
        self.bind("<Control-a>", lambda e: self.grid_panel.select_all_rows())
        self.bind("<Control-A>", lambda e: self.grid_panel.select_all_rows())
        self.bind("<Control-f>", lambda e: self.focus_header_search())
        self.bind("<Control-F>", lambda e: self.focus_header_search())
        self.bind("<Control-Shift-F>", lambda e: self.advanced_filter_panel.toggle_panel())
        self.bind("<Control-Shift-f>", lambda e: self.advanced_filter_panel.toggle_panel())
        self.bind("<Control-r>", lambda e: self.open_replace_dialog())
        self.bind("<Control-R>", lambda e: self.open_replace_dialog())

        # Conmutación de visibilidad del panel lateral
        def _toggle_shortcut():
            self.show_detail_panel_var.set(not self.show_detail_panel_var.get())
            self.toggle_detail_panel()

        self.bind("<Control-b>", lambda e: _toggle_shortcut())
        self.bind("<Control-B>", lambda e: _toggle_shortcut())
        self.bind("<Escape>", lambda e: self.search_manager.on_escape_pressed(e))
        self.tree.bind("<Delete>", lambda e: self.process_manager.delete_selected_files())

        # Atajo global de tecla Espacio para reproducción/pausa
        self.bind_all("<space>", self._on_space_key)

        # Atajos Deshacer / Rehacer
        self.bind_all("<Control-z>", self.undo_manager.undo)
        self.bind_all("<Control-Z>", self.undo_manager.undo)
        self.bind_all("<Control-y>", self.undo_manager.redo)
        self.bind_all("<Control-Y>", self.undo_manager.redo)
        self.bind_all("<Command-z>", self.undo_manager.undo)
        self.bind_all("<Command-Shift-z>", self.undo_manager.redo)

        # Zoom de la tabla
        self.bind_all("<Control-plus>", lambda e: self.grid_panel._on_key_zoom_in(e))
        self.bind_all("<Control-KP_Add>", lambda e: self.grid_panel._on_key_zoom_in(e))
        self.bind_all("<Control-minus>", lambda e: self.grid_panel._on_key_zoom_out(e))
        self.bind_all("<Control-KP_Subtract>", lambda e: self.grid_panel._on_key_zoom_out(e))

        self.bind_all("<Control-0>", lambda e: self.grid_panel._on_key_zoom_reset(e))
        self.bind_all("<Control-KP_0>", lambda e: self.grid_panel._on_key_zoom_reset(e))
        self.bind_all("<Control-Key-0>", lambda e: self.grid_panel._on_key_zoom_reset(e))

        # Redirección global de teclado a la tabla
        nav_keys = [
            "<Up>", "<Down>", "<Prior>", "<Next>", "<Home>", "<End>",
            "<Shift-Up>", "<Shift-Down>", "<Shift-Prior>", "<Shift-Next>",
            "<Shift-Home>", "<Shift-End>"
        ]
        for key in nav_keys:
            self.bind_all(key, self._on_global_key)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def focus_header_search(self):
        """Pone el foco en el cuadro de búsqueda del Header al presionar Ctrl+F."""
        if hasattr(self, "header_panel") and hasattr(self.header_panel, "entry_search"):
            self.header_panel.entry_search.focus()
            self.header_panel.entry_search.select_range(0, "end")

    def open_replace_dialog(self):
        """Abre el diálogo modal para reemplazar texto en nombres de archivo sobre el grid."""
        target_items = []
        for row_id, file_path in self.file_paths_map.items():
            filename = os.path.basename(file_path) if file_path else ""
            target_items.append({
                "row_id": row_id,
                "filename": filename
            })

        DialogManager.show_replace_filename_dialog(self, target_items)

    def _check_initial_status(self):
        self.logger.info("Aplicación Sonometa iniciada correctamente.")
        if self.discogs_token:
            self.logger.info("Token de Discogs activo ✓")
        else:
            self.logger.warning("No hay token de Discogs configurado.")

        if self.supabase_manager.is_authenticated():
            self.on_user_logged_in()

    def show_themed_dialog(self, title, message, level="info"):
        DialogManager.show_themed_dialog(self, title, message, level)

    # --- Acciones Principales ---

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path = path
            self.header_panel.set_folder_path(path)
            self.load_audio_files(path)

    def refresh_folder(self):
        if not self.folder_path:
            self.logger.warning("No hay ninguna carpeta seleccionada para actualizar.")
            return
        self.logger.info("Actualizando lista de archivos...")
        self.load_audio_files(self.folder_path)

    def clear_all(self):
        if hasattr(self, "audio_manager") and hasattr(self.audio_manager, "clear_runtime_caches"):
            self.audio_manager.clear_runtime_caches()
        if hasattr(self, "discogs_client") and hasattr(self.discogs_client, "clear_runtime_cache"):
            self.discogs_client.clear_runtime_cache()

        if self._multi_select_mode:
            self.detail_panel.exit_multi_mode()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self.search_manager.reset_all_tree_items()

        self.detail_panel.clear_fields()
        self.folder_path = ""
        self.header_panel.set_folder_path("")
        self.progress_bar.set(0)
        self.detail_panel.refresh_process_button_text(0)
        self.logger.info("Lista y estado limpiados.")

    def on_close(self):
        if hasattr(self, "sync_worker") and self.sync_worker:
            self.sync_worker.stop()
            self.sync_worker = None
        if hasattr(self, "detail_panel") and self.detail_panel.audio_player:
            self.detail_panel.audio_player.stop_and_unload()
        if hasattr(self, "audio_manager") and hasattr(self.audio_manager, "clear_runtime_caches"):
            self.audio_manager.clear_runtime_caches()
        if hasattr(self, "discogs_client") and hasattr(self.discogs_client, "clear_runtime_cache"):
            self.discogs_client.clear_runtime_cache()
        self.catalog_manager.save_catalog_values()
        self.catalog_manager.save_settings()
        self.destroy()

    def load_audio_files(self, folder):
        if self._is_loading_audio:
            self.logger.warning("Ya hay una carga en curso. Espera a que finalice para iniciar otra.")
            return

        scan_started_at = time.perf_counter()
        self._is_loading_audio = True
        self._load_job_id += 1
        job_id = self._load_job_id

        if hasattr(self, "audio_manager") and hasattr(self.audio_manager, "clear_runtime_caches"):
            self.audio_manager.clear_runtime_caches()

        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self.search_manager.reset_all_tree_items()

        self.logger.info(f"Escaneando carpeta: {folder}")
        self.progress_bar.set(0)
        self.label_status.configure(text="Iniciando escaneo masivo...")
        self._progress_dialog = DialogManager.show_progress_dialog(
            self,
            title_text="Escaneando colección",
            message="Leyendo metadatos de audio...",
            total=0
        )

        def _scan_progress(current, total, current_file):
            def _ui_update():
                if job_id != self._load_job_id or not self.winfo_exists():
                    return

                ratio = (current / total) if total > 0 else 0.0
                self.progress_bar.set(ratio)
                self.label_status.configure(text=f"Escaneando {current:,} / {total:,} canciones...")

                if self._progress_dialog and self._progress_dialog.winfo_exists():
                    self._progress_dialog.set_counter(current, total, current_file)

            try:
                self.after(0, _ui_update)
            except Exception:
                pass

        def _scan_worker():
            items = []
            error_message = None
            try:
                items = self.audio_manager.scan_audio_files(folder, progress_callback=_scan_progress)
            except Exception as exc:
                error_message = str(exc)

            def _done():
                self._on_scan_finished(job_id, items, scan_started_at, error_message)

            try:
                self.after(0, _done)
            except Exception:
                pass

        threading.Thread(target=_scan_worker, daemon=True, name="SonometaScanWorker").start()

    def _on_scan_finished(self, job_id, items, started_at, error_message=None):
        if job_id != self._load_job_id or not self.winfo_exists():
            return

        if error_message:
            self._finalize_load_job(job_id, started_at, loaded_count=0, error_message=error_message)
            return

        total = len(items)
        if self._progress_dialog and self._progress_dialog.winfo_exists():
            self._progress_dialog.set_text(
                title="Insertando en grilla",
                message="Renderizando registros en lotes..."
            )

        self._insert_items_in_batches(job_id, items, started_at, batch_size=300)

    def _insert_items_in_batches(self, job_id, items, started_at, batch_size=300):
        total = len(items)
        cursor = 0

        def _insert_step():
            nonlocal cursor
            if job_id != self._load_job_id or not self.winfo_exists():
                return

            end = min(cursor + batch_size, total)
            raw_batch = items[cursor:end]
            normalized_batch = []

            for item in raw_batch:
                file_path = item.get("file_path", "")
                metadata = dict(item.get("metadata") or {})

                for key in self.CATALOG_KEYS:
                    val = CatalogManager.normalize_catalog_text(metadata.get(key, ""))
                    metadata[key] = val
                    self.catalog_manager.add_catalog_value(key, val, persist=False)

                normalized_batch.append({"file_path": file_path, "metadata": metadata})

            inserted_rows = self.grid_panel.insert_audio_rows_batch(normalized_batch, start_count=cursor)
            for row_id, file_path in inserted_rows:
                if row_id and file_path:
                    self.file_paths_map[row_id] = file_path

            cursor = end
            ratio = (cursor / total) if total > 0 else 0.0
            self.progress_bar.set(ratio)
            self.label_status.configure(text=f"Insertando {cursor:,} / {total:,} canciones...")

            if self._progress_dialog and self._progress_dialog.winfo_exists():
                self._progress_dialog.set_text(
                    title="Insertando en grilla",
                    message="Renderizando registros en lotes...",
                    counter_text=f"Procesando {cursor:,} / {total:,} canciones..."
                )
                self._progress_dialog.set_progress(ratio)

            if cursor < total:
                self.after(1, _insert_step)
                return

            self._finalize_load_job(job_id, started_at, loaded_count=total)

        self.after(0, _insert_step)

    def _finalize_load_job(self, job_id, started_at, loaded_count, error_message=None):
        if job_id != self._load_job_id:
            return

        try:
            if error_message:
                self.label_status.configure(text="Error durante la carga de audio.")
                self.progress_bar.set(0)
                self.logger.error(f"Error al cargar archivos de audio: {error_message}")
            else:
                self.detail_panel.refresh_catalog_comboboxes()
                self.search_manager.sync_all_tree_items()
                if hasattr(self.header_panel, "entry_search") and self.header_panel.entry_search.get():
                    self.search_manager.apply_search_filter()

                self.progress_bar.set(1 if loaded_count > 0 else 0)
                self.label_status.configure(text=f"Carga completada: {loaded_count:,} canciones.")
                self.logger.info(f"Se encontraron {loaded_count} archivo(s) de audio compatibles.")
        finally:
            if self._progress_dialog and self._progress_dialog.winfo_exists():
                self._progress_dialog.close()
            self._progress_dialog = None
            self._is_loading_audio = False

    def _on_global_key(self, event):
        if getattr(self, "_is_redirecting_key", False):
            return

        # Si hay una celda en edición activa en el GridPanel, no redirigir teclas
        if hasattr(self, "grid_panel") and getattr(self.grid_panel, "cell_entry", None):
            return

        try:
            focused_widget = self.focus_get()
        except (KeyError, AttributeError, Exception):
            return

        if focused_widget is not None:
            try:
                widget_class = focused_widget.winfo_class().lower()
            except AttributeError:
                widget_class = ""

            if any(k in widget_class for k in ["entry", "text", "spinbox", "combobox"]):
                return

            if getattr(focused_widget, "_is_cell_editing", False):
                return

        tree = self.grid_panel.tree
        if not tree.get_children(""):
            return

        if focused_widget == tree:
            return

        try:
            self._is_redirecting_key = True
            tree.focus_set()
            tree.event_generate(
                f"<{event.type.name}>",
                keysym=event.keysym,
                keycode=event.keycode,
                state=event.state
            )
        except Exception:
            pass
        finally:
            self._is_redirecting_key = False

        return "break"


if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('sonometa.audiotagsuite.1.0')
    except Exception:
        pass

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()