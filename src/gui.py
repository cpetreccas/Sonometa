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
from log_handler import LogManager
from tool_panel import ToolPanel
from search_manager import SearchManager

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

    def __init__(self):
        super().__init__()

        self.logger = LogManager.setup_logger()

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
        self._multi_entries: dict = {}
        self.log_window = None
        self.log_textbox = None
        self.catalog_fields = self.catalog_manager.catalog_fields
        self.catalog_labels = self.catalog_manager.catalog_labels
        self.catalog_values = self.catalog_manager.catalog_values
        self.catalog_file_path = self.catalog_manager.get_catalog_file_path()
        self.catalog_manager.load_catalog_values()

        self.discogs_token = os.getenv("DISCOGS_TOKEN", "").strip()
        self.settings_file_path = self.catalog_manager.get_settings_file_path()
        self.catalog_values = self.catalog_manager.catalog_values
        self.catalog_manager.get_catalog_file_path()
        self.catalog_manager.load_settings()

        self.ico_path = UiUtils.get_resource_path("assets/logo.ico")
        png_path = UiUtils.get_resource_path("assets/logo.png")
        self.app_icon_photo = None

        broom_path = UiUtils.get_resource_path("assets/broom_icon.png")
        self.broom_icon = None
        if os.path.exists(broom_path):
            icon_broom_img = Image.open(broom_path)
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

        # 0. Toolbar superior (Menú principal)
        self.tool_panel = ToolPanel(self)
        self.tool_panel.pack(side="top", fill="x")

        # 1. Barra superior (Logo y selección de carpeta)
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

        # 2. Panel principal (Edición de etiquetas y Tabla)
        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        self.detail_panel = DetailPanel(
            app=self,
            parent=self.frame_main,
            logger=self.logger,
            get_resource_path=UiUtils.get_resource_path
        )
        self.frame_sidebar = self.detail_panel.frame_sidebar
        self.panel_combo_fields = self.detail_panel.panel_combo_fields
        self.tag_entries = self.detail_panel.tag_entries
        self._multi_entries = self.detail_panel.multi_entries
        self.label_cover = self.detail_panel.label_cover
        self.btn_process = self.detail_panel.btn_process

        self.grid_panel = GridPanel(app=self, parent=self.frame_main, logger=self.logger)
        self.tree = self.grid_panel.tree
        self.columns = self.grid_panel.columns
        self.vsb = self.grid_panel.vsb
        self.hsb = self.grid_panel.hsb

        # 3. Pie de página
        self.frame_bottom = ctk.CTkFrame(self)
        self.frame_bottom.pack(fill="x", padx=15, pady=(5, 10))

        # 4. Gestor de búsqueda
        self.search_manager = SearchManager(
            app=self,
            tree=self.tree,
            frame_bottom_ref=self.frame_bottom,
            detail_panel=self.detail_panel,
            grid_panel=self.grid_panel
        )

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

        # Atajos de teclado
        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.refresh_folder())
        self.bind("<Control-q>", lambda e: self.on_close())
        self.bind("<Control-a>", lambda e: self.select_all_rows())
        self.bind("<Control-f>", lambda e: self.search_manager.toggle_search_bar())
        self.bind("<Control-F>", lambda e: self.search_manager.toggle_search_bar())
        self.bind("<Escape>", lambda e: self.search_manager.on_escape_pressed(e))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.logger.info("Aplicación Sonometa iniciada correctamente.")
        if self.discogs_token:
            self.logger.info("Token de Discogs activo ✓")
        else:
            self.logger.warning("No hay token de Discogs configurado. Ve a Archivo → ⚙ Configuración.")

    def process_discogs_data(self):
        target_rows = self.tree.selection()
        if not target_rows:
            target_rows = self.tree.get_children()

        if not target_rows:
            DialogManager.show_themed_dialog(self, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

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
            self.logger.info(f"Iniciando procesado para {total_files} archivo(s)...")

            processed = 0
            for row_id in target_rows:
                file_path = self.file_paths_map.get(row_id)
                if not file_path or not os.path.exists(file_path):
                    continue

                values = list(self.tree.item(row_id, "values"))

                catalog_fields = (("Album", 4), ("Genre", 5), ("Publisher", 6))
                invalid_catalog_fields = []
                for field_name, col_index in catalog_fields:
                    if col_index >= len(values):
                        continue
                    current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
                    if not current_value:
                        continue

                    normalized_value = CatalogManager.normalize_catalog_text(current_value)
                    allowed_values = {
                        CatalogManager.normalize_catalog_text(v)
                        for v in self.catalog_values.get(field_name, [])
                        if str(v).strip()
                    }
                    if normalized_value not in allowed_values:
                        values[col_index] = ""
                        self.audio_manager.save_single_tag(file_path, field_name, "")
                        invalid_catalog_fields.append(field_name)

                if invalid_catalog_fields:
                    self.tree.item(row_id, values=values)
                    self.logger.info(
                        f"Se limpiaron campos fuera de catálogo en '{os.path.basename(file_path)}': "
                        f"{', '.join(invalid_catalog_fields)}"
                    )

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
                        self.logger.info(f"Renombrado archivo: '{old_filename}' -> '{new_filename}'")
                    except Exception as e:
                        self.logger.error(f"No se pudo renombrar el archivo '{old_filename}': {str(e)}")

                clean_name = os.path.splitext(new_filename)[0]

                artist_parsed = ""
                title_parsed = clean_name
                mixartist_parsed = ""

                parentheses = re.findall(r'\((.*?)\)', clean_name)
                if parentheses:
                    mixartist_parsed = " ".join(parentheses).strip()
                    clean_name = re.sub(r'\(.*?\)', '', clean_name).strip()

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
                    self.audio_manager.save_single_tag(file_path, tag_name, new_value)

                    if previous_value != new_value:
                        action = "vaciado" if not new_value else "actualizado"
                        metadata_changes.append(
                            f"{label} {action}: '{previous_value}' -> '{new_value}'"
                        )

                self.tree.item(row_id, values=values)
                already_has_cover = self.row_has_cover(row_id)
                if already_has_cover:
                    self.logger.info(f"Se omite solo la descarga de carátula para '{new_filename}' porque ya tiene una incrustada.")

                query_term = self.build_discogs_query(
                    values[1] if len(values) > 1 else "",
                    values[2] if len(values) > 2 else "",
                    fallback_text=re.sub(r'^\d+[\s\-_.]*', '', clean_name)
                )
                query_term = omit_pattern.sub('', query_term)
                query_term = query_term.replace('_', ' ')
                query_term = re.sub(r'\s+[._-]\s+', ' ', query_term)
                query_term = re.sub(r'\s+', ' ', query_term).strip()

                self.logger.info(f"Procesando archivo: '{new_filename}' (Búsqueda Discogs: '{query_term}')")

                _, _, year, cover_url = self.discogs_client.search_release(query_term)

                if year:
                    values[7] = str(year)
                    self.audio_manager.save_single_tag(file_path, "Year", str(year))

                if already_has_cover:
                    values[8] = "Sí"
                    self.update_row_cover_status(row_id, "Sí")
                elif cover_url:
                    self.logger.info(f"Descargando carátula del vinilo desde: {cover_url}")
                    image_data = self.discogs_client.download_image_bytes(cover_url)
                    if image_data:
                        image_data = AudioManager.normalize_cover_image_bytes(image_data)
                        if self.audio_manager.embed_cover_art_verified(file_path, image_data):
                            values[8] = "Sí"
                            self.logger.info(f"Carátula incrustada con éxito en: {new_filename}")
                            self.detail_panel.display_cover_art(image_data)
                            self.update_row_cover_status(row_id, "Sí")
                        else:
                            values[8] = "No"
                            self.logger.error(f"La carátula no quedó persistida en el archivo: {new_filename}")
                    else:
                        values[8] = "No"
                        self.logger.warning(f"No se pudieron descargar los bytes de la carátula ({cover_url})")
                else:
                    values[8] = "No"
                    self.logger.warning(f"Discogs no devolvió carátula para: '{query_term}'")
                    self.update_row_cover_status(row_id, "No")

                self.tree.item(row_id, values=values)
                if metadata_changes:
                    self.logger.info(f"Metadatos desde nombre -> {' | '.join(metadata_changes)}")
                else:
                    self.logger.info("Metadatos desde nombre -> sin cambios")
                self.logger.info(f"Actualizado Discogs -> Año: '{year}'")

                processed += 1
                self.progress_bar.set(processed / total_files)
                self.update_idletasks()

            self.detail_panel.on_row_select(None)
            self.logger.info("Procesamiento finalizado con éxito.")

        finally:
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
    def _pil_to_bytes(img):
        out = io.BytesIO()
        rgb = img.convert("RGB") if img.mode not in ("RGB", "L") else img
        rgb.save(out, format="JPEG", quality=95, optimize=True)
        return out.getvalue()

    def _update_row_from_file_metadata(self, row_id, file_path):
        metadata = self.audio_manager.extract_metadata(file_path, os.path.basename(file_path))
        metadata["Album"] = CatalogManager.normalize_catalog_text(metadata.get("Album", ""))
        metadata["Genre"] = CatalogManager.normalize_catalog_text(metadata.get("Genre", ""))
        metadata["Publisher"] = CatalogManager.normalize_catalog_text(metadata.get("Publisher", ""))

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
                self.logger.warning("Se omite limpieza de metadatos: archivo no encontrado en disco.")
                failed_count += 1
                continue

            if not self.audio_manager.clear_audio_file_metadata(file_path):
                failed_count += 1
                continue

            self._update_row_from_file_metadata(row_id, file_path)
            self.logger.info(f"Metadatos eliminados de: {os.path.basename(file_path)}")
            cleaned_count += 1

        if self.tree.selection():
            self.detail_panel.on_row_select(None)

        self.logger.info(
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
        self.label_folder.configure(text="Ninguna carpeta seleccionada", text_color="gray")
        self.progress_bar.set(0)
        self.detail_panel.refresh_process_button_text(0)
        self.logger.info("Lista y estado limpiados.")

    def _apply_catalog_selection_to_row(self, row_id, attr_name, catalog_key, new_value):
        column_map = {
            "entry_album": CatalogManager.get_catalog_column_info("Album"),
            "entry_genre": CatalogManager.get_catalog_column_info("Genre"),
            "entry_publisher": CatalogManager.get_catalog_column_info("Publisher"),
        }
        if attr_name not in column_map:
            return

        col_name, col_index = column_map[attr_name]
        values = list(self.tree.item(row_id, "values"))
        if col_index >= len(values):
            return
        if CatalogManager.normalize_catalog_text(values[col_index]) == new_value:
            return

        values[col_index] = new_value
        self.tree.item(row_id, values=values)

        file_path = self.file_paths_map.get(row_id)
        if file_path:
            self.audio_manager.save_single_tag(file_path, col_name, new_value)

        self.catalog_manager.add_catalog_value(catalog_key, new_value, persist=True)
        self.logger.info(
            f"Campo '{self.catalog_labels.get(catalog_key, catalog_key)}' actualizado desde panel: "
            f"'{self.columns[col_index]}' -> '{new_value}'"
        )
        self.detail_panel.on_row_select(None)

    def on_close(self):
        self.catalog_manager.save_catalog_values()
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

            metadata["Album"] = CatalogManager.normalize_catalog_text(metadata.get("Album", ""))
            metadata["Genre"] = CatalogManager.normalize_catalog_text(metadata.get("Genre", ""))
            metadata["Publisher"] = CatalogManager.normalize_catalog_text(metadata.get("Publisher", ""))

            self.catalog_manager.add_catalog_value("Album", metadata.get("Album", ""), persist=False)
            self.catalog_manager.add_catalog_value("Genre", metadata.get("Genre", ""), persist=False)
            self.catalog_manager.add_catalog_value("Publisher", metadata.get("Publisher", ""), persist=False)

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

        self.detail_panel.refresh_catalog_comboboxes()
        self.search_manager.sync_all_tree_items()
        if self.search_manager.is_visible:
            self.search_manager.apply_search_filter()
        self.logger.info(f"Se encontraron {len(items)} archivo(s) de audio compatibles.")

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
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        self.detail_panel.refresh_process_button_text(len(all_items))
        self.logger.info(f"Seleccionados todos los {len(all_items)} archivo(s).")

if __name__ == "__main__":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('sonometa.audiotagsuite.1.0')
    except Exception:
        pass

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.mainloop()