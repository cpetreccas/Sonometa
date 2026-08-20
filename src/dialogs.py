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


class MultiCoverSelectionDialog(ctk.CTkToplevel):
    """Ventana consolidada que muestra todas las canciones pendientes en filas con sus opciones en columnas."""

    def __init__(self, parent, pending_reviews):
        super().__init__(parent)
        self.title("Selección de Carátulas - Sonometa")

        self.geometry("900x620")
        self.minsize(820, 500)

        self.app = parent
        self.pending_reviews = pending_reviews
        self.selections = {}
        self.cards_ui = {}

        for item in self.pending_reviews:
            self.selections[item["row_id"]] = item["images"][0] if item["images"] else None

        self._setup_ui()
        self._load_images_async()

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=900, height=620)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E")
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Revisión de Carátulas Encontradas",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#F3F4F6"
        )
        lbl_title.pack(anchor="w", padx=5, pady=(0, 2))

        lbl_subtitle = ctk.CTkLabel(
            main_frame,
            text=f"Revisando {len(self.pending_reviews)} elemento(s). Haz clic directamente sobre la portada deseada para seleccionarla.",
            text_color="#9CA3AF"
        )
        lbl_subtitle.pack(anchor="w", padx=5, pady=(0, 8))

        self.scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color="#181818")
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 10))

        corp_color = getattr(self.app, "CORP_COLOR", "#6B21A8")

        def _forward_scroll(event):
            if sys.platform == "darwin":
                delta = -event.delta
            elif sys.platform == "win32":
                delta = -int(event.delta / 120)
            else:
                delta = 1 if event.num == 5 else -1

            self.scroll_frame._parent_canvas.yview_scroll(delta * 20, "units")
            return "break"

        for item in self.pending_reviews:
            row_id = item["row_id"]
            filename = item["filename"]
            images = item["images"] + ["__NO_COVER__"]

            self.cards_ui[row_id] = {}

            card = ctk.CTkFrame(self.scroll_frame, fg_color="#262626", corner_radius=8)
            card.pack(fill="x", pady=6, padx=6, ipady=4)

            lbl_file = ctk.CTkLabel(
                card,
                text=f"🎵 {filename}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                text_color="#E5E7EB"
            )
            lbl_file.pack(fill="x", padx=12, pady=(6, 4))

            covers_container = ctk.CTkScrollableFrame(
                card,
                fg_color="transparent",
                orientation="horizontal",
                height=170
            )
            covers_container.pack(fill="x", padx=6, pady=(0, 6))

            if sys.platform in ("win32", "darwin"):
                covers_container._parent_canvas.bind("<MouseWheel>", _forward_scroll)
            else:
                covers_container._parent_canvas.bind("<Button-4>", _forward_scroll)
                covers_container._parent_canvas.bind("<Button-5>", _forward_scroll)

            selected_url = self.selections.get(row_id)

            for img_idx, img_url in enumerate(images):
                is_selected = (img_url == selected_url)
                if img_url == "__NO_COVER__" and selected_url == "__NO_COVER__":
                    is_selected = True

                col_frame = ctk.CTkFrame(
                    covers_container,
                    width=130,
                    height=155,
                    fg_color=corp_color if is_selected else "#1E1E1E",
                    border_color=corp_color,
                    border_width=2 if is_selected else 0,
                    corner_radius=8,
                    cursor="hand2"
                )
                col_frame.pack(side="left", padx=4, pady=2)
                col_frame.pack_propagate(False)

                img_label = ctk.CTkLabel(
                    col_frame,
                    text="Cargando...",
                    width=115,
                    height=115,
                    fg_color="#141414",
                    corner_radius=6,
                    cursor="hand2"
                )
                img_label.pack(padx=5, pady=(5, 2))
                img_label.image_url = img_url

                lbl_num = ctk.CTkLabel(
                    col_frame,
                    text=f"Opción #{img_idx + 1}",
                    font=ctk.CTkFont(size=10, weight="bold" if is_selected else "normal"),
                    text_color="#FFFFFF" if is_selected else "#9CA3AF",
                    cursor="hand2"
                )
                lbl_num.pack(padx=4, pady=(0, 3))

                if img_url == "__NO_COVER__":
                    img_label.configure(text="🚫\nSin carátula", text_color="#EF4444")
                    lbl_num.configure(text="Ninguna")

                self.cards_ui[row_id][img_url] = {
                    "frame": col_frame,
                    "lbl_num": lbl_num,
                    "img_label": img_label
                }

                for widget in (col_frame, img_label, lbl_num):
                    widget.bind("<Button-1>", lambda e, r=row_id, u=img_url: self._select_card(r, u))
                    widget.bind("<Enter>", lambda e, r=row_id, u=img_url: self._on_card_hover(r, u, True))
                    widget.bind("<Leave>", lambda e, r=row_id, u=img_url: self._on_card_hover(r, u, False))

                    if sys.platform in ("win32", "darwin"):
                        widget.bind("<MouseWheel>", _forward_scroll)
                    else:
                        widget.bind("<Button-4>", _forward_scroll)
                        widget.bind("<Button-5>", _forward_scroll)

        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        process_icon = getattr(self.app, "process_icon", None)

        self.btn_confirm = ctk.CTkButton(
            btn_bar,
            text="Procesando...",
            image=process_icon,
            compound="left",
            state="disabled",
            text_color="#9CA3AF",
            fg_color=getattr(self.app, "CORP_COLOR", "#6B21A8"),
            hover_color=getattr(self.app, "CORP_HOVER", "#581C87"),
            command=self._on_confirm
        )
        self.btn_confirm.pack(side="right", padx=(8, 0))

        self.btn_omit = ctk.CTkButton(
            btn_bar,
            text="Omitir Todas",
            fg_color="transparent",
            border_width=1,
            border_color="#EF4444",
            text_color="#EF4444",
            hover_color="#7F1D1D",
            command=self._on_cancel
        )
        self.btn_omit.pack(side="right")

    def _select_card(self, row_id, selected_url):
        self.selections[row_id] = selected_url
        corp_color = getattr(self.app, "CORP_COLOR", "#6B21A8")

        for url, ui_item in self.cards_ui[row_id].items():
            frame = ui_item["frame"]
            lbl_num = ui_item["lbl_num"]

            if url == selected_url:
                frame.configure(fg_color=corp_color, border_width=2)
                lbl_num.configure(text_color="#FFFFFF", font=ctk.CTkFont(size=10, weight="bold"))
            else:
                frame.configure(fg_color="#1E1E1E", border_width=0)
                lbl_num.configure(text_color="#9CA3AF", font=ctk.CTkFont(size=10, weight="normal"))

    def _on_card_hover(self, row_id, url, is_hovering):
        if self.selections.get(row_id) == url:
            return

        ui_item = self.cards_ui[row_id].get(url)
        if not ui_item:
            return

        frame = ui_item["frame"]
        if is_hovering:
            frame.configure(fg_color="#333333")
        else:
            frame.configure(fg_color="#1E1E1E")

    def _load_images_async(self):
        def _worker():
            for row_id, urls_dict in self.cards_ui.items():
                for url, ui_item in urls_dict.items():
                    if url == "__NO_COVER__":
                        continue

                    widget = ui_item.get("img_label")
                    if not widget:
                        continue

                    try:
                        raw_data = None
                        if hasattr(self.app, "discogs_client") and hasattr(self.app.discogs_client, "download_image_bytes"):
                            raw_data = self.app.discogs_client.download_image_bytes(url)
                        else:
                            req = urllib.request.Request(url, headers={"User-Agent": "Sonometa/1.0"})
                            with urllib.request.urlopen(req, timeout=5) as resp:
                                raw_data = resp.read()

                        if raw_data:
                            pil_img = Image.open(io.BytesIO(raw_data))
                            pil_img.thumbnail((110, 110), Image.Resampling.LANCZOS)
                            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)

                            def _update_ui(w=widget, img=ctk_img):
                                try:
                                    if w.winfo_exists():
                                        w.configure(image=img, text="")
                                except Exception:
                                    pass

                            self.after(0, _update_ui)
                    except Exception:
                        def _update_error(w=widget):
                            try:
                                if w.winfo_exists():
                                    w.configure(text="Error")
                            except Exception:
                                pass
                        self.after(0, _update_error)

            self.after(0, self._on_loading_finished)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_loading_finished(self):
        if self.btn_confirm.winfo_exists():
            process_icon = getattr(self.app, "process_icon", None)
            self.btn_confirm.configure(
                state="normal",
                text="Confirmar Selección",
                text_color="#FFFFFF",
                image=process_icon,
                compound="left"
            )

    def _on_confirm(self):
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.selections = {item["row_id"]: None for item in self.pending_reviews}
        self.grab_release()
        self.destroy()


