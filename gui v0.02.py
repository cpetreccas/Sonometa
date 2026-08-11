import logging
import os
import sys
import ctypes
import io
import re
import urllib.request
import json
from collections import deque
import tkinter as tk
import urllib.parse
from tkinter import ttk, messagebox
import customtkinter as ctk
from customtkinter import filedialog
from PIL import Image, ImageTk

AUDIO_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.aac', '.wav', '.ogg', '.wma', '.aiff')


def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


ruta_logo = get_resource_path("logo_blanco.png")
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

    def __init__(self):
        super().__init__()

        self.title("Sonometa v0.02 - Audio Tag Suite")
        self.geometry("1180x780")
        self.minsize(1000, 680)

        self.after(10, self.maximize_window)

        self.folder_path = ""
        self.sort_directions = {}
        self.file_paths_map = {}
        self.cell_entry = None
        self.log_history = deque(maxlen=5000)

        self.gui_log_handler = TextHandler(self)
        self.gui_log_handler.setFormatter(formatter)
        logger.addHandler(self.gui_log_handler)

        ico_path = get_resource_path("logo.ico")
        png_path = get_resource_path("logo.png")

        if os.path.exists(ico_path):
            self.iconbitmap(ico_path)

        logo_pil = None
        if os.path.exists(png_path):
            logo_pil = Image.open(png_path)
            img_icon = ImageTk.PhotoImage(logo_pil)
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
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self.refresh_folder
        )
        self.btn_refresh.pack(side="left", padx=5, pady=5)

        self.label_folder = ctk.CTkLabel(self.frame_top, text="Ninguna carpeta seleccionada", text_color="gray")
        self.label_folder.pack(side="left", padx=10, pady=5)

        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        self.setup_treeview()
        self.setup_tag_panel()

        self.frame_bottom = ctk.CTkFrame(self)
        self.frame_bottom.pack(fill="x", padx=15, pady=(5, 10))

        self.progress_bar = ctk.CTkProgressBar(self.frame_bottom, progress_color=self.CORP_COLOR)
        self.progress_bar.pack(fill="x", padx=10, pady=2)
        self.progress_bar.set(0)

        self.label_status = ctk.CTkLabel(
            self.frame_bottom, 
            text="Listo", 
            anchor="w", 
            font=ctk.CTkFont(size=11),
            text_color="#9CA3AF"
        )
        self.label_status.pack(fill="x", padx=12, pady=(2, 6))

        self.bind("<Control-o>", lambda e: self.browse_folder())
        self.bind("<F5>", lambda e: self.refresh_folder())
        self.bind("<Control-q>", lambda e: self.destroy())
        self.bind("<Control-a>", lambda e: self.select_all_rows())

        logger.info("Aplicación Sonometa iniciada correctamente.")

    def maximize_window(self):
        try:
            self.state("zoomed")
        except Exception:
            # Fallback multiplataforma si zoomed no está disponible.
            self.state("normal")
            self.geometry(f"{self.winfo_screenwidth()}x{self.winfo_screenheight()}+0+0")

    @staticmethod
    def format_filename_pattern(filename):
        name, ext = os.path.splitext(filename)

        # Palabras reservadas que deben permanecer en minúsculas
        LOWER_WORDS_PAR = {'remix', 'mix', 'rework', 'edit', 'side'}
        LOWER_WORDS_PREFIX = {'feat.', 'feat', 'ft.', 'ft', 'pres.', 'pres', 'presents'}

        def format_parentheses(match):
            content = match.group(1).strip()
            words = content.split()
            formatted_words = [
                w.lower() if w.lower() in LOWER_WORDS_PAR else w.capitalize()
                for w in words
            ]
            return f"({' '.join(formatted_words)})"

        # 1. Formatear los paréntesis
        name = re.sub(r'\((.*?)\)', format_parentheses, name)

        if " - " in name:
            prefix, suffix = name.split(" - ", 1)
        elif "-" in name:
            prefix, suffix = name.split("-", 1)
        else:
            words = name.strip().split()
            if not words:
                return filename
            formatted = words[0].capitalize() + (" " + " ".join(w.lower() for w in words[1:]) if len(words) > 1 else "")
            return f"{formatted}{ext}"

        # 2. Formatear el Prefijo (Intérprete): ignorar mayúsculas en 'feat.', 'pres.', etc.
        prefix_words = prefix.strip().split()
        formatted_prefix_words = [
            w.lower() if w.lower() in LOWER_WORDS_PREFIX else w.capitalize()
            for w in prefix_words
        ]
        formatted_prefix = " ".join(formatted_prefix_words)

        # 3. Formatear el Sufijo (Título)
        suffix_words = suffix.strip().split()
        if suffix_words:
            first_word = suffix_words[0].capitalize()
            rest_words = [w if w.startswith("(") or w.endswith(")") else w.lower() for w in suffix_words[1:]]
            formatted_suffix = " ".join([first_word] + rest_words)
        else:
            formatted_suffix = ""

        return f"{formatted_prefix} - {formatted_suffix}{ext}"

    def setup_custom_dark_menu(self):
        self.menu_bar_frame = ctk.CTkFrame(self, height=28, corner_radius=0, fg_color="#181818")
        self.menu_bar_frame.pack(side="top", fill="x")

        self.menu_archivo = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1)
        self.menu_archivo.add_command(label="Seleccionar carpeta...  (Ctrl+O)", command=self.browse_folder)
        self.menu_archivo.add_command(label="Actualizar  (F5)", command=self.refresh_folder)
        self.menu_archivo.add_separator()
        self.menu_archivo.add_command(label="Cerrar  (Ctrl+Q)", command=self.destroy)

        self.menu_acciones = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1)
        self.menu_acciones.add_command(label="Procesar con Discogs", command=self.process_discogs_data)
        self.menu_acciones.add_command(label="Seleccionar todo  (Ctrl+A)", command=self.select_all_rows)
        self.menu_acciones.add_separator()
        self.menu_acciones.add_command(label="Limpiar todo", command=self.clear_all)

        self.menu_ayuda = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1)
        self.menu_ayuda.add_command(label="Atajos de teclado", command=self.show_keyboard_shortcuts_dialog)
        self.menu_ayuda.add_command(label="Ver logs", command=self.show_logs_dialog)
        self.menu_ayuda.add_separator()
        self.menu_ayuda.add_command(label="Acerca de Sonometa", command=self.show_about_dialog)

        def create_menu_btn(text, menu_widget):
            btn = ctk.CTkButton(
                self.menu_bar_frame,
                text=text,
                width=65,
                height=24,
                fg_color="transparent",
                hover_color="#2A2D32",
                text_color="#E0E0E0",
                font=ctk.CTkFont(size=12)
            )
            btn.configure(command=lambda: menu_widget.post(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height()))
            btn.pack(side="left", padx=2, pady=2)

        create_menu_btn("Archivo", self.menu_archivo)
        create_menu_btn("Acciones", self.menu_acciones)
        create_menu_btn("Ayuda", self.menu_ayuda)

    def setup_tag_panel(self):
        # Panel inferior principal
        self.frame_bottom_panel = ctk.CTkFrame(
            self.frame_main,
            height=200,
            fg_color="#1E1E1E",
            border_color="#2D2D2D",
            border_width=1,
            corner_radius=8
        )
        self.frame_bottom_panel.pack(side="bottom", fill="x", padx=0, pady=(8, 0))
        self.frame_bottom_panel.pack_propagate(False)

        # --- SECCIÓN IZQUIERDA: Carátula y Botón ---
        self.frame_left_section = ctk.CTkFrame(self.frame_bottom_panel, fg_color="transparent")
        self.frame_left_section.pack(side="left", fill="y", padx=12, pady=10)

        self.cover_border_frame = ctk.CTkFrame(
            self.frame_left_section,
            fg_color="#121212",
            border_color="#333333",
            border_width=1,
            corner_radius=6
        )
        self.cover_border_frame.pack(side="top")

        self.label_cover = ctk.CTkLabel(
            self.cover_border_frame,
            text="Sin carátula",
            width=135,
            height=135,
            fg_color="transparent",
            text_color="#666666",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.label_cover.pack(padx=2, pady=2)

        logo3_path = get_resource_path("logo_blanco.png")
        btn_icon = None
        if os.path.exists(logo3_path):
            try:
                img_logo3 = Image.open(logo3_path)
                btn_icon = ctk.CTkImage(light_image=img_logo3, dark_image=img_logo3, size=(16, 16))
            except Exception as e:
                logger.error(f"Error al cargar logo_blanco.png: {str(e)}")

        self.btn_process = ctk.CTkButton(
            self.frame_left_section,
            text="Procesar",
            image=btn_icon if btn_icon else icono_procesar,
            compound="left",
            fg_color=self.CORP_COLOR,
            hover_color=self.CORP_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
            height=30,
            corner_radius=6,
            command=self.process_discogs_data
        )
        self.btn_process.pack(fill="x", pady=(6, 0))

        # --- SEPARADOR VERTICAL ---
        separator = ctk.CTkFrame(self.frame_bottom_panel, width=1, fg_color="#2D2D2D")
        separator.pack(side="left", fill="y", padx=(0, 10), pady=10)

        # --- SECCIÓN DERECHA: Grid Único de 12 Columnas (Alineación perfecta) ---
        self.frame_right_section = ctk.CTkFrame(self.frame_bottom_panel, fg_color="transparent")
        self.frame_right_section.pack(side="right", fill="both", expand=True, padx=(5, 12), pady=10)

        # Configuramos 12 columnas del mismo peso para flexibilidad exacta
        for i in range(12):
            self.frame_right_section.grid_columnconfigure(i, weight=1, uniform="col")

        # Fila 0 (Campos largos de 30 chars): 4 columnas por cada campo (4+4+4 = 12)
        # Fila 1 (Campos cortos de 10 chars): Álbum(4), Género(3), Publisher(3), Año(2) (4+3+3+2 = 12)
        fields_layout = [
            # (Etiqueta, Nombre Atributo, Fila, Columna Inicio, Ancho en Columnas / Columnspan)
            ("INTÉRPRETE", "entry_artist", 0, 0, 4),
            ("TÍTULO", "entry_title", 0, 4, 4),
            ("REMIX / VERSIÓN", "entry_mixartist", 0, 8, 4),

            ("ÁLBUM", "entry_album", 1, 0, 4),
            ("GÉNERO", "entry_genre", 1, 4, 3),
            ("PUBLISHER", "entry_publisher", 1, 7, 3),
            ("AÑO", "entry_year", 1, 10, 2),
        ]

        self.tag_entries = {}

        for label_text, attr_name, row, col, span in fields_layout:
            field_container = ctk.CTkFrame(self.frame_right_section, fg_color="transparent")
            field_container.grid(row=row, column=col, columnspan=span, sticky="ew", padx=4, pady=4)

            lbl = ctk.CTkLabel(
                field_container,
                text=label_text,
                anchor="w",
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color="#9CA3AF"
            )
            lbl.pack(fill="x", padx=1, pady=(0, 2))

            entry = ctk.CTkEntry(
                field_container,
                height=30,
                font=ctk.CTkFont(size=11),
                fg_color="#121212",
                border_color="#333333",
                border_width=1,
                corner_radius=5
            )
            entry.pack(fill="x", expand=True)
            self.tag_entries[attr_name] = entry

    def setup_treeview(self):
        self.frame_grid = ctk.CTkFrame(self.frame_main)
        self.frame_grid.pack(side="top", fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")

        # ...existing code...
        style.configure(
            "Treeview",
            background="#181818",
            foreground="#E0E0E0",
            fieldbackground="#181818",
            rowheight=22,
            font=('Segoe UI', 8),
            borderwidth=1,
            relief="solid"
        )

        style.configure(
            "Treeview.Item",
            borderwidth=1,
            relief="solid",
            lightcolor="#383838",
            darkcolor="#383838",
            bordercolor="#383838"
        )

        style.configure(
            "Treeview.Heading",
            background="#111111",
            foreground="#FFFFFF",
            font=('Segoe UI', 8, 'bold'),
            borderwidth=1,
            relief="solid",
            lightcolor="#444444",
            darkcolor="#444444",
            bordercolor="#444444"
        )

        style.map("Treeview", background=[('selected', self.CORP_COLOR)])

        self.columns = ("Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Cover")
        self.tree = ttk.Treeview(self.frame_grid, columns=self.columns, show="headings", selectmode="extended")

        col_titles = {
            "Filename": "Nombre de archivo",
            "Artist": "Intérprete",
            "Title": "Título",
            "MixArtist": "Remix",
            "Album": "Álbum",
            "Genre": "Género",
            "Publisher": "Publisher",
            "Year": "Año",
            "Cover": "Carátula"
        }

        col_config = {
            "Filename":  {"width": 280, "minwidth": 180, "stretch": True,  "anchor": "w"},
            "Artist":    {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "Title":     {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "MixArtist": {"width": 160, "minwidth": 100, "stretch": True,  "anchor": "w"},
            "Album":     {"width": 100, "minwidth": 70,  "stretch": False, "anchor": "w"},
            "Genre":     {"width": 70,  "minwidth": 50,  "stretch": False, "anchor": "w"},
            "Publisher": {"width": 120, "minwidth": 80,  "stretch": False, "anchor": "w"},
            "Year":      {"width": 45,  "minwidth": 40,  "stretch": False, "anchor": "center"},
            "Cover":     {"width": 55,  "minwidth": 45,  "stretch": False, "anchor": "center"}
        }

        for col in self.columns:
            self.sort_directions[col] = False
            title = col_titles.get(col, col)
            cfg = col_config[col]
            
            self.tree.heading(col, text=title, command=lambda _col=col: self.sort_by_column(_col))
            self.tree.column(
                col, 
                width=cfg["width"], 
                minwidth=cfg["minwidth"], 
                anchor=cfg["anchor"], 
                stretch=cfg["stretch"]
            )

        self.tree.tag_configure("even", background="#1A1A1A")
        self.tree.tag_configure("odd", background="#242424")

        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self.on_cell_double_click)

        vsb = ttk.Scrollbar(self.frame_grid, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.frame_grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

    def on_cell_double_click(self, event):
        if self.cell_entry:
            self.cell_entry.destroy()
            self.cell_entry = None

        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        col_index = int(column_id.replace("#", "")) - 1
        if col_index < 0 or col_index >= len(self.columns):
            return
        col_name = self.columns[col_index]

        if col_name in ("Filename", "Cover"):
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, w, h = bbox

        row_values = self.tree.item(row_id, "values")
        if col_index >= len(row_values):
            return
        current_value = row_values[col_index]

        entry = ttk.Entry(self.tree)
        entry.insert(0, current_value)
        entry.select_range(0, "end")
        entry.focus_set()
        entry.place(x=x, y=y, width=w, height=h)

        def save_edit(evt=None):
            new_value = entry.get().strip()
            entry.destroy()
            self.cell_entry = None

            if new_value == str(current_value).strip():
                return

            values = list(self.tree.item(row_id, "values"))
            values[col_index] = new_value
            self.tree.item(row_id, values=values)

            self.on_row_select(None)

            file_path = self.file_paths_map.get(row_id)
            if file_path:
                self.save_single_tag(file_path, col_name, new_value)

        entry.bind("<Return>", save_edit)
        entry.bind("<FocusOut>", save_edit)
        self.cell_entry = entry

    def process_discogs_data(self):
        target_rows = self.tree.selection()
        if not target_rows:
            target_rows = self.tree.get_children()

        if not target_rows:
            messagebox.showwarning("Advertencia", "No hay archivos cargados en la tabla.")
            return

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

            # --- PASO 1: Formatear y Renombrar archivo ---
            old_filename = os.path.basename(file_path)
            new_filename = self.format_filename_pattern(old_filename)
            dir_name = os.path.dirname(file_path)
            new_file_path = os.path.join(dir_name, new_filename)

            if old_filename != new_filename:
                try:
                    os.rename(file_path, new_file_path)
                    self.file_paths_map[row_id] = new_file_path
                    file_path = new_file_path
                    
                    values = list(self.tree.item(row_id, "values"))
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

            values = list(self.tree.item(row_id, "values"))
            if artist_parsed:
                values[1] = artist_parsed
                self.save_single_tag(file_path, "Artist", artist_parsed)

            if title_parsed:
                values[2] = title_parsed
                self.save_single_tag(file_path, "Title", title_parsed)

            if mixartist_parsed:
                values[3] = mixartist_parsed
                self.save_single_tag(file_path, "MixArtist", mixartist_parsed)

            # --- PASO 3: Búsqueda de metadatos adicionales en Discogs (Año y Carátula) ---
            query_term = re.sub(r'^\d+[\s\-_.]*', '', clean_name)
            query_term = omit_pattern.sub('', query_term)
            query_term = query_term.replace('_', ' ')
            query_term = re.sub(r'\s+[._-]\s+', ' ', query_term)
            query_term = re.sub(r'\s+', ' ', query_term).strip()

            logger.info(f"Procesando archivo: '{new_filename}' (Búsqueda Discogs: '{query_term}')")

            _, _, year, cover_url = self.search_discogs_api(query_term)

            if year:
                values[7] = str(year)
                self.save_single_tag(file_path, "Year", str(year))

            if cover_url:
                logger.info(f"Descargando carátula del vinilo desde: {cover_url}")
                image_data = self.download_image_bytes(cover_url)
                if image_data:
                    if self.embed_cover_art(file_path, image_data):
                        values[8] = "Sí"
                        logger.info(f"Carátula incrustada con éxito en: {new_filename}")
                        self.display_cover_art(image_data)
                    else:
                        logger.error(f"Error al incrustar la carátula en el archivo: {new_filename}")
                else:
                    logger.warning(f"No se pudieron descargar los bytes de la carátula ({cover_url})")

            self.tree.item(row_id, values=values)
            logger.info(f"Actualizado -> Autor: '{artist_parsed}', Título: '{title_parsed}', Remix: '{mixartist_parsed}', Año: '{year}'")

            processed += 1
            self.progress_bar.set(processed / total_files)
            self.update_idletasks()

        self.on_row_select(None)
        logger.info("Procesamiento finalizado con éxito.")

    def search_discogs_api(self, query):
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.discogs.com/database/search?q={encoded_query}&format=Vinyl&type=release"
            headers = {"User-Agent": "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"}

            logger.info("--- [DISCOGS REQUEST (VINYL FILTER)] ---")
            logger.info(f"URL: {url}")

            req = urllib.request.Request(url, headers=headers)

            with urllib.request.urlopen(req, timeout=5) as response:
                status_code = response.status
                raw_response = response.read().decode("utf-8")
                data = json.loads(raw_response)

                logger.info(f"--- [DISCOGS RESPONSE] (Status Code: {status_code}) ---")

                results = data.get("results", [])
                if results:
                    first_result = results[0]
                    title_full = first_result.get("title", "")
                    cover_url = first_result.get("cover_image") or first_result.get("thumb") or ""
                    year = first_result.get("year", "")

                    artist = ""
                    title = title_full
                    if " - " in title_full:
                        parts = title_full.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()

                    return artist, title, year, cover_url

        except urllib.error.HTTPError as e:
            logger.error(f"HTTPError Discogs API [{e.code}]: {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"URLError Discogs API: {e.reason}")
        except Exception as e:
            logger.error(f"Error consultando la API de Discogs: {str(e)}")

        return "", "", "", ""

    def download_image_bytes(self, image_url):
        try:
            headers = {
                "User-Agent": "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"
            }
            req = urllib.request.Request(image_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read()
        except Exception as e:
            logger.error(f"Error descargando imagen de carátula ({image_url}): {str(e)}")
        return None

    def embed_cover_art(self, file_path, image_bytes):
        from mutagen.id3 import ID3, APIC, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC, Picture
        from mutagen.mp4 import MP4, MP4Cover
        from mutagen import File as MutagenFile

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in (".mp3", ".wav"):
                if ext == ".wav":
                    audio_wav = WAVE(file_path)
                    if audio_wav.tags is None:
                        audio_wav.add_tags()
                    audio_tags = audio_wav.tags
                else:
                    try:
                        audio_tags = ID3(file_path)
                    except ID3NoHeaderError:
                        audio_tags = ID3()

                audio_tags.delall("APIC")
                audio_tags.add(APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=image_bytes
                ))

                if ext == ".wav":
                    audio_wav.save()
                else:
                    audio_tags.save(file_path)

            elif ext == ".flac":
                audio = FLAC(file_path)
                image = Picture()
                image.type = 3
                image.mime = "image/jpeg"
                image.desc = "Cover"
                image.data = image_bytes
                audio.clear_pictures()
                audio.add_picture(image)
                audio.save()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                audio["covr"] = [MP4Cover(image_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()

            else:
                audio = MutagenFile(file_path)
                if hasattr(audio, 'tags') and audio.tags is not None:
                    audio.tags['covr'] = image_bytes
                    audio.save()

            return True

        except Exception as e:
            logger.error(f"Error incrustando la carátula en {os.path.basename(file_path)}: {str(e)}")
            return False

    def update_cover_image(self, image_bytes_or_path):
        """
        Función para actualizar la carátula manteniendo estrictamente
        el tamaño del contenedor y la visibilidad del botón Procesar.
        """
        # Dimensión fija exacta que coincide con el label por defecto
        COVER_SIZE = (135, 135)

        if not image_bytes_or_path:
            # Caso: Sin carátula
            self.label_cover.configure(
                image=None,
                text="Sin carátula",
                width=COVER_SIZE[0],
                height=COVER_SIZE[1]
            )
            return

        try:
            # Cargar imagen desde ruta o bytes
            if isinstance(image_bytes_or_path, (str, os.PathLike)):
                pil_img = Image.open(image_bytes_or_path)
            else:
                pil_img = Image.open(io.BytesIO(image_bytes_or_path))

            # Forzar el escalado al tamaño exacto del cuadro (135x135)
            ctk_img = ctk.CTkImage(
                light_image=pil_img,
                dark_image=pil_img,
                size=COVER_SIZE
            )

            # Asignar la imagen y limpiar el texto
            self.label_cover.configure(
                image=ctk_img,
                text="",
                width=COVER_SIZE[0],
                height=COVER_SIZE[1]
            )
            # Guardar referencia para evitar que el GC de Python elimine la imagen
            self.label_cover._image_ref = ctk_img

        except Exception as e:
            logger.error(f"Error al cargar la carátula: {str(e)}")
            self.label_cover.configure(
                image=None,
                text="Sin carátula",
                width=COVER_SIZE[0],
                height=COVER_SIZE[1]
            )
            
    def save_single_tag(self, file_path, field_name, new_value):
        from mutagen.id3 import ID3, TIT2, TPE1, TPE4, TALB, TCON, TPUB, TDRC, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen import File as MutagenFile

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext in (".mp3", ".wav"):
                if ext == ".wav":
                    audio_wav = WAVE(file_path)
                    if audio_wav.tags is None:
                        audio_wav.add_tags()
                    audio_tags = audio_wav.tags
                else:
                    try:
                        audio_tags = ID3(file_path)
                    except ID3NoHeaderError:
                        audio_tags = ID3()

                frame_map = {
                    "Title": TIT2,
                    "Artist": TPE1,
                    "MixArtist": TPE4,
                    "Album": TALB,
                    "Genre": TCON,
                    "Publisher": TPUB,
                    "Year": TDRC
                }

                frame_cls = frame_map.get(field_name)
                if not frame_cls:
                    return

                if new_value:
                    audio_tags.add(frame_cls(encoding=3, text=str(new_value)))
                else:
                    frame_id = frame_cls.__name__
                    audio_tags.delall(frame_id)

                if ext == ".wav":
                    audio_wav.save()
                else:
                    audio_tags.save(file_path)

            else:
                tag_map = {
                    "Title": "title",
                    "Artist": "artist",
                    "MixArtist": "mixartist",
                    "Album": "album",
                    "Genre": "genre",
                    "Publisher": "organization",
                    "Year": "date"
                }

                mutagen_key = tag_map.get(field_name)
                if not mutagen_key:
                    return

                audio = MutagenFile(file_path, easy=True)
                if audio is None:
                    return

                if audio.tags is None:
                    audio.add_tags()

                if new_value:
                    audio[mutagen_key] = [str(new_value)]
                else:
                    audio.pop(mutagen_key, None)

                audio.save()

            logger.info(f"Guardado '{field_name}' en: {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Error al guardar etiqueta '{field_name}': {str(e)}")

    def on_row_select(self, event):
        selected = self.tree.selection()
        if not selected:
            return

        item_id = selected[0]
        item = self.tree.item(item_id)
        values = item['values']
        if len(values) < 8:
            logger.warning("Fila con metadatos incompletos; se omite actualización de panel.")
            return

        val_map = {
            "entry_artist": values[1],
            "entry_title": values[2],
            "entry_mixartist": values[3],
            "entry_album": values[4],
            "entry_genre": values[5],
            "entry_publisher": values[6],
            "entry_year": values[7]
        }

        for attr, val in val_map.items():
            entry = self.tag_entries.get(attr)
            if entry:
                entry.delete(0, "end")
                entry.insert(0, str(val) if val else "")

        file_path = self.file_paths_map.get(item_id)
        if file_path:
            self.display_cover_art(file_path)

    def display_cover_art(self, file_path_or_bytes):
        cover_data = None

        if isinstance(file_path_or_bytes, (bytes, bytearray)):
            cover_data = file_path_or_bytes
        elif isinstance(file_path_or_bytes, str) and os.path.exists(file_path_or_bytes):
            cover_data = self.extract_cover_bytes(file_path_or_bytes)

        if cover_data:
            try:
                image_stream = io.BytesIO(cover_data)
                img = Image.open(image_stream)
                
                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                img = img.resize((180, 180), Image.Resampling.LANCZOS)
                
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 180))
                self.label_cover.configure(image=ctk_img, text="")
                self.label_cover.image = ctk_img
                return
            except Exception as e:
                logger.error(f"Error procesando vista previa de la carátula: {str(e)}")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None

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
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.file_paths_map.clear()

        for entry in self.tag_entries.values():
            entry.delete(0, "end")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None
        self.folder_path = ""
        self.label_folder.configure(text="Ninguna carpeta seleccionada", text_color="gray")
        self.progress_bar.set(0)
        logger.info("Lista y estado limpiados.")

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

        logger.info(f"Escaneando carpeta: {folder}")
        count = 0

        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(AUDIO_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    metadata = self.extract_metadata(file_path, file)
                    
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

        logger.info(f"Se encontraron {count} archivo(s) de audio compatibles.")

    def extract_cover_bytes(self, file_path):
        from mutagen import File as MutagenFile
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return None

            if hasattr(audio, 'tags') and audio.tags:
                for tag_key in audio.tags.keys():
                    if tag_key.startswith("APIC") or tag_key.startswith("PIC"):
                        return audio.tags[tag_key].data

            if hasattr(audio, 'pictures') and audio.pictures:
                return audio.pictures[0].data

            if "covr" in audio:
                covers = audio["covr"]
                if covers:
                    return bytes(covers[0])

        except Exception:
            pass

        return None

    def extract_metadata(self, file_path, filename):
        from mutagen.wave import WAVE
        from mutagen import File as MutagenFile

        data = {
            "Filename": filename,
            "Title": "",
            "Artist": "",
            "MixArtist": "",
            "Album": "",
            "Genre": "",
            "Publisher": "",
            "Year": "",
            "Cover": "No"
        }

        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".wav":
                audio = WAVE(file_path)
                if audio.tags:
                    data["Title"] = str(audio.tags.get("TIT2", ""))
                    data["Artist"] = str(audio.tags.get("TPE1", ""))
                    data["MixArtist"] = str(audio.tags.get("TPE4", ""))
                    data["Album"] = str(audio.tags.get("TALB", ""))
                    data["Genre"] = str(audio.tags.get("TCON", ""))
                    data["Publisher"] = str(audio.tags.get("TPUB", ""))
                    data["Year"] = str(audio.tags.get("TDRC", ""))
            else:
                audio = MutagenFile(file_path, easy=True)
                if audio is not None:
                    def get_tag(tag_name):
                        val = audio.get(tag_name, [""])
                        return val[0] if val else ""

                    data["Title"] = get_tag("title")
                    data["Artist"] = get_tag("artist")
                    data["MixArtist"] = get_tag("mixartist")
                    data["Album"] = get_tag("album")
                    data["Genre"] = get_tag("genre")
                    data["Publisher"] = get_tag("organization") or get_tag("publisher")
                    data["Year"] = get_tag("date") or get_tag("year")

            if self.extract_cover_bytes(file_path):
                data["Cover"] = "Sí"

        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {filename}: {str(e)}")

        return data

    def show_logs_dialog(self):
        log_win = ctk.CTkToplevel(self)
        log_win.title("Historial de Logs")
        log_win.geometry("700x400")
        log_win.transient(self)

        txt = ctk.CTkTextbox(log_win, wrap="none")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        
        txt.insert("1.0", "\n".join(self.log_history))
        txt.configure(state="disabled")

    def show_about_dialog(self):
        messagebox.showinfo(
            "Acerca de Sonometa",
            "Sonometa v0.02 - Audio Tag Suite\n\n"
            "Herramienta avanzada para la automatización y gestión de metadatos de audio.\n"
            "Integración con API Discogs para vinilos y soporte nativo de ID3, FLAC y MP4."
        )

    def select_all_rows(self):
        """Selecciona todas las filas del árbol de archivos."""
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        logger.info(f"Seleccionados todos los {len(all_items)} archivo(s).")

    def show_keyboard_shortcuts_dialog(self):
        """Muestra un diálogo modal con los atajos de teclado disponibles."""
        shortcuts_win = ctk.CTkToplevel(self)
        shortcuts_win.title("Atajos de Teclado")
        shortcuts_win.geometry("500x350")
        shortcuts_win.transient(self)

        # Frame para el contenido
        frame_content = ctk.CTkFrame(shortcuts_win)
        frame_content.pack(fill="both", expand=True, padx=15, pady=15)

        # Título
        lbl_title = ctk.CTkLabel(
            frame_content, 
            text="Atajos de Teclado Disponibles", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_title.pack(fill="x", pady=(0, 12))

        # Contenedor scrollable para los atajos
        frame_scroll = ctk.CTkScrollableFrame(frame_content)
        frame_scroll.pack(fill="both", expand=True)

        shortcuts = [
            ("Ctrl+O", "Seleccionar carpeta"),
            ("F5", "Actualizar lista de archivos"),
            ("Ctrl+A", "Seleccionar todo"),
            ("Ctrl+Q", "Cerrar aplicación"),
            ("Doble-clic", "Editar celda en tabla"),
            ("Enter", "Guardar edición de celda"),
            ("Esc", "Cancelar edición de celda"),
        ]

        for shortcut, description in shortcuts:
            # Frame para cada atajo
            frame_shortcut = ctk.CTkFrame(frame_scroll)
            frame_shortcut.pack(fill="x", padx=0, pady=6)

            # Tecla (izquierda)
            lbl_key = ctk.CTkLabel(
                frame_shortcut,
                text=shortcut,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=self.CORP_COLOR,
                width=80,
                anchor="w"
            )
            lbl_key.pack(side="left", padx=(0, 15))

            # Descripción (derecha)
            lbl_desc = ctk.CTkLabel(
                frame_shortcut,
                text=description,
                font=ctk.CTkFont(size=10),
                anchor="w"
            )
            lbl_desc.pack(side="left", fill="x", expand=True)

        # Botón cerrar
        btn_close = ctk.CTkButton(
            frame_content,
            text="Cerrar",
            height=32,
            command=shortcuts_win.destroy
        )
        btn_close.pack(fill="x", pady=(12, 0))


if __name__ == "__main__":
    app = App()
    app.mainloop()