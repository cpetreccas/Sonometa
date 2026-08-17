import os
import sys
import ctypes
import tkinter as tk
import customtkinter as ctk


class DialogManager:
    """Clase especializada en la gestión de ventanas emergentes, diálogos y popups de la aplicación."""

    @staticmethod
    def apply_popup_style(app, win, is_modal=True, owner=None):
        try:
            if os.path.exists(app.ico_path):
                win.iconbitmap(app.ico_path)
            if app.app_icon_photo is not None:
                win.wm_iconphoto(True, app.app_icon_photo)
        except Exception:
            pass

        win.configure(fg_color="#181818")
        owner_window = owner if owner is not None else app
        win.transient(owner_window)

        try:
            win.update_idletasks()
            DialogManager.center_popup_on_screen(win)
            DialogManager.apply_dark_title_bar(win)
            win.bind("<Map>", lambda _e, w=win: DialogManager.apply_dark_title_bar(w), add="+")
            win.after(80, lambda w=win: DialogManager.apply_dark_title_bar(w))
            win.after(220, lambda w=win: DialogManager.apply_dark_title_bar(w))
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
        if sys.platform != "win32" or not win.winfo_exists():
            return
        try:
            hwnd = win.winfo_id()
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    @staticmethod
    def show_themed_dialog(app, title, message, level="info", is_confirm=False, parent=None):
        host = parent if parent is not None else app
        dialog = ctk.CTkToplevel(host)
        dialog.title(title)
        dialog.geometry("460x210")
        dialog.resizable(False, False)
        DialogManager.apply_popup_style(app, dialog, is_modal=True, owner=host)

        frame = ctk.CTkFrame(dialog, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        icon_text = "!" if level == "warning" else ("x" if level == "error" else "i")

        lbl_icon = ctk.CTkLabel(
            frame,
            text=icon_text,
            width=26,
            height=26,
            corner_radius=13,
            fg_color=app.CORP_COLOR,
            text_color="white",
            font=ctk.CTkFont(family="Inter", size=13, weight="bold")
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
                btns, text="Cancelar", command=cancel,
                fg_color="#374151", hover_color="#1F2937"
            ).pack(side="right", padx=(6, 0))

        ctk.CTkButton(
            btns, text="Aceptar", command=accept,
            fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER
        ).pack(side="right")

        dialog.wait_window()
        return result["value"]

    @staticmethod
    def show_about_dialog(app):
        DialogManager.show_themed_dialog(
            app,
            "Acerca de Sonometa",
            "Sonometa v0.06 - Audio Tag Suite\n\n"
            "Herramienta avanzada para la automatización y gestión de metadatos de audio.\n"
            "Integración con API Discogs para vinilos y soporte nativo de ID3, FLAC y MP4.",
            level="info"
        )

    @staticmethod
    def show_keyboard_shortcuts_dialog(app):
        shortcuts_win = ctk.CTkToplevel(app)
        shortcuts_win.title("Atajos de Teclado")
        shortcuts_win.geometry("500x350")
        DialogManager.apply_popup_style(app, shortcuts_win, is_modal=True, owner=app)

        frame_content = ctk.CTkFrame(shortcuts_win)
        frame_content.pack(fill="both", expand=True, padx=15, pady=15)

        lbl_title = ctk.CTkLabel(
            frame_content,
            text="Atajos de Teclado Disponibles",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        lbl_title.pack(fill="x", pady=(0, 12))

        frame_scroll = ctk.CTkScrollableFrame(frame_content)
        frame_scroll.pack(fill="both", expand=True)

        shortcuts = [
            ("Ctrl+O", "Seleccionar carpeta"),
            ("F5", "Actualizar lista de archivos"),
            ("Ctrl+A", "Seleccionar todo"),
            ("Ctrl+F", "Mostrar/Ocultar barra de búsqueda"),
            ("Ctrl+Q", "Cerrar aplicación"),
            ("Doble-clic", "Editar celda en tabla"),
            ("Enter", "Guardar edición de celda"),
            ("Esc", "Cerrar búsqueda activa"),
        ]

        for shortcut, description in shortcuts:
            frame_shortcut = ctk.CTkFrame(frame_scroll)
            frame_shortcut.pack(fill="x", padx=0, pady=6)

            lbl_key = ctk.CTkLabel(
                frame_shortcut,
                text=shortcut,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=app.CORP_COLOR,
                width=80,
                anchor="w"
            )
            lbl_key.pack(side="left", padx=(0, 15))

            lbl_desc = ctk.CTkLabel(
                frame_shortcut, text=description,
                font=ctk.CTkFont(size=10), anchor="w"
            )
            lbl_desc.pack(side="left", fill="x", expand=True)

        btn_close = ctk.CTkButton(
            frame_content,
            text="Cerrar",
            height=32,
            fg_color=app.CORP_COLOR,
            hover_color=app.CORP_HOVER,
            command=shortcuts_win.destroy
        )
        btn_close.pack(fill="x", pady=(12, 0))

    @staticmethod
    def show_settings_dialog(app, logger):
        win = ctk.CTkToplevel(app)
        win.title("Configuración - Token Discogs")
        win.geometry("500x260")
        win.resizable(False, False)
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        frame = ctk.CTkFrame(win, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame, text="Token de Discogs",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(
            frame,
            text=(
                "El token se usa para buscar carátulas de vinilos.\n"
                "Puedes obtenerlo en discogs.com → Ajustes → Desarrolladores."
            ),
            font=ctk.CTkFont(size=11), text_color="#9CA3AF",
            anchor="w", justify="left"
        ).pack(fill="x", pady=(0, 10))

        entry_token = ctk.CTkEntry(
            frame, placeholder_text="Pega aquí tu token de Discogs",
            height=34, font=ctk.CTkFont(size=12), show="*"
        )
        entry_token.pack(fill="x", pady=(0, 4))
        if app.discogs_token:
            entry_token.insert(0, app.discogs_token)

        show_var = tk.BooleanVar(value=False)
        chk = ctk.CTkCheckBox(
            frame, text="Mostrar token", variable=show_var,
            command=lambda: entry_token.configure(show="" if show_var.get() else "*"),
            font=ctk.CTkFont(size=11)
        )
        chk.pack(anchor="w", pady=(0, 12))

        def save_token():
            token = entry_token.get().strip()
            app.discogs_token = token
            app._save_settings()
            if token:
                logger.info("Token de Discogs guardado correctamente.")
            else:
                logger.info("Token de Discogs eliminado.")
            win.destroy()

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", side="bottom")
        ctk.CTkButton(
            btns, text="Cancelar", fg_color="#374151", hover_color="#1F2937",
            command=win.destroy
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btns, text="Guardar", fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER,
            command=save_token
        ).pack(side="right")