class DialogManager:
    """Clase especializada en la gestión de ventanas emergentes, diálogos y popups de la aplicación."""

    @staticmethod
    def apply_popup_style(app, win, is_modal=True, owner=None):
        DialogManager.apply_dark_title_bar(win)

        if hasattr(app, "app_icon_ico") and app.app_icon_ico and os.path.exists(app.app_icon_ico):
            try:
                win.iconbitmap(app.app_icon_ico)
            except Exception:
                pass

        win.deiconify()

        if is_modal:
            win.grab_set()
            win.focus_force()
        else:
            win.lift()
            win.focus()

    @staticmethod
    def center_popup_on_screen(win):
        win.update_idletasks()
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
        DialogManager.center_popup_on_parent(dialog, host, width=460, height=210)
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
            "Sonometa v0.08 - Audio Tag Suite\n\n"
            "Herramienta avanzada para la automatización y gestión de metadatos de audio.\n"
            "Integración con API Discogs para vinilos y soporte nativo de ID3, FLAC y MP4.",
            level="info"
        )

    @staticmethod
    def show_keyboard_shortcuts_dialog(app):
        shortcuts_win = ctk.CTkToplevel(app)
        shortcuts_win.title("Atajos de Teclado")
        shortcuts_win.geometry("500x350")
        DialogManager.center_popup_on_parent(shortcuts_win, app, width=500, height=350)
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
        DialogManager.center_popup_on_parent(win, app, width=450, height=180)
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        frame = ctk.CTkFrame(win, fg_color="#1E1E1E")
        frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            frame, text="Opciones de Procesamiento",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w"
        ).pack(fill="x", pady=(0, 10))

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

        DialogManager.center_popup_on_parent(app.log_window, app, width=700, height=400)
        DialogManager.apply_popup_style(app, app.log_window, is_modal=False, owner=app)
        app.log_window.protocol("WM_DELETE_WINDOW", lambda: DialogManager.close_logs_dialog(app))

        app.log_textbox = ctk.CTkTextbox(app.log_window, wrap="none")
        app.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        app.log_textbox.insert("1.0", "\n".join(app.log_history))
        app.log_textbox.configure(state="disabled")

        app.log_window.lift()
        app.log_window.attributes("-topmost", True)
        app.log_window.after(150, lambda: app.log_window.attributes("-topmost", False) if app.log_window and app.log_window.winfo_exists() else None)
        app.log_window.focus_force()

    @staticmethod
    def close_logs_dialog(app):
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.destroy()
        app.log_window = None
        app.log_textbox = None

    @staticmethod
    def open_unified_catalog_manager(app):
        """Abre el Gestor Unificado de Catálogos con soporte para múltiples selecciones, edición modal y relaciones."""
        app.logger.info("Abriendo gestión unificada de catálogos con relaciones.")

        win = ctk.CTkToplevel(app)
        win.title("Gestor Unificado de Catálogos")
        win.geometry("820x600")
        DialogManager.center_popup_on_parent(win, app, width=820, height=600)
        DialogManager.apply_popup_style(app, win, is_modal=True, owner=app)

        font_btn = ctk.CTkFont(size=12, weight="bold")

        lbl_header = ctk.CTkLabel(
            win,
            text="Gestión de Catálogos y Relaciones",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#F3F4F6"
        )
        lbl_header.pack(anchor="w", padx=16, pady=(16, 4))

        lbl_sub = ctk.CTkLabel(
            win,
            text="Añade, edita o elimina valores y asigna jerarquías entre ellos.",
            text_color="#9CA3AF"
        )
        lbl_sub.pack(anchor="w", padx=16, pady=(0, 4))

        tabview = ctk.CTkTabview(win)
        tabview.pack(fill="both", expand=True, padx=16, pady=(4, 16))

        def prompt_for_value(title, prompt_text, default_value=""):
            result = [None]
            dlg = ctk.CTkToplevel(win)
            dlg.title(title)
            dlg.geometry("400x150")
            DialogManager.center_popup_on_parent(dlg, win, width=400, height=150)
            DialogManager.apply_popup_style(app, dlg, is_modal=True, owner=win)

            ctk.CTkLabel(dlg, text=prompt_text, text_color="#E5E7EB", font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))

            entry = ctk.CTkEntry(dlg, width=320)
            entry.pack(pady=5)
            if default_value:
                entry.insert(0, default_value)

            entry.focus()

            def on_submit(event=None):
                result[0] = entry.get()
                dlg.destroy()

            entry.bind("<Return>", on_submit)

            btn = ctk.CTkButton(dlg, text="Aceptar", font=font_btn, command=on_submit, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER)
            btn.pack(pady=(10, 15))

            dlg.wait_window()
            return result[0]

        def refresh_listbox(k, lb):
            lb.delete(0, "end")
            for item in app.catalog_manager.catalog_values.get(k, []):
                lb.insert("end", item)

        def add_value(k, lb, lname):
            raw_val = prompt_for_value("Añadir Valor", f"Introduce el nuevo valor para {lname}:")
            if raw_val is None:
                return

            value = CatalogManager.normalize_catalog_text(raw_val)
            if not value:
                DialogManager.show_themed_dialog(app, "Valor no válido", "Debes introducir un valor.", level="warning", parent=win)
                return
            if value in app.catalog_manager.catalog_values[k]:
                DialogManager.show_themed_dialog(app, "Duplicado", "Ese valor ya existe.", level="warning", parent=win)
                return

            app.catalog_manager.add_catalog_value(k, value, persist=True, is_user_action=True)
            refresh_listbox(k, lb)

        def update_value(k, lb, lname):
            selected = lb.curselection()
            if not selected:
                DialogManager.show_themed_dialog(app, "Selección requerida", "Selecciona al menos un valor para modificar.", level="warning", parent=win)
                return

            old_values = [CatalogManager.normalize_catalog_text(app.catalog_manager.catalog_values[k][idx]) for idx in selected]

            default_val = old_values[0] if len(old_values) == 1 else ""
            prompt_msg = f"Reemplazar {len(old_values)} elemento(s) por:" if len(old_values) > 1 else f"Modificar '{default_val}':"

            raw_val = prompt_for_value("Modificar Valor", prompt_msg, default_val)
            if raw_val is None:
                return

            new_value = CatalogManager.normalize_catalog_text(raw_val)
            if not new_value:
                DialogManager.show_themed_dialog(app, "Valor no válido", "Debes introducir el nuevo valor.", level="warning", parent=win)
                return

            updated_count_total = 0
            for old_value in old_values:
                if new_value == old_value:
                    continue

                if k in ("Album", "Genre"):
                    child_key = "Genre" if k == "Album" else "Publisher"
                    if k == "Album":
                        old_rels = app.catalog_manager.album_genres.get(old_value, [])
                        new_rels = app.catalog_manager.album_genres.get(new_value, [])
                    else:
                        old_rels = app.catalog_manager.genre_publishers.get(old_value, [])
                        new_rels = app.catalog_manager.genre_publishers.get(new_value, [])

                    if not old_rels or not new_rels:
                        merged = []
                    else:
                        c_old = [] if old_rels == ["__NONE__"] else old_rels
                        c_new = [] if new_rels == ["__NONE__"] else new_rels
                        merged = list(set(c_old + c_new))

                        if not merged:
                            merged = ["__NONE__"]
                        elif len(merged) == len(app.catalog_manager.catalog_values.get(child_key, [])):
                            merged = []

                    if k == "Album":
                        app.catalog_manager.set_album_genres(new_value, merged)
                        if old_value in app.catalog_manager.album_genres:
                            del app.catalog_manager.album_genres[old_value]
                    else:
                        app.catalog_manager.set_genre_publishers(new_value, merged)
                        if old_value in app.catalog_manager.genre_publishers:
                            del app.catalog_manager.genre_publishers[old_value]

                updated_count, _ = app.catalog_manager.rename_catalog_value(k, old_value, new_value)
                updated_count_total += updated_count

            refresh_listbox(k, lb)
            DialogManager.show_themed_dialog(
                app,
                "Actualización completa",
                f"Se modificaron {len(old_values)} registro(s) hacia '{new_value}'.\nAfectados: {updated_count_total} archivo(s).",
                level="info",
                parent=win
            )

        def delete_value(k, lb, lname):
            selected = lb.curselection()
            if not selected:
                DialogManager.show_themed_dialog(app, "Selección requerida", "Selecciona al menos un valor para eliminar.", level="warning", parent=win)
                return

            values_to_delete = [app.catalog_manager.catalog_values[k][idx] for idx in selected]

            affected_count = 0
            col_info = CatalogManager.get_catalog_column_info(k)
            if col_info:
                _, col_index = col_info
                for row_id in app.tree.get_children():
                    row_values = app.tree.item(row_id, "values")
                    if col_index < len(row_values) and CatalogManager.normalize_catalog_text(row_values[col_index]) in values_to_delete:
                        affected_count += 1

            msg = f"¿Eliminar {len(values_to_delete)} elemento(s)?\n\nVaciará el campo en {affected_count} archivo(s)."
            if not DialogManager.show_themed_dialog(app, "Confirmar eliminación", msg, level="warning", is_confirm=True, parent=win):
                return

            for value in values_to_delete:
                app.catalog_manager.apply_catalog_value_change(k, value, "")
                if value in app.catalog_manager.catalog_values[k]:
                    app.catalog_manager.catalog_values[k].remove(value)

            app.catalog_manager.save_catalog_values()

            if hasattr(app, "detail_panel"):
                app.detail_panel.refresh_catalog_comboboxes()
                app.detail_panel.on_row_select(None)

            refresh_listbox(k, lb)
            DialogManager.show_themed_dialog(app, "Valores eliminados", f"Se eliminaron {len(values_to_delete)} registro(s).", level="info", parent=win)

        ordered_keys = ["Album", "Genre", "Publisher"]

        for catalog_key in ordered_keys:
            if catalog_key not in app.catalog_manager.catalog_fields:
                continue

            label_name = app.catalog_manager.catalog_labels.get(catalog_key, catalog_key)
            tab = tabview.add(label_name)

            content_frame = ctk.CTkFrame(tab, fg_color="transparent")
            content_frame.pack(fill="both", expand=True)

            left_panel = ctk.CTkFrame(content_frame, fg_color="transparent")
            left_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))

            listbox_frame = ctk.CTkFrame(left_panel, fg_color="#1E1E1E", corner_radius=6)
            listbox_frame.pack(fill="both", expand=True, pady=(0, 15))

            lb = tk.Listbox(
                listbox_frame,
                bg="#1E1E1E",
                fg="#E5E7EB",
                selectbackground=app.CORP_COLOR,
                height=14,
                selectmode=tk.EXTENDED,
                borderwidth=0,
                highlightthickness=0,
                font=("Arial", 11)
            )
            lb.pack(fill="both", expand=True, padx=8, pady=8)

            btns = ctk.CTkFrame(left_panel, fg_color="transparent")
            btns.pack(fill="x", pady=(0, 5))

            ctk.CTkButton(btns, text="Añadir", font=font_btn, command=lambda k=catalog_key, l=lb, ln=label_name: add_value(k, l, ln), fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=(0, 2))
            ctk.CTkButton(btns, text="Modificar", font=font_btn, command=lambda k=catalog_key, l=lb, ln=label_name: update_value(k, l, ln), fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER).pack(side="left", expand=True, fill="x", padx=2)

            # Botón Eliminar: Transparente, borde rojo, texto blanco y en negrita
            ctk.CTkButton(
                btns,
                text="Eliminar",
                font=font_btn,
                command=lambda k=catalog_key, l=lb, ln=label_name: delete_value(k, l, ln),
                fg_color="transparent",
                border_width=1,
                border_color="#EF4444",
                text_color="#FFFFFF",
                hover_color="#7F1D1D"
            ).pack(side="left", expand=True, fill="x", padx=(2, 0))

            refresh_listbox(catalog_key, lb)

            if catalog_key in ("Album", "Genre"):
                right_panel = ctk.CTkFrame(content_frame, fg_color="#181818", corner_radius=8)
                right_panel.pack(side="right", fill="both", expand=True, padx=(6, 0))

                rel_title = "Géneros permitidos para los elementos seleccionados:" if catalog_key == "Album" else "Etiquetas permitidas para los elementos seleccionados:"
                ctk.CTkLabel(right_panel, text=rel_title, font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(fill="x", padx=12, pady=(12, 4))

                check_vars = {}
                btn_rel_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
                btn_rel_frame.pack(fill="x", padx=12, pady=(0, 4))

                ctk.CTkButton(btn_rel_frame, text="Sel. Todo", font=font_btn, height=24, fg_color="#374151", hover_color="#1F2937", command=lambda cv=check_vars: [v.set(True) for v in cv.values()]).pack(side="left", expand=True, fill="x", padx=(0, 2))
                ctk.CTkButton(btn_rel_frame, text="Desel. Todo", font=font_btn, height=24, fg_color="#374151", hover_color="#1F2937", command=lambda cv=check_vars: [v.set(False) for v in cv.values()]).pack(side="left", expand=True, fill="x", padx=(2, 0))

                scroll_rel = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
                scroll_rel.pack(fill="both", expand=True, padx=8, pady=4)

                def load_relations(event=None, k=catalog_key, listbox=lb, scroll=scroll_rel, cvars=check_vars):
                    for w in scroll.winfo_children():
                        w.destroy()
                    cvars.clear()

                    sel = listbox.curselection()
                    if not sel:
                        ctk.CTkLabel(scroll, text="Selecciona al menos un registro a la izquierda", text_color="gray", font=ctk.CTkFont(size=11)).pack(pady=20)
                        return

                    parent_val = app.catalog_manager.catalog_values[k][sel[0]]
                    child_key = "Genre" if k == "Album" else "Publisher"
                    all_children = app.catalog_manager.catalog_values.get(child_key, [])

                    if k == "Album":
                        assigned = app.catalog_manager.album_genres.get(parent_val, [])
                    else:
                        assigned = app.catalog_manager.genre_publishers.get(parent_val, [])

                    for child in all_children:
                        is_checked = False
                        if assigned == ["__NONE__"]:
                            is_checked = False
                        elif child in assigned or len(assigned) == 0:
                            is_checked = True

                        var = tk.BooleanVar(value=is_checked)
                        cvars[child] = var
                        chk = ctk.CTkCheckBox(scroll, text=child, variable=var, font=ctk.CTkFont(size=11), fg_color=app.CORP_COLOR)
                        chk.pack(anchor="w", pady=4, padx=4)

                def save_relations(k=catalog_key, listbox=lb, cvars=check_vars):
                    sel = listbox.curselection()
                    if not sel:
                        return

                    selected_parents = [app.catalog_manager.catalog_values[k][i] for i in sel]
                    selected_children = [c for c, var in cvars.items() if var.get()]
                    child_key = "Genre" if k == "Album" else "Publisher"

                    if not selected_children:
                        selected_children = ["__NONE__"]
                    elif len(selected_children) == len(app.catalog_manager.catalog_values.get(child_key, [])):
                        selected_children = []

                    for parent_val in selected_parents:
                        if k == "Album":
                            app.catalog_manager.set_album_genres(parent_val, selected_children)
                        else:
                            app.catalog_manager.set_genre_publishers(parent_val, selected_children)

                    if hasattr(app, "detail_panel"):
                        app.detail_panel.refresh_catalog_comboboxes()

                    msg = f"Asignaciones actualizadas para {len(selected_parents)} elemento(s)."
                    DialogManager.show_themed_dialog(app, "Relaciones guardadas", msg, level="info", parent=win)

                lb.bind("<<ListboxSelect>>", load_relations)

                btn_save_rel = ctk.CTkButton(right_panel, text="Guardar Relaciones", font=font_btn, command=save_relations, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER, height=32)
                btn_save_rel.pack(fill="x", padx=12, pady=12)
                load_relations()

        ctk.CTkButton(
            win,
            text="Cerrar Panel",
            font=font_btn,
            command=win.destroy,
            fg_color=app.CORP_COLOR,
            hover_color=app.CORP_HOVER,
            height=36
        ).pack(fill="x", padx=16, pady=(0, 16))

    @staticmethod
    def process_pending_covers_dialog(app, items_to_review):
        if not items_to_review:
            return {}

        dialog = MultiCoverSelectionDialog(app, items_to_review)
        app.wait_window(dialog)
        return dialog.selections

    @staticmethod
    def select_discogs_cover_dialog(app, image_urls):
        if not image_urls:
            return None
        if len(image_urls) == 1:
            return image_urls[0]

        mock_item = [{
            "row_id": "single_select",
            "filename": "Selección individual",
            "images": image_urls
        }]
        result = DialogManager.process_pending_covers_dialog(app, mock_item)
        return result.get("single_select")

    @staticmethod
    def center_popup_on_parent(win, parent, width=None, height=None):
        if width and height:
            w, h = width, height
        else:
            w = getattr(win, "_current_width", None) or win.winfo_reqwidth()
            h = getattr(win, "_current_height", None) or win.winfo_reqheight()

            if w < 200 or h < 200:
                w, h = 600, 400

        parent.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_w = parent.winfo_width()
        parent_h = parent.winfo_height()

        if parent_w < 100 or parent_h < 100:
            parent_w, parent_h = 1100, 700

        pos_x = max(0, parent_x + (parent_w - w) // 2)
        pos_y = max(0, parent_y + (parent_h - h) // 2)

        win.geometry(f"{w}x{h}+{pos_x}+{pos_y}")
        win.deiconify()