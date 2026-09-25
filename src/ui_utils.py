import os
import re
import sys
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import theme

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

    @staticmethod
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
                         background=theme.BG_CARD, foreground=theme.TEXT_MAIN,
                         relief="solid", borderwidth=1,
                         font=(theme.FONT_FAMILY, 9))
        label.pack(ipadx=5, ipady=3)

    @staticmethod
    def copy_files_to_clipboard(paths) -> bool:
        """Pone `paths` en el portapapeles de Windows como ARCHIVOS (formato CF_HDROP,
        el mismo que usa el Explorador al copiar), marcados como "copiar": al pegar en
        una carpeta se crean copias y los originales no se tocan. Solo Windows; en
        otros sistemas devuelve False sin hacer nada."""
        if sys.platform != "win32" or not paths:
            return False

        import ctypes
        from ctypes import wintypes

        CF_HDROP = 15
        GMEM_MOVEABLE = 0x0002
        DROPEFFECT_COPY = 1

        kernel32 = ctypes.windll.kernel32
        user32 = ctypes.windll.user32
        kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
        kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
        user32.OpenClipboard.argtypes = [wintypes.HWND]
        user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        user32.SetClipboardData.restype = wintypes.HANDLE
        user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
        user32.RegisterClipboardFormatW.restype = wintypes.UINT

        def _global_bytes(data):
            handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
            if not handle:
                return None
            ptr = kernel32.GlobalLock(handle)
            ctypes.memmove(ptr, data, len(data))
            kernel32.GlobalUnlock(handle)
            return handle

        # DROPFILES: pFiles (offset a la lista), pt (x, y), fNC, fWide=1 (UTF-16);
        # después, las rutas separadas por \0 y terminadas en doble \0.
        header = ctypes.c_uint32(20).value.to_bytes(4, "little") + bytes(12) + (1).to_bytes(4, "little")
        file_list = ("\0".join(os.path.abspath(p) for p in paths) + "\0\0").encode("utf-16-le")
        hdrop = _global_bytes(header + file_list)
        effect = _global_bytes(DROPEFFECT_COPY.to_bytes(4, "little"))
        if not hdrop or not effect:
            return False

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(hdrop)
            kernel32.GlobalFree(effect)
            return False
        try:
            user32.EmptyClipboard()
            # Tras SetClipboardData el sistema es dueño de la memoria: no liberarla.
            ok = bool(user32.SetClipboardData(CF_HDROP, hdrop))
            if not ok:
                kernel32.GlobalFree(hdrop)
            preferred = user32.RegisterClipboardFormatW("Preferred DropEffect")
            if not user32.SetClipboardData(preferred, effect):
                kernel32.GlobalFree(effect)
            return ok
        finally:
            user32.CloseClipboard()

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
    def _word_boundary_index(text, index, direction):
        """Calcula el índice del siguiente/anterior límite de palabra (estilo Ctrl+Flecha)."""
        length = len(text)
        if direction > 0:
            i = index
            while i < length and text[i].isspace():
                i += 1
            while i < length and not text[i].isspace():
                i += 1
            return i

        i = index
        while i > 0 and text[i - 1].isspace():
            i -= 1
        while i > 0 and not text[i - 1].isspace():
            i -= 1
        return i

    @staticmethod
    def extend_entry_selection(entry, target_index):
        """Extiende o colapsa la selección de texto de un Entry hacia target_index.

        El binding nativo de Tk para Shift-Home/End/Flechas usa 'selection adjust', que ajusta
        el límite de selección más cercano al nuevo índice; si ese límite ya coincide con el
        índice objetivo (p. ej. Ctrl+Shift+Home justo después de un Ctrl+Shift+End que dejó el
        inicio de la selección en 0), no hace nada y la selección completa queda visualmente
        intacta. Aquí se replica el modelo estándar de "ancla + cursor" de un editor de texto
        para que la selección colapse correctamente cuando el cursor vuelve al punto de anclaje.
        """
        try:
            target = entry.index(target_index)
            if entry.selection_present():
                sel_start = entry.index("sel.first")
                sel_end = entry.index("sel.last")
                cur = entry.index("insert")
                anchor = sel_end if cur <= sel_start else sel_start
            else:
                anchor = entry.index("insert")

            entry.icursor(target)
            if anchor == target:
                entry.selection_clear()
            else:
                entry.selection_range(min(anchor, target), max(anchor, target))
        except Exception:
            pass
        return "break"

    @staticmethod
    def bind_entry_selection_fix(entry):
        """Corrige Shift-Home/End y Ctrl-Shift-Izquierda/Derecha en un tk.Entry para que la
        selección colapse correctamente al volver al punto de anclaje (ver extend_entry_selection).
        Debe aplicarse sobre el Entry real; para CTkEntry usar su atributo interno `_entry`.
        """
        entry.bind("<Shift-Home>", lambda e: UiUtils.extend_entry_selection(entry, 0))
        entry.bind("<Shift-End>", lambda e: UiUtils.extend_entry_selection(entry, "end"))
        entry.bind(
            "<Control-Shift-Right>",
            lambda e: UiUtils.extend_entry_selection(
                entry, UiUtils._word_boundary_index(entry.get(), entry.index("insert"), 1)
            )
        )
        entry.bind(
            "<Control-Shift-Left>",
            lambda e: UiUtils.extend_entry_selection(
                entry, UiUtils._word_boundary_index(entry.get(), entry.index("insert"), -1)
            )
        )

    @staticmethod
    def build_discogs_query(artist, title, fallback_text=""):
        parts = [str(artist).strip(), str(title).strip()]
        query = " ".join(part for part in parts if part)
        if not query:
            query = str(fallback_text).strip()
        return re.sub(r"\s+", " ", query).strip()

    @staticmethod
    def load_app_icons(app):
        """Carga los iconos (.ico y .png) principales de la ventana, cabecera y botones."""
        import ctypes

        # Forzar a Windows a agrupar e identificar el icono en la barra de tareas
        try:
            myappid = 'sonometa.audiotagsuite.app.2.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

        # 1. Icono nativo de ventana para Windows (.ico) y fallback a .png
        ico_path = UiUtils.get_resource_path("assets/logo_relleno.ico")
        png_icon_path = UiUtils.get_resource_path("assets/logo_relleno.png")

        # Configurar icono nativo en la ventana (.ico)
        if os.path.exists(ico_path):
            try:
                app.iconbitmap(ico_path)
            except Exception:
                pass

        # 2. Logo panorámico para el Header Panel
        header_logo_path = UiUtils.get_resource_path("assets/logo_completo.png")

        # 3. Iconos secundarios
        broom_path = UiUtils.get_resource_path("assets/icono_borrar.png")
        white_logo_path = UiUtils.get_resource_path("assets/icono_procesar.png")

        # Cargar icono de aplicación (para iconphoto/referencia PIL)
        logo_pil = None
        target_icon_path = png_icon_path if os.path.exists(png_icon_path) else ico_path

        if os.path.exists(target_icon_path):
            with Image.open(target_icon_path) as icon_img:
                logo_pil = icon_img.copy()
            img_icon = ImageTk.PhotoImage(logo_pil)
            app.app_icon_photo = img_icon
            try:
                app.wm_iconphoto(True, img_icon)
            except Exception:
                pass

        # Cargar logo de cabecera
        header_logo_pil = None
        if os.path.exists(header_logo_path):
            with Image.open(header_logo_path) as header_img:
                header_logo_pil = header_img.copy()

        broom_icon = None
        if os.path.exists(broom_path):
            with Image.open(broom_path) as broom_img:
                icon_broom_img = broom_img.copy()
            broom_icon = ctk.CTkImage(
                light_image=icon_broom_img,
                dark_image=icon_broom_img,
                size=(18, 18)
            )

        process_icon = None
        if os.path.exists(white_logo_path):
            with Image.open(white_logo_path) as process_img:
                icon_white_img = process_img.copy()
            process_icon = ctk.CTkImage(
                light_image=icon_white_img,
                dark_image=icon_white_img,
                size=(22, 22)
            )

        # Devolvemos ambas referencias de imágenes de manera separada
        return logo_pil, header_logo_pil, broom_icon, process_icon