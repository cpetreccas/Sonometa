# ui_utils.py
import tkinter as tk
import sys
import os

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