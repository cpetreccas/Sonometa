import os
import ctypes
import threading
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
        "entry_artist":    ("Artist",    1),
        "entry_title":     ("Title",     2),
        "entry_mixartist": ("MixArtist", 3),
        "entry_album":     ("Album",     4),
        "entry_genre":     ("Genre",     5),
        "entry_publisher": ("Publisher", 6),
        "entry_year":      ("Year",      7),
    }

    CATALOG_KEYS = ("Album", "Genre", "Publisher")

    def __init__(self):
        super().__init__()

        # Estado de la aplicación
        self.folder_path = ""
        self.sort_directions = {}
        self.file_paths_map = {}
        self.traktor_cache = {}
        self.log_history = deque(maxlen=5000)
        self._multi_select_mode = False
        self.log_window = None
        self.log_textbox = None

        self._configure_window()
        self._init_services()
        self._load_app_resources()
        self._setup_ui()
        self._bind_shortcuts()
        self._check_initial_status()

    def _configure_window(self):
        self.title("Sonometa v0.08 - Audio Tag Suite")
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

        self._setup_footer()

        self.search_manager = SearchManager(
            app=self,
            tree=self.grid_panel.tree,
            frame_bottom_ref=self.frame_bottom,
            detail_panel=self.detail_panel,
            grid_panel=self.grid_panel
        )

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

    @property
    def tree(self):
        return self.grid_panel.tree

    @property
    def catalog_values(self):
        return self.catalog_manager.catalog_values

    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.refresh_folder())
        self.bind("<Control-q>", lambda e: self.on_close())
        self.bind("<Control-a>", lambda e: self.grid_panel.select_all_rows())
        self.bind("<Control-A>", lambda e: self.grid_panel.select_all_rows())
        self.bind("<Control-f>", lambda e: self.search_manager.toggle_search_bar())
        self.bind("<Control-F>", lambda e: self.search_manager.toggle_search_bar())
        self.bind("<Escape>", lambda e: self.search_manager.on_escape_pressed(e))

        self.bind_all("<Control-z>", self.undo_manager.undo)
        self.bind_all("<Control-Z>", self.undo_manager.undo)
        self.bind_all("<Control-y>", self.undo_manager.redo)
        self.bind_all("<Control-Y>", self.undo_manager.redo)
        self.bind_all("<Command-z>", self.undo_manager.undo)
        self.bind_all("<Command-Shift-z>", self.undo_manager.redo)

        # Captura universal de navegación (simples y con Shift)
        nav_keys = [
            "<Up>", "<Down>", "<Prior>", "<Next>", "<Home>", "<End>",
            "<Shift-Up>", "<Shift-Down>", "<Shift-Prior>", "<Shift-Next>",
            "<Shift-Home>", "<Shift-End>"
        ]
        for key in nav_keys:
            self.bind_all(key, self._on_global_key)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _check_initial_status(self):
        self.logger.info("Aplicación Sonometa iniciada correctamente.")
        if self.discogs_token:
            self.logger.info("Token de Discogs activo ✓")
        else:
            self.logger.warning("No hay token de Discogs configurado. Ve a Archivo → ⚙ Configuración.")

    def show_themed_dialog(self, title, message, level="info"):
        """Delega la presentación de diálogos emergentes a DialogManager."""
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
        self.traktor_cache.clear()
        self.header_panel.reset_switches()
        self.header_panel.set_switches_state("disabled")
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
        self.destroy()

    def load_audio_files(self, folder):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self.traktor_cache.clear()
        self.header_panel.reset_switches()
        self.header_panel.set_switches_state("disabled")
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
        if self.search_manager.is_visible:
            self.search_manager.apply_search_filter()

        self.logger.info(f"Se encontraron {len(items)} archivo(s) de audio compatibles.")

        # Lanzar la lectura de metadatos de Traktor en segundo plano
        if items:
            threading.Thread(target=self._load_traktor_data_bg, daemon=True).start()

    def _load_traktor_data_bg(self):
        """Hilo secundario que analiza las etiquetas PRIV:TRAKTOR4 de cada archivo."""
        self.label_status.configure(text="Procesando datos de Traktor...")
        paths = list(self.file_paths_map.values())

        for path in paths:
            info = self.audio_manager.get_traktor_info(path)
            self.traktor_cache[path] = info

        # Regresar al hilo principal para habilitar la interfaz
        self.after(0, self._on_traktor_data_loaded)

    def _on_traktor_data_loaded(self):
        self.header_panel.set_switches_state("normal")
        self.label_status.configure(text=f"Listo ({len(self.file_paths_map)} canciones)")
        self.logger.info("Información de Traktor Pro cargada en caché.")

    def apply_traktor_filters(self):
        """Filtra el grid según el estado de los switches."""
        only_unanalyzed = bool(self.header_panel.switch_unanalyzed.get())
        cues_under_2 = bool(self.header_panel.switch_cues.get())

        self.grid_panel.filter_rows_by_traktor(
            only_unanalyzed=only_unanalyzed,
            cues_under_2=cues_under_2
        )

    def _on_global_key(self, event):
        """Redirige las teclas de navegación/selección al Treeview salvo si se edita un campo de texto."""
        if getattr(self, "_is_redirecting_key", False):
            return

        # Si el grid tiene un editor de celda activo, ignorar la captura global
        if hasattr(self, "grid_panel") and self.grid_panel.cell_entry:
            return

        try:
            focused_widget = self.focus_get()
        except (KeyError, AttributeError):
            # Ocurre cuando el popdown del Combobox se cierra o destruye
            return

        if focused_widget is not None:
            widget_class = focused_widget.winfo_class().lower()

            # Ignorar si el foco está en un control de entrada
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