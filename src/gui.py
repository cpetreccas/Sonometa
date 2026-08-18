import logging
import os
import ctypes
import io
import re
from collections import deque
import tkinter as tk
from grid_panel import GridPanel
import customtkinter as ctk
from customtkinter import filedialog
from PIL import Image, ImageTk
from audio_manager import AudioManager
from detail_panel import DetailPanel
from format_filename import FilenameFormatter
from discogs_client import DiscogsClient
from catalog_manager import CatalogManager
from dialogs import DialogManager
from ui_utils import UiUtils

AUDIO_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.aac', '.wav', '.ogg', '.wma', '.aiff')

ruta_logo = UiUtils.get_resource_path("assets/logo_blanco.png")
if os.path.exists(ruta_logo):
    try:
        img_pil = Image.open(ruta_logo)
        icono_procesar = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(20, 20))
    except Exception:
        icono_procesar = None
else:
    icono_procesar = None


class TextHandler(logging.Handler):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance

    def emit(self, record):
        msg = self.format(record)
        self.app_instance.log_history.append(msg)
        # Programar el update en el hilo de UI evita errores si llega desde callback externo.
        try:
            self.app_instance.after(0, lambda: self.app_instance.label_status.configure(text=record.getMessage()))
            self.app_instance.after(0, lambda: self.app_instance.append_log_to_dialog(msg))
        except Exception:
            pass


logger = logging.getLogger("Sonometa")
logger.setLevel(logging.INFO)

formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('sonometa.audiotagsuite.1.0')
except Exception:
    pass

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    CORP_COLOR = "#6B21A8"
    CORP_HOVER = "#581C87"
    DANGER_COLOR = "#B91C1C"
    DANGER_HOVER = "#991B1B"
    CLEAR_OPTION = "<Limpiar>"
    KEEP_VALUE = "<Mantener>"

    # Mapping attr_name → (tag_field_name, col_index_in_tree)
    PANEL_FIELD_COL_MAP = {
        "entry_artist":    ("Artist",    1),
        "entry_title":     ("Title",     2),
        "entry_mixartist": ("MixArtist", 3),
        "entry_album":     ("Album",     4),
        "entry_genre":     ("Genre",     5),
        "entry_publisher": ("Publisher", 6),
        "entry_year":      ("Year",      7),
    }

    def __init__(self):
        super().__init__()

        # Lógica de negocio de audio delegada a AudioManager (SRP)
        self.audio_manager = AudioManager()
        self.filename_formatter = FilenameFormatter()
        self.discogs_client = DiscogsClient(token_getter=lambda: self.discogs_token)
        self.catalog_manager = CatalogManager(self)

        self.title("Sonometa v0.06 - Audio Tag Suite")
        self.geometry("1180x780")
        self.minsize(1000, 680)
        self.after(100, lambda: UiUtils.maximize_window(self))
        self.after(10, lambda: DialogManager.apply_dark_title_bar(self))
        self.folder_path = ""
        self.sort_directions = {}
        self.file_paths_map = {}
        self.cell_entry = None
        self.log_history = deque(maxlen=5000)
        self._multi_select_mode = False
        self._multi_entries: dict = {}    # alias al panel lateral (se asigna tras crear DetailPanel)
        self.log_window = None
        self.log_textbox = None
        self.search_var = tk.StringVar()
        self._search_trace_id = None
        self._search_visible = False
        self._all_tree_items = []
        self.catalog_fields = self.catalog_manager.catalog_fields
        self.catalog_labels = self.catalog_manager.catalog_labels
        self.catalog_values = self.catalog_manager.catalog_values
        self.catalog_file_path = self.catalog_manager.get_catalog_file_path()
        self.load_catalog_values()

        # Token Discogs (leído del archivo de config, con fallback a variable de entorno)
        self.discogs_token = os.getenv("DISCOGS_TOKEN", "").strip()
        self.settings_file_path = self.catalog_manager.get_settings_file_path()
        self.catalog_values = self.catalog_manager.catalog_values
        self.catalog_manager.get_catalog_file_path()
        self.catalog_manager.load_settings()

        self.gui_log_handler = TextHandler(self)
        self.gui_log_handler.setFormatter(formatter)
        logger.addHandler(self.gui_log_handler)

        self.ico_path = UiUtils.get_resource_path("assets/logo.ico")
        png_path = UiUtils.get_resource_path("assets/logo.png")
        ruta_logo = UiUtils.get_resource_path("assets/logo_blanco.png")
        self.app_icon_photo = None

        icon_broom_img = Image.open("assets/broom_icon.png")
        self.broom_icon = ctk.CTkImage(
            light_image=icon_broom_img,
            dark_image=icon_broom_img,
            size=(18, 18)
        )

        if os.path.exists(self.ico_path):
            self.iconbitmap(self.ico_path)

        logo_pil = None
        if os.path.exists(png_path):
            logo_pil = Image.open(png_path)
            img_icon = ImageTk.PhotoImage(logo_pil)
            self.app_icon_photo = img_icon
            self.wm_iconphoto(True, img_icon)

        self.setup_custom_dark_menu()

        # Barra superior
        self.frame_top = ctk.CTkFrame(self)
        self.frame_top.pack(fill="x", padx=15, pady=(5, 5))

        if logo_pil is not None:
            logo_img = ctk.CTkImage(
                light_image=logo_pil,
                dark_image=logo_pil,
                size=(180, 43)
            )
            self.label_logo = ctk.CTkLabel(self.frame_top, image=logo_img, text="")
            self.label_logo.pack(side="left", padx=10, pady=5)

        self.btn_browse = ctk.CTkButton(
            self.frame_top,
            text="📁 Seleccionar Carpeta",
            fg_color=self.CORP_COLOR,
            hover_color=self.CORP_HOVER,
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self.browse_folder
        )
        self.btn_browse.pack(side="left", padx=5, pady=5)

        self.btn_refresh = ctk.CTkButton(
            self.frame_top,
            text="🔄 Actualizar",
            width=100,
            fg_color=self.CORP_COLOR,
            hover_color=self.CORP_HOVER,
            font=ctk.CTkFont(family="Inter", size=13, weight="bold"),
            height=32,
            command=self.refresh_folder
        )
        self.btn_refresh.pack(side="left", padx=5, pady=5)

        self.label_folder = ctk.CTkLabel(self.frame_top, text="Ninguna carpeta seleccionada", text_color="gray")
        self.label_folder.pack(side="left", padx=10, pady=5)

        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        # El panel de etiquetas se crea primero para reservar el ancho lateral.
        self.detail_panel = DetailPanel(
            app=self,
            parent=self.frame_main,
            logger=logger,
            get_resource_path=UiUtils.get_resource_path,
            fallback_process_icon=icono_procesar
        )
        # Compatibilidad con referencias existentes en la app.
        self.frame_sidebar = self.detail_panel.frame_sidebar
        self.panel_combo_fields = self.detail_panel.panel_combo_fields
        self.tag_entries = self.detail_panel.tag_entries
        self._multi_entries = self.detail_panel.multi_entries
        self.label_cover = self.detail_panel.label_cover
        self.btn_process = self.detail_panel.btn_process
        self.grid_panel = GridPanel(app=self, parent=self.frame_main, logger=logger)
        self.tree = self.grid_panel.tree
        self.columns = self.grid_panel.columns
        self.vsb = self.grid_panel.vsb
        self.hsb = self.grid_panel.hsb
        self.setup_search_bar()

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

        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.refresh_folder())
        self.bind("<Control-q>", lambda e: self.on_close())
        self.bind("<Control-a>", lambda e: self.select_all_rows())
        self.bind("<Control-f>", self.toggle_search_bar)
        self.bind("<Control-F>", self.toggle_search_bar)
        self.bind("<Escape>", self.on_escape_pressed)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        logger.info("Aplicación Sonometa iniciada correctamente.")
        if self.discogs_token:
            logger.info("Token de Discogs activo ✓")
        else:
            logger.warning("No hay token de Discogs configurado. Ve a Archivo → ⚙ Configuración.")


    def load_catalog_values(self):
        self.catalog_manager.load_catalog_values()

    def normalize_catalog_text(self, value):
        return CatalogManager.normalize_catalog_text(value)

    def save_catalog_values(self):
        self.catalog_manager.save_catalog_values()

    def add_catalog_value(self, field_name, value, persist=False):
        return self.catalog_manager.add_catalog_value(
            field_name, value, persist=persist
        )

    def get_catalog_combo_values(self, catalog_key):
        return self.catalog_manager.get_catalog_combo_values(catalog_key)

    def get_catalog_column_info(self, catalog_key):
        return CatalogManager.get_catalog_column_info(catalog_key)

    def apply_catalog_value_change(self, catalog_key, old_value, new_value):
        return self.catalog_manager.apply_catalog_value_change(
            catalog_key, old_value, new_value
        )

    def rename_catalog_value(self, catalog_key, old_value, new_value):
        return self.catalog_manager.rename_catalog_value(
            catalog_key, old_value, new_value
        )

    def setup_custom_dark_menu(self):
        self.menu_bar_frame = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="#181818")
        self.menu_bar_frame.pack(side="top", fill="x")

        self.menu_archivo = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1, relief="flat", font=('Segoe UI', 10))
        self.menu_archivo.add_command(label="Seleccionar carpeta...  (Ctrl+O)", command=self.browse_folder)
        self.menu_archivo.add_command(label="Actualizar  (F5)", command=self.refresh_folder)
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(label="⚙ Configuración (Token Discogs)", command=lambda: DialogManager.show_settings_dialog(self, logger))
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(label="Cerrar  (Ctrl+Q)", command=self.destroy)

        self.menu_acciones = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1, relief="flat", font=('Segoe UI', 10))
        self.menu_acciones.add_command(label="Procesar con Discogs", command=self.process_discogs_data)
        self.menu_acciones.add_command(label="Seleccionar todo  (Ctrl+A)", command=self.select_all_rows)
        self.menu_acciones.add_command(label="Buscar en la lista  (Ctrl+F)", command=self.toggle_search_bar)
        self.menu_acciones.add_separator()
        self.menu_acciones.add_command(label="Limpiar todo", command=self.clear_all_loaded_metadata)

        self.menu_gestionar = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1, relief="flat", font=('Segoe UI', 10))
        self.menu_gestionar.add_command(label="Géneros", command=lambda: DialogManager.open_catalog_manager(self, "Genre"))
        self.menu_gestionar.add_command(label="Álbumes", command=lambda: DialogManager.open_catalog_manager(self, "Album"))
        self.menu_gestionar.add_command(label="Etiquetas", command=lambda: DialogManager.open_catalog_manager(self, "Publisher"))

        self.menu_ayuda = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1, relief="flat", font=('Segoe UI', 10))
        self.menu_ayuda.add_command(label="Atajos de teclado", command=lambda: DialogManager.show_keyboard_shortcuts_dialog(self))
        self.menu_ayuda.add_command(label="Ver logs", command=lambda: DialogManager.show_logs_dialog(self))
        self.menu_ayuda.add_separator()
        self.menu_ayuda.add_command(label="Acerca de Sonometa", command=lambda: DialogManager.show_about_dialog(self))

        def create_menu_btn(text, menu_widget):
            btn = ctk.CTkButton(
                self.menu_bar_frame,
                text=text,
                width=65,
                height=24,
                fg_color="transparent",
                hover_color="#2A2D32",
                text_color="#E0E0E0",
                font=ctk.CTkFont(family="Inter", size=13)
            )
            btn.configure(command=lambda: menu_widget.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height()))
            btn.pack(side="left", padx=2, pady=2)

        create_menu_btn("Archivo", self.menu_archivo)
        create_menu_btn("Acciones", self.menu_acciones)
        create_menu_btn("Gestionar", self.menu_gestionar)
        create_menu_btn("Ayuda", self.menu_ayuda)


    def setup_search_bar(self):
        self.frame_search = ctk.CTkFrame(self)

        self.entry_search = ctk.CTkEntry(
            self.frame_search,
            textvariable=self.search_var,
            placeholder_text="Buscar por archivo, artista, titulo, album, genero...",
            height=30
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=6)

        self.btn_close_search = ctk.CTkButton(
            self.frame_search,
            text="X",
            width=32,
            height=30,
            fg_color="#374151",
            hover_color="#1F2937",
            command=self.hide_search_bar
        )
        self.btn_close_search.pack(side="right", padx=(0, 10), pady=6)

        self.entry_search.bind("<Escape>", lambda _e: self.hide_search_bar() or "break")
        self._search_trace_id = self.search_var.trace_add("write", self._on_search_text_changed)

    def toggle_search_bar(self, event=None):
        if self._search_visible:
            self.hide_search_bar()
        else:
            self.show_search_bar()
        return "break"

    def show_search_bar(self):
        if self._search_visible:
            self.entry_search.focus_set()
            return
        self.frame_search.pack(fill="x", padx=15, pady=(0, 2), before=self.frame_bottom)
        self._search_visible = True
        self.entry_search.focus_set()
        self.apply_search_filter()

    def hide_search_bar(self):
        if self._search_visible:
            self.frame_search.pack_forget()
            self._search_visible = False
        if self.search_var.get():
            self.search_var.set("")
        self.apply_search_filter()
        self.focus_set()

    def on_escape_pressed(self, event=None):
        if self._search_visible:
            self.hide_search_bar()
            return "break"
        return None

    def _on_search_text_changed(self, *_args):
        if self._search_visible:
            self.apply_search_filter()

    @staticmethod
    def _build_row_search_text(values):
        searchable_indexes = (0, 1, 2, 3, 4, 5, 6, 7)
        parts = []
        for idx in searchable_indexes:
            if idx < len(values) and values[idx] is not None:
                parts.append(str(values[idx]))
        return " ".join(parts).lower()

    def _sync_all_tree_items(self):
        existing_ids = [row_id for row_id in self._all_tree_items if self.tree.exists(row_id)]
        for row_id in self.tree.get_children(""):
            if row_id not in existing_ids:
                existing_ids.append(row_id)
        self._all_tree_items = existing_ids

    def _retag_visible_rows(self):
        for index, row_id in enumerate(self.tree.get_children("")):
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(row_id, tags=(tag,))

    def apply_search_filter(self):
        self._sync_all_tree_items()
        query = self.search_var.get().strip().lower()

        matching_rows = []
        for row_id in self._all_tree_items:
            if not self.tree.exists(row_id):
                continue
            values = self.tree.item(row_id, "values")
            if not query or query in self._build_row_search_text(values):
                matching_rows.append(row_id)

        current_rows = self.tree.get_children("")
        if current_rows:
            self.tree.detach(*current_rows)

        for row_id in matching_rows:
            if self.tree.exists(row_id):
                self.tree.reattach(row_id, "", "end")

        self._retag_visible_rows()

        visible_set = set(self.tree.get_children(""))
        selected_visible = [row_id for row_id in self.tree.selection() if row_id in visible_set]
        self.tree.selection_set(selected_visible)

        self.detail_panel.refresh_process_button_text(len(selected_visible))
        self.detail_panel.on_row_select(None)
        if hasattr(self.grid_panel, "_update_tree_scrollbars"):
            self.grid_panel._update_tree_scrollbars()


    def process_discogs_data(self):
        target_rows = self.tree.selection()
        if not target_rows:
            target_rows = self.tree.get_children()

        if not target_rows:
            DialogManager.show_themed_dialog(self, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

        # Bloquear el botón y dar feedback visual al usuario
        if hasattr(self, 'btn_process'):
            self.btn_process.configure(state="disabled", text="Procesando...")
            self.update_idletasks()

        try:
            words_to_omit = [
                r'\bfeat\.\b', r'\bfeat\b',
                r'\bft\.\b', r'\bft\b',
                r'\bpres\.\b', r'\bpres\b',
                r'\bpresents\b'
            ]
            omit_pattern = re.compile('|'.join(words_to_omit), flags=re.IGNORECASE)

            total_files = len(target_rows)
            logger.info(f"Iniciando procesado para {total_files} archivo(s)...")

            processed = 0
            for row_id in target_rows:
                file_path = self.file_paths_map.get(row_id)
                if not file_path or not os.path.exists(file_path):
                    continue

                values = list(self.tree.item(row_id, "values"))

                # Validar campos de catálogo en cada fila antes de procesar.
                catalog_fields = (("Album", 4), ("Genre", 5), ("Publisher", 6))
                invalid_catalog_fields = []
                for field_name, col_index in catalog_fields:
                    if col_index >= len(values):
                        continue
                    current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
                    if not current_value:
                        continue

                    normalized_value = self.normalize_catalog_text(current_value)
                    allowed_values = {
                        self.normalize_catalog_text(v)
                        for v in self.catalog_values.get(field_name, [])
                        if str(v).strip()
                    }
                    if normalized_value not in allowed_values:
                        values[col_index] = ""
                        self.save_single_tag(file_path, field_name, "")
                        invalid_catalog_fields.append(field_name)

                if invalid_catalog_fields:
                    self.tree.item(row_id, values=values)
                    logger.info(
                        f"Se limpiaron campos fuera de catálogo en '{os.path.basename(file_path)}': "
                        f"{', '.join(invalid_catalog_fields)}"
                    )

                # --- PASO 1: Formatear y Renombrar archivo ---
                old_filename = os.path.basename(file_path)
                new_filename = self.filename_formatter.format_filename_pattern(old_filename)
                dir_name = os.path.dirname(file_path)
                new_file_path = os.path.join(dir_name, new_filename)

                if old_filename != new_filename:
                    try:
                        os.rename(file_path, new_file_path)
                        self.file_paths_map[row_id] = new_file_path
                        file_path = new_file_path

                        values[0] = new_filename
                        self.tree.item(row_id, values=values)
                        logger.info(f"Renombrado archivo: '{old_filename}' -> '{new_filename}'")
                    except Exception as e:
                        logger.error(f"No se pudo renombrar el archivo '{old_filename}': {str(e)}")

                # --- PASO 2: Extraer Intérprete, Título y MIXARTIST desde el nombre ---
                clean_name = os.path.splitext(new_filename)[0]

                artist_parsed = ""
                title_parsed = clean_name
                mixartist_parsed = ""

                # Extraer paréntesis para MIXARTIST (sin paréntesis)
                parentheses = re.findall(r'\((.*?)\)', clean_name)
                if parentheses:
                    mixartist_parsed = " ".join(parentheses).strip()
                    clean_name = re.sub(r'\(.*?\)', '', clean_name).strip()

                # Separar por el guión medio
                if " - " in clean_name:
                    parts = clean_name.split(" - ", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()
                elif "-" in clean_name:
                    parts = clean_name.split("-", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()

                metadata_changes = []
                metadata_mappings = (
                    (1, "Artist", "Autor", artist_parsed),
                    (2, "Title", "Título", title_parsed),
                    (3, "MixArtist", "Remix", mixartist_parsed),
                )
                for col_index, tag_name, label, new_value in metadata_mappings:
                    previous_value = str(values[col_index]).strip() if col_index < len(values) and values[col_index] is not None else ""
                    if col_index < len(values):
                        values[col_index] = new_value
                    self.save_single_tag(file_path, tag_name, new_value)

                    if previous_value != new_value:
                        action = "vaciado" if not new_value else "actualizado"
                        metadata_changes.append(
                            f"{label} {action}: '{previous_value}' -> '{new_value}'"
                        )

                self.tree.item(row_id, values=values)
                already_has_cover = self.row_has_cover(row_id)
                if already_has_cover:
                    logger.info(f"Se omite solo la descarga de carátula para '{new_filename}' porque ya tiene una incrustada.")

                # --- PASO 3: Búsqueda de metadatos adicionales en Discogs (Año y Carátula) ---
                query_term = self.build_discogs_query(
                    values[1] if len(values) > 1 else "",
                    values[2] if len(values) > 2 else "",
                    fallback_text=re.sub(r'^\d+[\s\-_.]*', '', clean_name)
                )
                query_term = omit_pattern.sub('', query_term)
                query_term = query_term.replace('_', ' ')
                query_term = re.sub(r'\s+[._-]\s+', ' ', query_term)
                query_term = re.sub(r'\s+', ' ', query_term).strip()

                logger.info(f"Procesando archivo: '{new_filename}' (Búsqueda Discogs: '{query_term}')")

                _, _, year, cover_url = self.discogs_client.search_release(query_term)

                if year:
                    values[7] = str(year)
                    self.save_single_tag(file_path, "Year", str(year))

                if already_has_cover:
                    values[8] = "Sí"
                    self.update_row_cover_status(row_id, "Sí")
                elif cover_url:
                    logger.info(f"Descargando carátula del vinilo desde: {cover_url}")
                    image_data = self.discogs_client.download_image_bytes(cover_url)
                    if image_data:
                        image_data = self.normalize_cover_image_bytes(image_data)
                        if self.audio_manager.embed_cover_art_verified(file_path, image_data):
                            values[8] = "Sí"
                            logger.info(f"Carátula incrustada con éxito en: {new_filename}")
                            self.display_cover_art(image_data)
                            self.update_row_cover_status(row_id, "Sí")
                        else:
                            values[8] = "No"
                            logger.error(f"La carátula no quedó persistida en el archivo: {new_filename}")
                    else:
                        values[8] = "No"
                        logger.warning(f"No se pudieron descargar los bytes de la carátula ({cover_url})")
                else:
                    values[8] = "No"
                    logger.warning(f"Discogs no devolvió carátula para: '{query_term}'")
                    self.update_row_cover_status(row_id, "No")

                self.tree.item(row_id, values=values)
                if metadata_changes:
                    logger.info(f"Metadatos desde nombre -> {' | '.join(metadata_changes)}")
                else:
                    logger.info("Metadatos desde nombre -> sin cambios")
                logger.info(f"Actualizado Discogs -> Año: '{year}'")

                processed += 1
                self.progress_bar.set(processed / total_files)
                self.update_idletasks()

            self.detail_panel.on_row_select(None)
            logger.info("Procesamiento finalizado con éxito.")

        finally:
            # Restaurar el botón al estado normal siempre (incluso si hay excepciones)
            if hasattr(self, 'btn_process'):
                self.btn_process.configure(state="normal", text="Procesar")
                self.update_idletasks()


    def row_has_cover(self, row_id):
        try:
            values = list(self.tree.item(row_id, "values"))
            return len(values) > 8 and str(values[8]).strip().lower() in ("sí", "si", "yes", "true", "1")
        except Exception:
            return False

    @staticmethod
    def build_discogs_query(artist, title, fallback_text=""):
        parts = [str(artist).strip(), str(title).strip()]
        query = " ".join(part for part in parts if part)
        if not query:
            query = str(fallback_text).strip()
        query = re.sub(r"\s+", " ", query).strip()
        return query

    def get_row_artist_title(self, row_id):
        values = list(self.tree.item(row_id, "values"))
        artist = values[1] if len(values) > 1 else ""
        title = values[2] if len(values) > 2 else ""
        return artist, title

    def update_row_cover_status(self, row_id, status="Sí"):
        values = list(self.tree.item(row_id, "values"))
        if len(values) > 8:
            values[8] = status
            self.tree.item(row_id, values=values)

    @staticmethod
    def normalize_cover_image_bytes(image_bytes):
        return AudioManager.normalize_cover_image_bytes(image_bytes)


    def save_single_tag(self, file_path, field_name, new_value):
        self.audio_manager.save_single_tag(file_path, field_name, new_value)

    def _enter_multi_mode(self, selected_rows):
        self.detail_panel.enter_multi_mode(selected_rows)

    def _exit_multi_mode(self):
        self.detail_panel.exit_multi_mode()

    def _on_multi_panel_commit(self, attr_name):
        self.detail_panel.on_multi_panel_commit(attr_name)

    def display_multi_cover_placeholder(self, selected_rows=None):
        self.detail_panel.display_multi_cover_placeholder(selected_rows=selected_rows)

    def _refresh_process_button_text(self, selected_count=None):
        self.detail_panel.refresh_process_button_text(selected_count=selected_count)

    def display_cover_art(self, file_path_or_bytes):
        self.detail_panel.display_cover_art(file_path_or_bytes)

    def refresh_catalog_comboboxes(self):
        if hasattr(self, "detail_panel"):
            self.detail_panel.refresh_catalog_comboboxes()

    def _set_panel_widget_value(self, attr_name, value):
        self.detail_panel.set_panel_widget_value(attr_name, value)

    def on_panel_catalog_selected(self, attr_name, catalog_key):
        self.detail_panel.on_panel_catalog_selected(attr_name, catalog_key)

    def on_panel_combo_click(self, combo_widget):
        return self.detail_panel.on_panel_combo_click(combo_widget)

    def on_panel_catalog_enter(self, attr_name, catalog_key):
        return self.detail_panel.on_panel_catalog_enter(attr_name, catalog_key)

    def on_panel_catalog_focus_out(self, attr_name, catalog_key):
        self.detail_panel.on_panel_catalog_focus_out(attr_name, catalog_key)

    def on_panel_text_field_enter(self, attr_name):
        return self.detail_panel.on_panel_text_field_enter(attr_name)

    def on_panel_text_field_commit(self, attr_name):
        self.detail_panel.on_panel_text_field_commit(attr_name)


    @staticmethod
    def _pil_to_bytes(img):
        """Convierte un objeto PIL.Image a bytes JPEG."""
        out = io.BytesIO()
        rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        rgb.save(out, format="JPEG", quality=95, optimize=True)
        return out.getvalue()


    def _strip_cover_tags(self, file_path):
        self.audio_manager.strip_cover_tags(file_path)

    def clear_audio_file_metadata(self, file_path):
        return self.audio_manager.clear_audio_file_metadata(file_path)

    def _update_row_from_file_metadata(self, row_id, file_path):
        metadata = self.audio_manager.extract_metadata(file_path, os.path.basename(file_path))
        metadata["Album"] = self.normalize_catalog_text(metadata.get("Album", ""))
        metadata["Genre"] = self.normalize_catalog_text(metadata.get("Genre", ""))
        metadata["Publisher"] = self.normalize_catalog_text(metadata.get("Publisher", ""))

        self.tree.item(row_id, values=(
            metadata["Filename"],
            metadata["Artist"],
            metadata["Title"],
            metadata["MixArtist"],
            metadata["Album"],
            metadata["Genre"],
            metadata["Publisher"],
            metadata["Year"],
            metadata["Cover"]
        ))

    def clear_metadata_for_rows(self, target_rows, scope_label="selección"):
        target_rows = list(target_rows)
        if not target_rows:
            DialogManager.show_themed_dialog(
                self,
                "Sin archivos",
                "No hay archivos disponibles para limpiar metadatos.",
                level="warning"
            )
            return 0

        if len(target_rows) == 1:
            row_id = target_rows[0]
            file_path = self.file_paths_map.get(row_id)
            file_name = os.path.basename(file_path) if file_path else "el archivo seleccionado"
            message = f"¿Eliminar todos los metadatos de:\n{file_name}?"
        else:
            message = (
                f"¿Eliminar todos los metadatos de {len(target_rows)} archivo(s) "
                f"de la {scope_label}?"
            )

        if not DialogManager.show_themed_dialog(self, "Confirmar limpieza", message, level="warning", is_confirm=True):
            return 0

        cleaned_count = 0
        failed_count = 0

        for row_id in target_rows:
            file_path = self.file_paths_map.get(row_id)
            if not file_path or not os.path.exists(file_path):
                logger.warning("Se omite limpieza de metadatos: archivo no encontrado en disco.")
                failed_count += 1
                continue

            if not self.clear_audio_file_metadata(file_path):
                failed_count += 1
                continue

            self._update_row_from_file_metadata(row_id, file_path)
            logger.info(f"Metadatos eliminados de: {os.path.basename(file_path)}")
            cleaned_count += 1

        if self.tree.selection():
            self.detail_panel.on_row_select(None)

        logger.info(
            f"Limpieza de metadatos completada ({scope_label}) -> OK: {cleaned_count}, Fallos: {failed_count}"
        )
        return cleaned_count

    def clear_selected_metadata(self):
        selected_rows = self.tree.selection()
        if not selected_rows:
            DialogManager.show_themed_dialog(
                self,
                "Sin selección",
                "Selecciona al menos un archivo en la tabla para limpiar sus metadatos.",
                level="warning"
            )
            return

        scope_label = "selección" if len(selected_rows) > 1 else "archivo seleccionado"
        self.clear_metadata_for_rows(selected_rows, scope_label=scope_label)

    def clear_all_loaded_metadata(self):
        all_rows = self.tree.get_children()
        self.clear_metadata_for_rows(all_rows, scope_label="lista cargada")

    def sort_by_column(self, col):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        reverse = self.sort_directions[col]
        data.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        for index, item in enumerate(data):
            self.tree.move(item[1], '', index)
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(item[1], tags=(tag,))

        self.sort_directions[col] = not reverse

    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.folder_path = path
            self.label_folder.configure(text=path, text_color="white")
            self.load_audio_files(path)

    def refresh_folder(self):
        if not self.folder_path:
            logger.warning("No hay ninguna carpeta seleccionada para actualizar.")
            return
        logger.info("Actualizando lista de archivos...")
        self.load_audio_files(self.folder_path)

    def clear_all(self):
        if self._multi_select_mode:
            self.detail_panel.exit_multi_mode()
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self._all_tree_items = []

        self.detail_panel.clear_fields()
        self.folder_path = ""
        self.label_folder.configure(text="Ninguna carpeta seleccionada", text_color="gray")
        self.progress_bar.set(0)
        self.detail_panel.refresh_process_button_text(0)
        logger.info("Lista y estado limpiados.")

    def _apply_catalog_selection_to_row(self, row_id, attr_name, catalog_key, new_value):
        column_map = {
            "entry_album": self.get_catalog_column_info("Album"),
            "entry_genre": self.get_catalog_column_info("Genre"),
            "entry_publisher": self.get_catalog_column_info("Publisher"),
        }
        if attr_name not in column_map:
            return

        col_name, col_index = column_map[attr_name]
        values = list(self.tree.item(row_id, "values"))
        if col_index >= len(values):
            return
        if self.normalize_catalog_text(values[col_index]) == new_value:
            return

        values[col_index] = new_value
        self.tree.item(row_id, values=values)

        file_path = self.file_paths_map.get(row_id)
        if file_path:
            self.save_single_tag(file_path, col_name, new_value)

        self.add_catalog_value(catalog_key, new_value, persist=True)
        logger.info(
            f"Campo '{self.catalog_labels.get(catalog_key, catalog_key)}' actualizado desde panel: "
            f"'{self.columns[col_index]}' -> '{new_value}'"
        )
        self.detail_panel.on_row_select(None)

    def on_close(self):
        self.save_catalog_values()
        self.destroy()

    def load_audio_files(self, folder):
        if not os.path.isdir(folder):
            logger.error(f"La ruta seleccionada no es una carpeta válida: {folder}")
            return
        if not os.access(folder, os.R_OK):
            logger.error(f"No hay permisos de lectura sobre la carpeta: {folder}")
            return

        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()
        self._all_tree_items = []

        logger.info(f"Escaneando carpeta: {folder}")
        count = 0

        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(AUDIO_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    metadata = self.audio_manager.extract_metadata(file_path, file)

                    metadata["Album"] = self.normalize_catalog_text(metadata.get("Album", ""))
                    metadata["Genre"] = self.normalize_catalog_text(metadata.get("Genre", ""))
                    metadata["Publisher"] = self.normalize_catalog_text(metadata.get("Publisher", ""))

                    self.add_catalog_value("Album", metadata.get("Album", ""), persist=False)
                    self.add_catalog_value("Genre", metadata.get("Genre", ""), persist=False)
                    self.add_catalog_value("Publisher", metadata.get("Publisher", ""), persist=False)

                    tag = "even" if count % 2 == 0 else "odd"

                    row_id = self.tree.insert("", "end", values=(
                        metadata["Filename"],
                        metadata["Artist"],
                        metadata["Title"],
                        metadata["MixArtist"],
                        metadata["Album"],
                        metadata["Genre"],
                        metadata["Publisher"],
                        metadata["Year"],
                        metadata["Cover"]
                    ), tags=(tag,))

                    self.file_paths_map[row_id] = file_path
                    count += 1

        self.refresh_catalog_comboboxes()
        self._all_tree_items = list(self.tree.get_children(""))
        if self._search_visible:
            self.apply_search_filter()
        logger.info(f"Se encontraron {count} archivo(s) de audio compatibles.")

    def append_log_to_dialog(self, msg):
        if self.log_window is None or self.log_textbox is None:
            return
        if not self.log_window.winfo_exists():
            self.log_window = None
            self.log_textbox = None
            return

        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", f"{msg}\n")
        self.log_textbox.see("end")
        self.log_textbox.configure(state="disabled")

    def select_all_rows(self):
        """Selecciona todas las filas del árbol de archivos."""
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        self.detail_panel.refresh_process_button_text(len(all_items))
        logger.info(f"Seleccionados todos los {len(all_items)} archivo(s).")


if __name__ == "__main__":
    app = App()
    app.mainloop()