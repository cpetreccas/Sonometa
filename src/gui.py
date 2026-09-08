import os
import ctypes
import threading
import tkinter as tk
from collections import deque
import customtkinter as ctk
from PIL import Image, ImageTk
from customtkinter import filedialog

from grid_panel import GridPanel
from audio_manager import AudioManager
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


class App(ctk.CTk):
    CORP_COLOR = "#6B21A8"
    CORP_HOVER = "#581C87"
    DANGER_COLOR = "#B91C1C"
    DANGER_HOVER = "#991B1B"
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

        self._configure_window()
        self._init_services()
        self._load_app_resources()
        self._setup_ui()
        self._bind_shortcuts()
        self._check_initial_status()

    def _configure_window(self):
        self.title("Sonometa v0.10 - Audio Tag Suite")
        self.geometry("1180x780")
        self.minsize(1000, 680)
        self.after(100, lambda: UiUtils.maximize_window(self))
        self.after(10, lambda: DialogManager.apply_dark_title_bar(self))

    def _init_services(self):
        self.logger = LogManager.setup_logger(self)
        self.undo_manager = UndoManager(self)
        self.audio_manager = AudioManager()
        self.filename_formatter = FilenameFormatter()

        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.DEFAULT_COVER_PATH = os.path.join(base_dir, "assets", "no_cover_art.jpg")

        self.discogs_token = os.getenv("DISCOGS_TOKEN", "RYvclJgMalquxdkpdHutNJEQqGjlaiqtuBvipCfq").strip()

        self.catalog_manager = CatalogManager(self)
        self.catalog_manager.load_catalog_values()
        self.catalog_manager.load_settings()

        # 'Revisar carátulas' activado por defecto
        settings_dict = getattr(self.catalog_manager, "settings", {})
        manual_rev = settings_dict.get("manual_cover_review", True) if isinstance(settings_dict, dict) else True
        self.review_covers_var = tk.BooleanVar(value=manual_rev)

        self.discogs_client = DiscogsClient(token_getter=lambda: self.discogs_token)
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

        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        self.detail_panel = DetailPanel(
            app=self,
            parent=self.frame_main,
            logger=self.logger,
            get_resource_path=UiUtils.get_resource_path
        )
        self.grid_panel = GridPanel(app=self, parent=self.frame_main, logger=self.logger)

        # Mostrar el panel lateral según el estado inicial
        self.detail_panel.frame_sidebar.pack(side="left", fill="y", padx=(0, 10))

        self._setup_footer()

        # Instanciación e integración con SearchManager
        self.search_manager = SearchManager(
            app=self,
            tree=self.grid_panel.tree,
            frame_bottom_ref=self.frame_bottom,
            detail_panel=self.detail_panel,
            grid_panel=self.grid_panel
        )

    def _on_toggle_manual_cover_review(self):
        """Callback directo al cambiar la opción 'revisar carátulas manualmente'."""
        val = self.review_covers_var.get()
        if hasattr(self.catalog_manager, "settings") and isinstance(self.catalog_manager.settings, dict):
            self.catalog_manager.settings["manual_cover_review"] = val
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
            font=ctk.CTkFont(family="Inter", size=11),
            text_color="#9CA3AF"
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

    def set_tree_value(self, values, column_name, new_value):
        idx = self.get_tree_column_index(column_name)
        if idx is None or idx >= len(values):
            return False
        values[idx] = new_value
        return True

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

        # Diálogo de reemplazo masivo de texto en nombres de archivo
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
        if hasattr(self, "detail_panel") and self.detail_panel.audio_player:
            self.detail_panel.audio_player.stop_and_unload()
        self.catalog_manager.save_catalog_values()
        self.catalog_manager.save_settings()
        self.destroy()

    def load_audio_files(self, folder):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self.search_manager.reset_all_tree_items()

        self.logger.info(f"Escaneando carpeta: {folder}")
        items = self.audio_manager.scan_audio_files(folder)

        for count, item in enumerate(items):
            file_path = item["file_path"]
            metadata = item["metadata"]

            for key in self.CATALOG_KEYS:
                val = CatalogManager.normalize_catalog_text(metadata.get(key, ""))
                metadata[key] = val
                self.catalog_manager.add_catalog_value(key, val, persist=False)

            row_id = self.grid_panel.insert_audio_row(metadata, count)
            self.file_paths_map[row_id] = file_path

        self.detail_panel.refresh_catalog_comboboxes()
        self.search_manager.sync_all_tree_items()
        if hasattr(self.header_panel, "entry_search") and self.header_panel.entry_search.get():
            self.search_manager.apply_search_filter()

        self.logger.info(f"Se encontraron {len(items)} archivo(s) de audio compatibles.")

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