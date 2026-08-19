import io
import os
import sys
import ctypes
import threading
import urllib.request
from PIL import Image
import tkinter as tk
from catalog_manager import CatalogManager
import customtkinter as ctk

class DialogManager:
    """Clase especializada en la gestión de ventanas emergentes, diálogos y popups de la aplicación."""

    @staticmethod
    def apply_popup_style(app, win, is_modal=True, owner=None):
        """Aplica estilos comunes, centra la ventana emergente y asigna el icono correctamente."""
        # Se aplica la barra de título oscura
        DialogManager.apply_dark_title_bar(win)

        # Asignación del icono usando iconbitmap nativo
        if hasattr(app, "app_icon_ico") and app.app_icon_ico and os.path.exists(app.app_icon_ico):
            try:
                win.iconbitmap(app.app_icon_ico)
            except Exception:
                pass

        # Centrar respecto a la ventana principal o el propietario
        if owner:
            win.update_idletasks()
            x = owner.winfo_x() + (owner.winfo_width() // 2) - (win.winfo_width() // 2)
            y = owner.winfo_y() + (owner.winfo_height() // 2) - (win.winfo_height() // 2)
            win.geometry(f"+{max(0, x)}+{max(0, y)}")

        # Asegurar visibilidad
        win.deiconify()

        if is_modal:
            win.grab_set()
            win.focus_force()
        else:
            win.lift()
            win.focus()

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
        win.title("Configuración")
        win.geometry("450x180")
        win.resizable(False, False)
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        frame = ctk.CTkFrame(win, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame, text="Opciones de Procesamiento",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Flag de selección manual
        current_val = getattr(app.catalog_manager, "manual_cover_selection", True)
        manual_cover_var = tk.BooleanVar(value=current_val)

        chk_manual_cover = ctk.CTkCheckBox(
            frame,
            text="Seleccionar manualmente la carátula",
            variable=manual_cover_var,
            font=ctk.CTkFont(size=12),
            fg_color=app.CORP_COLOR,
            hover_color=app.CORP_HOVER
        )
        chk_manual_cover.pack(anchor="w", pady=(5, 15))

        def save_settings():
            new_val = manual_cover_var.get()
            app.catalog_manager.manual_cover_selection = new_val
            app.catalog_manager.save_settings()
            logger_inst.info(f"Configuración guardada -> Selección manual de carátula: {new_val}")
            win.destroy()

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", side="bottom")
        ctk.CTkButton(
            btns, text="Cancelar", fg_color="#374151", hover_color="#1F2937",
            command=win.destroy
        ).pack(side="right", padx=(6, 0))
        ctk.CTkButton(
            btns, text="Guardar", fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER,
            command=save_settings
        ).pack(side="right")

    @staticmethod
    def show_logs_dialog(app):
        # Si la ventana ya existe, solo la mostramos y la traemos al frente
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.deiconify()
            app.log_window.lift()
            app.log_window.attributes("-topmost", True)
            app.log_window.after(100, lambda: app.log_window.attributes("-topmost", False))
            app.log_window.focus_force()
            return

        app.log_window = ctk.CTkToplevel(app)
        app.log_window.title("Historial de Logs")
        app.log_window.geometry("700x400")

        # Aplicamos estilo sin bloqueo modal
        DialogManager.apply_popup_style(app, app.log_window, is_modal=False, owner=app)
        app.log_window.protocol("WM_DELETE_WINDOW", lambda: DialogManager.close_logs_dialog(app))

        app.log_textbox = ctk.CTkTextbox(app.log_window, wrap="none")
        app.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        app.log_textbox.insert("1.0", "\n".join(app.log_history))
        app.log_textbox.configure(state="disabled")

        # Forzar el foco y traer al primer plano inmediato en Windows
        app.log_window.lift()
        app.log_window.attributes("-topmost", True)
        # Desactivamos topmost tras 150ms para que no se quede bloqueada de forma molesta sobre otras Apps externas
        app.log_window.after(150, lambda: app.log_window.attributes("-topmost", False) if app.log_window and app.log_window.winfo_exists() else None)
        app.log_window.focus_force()

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

    @staticmethod
    def select_discogs_cover_dialog(app, image_urls):
        """Muestra un diálogo con previsualización de imágenes mediante clics en miniaturas."""
        if not image_urls:
            return None

        # Si solo hay una imagen, no es necesario abrir el diálogo
        if len(image_urls) == 1:
            return image_urls[0]

        selected_url = [None]  # Lista mutable para almacenar el resultado

        win = ctk.CTkToplevel(app)
        win.title("Seleccionar Carátula - Discogs")
        # Cuadro de diálogo más grande
        win.geometry("800x600")
        win.resizable(True, True)

        # Configuración de estilo y asignación del icono de la aplicación a la barra de título
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        frame = ctk.CTkFrame(win, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame,
            text=f"Se encontraron {len(image_urls)} carátulas. Haz clic sobre una para seleccionarla:",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        ).pack(fill="x", pady=(0, 10))

        # Marco con scroll dinámico para la cuadrícula de previsualizaciones
        scroll_frame = ctk.CTkScrollableFrame(frame, fg_color="#111827")
        scroll_frame.pack(fill="both", expand=True, pady=(0, 10))

        # Configurar 3 columnas en la cuadrícula
        scroll_frame.grid_columnconfigure((0, 1, 2), weight=1, uniform="cover_grid")

        def select_and_close(url):
            selected_url[0] = url
            win.destroy()

        def on_cancel():
            selected_url[0] = None
            win.destroy()

        win.protocol("WM_DELETE_WINDOW", on_cancel)

        # Función que descarga la miniatura en segundo plano para no bloquear la interfaz
        def load_thumbnail_async(url, parent_button, img_label):
            try:
                headers = app.discogs_client._get_headers() if hasattr(app, 'discogs_client') else {}
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw_data = resp.read()

                pil_img = Image.open(io.BytesIO(raw_data))
                pil_img.thumbnail((200, 200), Image.Resampling.LANCZOS)

                # Crear CTkImage compatible con customtkinter
                ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                # Actualizar la UI en el hilo principal
                def update_ui():
                    if win.winfo_exists():
                        img_label.configure(image=ctk_img, text="")
                        img_label._image_ref = ctk_img  # Evitar que el recolector de basura elimine la imagen

                win.after(0, update_ui)
            except Exception:
                def update_err():
                    if win.winfo_exists():
                        img_label.configure(text="Error al cargar")
                win.after(0, update_err)

        # Generar las tarjetas de previsualización sin RadioButtons
        for idx, url in enumerate(image_urls):
            row = idx // 3
            col = idx % 3

            card = ctk.CTkFrame(scroll_frame, fg_color="#1F2937", corner_radius=8)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")

            # Etiqueta contenedora para la imagen/loader
            img_label = ctk.CTkLabel(
                card,
                text="Cargando...",
                width=200,
                height=200,
                fg_color="#111827",
                corner_radius=6
            )
            img_label.pack(padx=10, pady=(10, 5))

            # Botón de selección por clic directo
            btn_select = ctk.CTkButton(
                card,
                text=f"Seleccionar #{idx + 1}",
                fg_color=app.CORP_COLOR,
                hover_color=app.CORP_HOVER,
                command=lambda u=url: select_and_close(u)
            )
            btn_select.pack(padx=10, pady=(5, 10), fill="x")

            # Hacer que hacer clic directamente sobre la imagen o la tarjeta también seleccione
            img_label.bind("<Button-1>", lambda e, u=url: select_and_close(u))
            card.bind("<Button-1>", lambda e, u=url: select_and_close(u))

            # Lanzar descarga asíncrona de la imagen
            threading.Thread(target=load_thumbnail_async, args=(url, btn_select, img_label), daemon=True).start()

        # Botón inferior de cancelación
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(fill="x", side="bottom")

        ctk.CTkButton(
            btns, text="Cancelar", fg_color="#374151", hover_color="#1F2937",
            command=on_cancel
        ).pack(side="right")

        app.wait_window(win)
        return selected_url[0]