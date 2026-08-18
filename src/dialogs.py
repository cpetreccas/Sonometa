import os
import sys
import ctypes
import logging as logger
import tkinter as tk
from catalog_manager import CatalogManager
import customtkinter as ctk


class DialogManager:
    """Clase especializada en la gestión de ventanas emergentes, diálogos y popups de la aplicación."""

    @staticmethod
    def apply_popup_style(app, win, is_modal=True, owner=None):
        try:
            ico_path = getattr(app, "ico_path", "")
            if os.path.exists(ico_path):
                win.iconbitmap(ico_path)
            if getattr(app, "app_icon_photo", None) is not None:
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
    def show_settings_dialog(app, logger_inst):
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
        if getattr(app, "discogs_token", None):
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
            app.catalog_manager.save_settings(app.discogs_token)
            if token:
                logger_inst.info("Token de Discogs guardado correctamente.")
            else:
                logger_inst.info("Token de Discogs eliminado.")
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

    @staticmethod
    def show_logs_dialog(app):
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.deiconify()
            app.log_window.lift()
            app.log_window.focus_force()
            return

        app.log_window = ctk.CTkToplevel(app)
        app.log_window.title("Historial de Logs")
        app.log_window.geometry("700x400")
        DialogManager.apply_popup_style(app, app.log_window, is_modal=False, owner=app)
        app.log_window.protocol("WM_DELETE_WINDOW", lambda: DialogManager.close_logs_dialog(app))

        app.log_textbox = ctk.CTkTextbox(app.log_window, wrap="none")
        app.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        app.log_textbox.insert("1.0", "\n".join(app.log_history))
        app.log_textbox.configure(state="disabled")

    @staticmethod
    def close_logs_dialog(app):
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.destroy()
        app.log_window = None
        app.log_textbox = None

    @staticmethod
    def open_catalog_manager(app, catalog_key):
        if catalog_key not in app.catalog_manager.catalog_fields:
            return

        label_name = app.catalog_manager.catalog_labels.get(catalog_key, catalog_key)
        app.logger.info(f"Abriendo gestión de {label_name}.")

        win = ctk.CTkToplevel(app)
        win.title(f"Gestionar {label_name}")
        win.geometry("420x380")
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        frame = ctk.CTkFrame(win)
        frame.pack(fill="both", expand=True, padx=12, pady=12)

        listbox = tk.Listbox(frame, bg="#1E1E1E", fg="#E5E7EB", selectbackground=app.CORP_COLOR, height=10)
        listbox.pack(fill="both", expand=True, pady=(0, 8))

        entry = ctk.CTkEntry(frame, placeholder_text="Nuevo valor o valor modificado")
        entry.pack(fill="x", pady=(0, 8))

        def refresh_listbox():
            listbox.delete(0, "end")
            for item in app.catalog_manager.catalog_values.get(catalog_key, []):
                listbox.insert("end", item)

        def add_value():
            value = CatalogManager.normalize_catalog_text(entry.get())
            if not value:
                app.logger.warning(f"Alta en {label_name} cancelada: valor vacío.")
                DialogManager.show_themed_dialog(app, "Valor no válido", "Debes introducir un valor.", level="warning", parent=win)
                return
            if value in app.catalog_manager.catalog_values[catalog_key]:
                app.logger.warning(f"Alta en {label_name} cancelada: '{value}' ya existe.")
                DialogManager.show_themed_dialog(app, "Duplicado", "Ese valor ya existe.", level="warning", parent=win)
                return

            app.catalog_manager.catalog_values[catalog_key].append(value)
            app.catalog_manager.catalog_values[catalog_key].sort(key=lambda x: x.lower())
            app.catalog_manager.save_catalog_values()

            if hasattr(app, "detail_panel"):
                app.detail_panel.refresh_catalog_comboboxes()

            refresh_listbox()
            entry.delete(0, "end")
            app.logger.info(f"Añadido '{value}' a {label_name}.")

        def update_value():
            selected = listbox.curselection()
            if not selected:
                app.logger.warning(f"Modificación en {label_name} cancelada: sin selección.")
                DialogManager.show_themed_dialog(app, "Selección requerida", "Selecciona un valor para modificar.", level="warning", parent=win)
                return

            new_value = CatalogManager.normalize_catalog_text(entry.get())
            if not new_value:
                app.logger.warning(f"Modificación en {label_name} cancelada: valor vacío.")
                DialogManager.show_themed_dialog(app, "Valor no válido", "Debes introducir el nuevo valor.", level="warning", parent=win)
                return

            idx = selected[0]
            old_value = CatalogManager.normalize_catalog_text(app.catalog_manager.catalog_values[catalog_key][idx])
            if new_value == old_value:
                app.logger.info(f"Modificación en {label_name} omitida: '{old_value}' no cambia.")
                return

            updated_count, merged = app.catalog_manager.rename_catalog_value(catalog_key, old_value, new_value)
            app.catalog_manager.save_catalog_values()

            if hasattr(app, "detail_panel"):
                app.detail_panel.refresh_catalog_comboboxes()

            refresh_listbox()
            entry.delete(0, "end")

            app.logger.info(f"Modificada {label_name}: '{old_value}' -> '{new_value}'. Afectados: {updated_count}.")

            if merged:
                DialogManager.show_themed_dialog(app, "Valores fusionados", f"'{old_value}' se fusionó con '{new_value}'.\nSe actualizaron {updated_count} archivo(s).", level="info", parent=win)
            else:
                DialogManager.show_themed_dialog(app, "Valor actualizado", f"Se reemplazó '{old_value}' por '{new_value}'.\nSe actualizaron {updated_count} archivo(s).", level="info", parent=win)

        def delete_value():
            selected = listbox.curselection()
            if not selected:
                app.logger.warning(f"Eliminación en {label_name} cancelada: sin selección.")
                DialogManager.show_themed_dialog(app, "Selección requerida", "Selecciona un valor para eliminar.", level="warning", parent=win)
                return

            idx = selected[0]
            value = app.catalog_manager.catalog_values[catalog_key][idx]

            affected_count = 0
            col_info = getattr(app.catalog_manager, "get_catalog_column_info", lambda k: None)(catalog_key)
            if col_info:
                _, col_index = col_info
                for row_id in app.tree.get_children():
                    row_values = app.tree.item(row_id, "values")
                    if col_index < len(row_values) and CatalogManager.normalize_catalog_text(row_values[col_index]) == value:
                        affected_count += 1

            confirm_msg = f"¿Eliminar '{value}'?\n\nEsto vaciará el campo en {affected_count} archivo(s)."
            if not DialogManager.show_themed_dialog(app, "Confirmar eliminación", confirm_msg, level="warning", is_confirm=True, parent=win):
                app.logger.info(f"Eliminación en {label_name} cancelada por usuario ('{value}').")
                return

            updated_count = app.catalog_manager.apply_catalog_value_change(catalog_key, value, "")
            app.catalog_manager.catalog_values[catalog_key].pop(idx)
            app.catalog_manager.save_catalog_values()

            if hasattr(app, "detail_panel"):
                app.detail_panel.refresh_catalog_comboboxes()
                app.detail_panel.on_row_select(None)

            refresh_listbox()
            entry.delete(0, "end")

            app.logger.info(f"Eliminado '{value}' de {label_name}. Campos vaciados en {updated_count} archivo(s).")
            DialogManager.show_themed_dialog(app, "Valor eliminado", f"Se eliminó '{value}'.\nSe vació el campo en {updated_count} archivo(s).", level="info", parent=win)

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", pady=(0, 6))

        ctk.CTkButton(btns, text="Añadir", command=add_value, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=(0, 4))
        ctk.CTkButton(btns, text="Modificar", command=update_value, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkButton(btns, text="Eliminar", command=delete_value, fg_color="#B91C1C", hover_color="#991B1B").pack(side="left", expand=True, fill="x", padx=(4, 0))

        ctk.CTkButton(frame, text="Cerrar", command=win.destroy, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER).pack(fill="x")

        refresh_listbox()