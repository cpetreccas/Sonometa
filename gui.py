import logging
import os
import sys
import ctypes
import io
import re
import time
import urllib.request
import json
from collections import deque
import tkinter as tk
import urllib.parse
from tkinter import ttk
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
    CLEAR_OPTION = "<Limpiar>"

    def __init__(self):
        super().__init__()

        self.title("Sonometa v0.04 - Audio Tag Suite")
        self.geometry("1180x780")
        self.minsize(1000, 680)

        self.after(10, self.maximize_window)

        # Aplicar dark title bar a la ventana principal
        self.after(50, lambda: self.apply_dark_title_bar(self))
        self.after(150, lambda: self.apply_dark_title_bar(self))
        self.after(300, lambda: self.apply_dark_title_bar(self))

        self.folder_path = ""
        self.sort_directions = {}
        self.file_paths_map = {}
        self.cell_entry = None
        self.log_history = deque(maxlen=5000)
        self.log_window = None
        self.log_textbox = None
        self.catalog_fields = ("Genre", "Album", "Publisher")
        self.catalog_labels = {
            "Genre": "Géneros",
            "Album": "Álbumes",
            "Publisher": "Etiquetas"
        }
        self.catalog_values = {field: [] for field in self.catalog_fields}
        self.catalog_file_path = self.get_catalog_file_path()
        self.load_catalog_values()

        self.gui_log_handler = TextHandler(self)
        self.gui_log_handler.setFormatter(formatter)
        logger.addHandler(self.gui_log_handler)

        self.ico_path = get_resource_path("logo.ico")
        png_path = get_resource_path("logo.png")
        self.app_icon_photo = None

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
            font=ctk.CTkFont(size=12, weight="bold"),
            height=32,
            command=self.refresh_folder
        )
        self.btn_refresh.pack(side="left", padx=5, pady=5)

        self.label_folder = ctk.CTkLabel(self.frame_top, text="Ninguna carpeta seleccionada", text_color="gray")
        self.label_folder.pack(side="left", padx=10, pady=5)

        self.frame_main = ctk.CTkFrame(self)
        self.frame_main.pack(fill="both", expand=True, padx=15, pady=5)

        # El panel de etiquetas se crea primero para reservar el ancho lateral.
        self.setup_tag_panel()
        self.setup_treeview()

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
        self.bind("<Control-q>", lambda e: self.on_close())
        self.bind("<Control-a>", lambda e: self.select_all_rows())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

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

    def get_catalog_file_path(self):
        base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(base_dir, "Sonometa")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "catalogos.json")

    def load_catalog_values(self):
        if not os.path.exists(self.catalog_file_path):
            return
        try:
            with open(self.catalog_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for field in self.catalog_fields:
                raw_values = data.get(field, [])
                if isinstance(raw_values, list):
                    cleaned = []
                    for value in raw_values:
                        value_str = self.normalize_catalog_text(value)
                        if value_str and value_str not in cleaned:
                            cleaned.append(value_str)
                    self.catalog_values[field] = cleaned
        except Exception as e:
            logger.warning(f"No se pudieron cargar catálogos persistidos: {str(e)}")

    @staticmethod
    def normalize_catalog_text(value):
        value_str = str(value).strip() if value is not None else ""
        if not value_str:
            return ""
        return value_str[0].upper() + value_str[1:].lower()

    def save_catalog_values(self):
        try:
            with open(self.catalog_file_path, "w", encoding="utf-8") as f:
                json.dump(self.catalog_values, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"No se pudieron guardar los catálogos: {str(e)}")

    def add_catalog_value(self, field_name, value, persist=False):
        value_str = self.normalize_catalog_text(value)
        if field_name not in self.catalog_fields or not value_str:
            return False
        if value_str in self.catalog_values[field_name]:
            return False
        self.catalog_values[field_name].append(value_str)
        self.catalog_values[field_name].sort(key=lambda x: x.lower())
        self.refresh_catalog_comboboxes()
        if persist:
            self.save_catalog_values()
        return True

    def get_catalog_combo_values(self, catalog_key):
        values = [v for v in self.catalog_values.get(catalog_key, []) if v and v != self.CLEAR_OPTION]
        values = sorted(dict.fromkeys(values), key=lambda x: x.lower())
        return values + [self.CLEAR_OPTION]

    @staticmethod
    def get_catalog_column_info(catalog_key):
        mapping = {
            "Album": ("Album", 4),
            "Genre": ("Genre", 5),
            "Publisher": ("Publisher", 6),
        }
        return mapping.get(catalog_key)

    def apply_catalog_value_change(self, catalog_key, old_value, new_value):
        info = self.get_catalog_column_info(catalog_key)
        if not info:
            return 0

        col_name, col_index = info
        old_value = self.normalize_catalog_text(old_value)
        new_value = self.normalize_catalog_text(new_value)
        if not old_value:
            return 0

        updated_count = 0
        for row_id in self.tree.get_children():
            row_values = list(self.tree.item(row_id, "values"))
            if col_index >= len(row_values):
                continue

            current_value = self.normalize_catalog_text(row_values[col_index])
            if current_value != old_value:
                continue

            row_values[col_index] = new_value
            self.tree.item(row_id, values=row_values)

            file_path = self.file_paths_map.get(row_id)
            if file_path:
                self.save_single_tag(file_path, col_name, new_value)
            updated_count += 1

        return updated_count

    def rename_catalog_value(self, catalog_key, old_value, new_value):
        if catalog_key not in self.catalog_fields:
            return 0, False

        old_value = self.normalize_catalog_text(old_value)
        new_value = self.normalize_catalog_text(new_value)
        if not old_value or not new_value:
            return 0, False

        if old_value == new_value:
            return 0, False

        values = self.catalog_values.get(catalog_key, [])
        if old_value not in values:
            return 0, False

        merged = new_value in values
        updated_count = self.apply_catalog_value_change(catalog_key, old_value, new_value)

        values.remove(old_value)
        if new_value not in values:
            values.append(new_value)
        values.sort(key=lambda x: x.lower())

        self.refresh_catalog_comboboxes()
        self.save_catalog_values()
        self.on_row_select(None)
        return updated_count, merged

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

        self.menu_gestionar = tk.Menu(self, tearoff=0, bg="#252526", fg="#FFFFFF", activebackground=self.CORP_COLOR, activeforeground="#FFFFFF", bd=1)
        self.menu_gestionar.add_command(label="Géneros", command=lambda: self.open_catalog_manager("Genre"))
        self.menu_gestionar.add_command(label="Álbumes", command=lambda: self.open_catalog_manager("Album"))
        self.menu_gestionar.add_command(label="Etiquetas", command=lambda: self.open_catalog_manager("Publisher"))

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
        create_menu_btn("Gestionar", self.menu_gestionar)
        create_menu_btn("Ayuda", self.menu_ayuda)

    def apply_popup_style(self, win, is_modal=True, owner=None):
        try:
            if os.path.exists(self.ico_path):
                win.iconbitmap(self.ico_path)
            if self.app_icon_photo is not None:
                win.wm_iconphoto(True, self.app_icon_photo)
        except Exception:
            pass

        win.configure(fg_color="#181818")
        owner_window = owner if owner is not None else self
        win.transient(owner_window)

        # No bloquear la ventana principal: sin grab_set aunque la ventana sea modal lógica.
        try:
            win.update_idletasks()
            self.center_popup_on_screen(win)
            self.apply_dark_title_bar(win)
            win.bind("<Map>", lambda _e, w=win: self.apply_dark_title_bar(w), add="+")
            win.after(80, lambda w=win: self.apply_dark_title_bar(w))
            win.after(220, lambda w=win: self.apply_dark_title_bar(w))
            win.lift()
            win.focus_force()
            win.attributes("-topmost", True)
            win.after(120, lambda w=win: w.attributes("-topmost", False) if w.winfo_exists() else None)
        except Exception:
            pass


    @staticmethod
    def center_popup_on_screen(win):
        geometry = win.geometry().split("+")[0]
        if "x" in geometry:
            width_str, height_str = geometry.split("x", 1)
            try:
                width = int(width_str)
                height = int(height_str)
            except ValueError:
                width = win.winfo_reqwidth()
                height = win.winfo_reqheight()
        else:
            width = win.winfo_reqwidth()
            height = win.winfo_reqheight()

        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()
        pos_x = max(0, (screen_w - width) // 2)
        pos_y = max(0, (screen_h - height) // 2)
        win.geometry(f"{width}x{height}+{pos_x}+{pos_y}")

    @staticmethod
    def apply_dark_title_bar(win):
        if sys.platform != "win32":
            return
        if not win.winfo_exists():
            return

        try:
            hwnd = win.winfo_id()
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attr,
                    ctypes.byref(value),
                    ctypes.sizeof(value)
                )
        except Exception:
            pass


    def show_themed_dialog(self, title, message, level="info", is_confirm=False, parent=None):
        host = parent if parent is not None else self
        dialog = ctk.CTkToplevel(host)
        dialog.title(title)
        dialog.geometry("460x210")
        dialog.resizable(False, False)
        self.apply_popup_style(dialog, is_modal=True, owner=host)

        frame = ctk.CTkFrame(dialog, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        icon_text = "i"
        if level == "warning":
            icon_text = "!"
        elif level == "error":
            icon_text = "x"

        lbl_icon = ctk.CTkLabel(
            frame,
            text=icon_text,
            width=26,
            height=26,
            corner_radius=13,
            fg_color=self.CORP_COLOR,
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl_icon.pack(anchor="w", pady=(2, 8))

        lbl_msg = ctk.CTkLabel(
            frame,
            text=message,
            justify="left",
            anchor="w",
            wraplength=420,
            text_color="#E5E7EB"
        )
        lbl_msg.pack(fill="x", pady=(0, 12))

        result = {"value": False}

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", side="bottom")

        def accept():
            result["value"] = True
            dialog.destroy()

        def cancel():
            result["value"] = False
            dialog.destroy()

        if is_confirm:
            ctk.CTkButton(
                btns,
                text="Cancelar",
                command=cancel,
                fg_color="#374151",
                hover_color="#1F2937"
            ).pack(side="right", padx=(6, 0))
            ctk.CTkButton(
                btns,
                text="Aceptar",
                command=accept,
                fg_color=self.CORP_COLOR,
                hover_color=self.CORP_HOVER
            ).pack(side="right")
        else:
            ctk.CTkButton(
                btns,
                text="Aceptar",
                command=accept,
                fg_color=self.CORP_COLOR,
                hover_color=self.CORP_HOVER
            ).pack(side="right")

        dialog.wait_window()
        return result["value"]

    def setup_tag_panel(self):
        self.frame_sidebar = ctk.CTkFrame(self.frame_main, width=260)
        self.frame_sidebar.pack(side="left", fill="y", padx=(0, 5), pady=0)
        self.frame_sidebar.pack_propagate(False)

        self.panel_combo_fields = {
            "entry_album": "Album",
            "entry_genre": "Genre",
            "entry_publisher": "Publisher"
        }

        fields = [
            ("Intérprete", "entry_artist"),
            ("Título", "entry_title"),
            ("Remix", "entry_mixartist"),
            ("Álbum", "entry_album"),
            ("Año", "entry_year"),
            ("Género", "entry_genre"),
            ("Etiqueta", "entry_publisher")
        ]

        self.tag_entries = {}
        for label_text, attr_name in fields:
            lbl = ctk.CTkLabel(self.frame_sidebar, text=label_text, anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
            lbl.pack(fill="x", padx=5, pady=(4, 0))

            if attr_name in self.panel_combo_fields:
                catalog_key = self.panel_combo_fields[attr_name]
                widget = ctk.CTkComboBox(
                    self.frame_sidebar,
                    values=self.get_catalog_combo_values(catalog_key),
                    state="readonly",
                    height=26,
                    font=ctk.CTkFont(size=12),
                    command=lambda _value, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_selected(_attr, _cat)
                )
                widget.set("")
                widget.bind("<Button-1>", lambda _e, _w=widget: self.on_panel_combo_click(_w))
                widget.bind(
                    "<FocusOut>",
                    lambda _e, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_focus_out(_attr, _cat)
                )
                widget.bind(
                    "<Return>",
                    lambda _e, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_enter(_attr, _cat)
                )
            else:
                widget = ctk.CTkEntry(self.frame_sidebar, height=26, font=ctk.CTkFont(size=12))
                widget.bind("<FocusOut>", lambda _e, _attr=attr_name: self.on_panel_text_field_commit(_attr))
                widget.bind("<Return>", lambda _e, _attr=attr_name: self.on_panel_text_field_enter(_attr))

            widget.pack(fill="x", padx=5, pady=(0, 4))
            self.tag_entries[attr_name] = widget


        lbl_cover_title = ctk.CTkLabel(self.frame_sidebar, text="Carátula", anchor="w", font=ctk.CTkFont(size=11, weight="bold"))
        lbl_cover_title.pack(fill="x", padx=5, pady=(8, 2))

        self.label_cover = ctk.CTkLabel(
            self.frame_sidebar,
            text="Sin carátula",
            width=180,
            height=180,
            fg_color="transparent",
            text_color="gray",
            border_color="#6B7280",
            border_width=1
        )
        self.label_cover.pack(padx=5, pady=5)

        logo3_path = get_resource_path("logo_blanco.png")
        btn_icon = None
        if os.path.exists(logo3_path):
            try:
                img_logo3 = Image.open(logo3_path)
                btn_icon = ctk.CTkImage(light_image=img_logo3, dark_image=img_logo3, size=(22, 22))
            except Exception as e:
                logger.error(f"Error al cargar logo_blanco.png para el botón Procesar: {str(e)}")

        self.btn_process = ctk.CTkButton(
            self.frame_sidebar,
            text="Procesar",
            image=btn_icon if btn_icon else icono_procesar,
            compound="left",
            fg_color=self.CORP_COLOR,
            hover_color=self.CORP_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            command=self.process_discogs_data
        )
        self.btn_process.pack(fill="x", padx=5, pady=(6, 10))

    def setup_treeview(self):
        self.frame_grid = ctk.CTkFrame(self.frame_main)
        self.frame_grid.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

        style = ttk.Style()
        style.theme_use("clam")
        self.tree_edit_combo_style = "Sonometa.TreeEdit.TCombobox"

        try:
            base_layout = style.layout("TCombobox")
            style.layout(self.tree_edit_combo_style, self._remove_combobox_arrow_from_layout(base_layout))
        except Exception:
            pass

        style.configure(
            self.tree_edit_combo_style,
            fieldbackground="#181818",
            background="#181818",
            foreground="#E0E0E0",
            selectbackground="#181818",
            selectforeground="#E0E0E0",
            arrowcolor="#181818",
            relief="flat",
            borderwidth=0,
            padding=(3, 2)
        )
        style.map(
            self.tree_edit_combo_style,
            fieldbackground=[("readonly", "#181818"), ("focus", "#181818")],
            background=[("readonly", "#181818"), ("focus", "#181818")],
            foreground=[("readonly", "#E0E0E0"), ("focus", "#E0E0E0")],
            selectbackground=[("readonly", "#181818"), ("focus", "#181818")],
            selectforeground=[("readonly", "#E0E0E0"), ("focus", "#E0E0E0")],
            arrowcolor=[("readonly", "#181818"), ("focus", "#181818")]
        )

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
            "Publisher": "Etiqueta",
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

        self.vsb = ttk.Scrollbar(self.frame_grid, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.frame_grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self._on_tree_y_scroll, xscrollcommand=self._on_tree_x_scroll)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Configure>", lambda _e: self._update_tree_scrollbars(), add="+")
        self.after_idle(self._update_tree_scrollbars)

    def _on_tree_y_scroll(self, first, last):
        self._update_scrollbar(self.vsb, first, last, side="right", fill="y")

    def _on_tree_x_scroll(self, first, last):
        self._update_scrollbar(self.hsb, first, last, side="bottom", fill="x")

    def _update_scrollbar(self, scrollbar, first, last, side, fill):
        scrollbar.set(first, last)
        needs_scroll = float(first) > 0.0 or float(last) < 1.0
        if needs_scroll and not scrollbar.winfo_ismapped():
            scrollbar.pack(side=side, fill=fill)
        elif not needs_scroll and scrollbar.winfo_ismapped():
            scrollbar.pack_forget()

    def _update_tree_scrollbars(self):
        x_first, x_last = self.tree.xview()
        y_first, y_last = self.tree.yview()
        self._on_tree_x_scroll(x_first, x_last)
        self._on_tree_y_scroll(y_first, y_last)

    @staticmethod
    def _remove_combobox_arrow_from_layout(layout):
        cleaned = []
        for item in layout:
            if not isinstance(item, tuple) or len(item) < 2:
                cleaned.append(item)
                continue

            element, options = item[0], item[1]
            if isinstance(element, str) and "downarrow" in element.lower():
                continue

            if isinstance(options, dict):
                new_options = dict(options)
                children = new_options.get("children")
                if children:
                    new_options["children"] = App._remove_combobox_arrow_from_layout(children)
                cleaned.append((element, new_options))
            else:
                cleaned.append(item)

        return cleaned

    def _open_tree_combo_dropdown(self, widget):
        try:
            widget.focus_set()
            widget.tk.call("ttk::combobox::Post", str(widget))
        except Exception:
            try:
                widget.event_generate("<Down>")
            except Exception:
                pass

    def _close_tree_combo_dropdown(self, widget):
        try:
            widget.tk.call("ttk::combobox::Unpost", str(widget))
        except Exception:
            pass

    def _is_tree_combo_dropdown_open(self, widget):
        try:
            popdown = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
            return bool(int(widget.tk.call("winfo", "ismapped", popdown)))
        except Exception:
            return False

    def _get_next_tree_edit_target(self, row_id, col_index, direction):
        editable_cols = [idx for idx, col in enumerate(self.columns) if col != "Cover"]
        if col_index not in editable_cols:
            return None

        rows = list(self.tree.get_children())
        try:
            row_pos = rows.index(row_id)
            col_pos = editable_cols.index(col_index)
        except ValueError:
            return None

        if direction == "tab":
            if col_pos < len(editable_cols) - 1:
                return rows[row_pos], editable_cols[col_pos + 1]
            if row_pos < len(rows) - 1:
                return rows[row_pos + 1], editable_cols[0]
        elif direction == "shift_tab":
            if col_pos > 0:
                return rows[row_pos], editable_cols[col_pos - 1]
            if row_pos > 0:
                return rows[row_pos - 1], editable_cols[-1]
        elif direction == "enter":
            if row_pos < len(rows) - 1:
                return rows[row_pos + 1], col_index
        elif direction == "shift_enter":
            if row_pos > 0:
                return rows[row_pos - 1], col_index

        return None

    def _start_tree_cell_edit(self, row_id, col_index, open_dropdown=True):
        if col_index < 0 or col_index >= len(self.columns):
            return

        col_name = self.columns[col_index]
        if col_name == "Cover":
            return

        if self.cell_entry:
            self.cell_entry.destroy()
            self.cell_entry = None

        column_id = f"#{col_index + 1}"
        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, w, h = bbox

        row_values = self.tree.item(row_id, "values")
        if col_index >= len(row_values):
            return
        current_value = row_values[col_index]

        managed_grid_fields = {"Album", "Genre", "Publisher"}
        if col_name in managed_grid_fields:
            entry = ttk.Combobox(
                self.tree,
                state="readonly",
                values=self.get_catalog_combo_values(col_name),
                style=self.tree_edit_combo_style,
                exportselection=False
            )
        else:
            entry = ttk.Entry(self.tree)

        current_value_str = str(current_value)
        if col_name == "Filename":
            current_stem, _ = os.path.splitext(current_value_str)
            entry.insert(0, current_stem)
        else:
            if col_name in managed_grid_fields:
                current_options = list(self.catalog_values.get(col_name, []))
                if current_value_str and current_value_str not in current_options:
                    current_options.append(current_value_str)
                    current_options.sort(key=lambda x: x.lower())
                entry.configure(values=current_options + [self.CLEAR_OPTION])
                entry.set(current_value_str)
            else:
                entry.insert(0, current_value_str)

        if col_name not in managed_grid_fields:
            entry.select_range(0, "end")
        entry.focus_set()
        entry.place(x=x, y=y, width=w, height=h)
        if col_name in managed_grid_fields:
            if open_dropdown:
                entry.after(50, lambda w=entry: self._open_tree_combo_dropdown(w) if w.winfo_exists() else None)

        finalized = False

        def save_edit(evt=None):
            nonlocal finalized
            if finalized:
                return True
            finalized = True
            self._close_tree_combo_dropdown(entry)
            new_value = entry.get().strip()
            entry.destroy()
            self.cell_entry = None

            if col_name in managed_grid_fields:
                if new_value == self.CLEAR_OPTION:
                    new_value = ""
                new_value = self.normalize_catalog_text(new_value)

            if col_name == "Filename":
                if not new_value:
                    logger.warning("Nombre de archivo vacío: se cancela el renombrado.")
                    self.show_themed_dialog("Nombre no válido", "El nombre del archivo no puede estar vacío.", level="warning")
                    return False

                safe_name = new_value.replace("/", "_").replace("\\", "_").rstrip(".").strip()
                if not safe_name:
                    logger.warning("Nombre de archivo inválido: se cancela el renombrado.")
                    self.show_themed_dialog("Nombre no válido", "El nombre del archivo no es válido.", level="warning")
                    return False

                original_filename = current_value_str.strip()
                _, original_ext = os.path.splitext(original_filename)
                final_filename = f"{safe_name}{original_ext}"

                if final_filename == original_filename:
                    return True

                file_path = self.file_paths_map.get(row_id)
                if not file_path or not os.path.exists(file_path):
                    logger.error("No se puede renombrar: archivo no encontrado.")
                    self.show_themed_dialog("Archivo no encontrado", "No se puede renombrar porque el archivo ya no existe en disco.", level="error")
                    return False

                target_path = os.path.join(os.path.dirname(file_path), final_filename)
                if os.path.normcase(target_path) != os.path.normcase(file_path) and os.path.exists(target_path):
                    logger.warning(f"Ya existe un archivo con ese nombre: {final_filename}")
                    self.show_themed_dialog("Nombre en uso", f"Ya existe un archivo con el nombre:\n{final_filename}", level="warning")
                    return False

                try:
                    os.rename(file_path, target_path)
                    self.file_paths_map[row_id] = target_path

                    values = list(self.tree.item(row_id, "values"))
                    values[col_index] = final_filename
                    self.tree.item(row_id, values=values)
                    self.on_row_select(None)
                    logger.info(f"Renombrado manual: '{original_filename}' -> '{final_filename}'")
                except Exception as e:
                    logger.error(f"No se pudo renombrar el archivo '{original_filename}': {str(e)}")
                    self.show_themed_dialog("Error al renombrar", f"No se pudo renombrar el archivo:\n{str(e)}", level="error")
                    return False

                return True

            if new_value == current_value_str.strip():
                return True

            if col_name in managed_grid_fields and new_value and new_value not in self.catalog_values.get(col_name, []):
                self.show_themed_dialog("Valor no permitido", f"El valor '{new_value}' no está en {self.catalog_labels[col_name]}.", level="warning")
                return False

            values = list(self.tree.item(row_id, "values"))
            values[col_index] = new_value
            self.tree.item(row_id, values=values)

            self.on_row_select(None)

            file_path = self.file_paths_map.get(row_id)
            if file_path:
                self.save_single_tag(file_path, col_name, new_value)

            return True

        def navigate(direction):
            if save_edit():
                next_target = self._get_next_tree_edit_target(row_id, col_index, direction)
                if next_target:
                    next_row_id, next_col_index = next_target
                    self.after_idle(lambda r=next_row_id, c=next_col_index: self._start_tree_cell_edit(r, c, open_dropdown=False))
            return "break"

        def commit_combo_selection(evt=None):
            entry.after_idle(save_edit)
            return "break"

        combo_type_state = {"buffer": "", "last_ts": 0.0, "matches": [], "match_idx": 0}

        def on_combo_type_search(evt=None):
            if col_name not in managed_grid_fields:
                return

            if evt is None:
                return "break"

            # No interferir con teclas de navegación/confirmación.
            if evt.keysym in {"Return", "KP_Enter", "Tab", "ISO_Left_Tab", "Up", "Down", "Left", "Right", "Escape"}:
                return

            values = [str(v) for v in entry.cget("values") if str(v) != self.CLEAR_OPTION]
            if not values:
                return "break"

            now = time.monotonic()
            if now - combo_type_state["last_ts"] > 1.0:
                combo_type_state["buffer"] = ""
            combo_type_state["last_ts"] = now

            if evt.keysym == "BackSpace":
                combo_type_state["buffer"] = combo_type_state["buffer"][:-1]
            else:
                char = evt.char or ""
                if not char.isprintable() or char.isspace():
                    return "break"
                combo_type_state["buffer"] += char.lower()

            if not combo_type_state["buffer"]:
                return "break"

            buffer = combo_type_state["buffer"]
            matches = [v for v in values if v.lower().startswith(buffer)]
            if not matches:
                matches = [v for v in values if buffer in v.lower()]
            combo_type_state["matches"] = matches
            combo_type_state["match_idx"] = 0
            if matches:
                match = matches[0]
                try:
                    idx = list(entry.cget("values")).index(match)
                    entry.current(idx)
                except Exception:
                    entry.set(match)

            return "break"

        def on_combo_cycle(forward=True):
            matches = combo_type_state.get("matches", [])
            if not matches:
                if forward:
                    self._open_tree_combo_dropdown(entry)
                return "break"

            idx = combo_type_state["match_idx"]
            idx = (idx + 1) % len(matches) if forward else (idx - 1) % len(matches)
            combo_type_state["match_idx"] = idx
            match = matches[idx]
            try:
                all_values = list(entry.cget("values"))
                entry.current(all_values.index(match))
            except Exception:
                entry.set(match)
            return "break"

        def on_focus_out(evt=None):
            def commit_if_closed():
                # Si el desplegable sigue abierto, no cerrar todavía (permite seleccionar).
                if col_name in managed_grid_fields and self._is_tree_combo_dropdown_open(entry):
                    return
                save_edit()

            # Esperar un poco para que Tk procese selección/cierre del popdown.
            entry.after(120, commit_if_closed)

        entry.bind("<Return>", lambda _e: navigate("enter"))
        entry.bind("<Shift-Return>", lambda _e: navigate("shift_enter"))
        entry.bind("<Tab>", lambda _e: navigate("tab"))
        entry.bind("<Shift-Tab>", lambda _e: navigate("shift_tab"))
        entry.bind("<ISO_Left_Tab>", lambda _e: navigate("shift_tab"))
        if col_name in managed_grid_fields:
            entry.bind("<<ComboboxSelected>>", commit_combo_selection)
            entry.bind("<KeyPress>", on_combo_type_search)
            entry.bind("<Down>", lambda _e: self._open_tree_combo_dropdown(entry) or "break")
            entry.bind("<space>", lambda _e: self._open_tree_combo_dropdown(entry) or "break")
            entry.bind("<Down>", lambda _e: on_combo_cycle(forward=True))
            entry.bind("<Up>", lambda _e: on_combo_cycle(forward=False))
        entry.bind("<FocusOut>", on_focus_out)
        self.cell_entry = entry

    def on_cell_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        col_index = int(column_id.replace("#", "")) - 1
        if col_index < 0 or col_index >= len(self.columns):
            return
        col_name = self.columns[col_index]

        if col_name == "Cover":
            return

        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return
        self._start_tree_cell_edit(row_id, col_index)

    def process_discogs_data(self):
        target_rows = self.tree.selection()
        if not target_rows:
            target_rows = self.tree.get_children()

        if not target_rows:
            self.show_themed_dialog("Advertencia", "No hay archivos cargados en la tabla.", level="warning")
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

    @staticmethod
    def _build_http_request(url, user_agent, timeout):
        headers = {"User-Agent": user_agent}
        return urllib.request.Request(url, headers=headers), timeout

    def search_discogs_api(self, query):
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.discogs.com/database/search?q={encoded_query}&format=Vinyl&type=release"
            req, timeout = self._build_http_request(
                url,
                "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)",
                5,
            )

            logger.info("--- [DISCOGS REQUEST (VINYL FILTER)] ---")
            logger.info(f"URL: {url}")

            with urllib.request.urlopen(req, timeout=timeout) as response:
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
            req, timeout = self._build_http_request(
                image_url,
                "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)",
                10,
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
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

        self._set_panel_widget_value("entry_artist", values[1])
        self._set_panel_widget_value("entry_title", values[2])
        self._set_panel_widget_value("entry_mixartist", values[3])
        self._set_panel_widget_value("entry_album", values[4])
        self._set_panel_widget_value("entry_genre", values[5])
        self._set_panel_widget_value("entry_publisher", values[6])
        self._set_panel_widget_value("entry_year", values[7])

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

        for widget in self.tag_entries.values():
            if isinstance(widget, ctk.CTkComboBox):
                widget.set("")
            else:
                widget.delete(0, "end")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None
        self.folder_path = ""
        self.label_folder.configure(text="Ninguna carpeta seleccionada", text_color="gray")
        self.progress_bar.set(0)
        logger.info("Lista y estado limpiados.")

    def refresh_catalog_comboboxes(self):
        for attr_name, catalog_key in getattr(self, "panel_combo_fields", {}).items():
            combo = self.tag_entries.get(attr_name)
            if not combo:
                continue
            current_value = combo.get().strip()
            allowed_values = self.get_catalog_combo_values(catalog_key)
            combo.configure(values=allowed_values)
            if current_value in allowed_values:
                combo.set(current_value)
            else:
                combo.set("")

    def _set_panel_widget_value(self, attr_name, value):
        widget = self.tag_entries.get(attr_name)
        if not widget:
            return

        value_str = str(value) if value else ""
        if attr_name in getattr(self, "panel_combo_fields", {}):
            catalog_key = self.panel_combo_fields[attr_name]
            normalized_value = self.normalize_catalog_text(value_str)
            self.add_catalog_value(catalog_key, normalized_value, persist=False)
            widget.set(normalized_value)
            return

        widget.delete(0, "end")
        widget.insert(0, value_str)

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
        self.on_row_select(None)

    def on_panel_catalog_selected(self, attr_name, catalog_key):
        selected_rows = self.tree.selection()
        if not selected_rows:
            logger.info(f"Selección de catálogo ignorada ({self.catalog_labels.get(catalog_key, catalog_key)}): no hay fila seleccionada.")
            return
        row_id = selected_rows[0]
        combo = self.tag_entries.get(attr_name)
        if not combo:
            return
        raw_value = combo.get().strip()
        if raw_value == self.CLEAR_OPTION:
            new_value = ""
        else:
            new_value = self.normalize_catalog_text(raw_value)
        self._apply_catalog_selection_to_row(row_id, attr_name, catalog_key, new_value)

    def on_panel_combo_click(self, combo_widget):
        try:
            combo_widget.focus_set()
            combo_widget._open_dropdown_menu()
        except Exception:
            pass
        return "break"

    def on_panel_catalog_enter(self, attr_name, catalog_key):
        self.on_panel_catalog_selected(attr_name, catalog_key)
        return "break"

    def on_panel_catalog_focus_out(self, attr_name, catalog_key):
        # Delay corto para que CTk actualice internamente el valor antes de guardar.
        self.after(50, lambda a=attr_name, c=catalog_key: self.on_panel_catalog_selected(a, c))

    def on_panel_text_field_enter(self, attr_name):
        self.on_panel_text_field_commit(attr_name)
        return "break"

    def on_panel_text_field_commit(self, attr_name):
        text_column_map = {
            "entry_artist": ("Artist", 1),
            "entry_title": ("Title", 2),
            "entry_mixartist": ("MixArtist", 3),
            "entry_year": ("Year", 7),
        }
        if attr_name not in text_column_map:
            return

        selected_rows = self.tree.selection()
        if not selected_rows:
            return
        row_id = selected_rows[0]

        widget = self.tag_entries.get(attr_name)
        if not widget:
            return
        new_value = widget.get().strip()

        col_name, col_index = text_column_map[attr_name]
        values = list(self.tree.item(row_id, "values"))
        if col_index >= len(values):
            return
        current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
        if current_value == new_value:
            return

        values[col_index] = new_value
        self.tree.item(row_id, values=values)

        file_path = self.file_paths_map.get(row_id)
        if file_path:
            self.save_single_tag(file_path, col_name, new_value)

        logger.info(f"Campo '{col_name}' actualizado desde panel izquierdo: '{current_value}' -> '{new_value}'")

    def open_catalog_manager(self, catalog_key):
        if catalog_key not in self.catalog_fields:
            return

        logger.info(f"Abriendo gestión de {self.catalog_labels[catalog_key]}.")

        win = ctk.CTkToplevel(self)
        win.title(f"Gestionar {self.catalog_labels[catalog_key]}")
        win.geometry("420x380")
        self.apply_popup_style(win, is_modal=True, owner=self)

        frame = ctk.CTkFrame(win)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        listbox = tk.Listbox(frame, bg="#1E1E1E", fg="#E5E7EB", selectbackground=self.CORP_COLOR, height=10)
        listbox.pack(fill="both", expand=True, pady=(0, 8))

        entry = ctk.CTkEntry(frame, placeholder_text="Nuevo valor o valor modificado")
        entry.pack(fill="x", pady=(0, 8))

        def refresh_listbox():
            listbox.delete(0, "end")
            for item in self.catalog_values.get(catalog_key, []):
                listbox.insert("end", item)

        def add_value():
            value = self.normalize_catalog_text(entry.get())
            if not value:
                logger.warning(f"Alta en {self.catalog_labels[catalog_key]} cancelada: valor vacío.")
                self.show_themed_dialog("Valor no válido", "Debes introducir un valor.", level="warning", parent=win)
                return
            if value in self.catalog_values[catalog_key]:
                logger.warning(f"Alta en {self.catalog_labels[catalog_key]} cancelada: '{value}' ya existe.")
                self.show_themed_dialog("Duplicado", "Ese valor ya existe.", level="warning", parent=win)
                return
            self.catalog_values[catalog_key].append(value)
            self.catalog_values[catalog_key].sort(key=lambda x: x.lower())
            self.refresh_catalog_comboboxes()
            self.save_catalog_values()
            refresh_listbox()
            entry.delete(0, "end")
            logger.info(f"Añadido '{value}' a {self.catalog_labels[catalog_key]}.")

        def update_value():
            selected = listbox.curselection()
            if not selected:
                logger.warning(f"Modificación en {self.catalog_labels[catalog_key]} cancelada: sin selección.")
                self.show_themed_dialog("Selección requerida", "Selecciona un valor para modificar.", level="warning", parent=win)
                return
            new_value = self.normalize_catalog_text(entry.get())
            if not new_value:
                logger.warning(f"Modificación en {self.catalog_labels[catalog_key]} cancelada: valor vacío.")
                self.show_themed_dialog("Valor no válido", "Debes introducir el nuevo valor.", level="warning", parent=win)
                return
            idx = selected[0]
            old_value = self.normalize_catalog_text(self.catalog_values[catalog_key][idx])
            if new_value == old_value:
                logger.info(
                    f"Modificación en {self.catalog_labels[catalog_key]} omitida: '{old_value}' no cambia."
                )
                return

            updated_count, merged = self.rename_catalog_value(catalog_key, old_value, new_value)
            refresh_listbox()
            entry.delete(0, "end")

            logger.info(
                f"Modificada {self.catalog_labels[catalog_key]}: '{old_value}' -> '{new_value}'. "
                f"Afectados: {updated_count}. Fusión: {'sí' if merged else 'no'}."
            )

            if merged:
                self.show_themed_dialog(
                    "Valores fusionados",
                    f"'{old_value}' se fusionó con '{new_value}'.\n"
                    f"Se actualizaron {updated_count} archivo(s).",
                    level="info",
                    parent=win
                )
            else:
                self.show_themed_dialog(
                    "Valor actualizado",
                    f"Se reemplazó '{old_value}' por '{new_value}'.\n"
                    f"Se actualizaron {updated_count} archivo(s).",
                    level="info",
                    parent=win
                )

        def delete_value():
            selected = listbox.curselection()
            if not selected:
                logger.warning(f"Eliminación en {self.catalog_labels[catalog_key]} cancelada: sin selección.")
                self.show_themed_dialog("Selección requerida", "Selecciona un valor para eliminar.", level="warning", parent=win)
                return
            idx = selected[0]
            value = self.catalog_values[catalog_key][idx]

            affected_count = 0
            col_info = self.get_catalog_column_info(catalog_key)
            if col_info:
                _, col_index = col_info
                for row_id in self.tree.get_children():
                    row_values = self.tree.item(row_id, "values")
                    if col_index < len(row_values) and self.normalize_catalog_text(row_values[col_index]) == value:
                        affected_count += 1

            confirm_msg = (
                f"¿Eliminar '{value}'?\n\n"
                f"Esto vaciará el campo en {affected_count} archivo(s)."
            )
            if not self.show_themed_dialog("Confirmar eliminación", confirm_msg, level="warning", is_confirm=True, parent=win):
                logger.info(f"Eliminación en {self.catalog_labels[catalog_key]} cancelada por usuario ('{value}').")
                return

            updated_count = self.apply_catalog_value_change(catalog_key, value, "")
            self.catalog_values[catalog_key].pop(idx)
            self.refresh_catalog_comboboxes()
            self.save_catalog_values()
            refresh_listbox()
            entry.delete(0, "end")
            self.on_row_select(None)

            logger.info(
                f"Eliminado '{value}' de {self.catalog_labels[catalog_key]}. "
                f"Campos vaciados en {updated_count} archivo(s)."
            )

            self.show_themed_dialog(
                "Valor eliminado",
                f"Se eliminó '{value}'.\n"
                f"Se vació el campo en {updated_count} archivo(s).",
                level="info",
                parent=win
            )

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(btns, text="Añadir", command=add_value, fg_color=self.CORP_COLOR, hover_color=self.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btns, text="Modificar", command=update_value, fg_color=self.CORP_COLOR, hover_color=self.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(btns, text="Eliminar", command=delete_value, fg_color="#B91C1C", hover_color="#991B1B").pack(side="left", expand=True, fill="x", padx=(4, 0))

        ctk.CTkButton(frame, text="Cerrar", command=win.destroy, fg_color=self.CORP_COLOR, hover_color=self.CORP_HOVER).pack(fill="x")

        refresh_listbox()

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

        logger.info(f"Escaneando carpeta: {folder}")
        count = 0

        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(AUDIO_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    metadata = self.extract_metadata(file_path, file)

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
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            self.log_window.focus_force()
            return

        self.log_window = ctk.CTkToplevel(self)
        self.log_window.title("Historial de Logs")
        self.log_window.geometry("700x400")
        self.apply_popup_style(self.log_window, is_modal=False, owner=self)
        self.log_window.protocol("WM_DELETE_WINDOW", self.close_logs_dialog)

        self.log_textbox = ctk.CTkTextbox(self.log_window, wrap="none")
        self.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        self.log_textbox.insert("1.0", "\n".join(self.log_history))
        self.log_textbox.configure(state="disabled")

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

    def close_logs_dialog(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.destroy()
        self.log_window = None
        self.log_textbox = None

    def show_about_dialog(self):
        self.show_themed_dialog(
            "Acerca de Sonometa",
            "Sonometa v0.04 - Audio Tag Suite\n\n"
            "Herramienta avanzada para la automatización y gestión de metadatos de audio.\n"
            "Integración con API Discogs para vinilos y soporte nativo de ID3, FLAC y MP4.",
            level="info"
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
        self.apply_popup_style(shortcuts_win, is_modal=True, owner=self)

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
            fg_color=self.CORP_COLOR,
            hover_color=self.CORP_HOVER,
            command=shortcuts_win.destroy
        )
        btn_close.pack(fill="x", pady=(12, 0))


if __name__ == "__main__":
    app = App()
    app.mainloop()