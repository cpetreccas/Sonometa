import os
import re
import sys
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

class UiUtils:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.id = self.widget.after(400, self.showtip)

    def maximize_window(window):
        """Maximiza una ventana de CustomTkinter/Tkinter correctamente."""
        try:
            # Previene que CustomTkinter vuelva a estado normal al configurar la barra de título
            if hasattr(window, "_state_before_windows_set_titlebar_color"):
                window._state_before_windows_set_titlebar_color = "zoomed"

            window.state("zoomed")
        except Exception:
            # Fallback multiplataforma si zoomed no está disponible
            window.state("normal")
            w = window.winfo_screenwidth()
            h = window.winfo_screenheight()
            window.geometry(f"{w}x{h}+0+0")

    def leave(self, event=None):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None
        self.hidetip()

    def showtip(self, event=None):
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        label = tk.Label(tw, text=self.text, justify="left",
                         background="#252526", foreground="#E0E0E0",
                         relief="solid", borderwidth=1,
                         font=("Segoe UI", 9))
        label.pack(ipadx=5, ipady=3)

    @staticmethod
    def get_resource_path(relative_path: str) -> str:
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.abspath("."), relative_path)

    def hidetip(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None

    @staticmethod
    def build_discogs_query(artist, title, fallback_text=""):
        parts = [str(artist).strip(), str(title).strip()]
        query = " ".join(part for part in parts if part)
        if not query:
            query = str(fallback_text).strip()
        return re.sub(r"\s+", " ", query).strip()

    @staticmethod
    def load_app_icons(app):
        """Carga los iconos (.png) principales de la ventana, cabecera y botones."""
        # 1. Icono de la aplicación / ventana
        icon_path = UiUtils.get_resource_path("assets/logo_relleno.png")

        # 2. Logo panorámico para el Header Panel
        header_logo_path = UiUtils.get_resource_path("assets/logo_completo.png")

        # 3. Iconos secundarios
        broom_path = UiUtils.get_resource_path("assets/icono_borrar.png")
        white_logo_path = UiUtils.get_resource_path("assets/icono_procesar.png")

        # Cargar icono de aplicación (para iconphoto/iconbitmap)
        logo_pil = None
        if os.path.exists(icon_path):
            logo_pil = Image.open(icon_path)
            img_icon = ImageTk.PhotoImage(logo_pil)
            app.app_icon_photo = img_icon
            try:
                app.wm_iconphoto(True, img_icon)
            except Exception:
                pass

        # Cargar logo de cabecera
        header_logo_pil = None
        if os.path.exists(header_logo_path):
            header_logo_pil = Image.open(header_logo_path)

        broom_icon = None
        if os.path.exists(broom_path):
            icon_broom_img = Image.open(broom_path)
            broom_icon = ctk.CTkImage(
                light_image=icon_broom_img,
                dark_image=icon_broom_img,
                size=(18, 18)
            )

        process_icon = None
        if os.path.exists(white_logo_path):
            icon_white_img = Image.open(white_logo_path)
            process_icon = ctk.CTkImage(
                light_image=icon_white_img,
                dark_image=icon_white_img,
                size=(22, 22)
            )

        # Devolvemos ambas referencias de imágenes de manera separada
        return logo_pil, header_logo_pil, broom_icon, process_icon