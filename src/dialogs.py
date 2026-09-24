import io
import os
import re
import sys
import ctypes
import logging
import queue
import threading
import urllib.request
from datetime import datetime
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from catalog_manager import CatalogManager
from ui_utils import UiUtils
import customtkinter as ctk
import theme

logger = logging.getLogger("Sonometa")


class SilentTitlebarMixin:
    """Desactiva la gestión automática de cabecera de Windows de CustomTkinter
    (CTkToplevel._windows_set_titlebar_color), que internamente hace su propio
    withdraw()+update() forzado durante __init__ -antes de que nuestro propio
    DialogManager.hide_until_ready tenga ocasión de ocultar la ventana con opacidad 0-
    y es quien le da pie a Windows a pintar un frame en blanco antes de tiempo.
    Solo se aplica a nuestras clases de diálogo modal: CustomMenuDropdown (el
    desplegable de la barra de herramientas) sí depende de ese ciclo interno para
    pintarse bien con su truco de color transparente, así que no se toca."""
    _deactivate_windows_window_header_manipulation = True


class _SilentCTkToplevel(SilentTitlebarMixin, ctk.CTkToplevel):
    """CTkToplevel genérico (sin clase propia) usado por _new_modal, show_themed_dialog
    y la ventana de logs. El tema oscuro del título se aplica manualmente en
    DialogManager.apply_popup_style vía apply_dark_title_bar."""
    pass


class ReplaceFilenameDialog(SilentTitlebarMixin, ctk.CTkToplevel):
    """Modal para buscar y reemplazar cadenas en los nombres de archivo (filename)."""

    def __init__(self, parent, target_items):
        """
        :param parent: Referencia a la ventana principal (App)
        :param target_items: Lista de dicts: [{"row_id": id, "filename": name}, ...]
        """
        super().__init__(parent)
        DialogManager.hide_until_ready(self)
        self.app = parent
        self.target_items = target_items  # Lista de dicts: [{"row_id": id, "filename": name}, ...]
        self.matches = []  # Ocurrencias encontradas: [{"row_id": id, "filename": name, "display_name": str, "ext": str}, ...]

        # Variable de estado para controlar la sensibilidad a mayúsculas/minúsculas (Activado por defecto)
        self.case_sensitive_var = ctk.BooleanVar(value=True)

        self.title("Reemplazar Texto en Nombres de Archivo - Sonometa")
        self.geometry("700x560")
        self.minsize(620, 460)

        self._setup_ui()

        # Atajo ESC para cerrar la ventana modal
        self.bind("<Escape>", lambda event: self.destroy())

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=700, height=560)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)

        # Foco predeterminado en el campo de búsqueda
        self.after(50, self._set_initial_focus)

    def _set_initial_focus(self):
        self.focus_force()
        if hasattr(self, "entry_search") and self.entry_search.winfo_exists():
            self.entry_search.focus_force()

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)

        # Título y Descripción
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Buscar y Reemplazar en Filename",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_title.pack(anchor="w", padx=5, pady=(0, 2))

        lbl_sub = ctk.CTkLabel(
            main_frame,
            text=f"Analizando {len(self.target_items)} archivo(s) seleccionado(s).",
            text_color=theme.TEXT_MUTED
        )
        lbl_sub.pack(anchor="w", padx=5, pady=(0, 10))

        # Inputs de Búsqueda y Reemplazo
        inputs_frame = ctk.CTkFrame(main_frame, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
        inputs_frame.pack(fill="x", pady=(0, 10), padx=5, ipady=5)

        # Buscar
        lbl_search = ctk.CTkLabel(inputs_frame, text="Buscar:", font=ctk.CTkFont(weight="bold"), text_color=theme.TEXT_MAIN)
        lbl_search.grid(row=0, column=0, padx=10, pady=8, sticky="w")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._find_matches())

        self.entry_search = ctk.CTkEntry(
            inputs_frame,
            placeholder_text="Texto a buscar...",
            textvariable=self.search_var,
            width=320
        )
        self.entry_search.grid(row=0, column=1, columnspan=2, padx=10, pady=8, sticky="ew")

        # Reemplazar por
        lbl_replace = ctk.CTkLabel(inputs_frame, text="Reemplazar por:", font=ctk.CTkFont(weight="bold"), text_color=theme.TEXT_MAIN)
        lbl_replace.grid(row=1, column=0, padx=10, pady=(0, 8), sticky="w")

        self.entry_replace = ctk.CTkEntry(inputs_frame, placeholder_text="Nuevo texto...", width=320)
        self.entry_replace.grid(row=1, column=1, columnspan=2, padx=10, pady=(0, 8), sticky="ew")

        # Checkbox para Case Sensitivity (marcado por defecto)
        self.chk_case_sensitive = ctk.CTkCheckBox(
            inputs_frame,
            text="Coincidir mayúsculas / minúsculas",
            variable=self.case_sensitive_var,
            font=ctk.CTkFont(size=12),
            fg_color=corp_color,
            hover_color=corp_hover,
            command=self._find_matches
        )
        self.chk_case_sensitive.grid(row=2, column=1, columnspan=2, padx=10, pady=(4, 8), sticky="w")

        inputs_frame.columnconfigure(1, weight=1)

        # Lista para Coincidencias
        lbl_matches_header = ctk.CTkLabel(
            main_frame,
            text="Coincidencias encontradas:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MUTED
        )
        lbl_matches_header.pack(anchor="w", padx=5, pady=(4, 4))

        list_container = ctk.CTkFrame(main_frame, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_CONTROL)
        list_container.pack(fill="both", expand=True, padx=5, pady=(0, 10))

        # Scrollbar y Listbox para selección de items sin aspecto de editor de texto ni cursor parpadeante
        scrollbar = ctk.CTkScrollbar(list_container)
        scrollbar.pack(side="right", fill="y", padx=(0, 4), pady=4)

        self.matches_listbox = tk.Listbox(
            list_container,
            bg=theme.BG_INPUT,
            fg=theme.TEXT_MAIN,
            selectbackground=corp_color,
            selectforeground=theme.TEXT_MAIN,
            font=("Consolas", 11),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set
        )
        self.matches_listbox.pack(fill="both", expand=True, padx=8, pady=8)
        scrollbar.configure(command=self.matches_listbox.yview)

        self.matches_listbox.bind("<<ListboxSelect>>", lambda e: self._update_buttons_state())

        # Barra de Botones
        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        self.btn_replace_all = ctk.CTkButton(
            btn_bar,
            text="Reemplazar todos",
            fg_color=corp_color,
            hover_color=corp_hover,
            state="disabled",
            command=self._replace_all_matches
        )
        self.btn_replace_all.pack(side="right", padx=(8, 0))

        self.btn_replace_single = ctk.CTkButton(
            btn_bar,
            text="Reemplazar",
            fg_color=corp_color,
            hover_color=corp_hover,
            state="disabled",
            command=self._replace_single_match
        )
        self.btn_replace_single.pack(side="right", padx=(8, 0))

        btn_close = ctk.CTkButton(
            btn_bar,
            text="Cerrar",
            fg_color="transparent",
            border_width=1,
            border_color=theme.BORDER_QUIET,
            text_color=theme.TEXT_MAIN,
            hover_color=theme.BG_CARD_HOVER,
            command=self.destroy
        )
        btn_close.pack(side="right")

    def _find_matches(self):
        search_str = self.entry_search.get()

        self.matches_listbox.delete(0, tk.END)
        self.matches.clear()

        if not search_str:
            self._update_buttons_state()
            return

        is_case_sensitive = self.case_sensitive_var.get()
        flags = 0 if is_case_sensitive else re.IGNORECASE

        try:
            pattern = re.compile(re.escape(search_str), flags)
        except Exception:
            self._update_buttons_state()
            return

        for item in self.target_items:
            row_id = item["row_id"]
            filename = item["filename"]

            # Separar extensión del nombre base
            base_name, ext = os.path.splitext(filename)

            # Buscar coincidencias únicamente sobre el nombre base (sin extensión)
            if pattern.search(base_name):
                self.matches.append({
                    "row_id": row_id,
                    "filename": filename,
                    "display_name": base_name,
                    "ext": ext
                })
                # Se inserta únicamente el nombre base (sin icono, sin código ID y sin extensión)
                self.matches_listbox.insert(tk.END, base_name)

        if not self.matches:
            self.matches_listbox.insert(tk.END, "Sin coincidencias encontradas.")

        self._update_buttons_state()

    def _update_buttons_state(self):
        has_matches = len(self.matches) > 0
        has_selection = len(self.matches_listbox.curselection()) > 0 and has_matches
        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)

        if has_matches:
            self.btn_replace_all.configure(state="normal", fg_color=corp_color)
        else:
            self.btn_replace_all.configure(state="disabled", fg_color=theme.BG_CARD_HOVER)

        if has_selection:
            self.btn_replace_single.configure(state="normal", fg_color=corp_color)
        else:
            self.btn_replace_single.configure(state="disabled", fg_color=theme.BG_CARD_HOVER)

    def _replace_single_match(self):
        selected_indices = self.matches_listbox.curselection()
        if not selected_indices or not self.matches:
            return

        idx = selected_indices[0]
        if idx >= len(self.matches):
            return

        match_item = self.matches[idx]
        search_str = self.entry_search.get()
        replace_str = self.entry_replace.get()
        is_case_sensitive = self.case_sensitive_var.get()

        flags = 0 if is_case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(search_str), flags)

        # 1. Aplicar reemplazo en ProcessManager
        if hasattr(self.app, "process_manager") and hasattr(self.app.process_manager, "apply_filename_replacement"):
            self.app.process_manager.apply_filename_replacement(
                [match_item["row_id"]],
                search_str,
                replace_str,
                case_sensitive=is_case_sensitive
            )

        # 2. Actualizar localmente la lista target_items manteniendo la extensión
        new_base = pattern.sub(replace_str, match_item["display_name"])
        new_filename = f"{new_base}{match_item['ext']}"

        for item in self.target_items:
            if item["row_id"] == match_item["row_id"]:
                item["filename"] = new_filename

        # 3. Refrescar la lista de búsquedas
        self._find_matches()

    def _replace_all_matches(self):
        if not self.matches:
            return

        search_str = self.entry_search.get()
        replace_str = self.entry_replace.get()
        target_ids = [m["row_id"] for m in self.matches]
        is_case_sensitive = self.case_sensitive_var.get()

        # 1. Aplicar reemplazo a través del ProcessManager
        if hasattr(self.app, "process_manager") and hasattr(self.app.process_manager, "apply_filename_replacement"):
            self.app.process_manager.apply_filename_replacement(
                target_ids,
                search_str,
                replace_str,
                case_sensitive=is_case_sensitive
            )

        # 2. Actualizar los nombres localmente en target_items para todos los modificados
        flags = 0 if is_case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(search_str), flags)
        target_ids_set = set(target_ids)

        for item in self.target_items:
            if item["row_id"] in target_ids_set:
                base_name, ext = os.path.splitext(item["filename"])
                new_base = pattern.sub(replace_str, base_name)
                item["filename"] = f"{new_base}{ext}"

        # 3. Volver a buscar para refrescar la lista
        self._find_matches()


class MultiCoverSelectionDialog(SilentTitlebarMixin, ctk.CTkToplevel):
    """Ventana consolidada que muestra todas las canciones pendientes en filas con sus opciones en columnas."""

    def __init__(self, parent, pending_reviews):
        super().__init__(parent)
        DialogManager.hide_until_ready(self)
        self.title("Selección de Carátulas - Sonometa")

        self.geometry("900x620")
        self.minsize(820, 500)

        self.app = parent
        self.pending_reviews = pending_reviews
        self.selections = {}
        self.cards_ui = {}
        self.no_cover_vars = {}
        self._ui_queue = queue.Queue()
        self._loader_done = False
        self._ui_pump_after_id = None

        for item in self.pending_reviews:
            self.selections[item["row_id"]] = item["images"][0] if item["images"] else None
            self.no_cover_vars[item["row_id"]] = tk.BooleanVar(value=False)

        self._setup_ui()
        self._start_ui_image_pump()
        self._load_images_async()

        # Atajo ESC para cancelar/omitir y cerrar
        self.bind("<Escape>", lambda event: self._on_cancel())
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=900, height=620)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Revisión de Carátulas Encontradas",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_title.pack(anchor="w", padx=5, pady=(0, 2))

        lbl_subtitle = ctk.CTkLabel(
            main_frame,
            text=f"Revisando {len(self.pending_reviews)} elemento(s). Haz clic directamente sobre la portada deseada para seleccionarla.",
            text_color=theme.TEXT_MUTED
        )
        lbl_subtitle.pack(anchor="w", padx=5, pady=(0, 8))

        self.scroll_frame = ctk.CTkScrollableFrame(main_frame, fg_color=theme.BG_INPUT)
        self.scroll_frame.pack(fill="both", expand=True, pady=(0, 10))

        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)

        def _forward_scroll(event):
            if sys.platform == "darwin":
                delta = -int(event.delta)
            elif sys.platform == "win32":
                delta = -int(event.delta / 120)
            else:
                delta = 1 if getattr(event, "num", None) == 5 else -1

            self.scroll_frame._parent_canvas.yview_scroll(delta * 20, "units")
            return "break"

        def _bind_mousewheel_recursive(widget):
            if sys.platform in ("win32", "darwin"):
                widget.bind("<MouseWheel>", _forward_scroll)
            else:
                widget.bind("<Button-4>", _forward_scroll)
                widget.bind("<Button-5>", _forward_scroll)

            for child in widget.winfo_children():
                _bind_mousewheel_recursive(child)

        for item in self.pending_reviews:
            row_id = item["row_id"]
            filename = item["filename"]
            images = item["images"]

            self.cards_ui[row_id] = {}

            card = ctk.CTkFrame(self.scroll_frame, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
            card.pack(fill="x", pady=6, padx=6, ipady=4)

            # Cabecera del item: Título y Toggle Box al lado
            header_frame = ctk.CTkFrame(card, fg_color="transparent")
            header_frame.pack(fill="x", padx=12, pady=(6, 4))

            lbl_file = ctk.CTkLabel(
                header_frame,
                text=f"🎵 {filename}",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                text_color=theme.TEXT_MAIN
            )
            lbl_file.pack(side="left", fill="x", expand=True)

            switch_no_cover = ctk.CTkSwitch(
                header_frame,
                text="No cargar carátula",
                variable=self.no_cover_vars[row_id],
                font=ctk.CTkFont(size=11),
                progress_color=corp_color,
                command=lambda r=row_id: self._toggle_no_cover(r)
            )
            switch_no_cover.pack(side="right", padx=(10, 0))

            covers_container = ctk.CTkScrollableFrame(
                card,
                fg_color="transparent",
                orientation="horizontal",
                height=170
            )
            covers_container.pack(fill="x", padx=6, pady=(0, 6))

            selected_url = self.selections.get(row_id)

            for img_idx, img_url in enumerate(images):
                is_selected = (img_url == selected_url)

                col_frame = ctk.CTkFrame(
                    covers_container,
                    width=130,
                    height=155,
                    fg_color=corp_color if is_selected else theme.BG_CARD,
                    border_color=corp_color,
                    border_width=2 if is_selected else 0,
                    corner_radius=theme.RADIUS_CONTROL,
                    cursor="hand2"
                )
                col_frame.pack(side="left", padx=4, pady=2)
                col_frame.pack_propagate(False)

                img_label = ctk.CTkLabel(
                    col_frame,
                    text="Cargando...",
                    width=115,
                    height=115,
                    fg_color=theme.BG_MAIN,
                    corner_radius=6,
                    cursor="hand2"
                )
                img_label.pack(padx=5, pady=(5, 2))
                img_label.image_url = img_url

                lbl_num = ctk.CTkLabel(
                    col_frame,
                    text=f"Opción #{img_idx + 1}",
                    font=ctk.CTkFont(size=10, weight="bold" if is_selected else "normal"),
                    text_color=theme.TEXT_MAIN if is_selected else theme.TEXT_MUTED,
                    cursor="hand2"
                )
                lbl_num.pack(padx=4, pady=(0, 3))

                self.cards_ui[row_id][img_url] = {
                    "frame": col_frame,
                    "lbl_num": lbl_num,
                    "img_label": img_label
                }

                for widget in (col_frame, img_label, lbl_num):
                    widget.bind("<Button-1>", lambda e, r=row_id, u=img_url: self._select_card(r, u))
                    widget.bind("<Enter>", lambda e, r=row_id, u=img_url: self._on_card_hover(r, u, True))
                    widget.bind("<Leave>", lambda e, r=row_id, u=img_url: self._on_card_hover(r, u, False))

            _bind_mousewheel_recursive(card)
            if hasattr(covers_container, "_parent_canvas"):
                _bind_mousewheel_recursive(covers_container._parent_canvas)

        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        process_icon = getattr(self.app, "process_icon", None)

        self.btn_confirm = ctk.CTkButton(
            btn_bar,
            text="Procesando...",
            image=process_icon,
            compound="left",
            state="disabled",
            text_color=theme.TEXT_MUTED,
            fg_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY),
            hover_color=getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER),
            command=self._on_confirm
        )
        self.btn_confirm.pack(side="right", padx=(8, 0))

        self.btn_omit = ctk.CTkButton(
            btn_bar,
            text="Omitir Todas",
            fg_color="transparent",
            border_width=1,
            border_color=theme.STATUS_DANGER,
            text_color=theme.STATUS_DANGER,
            hover_color=theme.STATUS_DANGER_HOVER,
            command=self._on_cancel
        )
        self.btn_omit.pack(side="right")

    def _toggle_no_cover(self, row_id):
        is_disabled = self.no_cover_vars[row_id].get()
        if is_disabled:
            self.selections[row_id] = "__NO_COVER__"
            for ui_item in self.cards_ui[row_id].values():
                frame = ui_item["frame"]
                lbl_num = ui_item["lbl_num"]
                img_label = ui_item["img_label"]

                frame.configure(fg_color=theme.BG_INPUT, border_width=0, cursor="arrow")
                lbl_num.configure(text_color=theme.TEXT_SUBTLE, font=ctk.CTkFont(size=10, weight="normal"), cursor="arrow")
                img_label.configure(cursor="arrow")
        else:
            first_url = list(self.cards_ui[row_id].keys())[0] if self.cards_ui[row_id] else None
            for ui_item in self.cards_ui[row_id].values():
                ui_item["frame"].configure(cursor="hand2")
                ui_item["lbl_num"].configure(cursor="hand2")
                ui_item["img_label"].configure(cursor="hand2")

            if first_url:
                self._select_card(row_id, first_url)

    def _select_card(self, row_id, selected_url):
        if self.no_cover_vars[row_id].get():
            return

        self.selections[row_id] = selected_url
        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)

        for url, ui_item in self.cards_ui[row_id].items():
            frame = ui_item["frame"]
            lbl_num = ui_item["lbl_num"]

            if url == selected_url:
                frame.configure(fg_color=corp_color, border_width=2)
                lbl_num.configure(text_color=theme.TEXT_MAIN, font=ctk.CTkFont(size=10, weight="bold"))
            else:
                frame.configure(fg_color=theme.BG_CARD, border_width=0)
                lbl_num.configure(text_color=theme.TEXT_MUTED, font=ctk.CTkFont(size=10, weight="normal"))

    def _on_card_hover(self, row_id, url, is_hovering):
        if self.no_cover_vars[row_id].get() or self.selections.get(row_id) == url:
            return

        ui_item = self.cards_ui[row_id].get(url)
        if not ui_item:
            return

        frame = ui_item["frame"]
        if is_hovering:
            frame.configure(fg_color=theme.BORDER_FOCUS)
        else:
            frame.configure(fg_color=theme.BG_CARD)

    def _load_images_async(self):
        def _worker():
            for row_id, urls_dict in self.cards_ui.items():
                for url, ui_item in urls_dict.items():
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
                            self._ui_queue.put(("image", widget, ctk_img))
                    except Exception:
                        self._ui_queue.put(("error", widget, None))

            self._ui_queue.put(("done", None, None))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_ui_image_pump(self):
        if self._ui_pump_after_id is None:
            self._ui_pump_after_id = self.after(20, self._drain_ui_image_queue)

    def _drain_ui_image_queue(self):
        self._ui_pump_after_id = None
        processed = 0

        while processed < 80:
            try:
                action, widget, payload = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            processed += 1

            if action == "image":
                try:
                    if widget and widget.winfo_exists():
                        widget.configure(image=payload, text="")
                except Exception:
                    pass
            elif action == "error":
                try:
                    if widget and widget.winfo_exists():
                        widget.configure(text="Error")
                except Exception:
                    pass
            elif action == "done":
                self._loader_done = True

        if self._loader_done and self._ui_queue.empty():
            self._on_loading_finished()
            return

        self._ui_pump_after_id = self.after(20, self._drain_ui_image_queue)

    def _on_loading_finished(self):
        if self.btn_confirm.winfo_exists():
            process_icon = getattr(self.app, "process_icon", None)
            self.btn_confirm.configure(
                state="normal",
                text="Confirmar Selección",
                text_color=theme.TEXT_MAIN,
                image=process_icon,
                compound="left"
            )

    def _on_confirm(self):
        if self._ui_pump_after_id:
            try:
                self.after_cancel(self._ui_pump_after_id)
            except Exception:
                pass
            self._ui_pump_after_id = None
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        self.selections = {item["row_id"]: None for item in self.pending_reviews}
        if self._ui_pump_after_id:
            try:
                self.after_cancel(self._ui_pump_after_id)
            except Exception:
                pass
            self._ui_pump_after_id = None
        self.grab_release()
        self.destroy()


import customtkinter.windows.ctk_toplevel as ctk_toplevel

_original_revert = ctk_toplevel.CTkToplevel._revert_withdraw_after_windows_set_titlebar_color
def _safe_revert_withdraw(self):
    try:
        if self.winfo_exists():
            _original_revert(self)
    except Exception:
        pass  # Si el widget ya no existe en Tcl, capturamos el TclError silenciosamente
ctk_toplevel.CTkToplevel._revert_withdraw_after_windows_set_titlebar_color = _safe_revert_withdraw


class ProgressDialog(SilentTitlebarMixin, ctk.CTkToplevel):
    """Modal de progreso para operaciones pesadas con actualización segura desde hilos."""

    def __init__(self, parent, title_text="Procesando", message="Iniciando...", total=0, on_cancel=None):
        super().__init__(parent)
        DialogManager.hide_until_ready(self)
        self.app = parent
        self._total = max(0, int(total or 0))
        self._current = 0
        self._ui_queue = queue.Queue()
        self._ui_pump_after_id = None
        self._is_closed = False
        self.on_cancel = on_cancel
        self.btn_cancel = None

        self.title("Progreso - Sonometa")
        self.geometry("520x190")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._trigger_cancel if on_cancel is not None else (lambda: None))

        self.bind("<Destroy>", self._on_destroy_cleanup)

        self._setup_ui(title_text, message)

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=520, height=190)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)
        self._start_ui_pump()

    def _trigger_cancel(self):
        """Deshabilita el botón (evita doble disparo) y avisa al hilo de trabajo vía
        el callback (normalmente threading.Event.set). El propio hilo es quien decide
        cuándo detenerse y cerrar el diálogo; esto solo señaliza la intención."""
        if self.btn_cancel is not None:
            try:
                self.btn_cancel.configure(state="disabled", text="Cancelando...")
            except Exception:
                pass
        if callable(self.on_cancel):
            self.on_cancel()

    def _on_destroy_cleanup(self, event=None):
        """Detiene cualquier temporizador activo cuando Tkinter destruye el widget."""
        self._is_closed = True
        if self._ui_pump_after_id is not None:
            try:
                self.after_cancel(self._ui_pump_after_id)
            except Exception:
                pass
            self._ui_pump_after_id = None

    def _setup_ui(self, title_text, message):
        frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        frame.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=theme.SPACE_MD)

        self.lbl_title = ctk.CTkLabel(
            frame,
            text=title_text,
            anchor="w",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        self.lbl_title.pack(fill="x", pady=(0, 2))

        self.lbl_message = ctk.CTkLabel(
            frame,
            text=message,
            anchor="w",
            justify="left",
            text_color=theme.TEXT_MUTED
        )
        self.lbl_message.pack(fill="x", pady=(0, 10))

        self.progress = ctk.CTkProgressBar(frame, progress_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY))
        self.progress.pack(fill="x", pady=(0, 8))
        self.progress.set(0)

        footer = ctk.CTkFrame(frame, fg_color="transparent")
        footer.pack(fill="x")
        footer.grid_columnconfigure(0, weight=1)

        self.lbl_counter = ctk.CTkLabel(
            footer,
            text="Procesando 0 / 0 canciones...",
            anchor="w",
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(size=11)
        )
        self.lbl_counter.grid(row=0, column=0, sticky="ew")

        if self.on_cancel is not None:
            self.btn_cancel = ctk.CTkButton(
                footer, text="Cancelar", command=self._trigger_cancel, width=90, height=24,
                corner_radius=theme.RADIUS_CONTROL,
                fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS,
                text_color=theme.TEXT_MAIN, font=ctk.CTkFont(size=11)
            )
            self.btn_cancel.grid(row=0, column=1, sticky="e", padx=(theme.SPACE_SM, 0))

    def close(self):
        if self._is_closed:
            return

        self._on_destroy_cleanup()

        def _do_destroy():
            try:
                self.grab_release()
            except Exception:
                pass

            try:
                if self.winfo_exists():
                    self.destroy()
            except Exception:
                pass

        # Si se cierra inmediatamente al crearla (0 archivos), posponemos el destroy 50ms
        # para darle tiempo a CustomTkinter a ejecutar su revert visual interno.
        try:
            if self.winfo_exists():
                self.after(50, _do_destroy)
            else:
                _do_destroy()
        except Exception:
            _do_destroy()

    def set_progress(self, value):
        value = max(0.0, min(1.0, float(value)))
        if not self._is_closed and self.winfo_exists():
            self.progress.set(value)

    def set_text(self, title=None, message=None, counter_text=None):
        if self._is_closed or not self.winfo_exists():
            return
        if title is not None:
            self.lbl_title.configure(text=title)
        if message is not None:
            self.lbl_message.configure(text=message)
        if counter_text is not None:
            self.lbl_counter.configure(text=counter_text)

    def set_counter(self, current, total=None, current_file=""):
        self._current = max(0, int(current or 0))
        if total is not None:
            self._total = max(0, int(total or 0))

        counter_text = f"Procesando {self._current:,} / {self._total:,} canciones..."
        message = "Leyendo metadatos de audio..."
        if current_file:
            message = f"Leyendo: {os.path.basename(current_file)}"

        progress_value = (self._current / self._total) if self._total > 0 else 0.0
        self.set_text(message=message, counter_text=counter_text)
        self.set_progress(progress_value)

    def set_progress_threadsafe(self, value):
        if not self._is_closed:
            self._ui_queue.put(("progress", value))

    def set_text_threadsafe(self, title=None, message=None, counter_text=None):
        if not self._is_closed:
            self._ui_queue.put(("text", {"title": title, "message": message, "counter_text": counter_text}))

    def set_counter_threadsafe(self, current, total=None, current_file=""):
        if not self._is_closed:
            self._ui_queue.put(("counter", {"current": current, "total": total, "current_file": current_file}))

    def _start_ui_pump(self):
        if not self._is_closed and self._ui_pump_after_id is None:
            try:
                self._ui_pump_after_id = self.after(30, self._drain_ui_queue)
            except Exception:
                pass

    def _drain_ui_queue(self):
        self._ui_pump_after_id = None

        if self._is_closed or not self.winfo_exists():
            return

        processed = 0
        while processed < 120:
            try:
                action, payload = self._ui_queue.get_nowait()
            except queue.Empty:
                break

            processed += 1
            if action == "progress":
                self.set_progress(payload)
            elif action == "text":
                self.set_text(**payload)
            elif action == "counter":
                self.set_counter(**payload)

        if not self._is_closed and self.winfo_exists():
            try:
                self._ui_pump_after_id = self.after(30, self._drain_ui_queue)
            except Exception:
                pass


class HealthReportModal(SilentTitlebarMixin, ctk.CTkToplevel):
    """Muestra el resultado de 'Evaluar salud' (audio_health_checker.HealthReport):
    una fila por chequeo (Integridad, Clipping, Volumen LUFS, Corte real de frecuencia)
    con una insignia de color verde/ámbar/rojo según su status."""

    _CHECK_ROWS = (
        ("integrity", "Integridad"),
        ("clipping", "Clipping"),
        ("loudness", "Volumen (LUFS)"),
        ("cutoff", "Corte real de frecuencia"),
    )

    _STATUS_COLORS = {
        "ok": theme.STATUS_SUCCESS,
        "warning": theme.STATUS_WARNING,
        "critical": theme.STATUS_DANGER,
    }

    def __init__(self, app, report, on_reanalyze=None, parent=None):
        """`app` se usa para CORP_COLOR/CORP_HOVER; `parent` (Tk owner para centrar) es
        `app` por defecto, pero puede ser otro modal (ej. BatchHealthReportModal) para
        que este se centre sobre él en vez de sobre la ventana principal."""
        host = parent if parent is not None else app
        super().__init__(host)
        DialogManager.hide_until_ready(self)
        self.app = app
        self._host = host
        self.report = report
        self.on_reanalyze = on_reanalyze

        self.title("Sonometa")
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())

        frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD)
        frame.pack(fill="both", expand=True)

        ctk.CTkLabel(
            frame,
            text="Salud del Archivo",
            anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        ).pack(fill="x", padx=theme.SPACE_MD, pady=(theme.SPACE_MD, 0))

        ctk.CTkLabel(
            frame,
            text=os.path.basename(report.file_path),
            anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE),
            text_color=theme.TEXT_SUBTLE
        ).pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_XXS))

        ctk.CTkLabel(
            frame,
            text=self._format_analyzed_at(report.analyzed_at),
            anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO),
            text_color=theme.TEXT_SUBTLE
        ).pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_MD))

        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=theme.SPACE_MD)

        if report.error:
            ctk.CTkLabel(
                body,
                text=report.error,
                anchor="w",
                justify="left",
                text_color=theme.STATUS_DANGER,
                wraplength=380
            ).pack(fill="x", pady=theme.SPACE_SM)
        else:
            for attr, title in self._CHECK_ROWS:
                self._build_check_row(body, title, getattr(report, attr))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(pady=(theme.SPACE_SM, 20))

        if on_reanalyze is not None:
            ctk.CTkButton(
                btns, text="Re-analizar", command=self._trigger_reanalyze, width=140,
                corner_radius=theme.RADIUS_CONTROL,
                fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS,
                text_color=theme.TEXT_MAIN
            ).pack(side="left", padx=(0, theme.SPACE_SM))

        ctk.CTkButton(
            btns, text="Cerrar", command=self.destroy, width=140,
            corner_radius=theme.RADIUS_CONTROL,
            fg_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY),
            hover_color=getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)
        ).pack(side="left")

        self.update_idletasks()
        width = 440
        height = max(260, min(560, frame.winfo_reqheight()))
        DialogManager.center_popup_on_parent(self, self._host, width=width, height=height)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self._host)

    @staticmethod
    def _format_analyzed_at(analyzed_at):
        if not analyzed_at:
            return ""
        try:
            parsed = datetime.fromisoformat(analyzed_at)
            return f"Analizado el {parsed.astimezone().strftime('%d/%m/%Y %H:%M')}"
        except (ValueError, TypeError):
            return ""

    def _trigger_reanalyze(self):
        callback = self.on_reanalyze
        self.destroy()
        if callable(callback):
            callback()

    def _build_check_row(self, parent, title, result):
        row = ctk.CTkFrame(parent, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
        row.pack(fill="x", pady=(0, theme.SPACE_SM))
        row.grid_columnconfigure(1, weight=1)

        color = self._STATUS_COLORS.get(result.status, theme.TEXT_MUTED)
        ctk.CTkLabel(row, text="", width=12, height=12, corner_radius=6, fg_color=color).grid(
            row=0, column=0, rowspan=2, padx=(theme.SPACE_MD, theme.SPACE_SM), pady=theme.SPACE_SM, sticky="n"
        )

        ctk.CTkLabel(
            row,
            text=f"{title}: {result.label}",
            anchor="w",
            justify="left",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, weight="bold"),
            text_color=theme.TEXT_MAIN,
            wraplength=360
        ).grid(row=0, column=1, sticky="ew", pady=(theme.SPACE_SM, 0))

        ctk.CTkLabel(
            row,
            text=result.detail,
            anchor="w",
            justify="left",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE),
            text_color=theme.TEXT_MUTED,
            wraplength=360
        ).grid(row=1, column=1, sticky="ew", padx=(0, theme.SPACE_MD), pady=(0, theme.SPACE_SM))


def _build_metric_chip(parent, label, count, color):
    """Tarjeta 'número grande + etiqueta' reutilizada por BatchHealthReportModal y
    HealthDashboardView (health_dashboard_view.py) para sus métricas rápidas."""
    chip = ctk.CTkFrame(parent, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
    ctk.CTkLabel(
        chip, text=str(count), text_color=color,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold")
    ).pack(padx=theme.SPACE_MD, pady=(theme.SPACE_XS, 0))
    ctk.CTkLabel(
        chip, text=label, text_color=theme.TEXT_MUTED,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO)
    ).pack(padx=theme.SPACE_MD, pady=(0, theme.SPACE_XS))
    return chip


class BatchHealthReportModal(SilentTitlebarMixin, ctk.CTkToplevel):
    """Resumen de 'Evaluar salud' para una selección múltiple o un lote de pendientes:
    métricas rápidas + lista de pistas. Doble clic en una fila abre su
    HealthReportModal individual (vía on_open_detail)."""

    _STATUS_COLORS = HealthReportModal._STATUS_COLORS

    def __init__(self, app, results, was_cancelled=False, on_open_detail=None, parent=None):
        host = parent if parent is not None else app
        super().__init__(host)
        DialogManager.hide_until_ready(self)
        self.app = app
        self._host = host
        self.results = results  # list[(file_path, HealthReport)]
        self.on_open_detail = on_open_detail

        self.title("Sonometa")
        self.resizable(False, False)
        self.bind("<Escape>", lambda e: self.destroy())

        frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD)
        frame.pack(fill="both", expand=True)

        total = len(results)
        avg_score = round(sum(r.health_score for _, r in results) / total) if total else 0
        ok_count = sum(1 for _, r in results if r.overall_status == "ok")
        warn_count = sum(1 for _, r in results if r.overall_status == "warning")
        crit_count = sum(1 for _, r in results if r.overall_status == "critical")
        fake_count = sum(1 for _, r in results if r.bitrate_fake)
        clip_count = sum(1 for _, r in results if r.has_clipping)

        ctk.CTkLabel(
            frame, text="Evaluación por Lote", anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        ).pack(fill="x", padx=theme.SPACE_MD, pady=(theme.SPACE_MD, 0))

        subtitle = f"{total} archivo(s) analizados — puntuación media {avg_score}/100"
        if was_cancelled:
            subtitle += " (cancelado antes de terminar)"
        ctk.CTkLabel(
            frame, text=subtitle, anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE),
            text_color=theme.TEXT_SUBTLE
        ).pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM))

        metrics = ctk.CTkFrame(frame, fg_color="transparent")
        metrics.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM))
        for label, count, color in (
            ("OK", ok_count, theme.STATUS_SUCCESS),
            ("Avisos", warn_count, theme.STATUS_WARNING),
            ("Críticos", crit_count, theme.STATUS_DANGER),
            ("Falsos 320k", fake_count, theme.STATUS_WARNING),
            ("Clipping", clip_count, theme.STATUS_DANGER),
        ):
            _build_metric_chip(metrics, label, count, color).pack(side="left", padx=(0, theme.SPACE_SM))

        list_container = ctk.CTkScrollableFrame(frame, fg_color=theme.BG_CARD, corner_radius=0, height=260)
        list_container.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM))

        for file_path, report in results:
            self._build_track_row(list_container, file_path, report)

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(pady=(0, 20))
        ctk.CTkButton(
            btns, text="Cerrar", command=self.destroy, width=140,
            corner_radius=theme.RADIUS_CONTROL,
            fg_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY),
            hover_color=getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)
        ).pack()

        self.update_idletasks()
        width = 520
        height = max(420, min(680, frame.winfo_reqheight()))
        DialogManager.center_popup_on_parent(self, self._host, width=width, height=height)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self._host)

    def _build_track_row(self, parent, file_path, report):
        row = ctk.CTkFrame(parent, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL, cursor="hand2")
        row.pack(fill="x", pady=(0, theme.SPACE_XS))
        row.grid_columnconfigure(1, weight=1)

        color = self._STATUS_COLORS.get(report.overall_status, theme.TEXT_MUTED)
        badge = ctk.CTkLabel(row, text="", width=10, height=10, corner_radius=5, fg_color=color)
        badge.grid(row=0, column=0, padx=(theme.SPACE_SM, theme.SPACE_SM), pady=theme.SPACE_SM)

        lbl_name = ctk.CTkLabel(
            row, text=os.path.basename(file_path), anchor="w", text_color=theme.TEXT_MAIN,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        )
        lbl_name.grid(row=0, column=1, sticky="ew", pady=theme.SPACE_SM)

        lbl_score = ctk.CTkLabel(
            row, text=f"{report.health_score}/100", anchor="e", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE, weight="bold")
        )
        lbl_score.grid(row=0, column=2, padx=(theme.SPACE_SM, theme.SPACE_MD), pady=theme.SPACE_SM)

        def _open_detail(event=None):
            if callable(self.on_open_detail):
                self.on_open_detail(report, file_path, self)

        for widget in (row, badge, lbl_name, lbl_score):
            widget.bind("<Double-Button-1>", _open_detail)


class DialogManager:
    """Clase especializada en la gestión de ventanas emergentes, diálogos y popups de la aplicación."""

    @staticmethod
    def center_popup_on_parent(win, parent, width=None, height=None):
        """Calcula la posición de la ventana emergente centrada con respecto a su ventana padre."""
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

    @staticmethod
    def show_replace_filename_dialog(app, target_items):
        """Muestra el diálogo para buscar y reemplazar en los nombres de archivo."""
        if not target_items:
            DialogManager.show_themed_dialog(
                app,
                "Sin selección",
                "Selecciona al menos un archivo en la grilla para realizar reemplazos de filename.",
                level="warning"
            )
            return

        dialog = ReplaceFilenameDialog(app, target_items)
        app.wait_window(dialog)

    # Al final de la clase DialogManager en dialogs.py

    @staticmethod
    def show_login_dialog(app, supabase_client, on_success_callback=None):
        """Muestra el diálogo modal para iniciar sesión en Supabase Cloud."""
        from login_dialog import LoginDialog
        dialog = LoginDialog(app, supabase_client=supabase_client, on_success_callback=on_success_callback)
        app.wait_window(dialog)

    @staticmethod
    def show_progress_dialog(app, title_text="Procesando", message="Iniciando...", total=0, on_cancel=None):
        return ProgressDialog(app, title_text=title_text, message=message, total=total, on_cancel=on_cancel)

    @staticmethod
    def run_single_health_check(app, file_path, parent=None):
        """Analiza un único archivo SIN comprobar caché (para forzar 're-analizar')
        con un ProgressDialog indeterminado, y al terminar abre HealthReportModal con
        su propio 'Re-analizar' ya enlazado a esta misma función. Único punto de
        entrada para análisis forzado: lo usa tanto el primer análisis desde
        grid_panel como el botón 'Re-analizar' de cualquier HealthReportModal
        (incluido el abierto desde una fila de BatchHealthReportModal)."""
        host = parent if parent is not None else app
        filename = os.path.basename(file_path)

        progress = DialogManager.show_progress_dialog(
            host, title_text="Evaluando Salud", message=f"Analizando {filename}...",
        )
        progress.lbl_counter.configure(text="Esto puede tardar unos segundos en temas largos.")
        progress.progress.configure(mode="indeterminate")
        progress.progress.start()

        def _worker():
            from audio_health_checker import AudioHealthChecker

            cache_manager = getattr(app, "cache_manager", None)
            error = None
            try:
                report = AudioHealthChecker.analyze(file_path, cache_manager=cache_manager)
            except Exception as e:
                logger.error(f"HealthCheck: fallo analizando '{file_path}': {e}")
                report = None
                error = str(e)

            app.after(0, lambda: _on_done(report, error))

        def _on_done(report, error):
            try:
                progress.progress.stop()
            except Exception:
                pass
            if progress.winfo_exists():
                progress.close()

            if report is None:
                DialogManager.show_themed_dialog(
                    app, "Error al analizar",
                    error or "No se pudo completar el análisis del archivo.",
                    level="error", parent=host
                )
                return

            if hasattr(app, "grid_panel"):
                app.grid_panel.refresh_health_columns([file_path])

            HealthReportModal(
                app, report,
                on_reanalyze=lambda: DialogManager.run_single_health_check(app, file_path, parent=parent),
                parent=parent,
            )

        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def run_batch_health_check(app, file_paths, parent=None, on_complete=None):
        """Orquesta 'Evaluar salud' para varios archivos: ProgressDialog determinado y
        cancelable, un hilo secundario que salta los que ya tienen caché válida, y al
        terminar un BatchHealthReportModal con el resumen. Punto de entrada único
        compartido por la selección múltiple de grid_panel y el botón 'Analizar
        pendientes' de HealthDashboardView (health_dashboard_view.py)."""
        existing_paths = [p for p in file_paths if p and os.path.exists(p)]
        if not existing_paths:
            DialogManager.show_themed_dialog(
                app, "Sin archivos", "Ninguno de los archivos indicados existe ya en disco.",
                level="error", parent=parent
            )
            return

        cancel_event = threading.Event()
        total = len(existing_paths)
        host = parent if parent is not None else app

        progress = DialogManager.show_progress_dialog(
            host,
            title_text="Evaluando Salud",
            message="Preparando análisis por lotes...",
            total=total,
            on_cancel=cancel_event.set,
        )
        progress.set_counter(0, total)

        def _worker():
            from audio_health_checker import AudioHealthChecker, HealthReport

            cache_manager = getattr(app, "cache_manager", None)
            results = []

            for idx, file_path in enumerate(existing_paths, start=1):
                if cancel_event.is_set():
                    break

                progress.set_counter_threadsafe(idx - 1, total, current_file=file_path)

                cached = cache_manager.get_cached_health(file_path) if cache_manager else None
                if cached is not None:
                    report = cached
                else:
                    try:
                        report = AudioHealthChecker.analyze(file_path, cache_manager=cache_manager)
                    except Exception as e:
                        logger.error(f"HealthCheck lote: fallo analizando '{file_path}': {e}")
                        report = HealthReport.failed(file_path, str(e))

                results.append((file_path, report))
                progress.set_counter_threadsafe(idx, total, current_file=file_path)

            was_cancelled = cancel_event.is_set()
            app.after(0, lambda: _on_done(results, was_cancelled))

        def _on_done(results, was_cancelled):
            try:
                progress.progress.stop()
            except Exception:
                pass
            if progress.winfo_exists():
                progress.close()

            if results and hasattr(app, "grid_panel"):
                app.grid_panel.refresh_health_columns([fp for fp, _ in results])

            if results:
                BatchHealthReportModal(
                    app, results, was_cancelled=was_cancelled,
                    on_open_detail=lambda report, file_path, parent_win: HealthReportModal(
                        app, report,
                        on_reanalyze=lambda: DialogManager.run_single_health_check(app, file_path, parent=parent_win),
                        parent=parent_win,
                    ),
                    parent=host,
                )

            if callable(on_complete):
                on_complete(results, was_cancelled)

        threading.Thread(target=_worker, daemon=True).start()

    @staticmethod
    def hide_until_ready(win):
        """Oculta la ventana con opacidad 0 desde el instante de su creación.
        Windows pinta el fondo blanco por defecto del HWND nativo del Toplevel antes de
        que CustomTkinter termine de dibujar el contenido y el tema oscuro; llamar a esto
        justo tras crear la ventana evita ese destello. Se revela en apply_popup_style
        una vez la ventana ya está construida, posicionada y con el estilo aplicado."""
        try:
            win.attributes("-alpha", 0.0)
        except Exception:
            pass

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
            win.focus_force()

        # Revela la ventana en el siguiente ciclo del mainloop (tras terminar de construir
        # y posicionar todo su contenido), no de forma instantánea con deiconify().
        def _reveal():
            try:
                win.attributes("-alpha", 1.0)
            except Exception:
                pass

        win.after(60, _reveal)

    @staticmethod
    def _new_modal(app, title, width, height, *, parent=None, resizable=False, is_modal=True, on_escape=None):
        """Crea un CTkToplevel con el patrón estándar de diálogo Sonometa: título, geometría,
        atajo ESC, centrado sobre `parent` (o `app` si no se indica) y estilo corporativo aplicado.
        """
        owner = parent if parent is not None else app
        win = _SilentCTkToplevel(owner)
        DialogManager.hide_until_ready(win)
        win.title(title)
        win.geometry(f"{width}x{height}")
        if not resizable:
            win.resizable(False, False)

        win.bind("<Escape>", on_escape if on_escape is not None else (lambda e: win.destroy()))

        DialogManager.center_popup_on_parent(win, owner, width=width, height=height)
        DialogManager.apply_popup_style(app, win, is_modal=is_modal, owner=owner)

        return win

    @staticmethod
    def apply_dark_title_bar(win):
        if sys.platform != "win32" or not win.winfo_exists():
            return
        try:
            # GetParent() sube del HWND "cliente" que devuelve Tk al HWND real de la
            # ventana decorada (el que tiene la barra de título); sin este paso,
            # DwmSetWindowAttribute apunta al handle equivocado y no hace nada.
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            value = ctypes.c_int(1)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    @staticmethod
    def show_themed_dialog(app, title, message, level="info", is_confirm=False, parent=None):
        """Diálogo modal estándar de Sonometa (icono, título y mensaje centrados en columna)
        para avisos, errores, información y confirmaciones. Devuelve forzosamente el foco a la
        ventana padre o principal al cerrarse, y bool en confirmaciones (True si se confirmó)."""
        host = parent if parent is not None else app
        # fg_color igual al del frame interior: sin ese contraste, el margen entre la
        # ventana y la tarjeta deja de leerse como un "doble marco".
        dialog = _SilentCTkToplevel(host, fg_color=theme.BG_CARD)
        dialog.withdraw()
        DialogManager.hide_until_ready(dialog)
        # Título neutro de la barra del SO: el descriptivo ("Sin selección", etc.) vive
        # únicamente en la etiqueta en negrita del cuerpo.
        dialog.title("Sonometa")
        dialog.resizable(False, False)

        result = {"value": False}

        def accept():
            result["value"] = True
            dialog.destroy()

        def cancel():
            result["value"] = False
            dialog.destroy()

        dialog.bind("<Escape>", lambda e: cancel() if is_confirm else accept())

        frame = ctk.CTkFrame(dialog, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD)
        frame.pack(fill="both", expand=True)

        # Ancho útil real del texto: 380px de ventana menos el padx de las propias etiquetas
        # (SPACE_MD a cada lado).
        text_wraplength = 380 - 2 * theme.SPACE_MD

        # Símbolo/color de respaldo por si el PNG del icono no está disponible.
        icon_symbol, icon_bg = {
            "warning": ("!", theme.STATUS_WARNING),
            "error": ("✕", theme.STATUS_DANGER),
            "success": ("✓", theme.MODAL_ICON_SUCCESS),
            "info": ("i", theme.STATUS_INFO),
        }.get(level, ("i", theme.STATUS_INFO))

        # Iconos vectoriales (pre-renderizados a PNG) para un círculo/triángulo nítido a 48px,
        # en vez del badge de texto achatado. "error" no tiene asset propio todavía y usa el
        # badge de respaldo.
        icon_asset = {
            "warning": "assets/warning_icon.png",
            "success": "assets/success_icon.png",
            "info": "assets/info_icon.png",
        }.get(level)

        icon_widget = None
        if icon_asset:
            icon_path = UiUtils.get_resource_path(icon_asset)
            if os.path.exists(icon_path):
                try:
                    with Image.open(icon_path) as icon_file:
                        pil_icon = icon_file.copy()
                    target_w = 48
                    target_h = int(target_w * pil_icon.height / pil_icon.width)
                    icon_image = ctk.CTkImage(
                        light_image=pil_icon, dark_image=pil_icon, size=(target_w, target_h)
                    )
                    icon_widget = ctk.CTkLabel(frame, image=icon_image, text="")
                except Exception:
                    icon_widget = None

        if icon_widget is None:
            icon_widget = ctk.CTkLabel(
                frame,
                text=icon_symbol,
                width=48,
                height=48,
                corner_radius=24,
                fg_color=icon_bg,
                text_color=theme.TEXT_MAIN,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
            )

        icon_widget.pack(pady=(theme.SPACE_LG, theme.SPACE_SM))

        ctk.CTkLabel(
            frame,
            text=title,
            justify="center",
            text_color=theme.TEXT_MAIN,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold"),
            wraplength=text_wraplength
        ).pack(padx=theme.SPACE_MD, pady=(0, theme.SPACE_XS))

        ctk.CTkLabel(
            frame,
            text=message,
            justify="center",
            text_color=theme.TEXT_MUTED,
            wraplength=text_wraplength
        ).pack(padx=theme.SPACE_MD, pady=(0, theme.SPACE_LG))

        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.pack(pady=(0, 20))

        if is_confirm:
            ctk.CTkButton(
                btns, text="Cancelar", command=cancel, width=110,
                corner_radius=theme.RADIUS_CONTROL,
                fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS,
                text_color=theme.TEXT_MAIN
            ).pack(side="left", padx=(0, theme.SPACE_SM))

            btn_ok = ctk.CTkButton(
                btns, text="Confirmar", command=accept, width=110,
                corner_radius=theme.RADIUS_CONTROL,
                fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER
            )
            btn_ok.pack(side="left")
        else:
            btn_ok = ctk.CTkButton(
                btns, text="Aceptar", command=accept, width=140,
                corner_radius=theme.RADIUS_CONTROL,
                fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER
            )
            btn_ok.pack()

        dialog.update_idletasks()
        width = 380
        height = max(220, min(420, frame.winfo_reqheight()))
        DialogManager.center_popup_on_parent(dialog, host, width=width, height=height)
        DialogManager.apply_popup_style(app, dialog, is_modal=True, owner=host)
        btn_ok.focus_force()

        dialog.wait_window()

        if host and host.winfo_exists():
            host.focus_force()

        return result["value"]

    @staticmethod
    def show_about_dialog(app):
        """Muestra el diálogo modal de 'Acerca de' estilizado con el logo oficial respetando su aspecto original."""
        dialog = DialogManager._new_modal(app, "Acerca de Sonometa", 460, 300)

        main_frame = ctk.CTkFrame(dialog, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # --- CARGA DEL LOGO (Mantenimiento de Aspect Ratio) ---
        logo_path = UiUtils.get_resource_path("assets/logo_completo.png")
        logo_image = None

        if os.path.exists(logo_path):
            try:
                with Image.open(logo_path) as logo_file:
                    pil_img = logo_file.copy()

                # Definir ancho objetivo y calcular alto proporcional
                target_width = 240
                aspect_ratio = pil_img.height / pil_img.width
                target_height = int(target_width * aspect_ratio)

                logo_image = ctk.CTkImage(
                    light_image=pil_img,
                    dark_image=pil_img,
                    size=(target_width, target_height)
                )
            except Exception:
                logo_image = None

        if logo_image:
            lbl_logo = ctk.CTkLabel(main_frame, image=logo_image, text="")
            lbl_logo.pack(pady=(12, 10))
        else:
            # Fallback en caso de no disponer de la imagen
            lbl_logo = ctk.CTkLabel(
                main_frame,
                text="🎵 SONOMETA",
                font=ctk.CTkFont(size=22, weight="bold"),
                text_color=theme.TEXT_MAIN
            )
            lbl_logo.pack(pady=(12, 10))

        # --- SUBTÍTULO Y DESCRIPCIÓN ---
        lbl_subtitle = ctk.CTkLabel(
            main_frame,
            text="Audio Tag Suite & Metadata Automation",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MUTED
        )
        lbl_subtitle.pack(pady=(0, 12))

        desc_text = (
            "Herramienta avanzada para la automatización, edición y gestión de "
            "metadatos de audio.\n\n"
            "• Integración directa con Discogs API para vinilos y lanzamientos.\n"
            "• Soporte nativo para etiquetas ID3v2, FLAC y MP4 / AAC."
        )

        lbl_desc = ctk.CTkLabel(
            main_frame,
            text=desc_text,
            justify="center",
            wraplength=400,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_MUTED
        )
        lbl_desc.pack(fill="x", pady=(0, 18))

        # --- BOTÓN DE CIERRE ---
        corp_color = getattr(app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(app, "CORP_HOVER", theme.PRIMARY_HOVER)

        btn_close = ctk.CTkButton(
            main_frame,
            text="Aceptar",
            fg_color=corp_color,
            hover_color=corp_hover,
            width=120,
            command=dialog.destroy
        )
        btn_close.pack(side="bottom")
        btn_close.focus_force()

        dialog.wait_window()
        if app and app.winfo_exists():
            app.focus_force()

    @staticmethod
    def show_keyboard_shortcuts_dialog(app):
        shortcuts_win = DialogManager._new_modal(app, "Atajos de Teclado", 500, 380, resizable=True)

        frame_content = ctk.CTkFrame(shortcuts_win)
        frame_content.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=theme.SPACE_MD)

        lbl_title = ctk.CTkLabel(
            frame_content,
            text="Atajos de Teclado Disponibles",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold")
        )
        lbl_title.pack(fill="x", pady=(0, 12))

        frame_scroll = ctk.CTkScrollableFrame(frame_content)
        frame_scroll.pack(fill="both", expand=True)

        shortcuts = [
            ("Ctrl+O", "Seleccionar carpeta"),
            ("F5", "Actualizar lista de archivos"),
            ("Ctrl+A", "Seleccionar todo"),
            ("Ctrl+F", "Buscar coincidencias en la lista"),
            ("Ctrl+R", "Abrir ventana para reemplazar texto en el nombre del archivo"),
            ("Ctrl+Q", "Cerrar aplicación"),
            ("Doble-clic", "Editar celda en tabla"),
            ("Enter", "Guardar edición de celda"),
            ("Esc", "Cerrar búsqueda activa o ventana emergente"),
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
        btn_close.focus_force()

    @staticmethod
    def show_logs_dialog(app):
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.deiconify()
            app.log_window.lift()
            app.log_window.attributes("-topmost", True)
            app.log_window.after(100, lambda: app.log_window.attributes("-topmost", False) if app.log_window and app.log_window.winfo_exists() else None)
            app.log_window.focus_force()
            return

        app.log_window = _SilentCTkToplevel(app)
        DialogManager.hide_until_ready(app.log_window)
        app.log_window.title("Historial de Logs - Sonometa")
        app.log_window.geometry("750x480")

        # Cierre con ESC
        app.log_window.bind("<Escape>", lambda e: DialogManager.close_logs_dialog(app))

        DialogManager.center_popup_on_parent(app.log_window, app, width=750, height=480)
        DialogManager.apply_popup_style(app, app.log_window, is_modal=False, owner=app)
        app.log_window.protocol("WM_DELETE_WINDOW", lambda: DialogManager.close_logs_dialog(app))

        # --- Frame Superior: Filtros y Acciones ---
        top_frame = ctk.CTkFrame(app.log_window, fg_color="transparent")
        top_frame.pack(fill="x", padx=10, pady=(10, 0))

        lbl_filter = ctk.CTkLabel(
            top_frame,
            text="Filtrar nivel:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_filter.pack(side="left", padx=(5, 8))

        corp_color = getattr(app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(app, "CORP_HOVER", theme.PRIMARY_HOVER)

        if not hasattr(app, "log_filter_var"):
            app.log_filter_var = tk.StringVar(value="TODOS")

        seg_filter = ctk.CTkSegmentedButton(
            top_frame,
            values=["TODOS", "INFO", "WARNING", "ERROR"],
            variable=app.log_filter_var,
            selected_color=corp_color,
            selected_hover_color=corp_hover,
            unselected_color=theme.BG_CARD_HOVER,
            unselected_hover_color=theme.BORDER_FOCUS,
            text_color=theme.TEXT_MAIN,
            command=lambda selected: DialogManager._filter_and_render_logs(app)
        )
        seg_filter.pack(side="left")

        # Botones de Acción en la barra superior (Copiar y Exportar)
        btn_copy = ctk.CTkButton(
            top_frame,
            text="Copiar",
            width=70,
            fg_color=theme.BG_CARD_HOVER,
            hover_color=theme.BORDER_FOCUS,
            command=lambda: DialogManager._copy_logs_to_clipboard(app)
        )
        btn_copy.pack(side="right", padx=(5, 0))

        btn_export = ctk.CTkButton(
            top_frame,
            text="Exportar .txt",
            width=90,
            fg_color=theme.BG_CARD_HOVER,
            hover_color=theme.BORDER_FOCUS,
            command=lambda: DialogManager._export_logs_to_file(app)
        )
        btn_export.pack(side="right", padx=(5, 0))

        # --- Textbox Principal ---
        app.log_textbox = ctk.CTkTextbox(app.log_window, wrap="none", font=("Consolas", 11))
        app.log_textbox.pack(fill="both", expand=True, padx=10, pady=10)

        # Configuración de tags de formato de texto (sin negrita)
        raw_textbox = app.log_textbox._textbox
        raw_textbox.tag_config("lvl_info", foreground=theme.STATUS_SUCCESS, font=("Consolas", 11))      # Verde
        raw_textbox.tag_config("lvl_warning", foreground=theme.STATUS_WARNING, font=("Consolas", 11))   # Amarillo
        raw_textbox.tag_config("lvl_error", foreground=theme.STATUS_DANGER, font=("Consolas", 11))     # Rojo
        raw_textbox.tag_config("lvl_purple", foreground=theme.PRIMARY, font=("Consolas", 11))    # Morado

        # Renderizar historial de logs actual
        DialogManager._filter_and_render_logs(app)

        # --- Frame Inferior: Botones de Acción ---
        btn_bar = ctk.CTkFrame(app.log_window, fg_color="transparent")
        btn_bar.pack(fill="x", padx=10, pady=(0, 10))

        broom_icon = getattr(app, "broom_icon", None)

        btn_clear = ctk.CTkButton(
            btn_bar,
            text="Limpiar consola",
            image=broom_icon,
            compound="left",
            fg_color="transparent",
            border_color=theme.STATUS_DANGER,
            border_width=1,
            text_color=theme.TEXT_MAIN,
            hover_color=theme.STATUS_DANGER_HOVER,
            corner_radius=theme.RADIUS_CONTROL,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=30,
            command=lambda: DialogManager._clear_console(app)
        )
        btn_clear.pack(side="left", padx=(5, 0))

        btn_close = ctk.CTkButton(
            btn_bar,
            text="Cerrar",
            fg_color=corp_color,
            hover_color=corp_hover,
            command=lambda: DialogManager.close_logs_dialog(app)
        )
        btn_close.pack(side="right", padx=(0, 5))

        app.log_window.lift()
        app.log_window.attributes("-topmost", True)
        app.log_window.after(150, lambda: app.log_window.attributes("-topmost", False) if app.log_window and app.log_window.winfo_exists() else None)

        # Asignar el foco a la ventana modal de logs para captura de eventos (p. ej. ESC)
        app.log_window.focus_force()
        app.log_window.after(50, lambda: app.log_window.focus_force() if app.log_window and app.log_window.winfo_exists() else None)

    @staticmethod
    def append_formatted_log_line(app, level, msg):
        """Inserta una línea de log enriched en el textbox respetando el filtro activo."""
        log_box = getattr(app, "log_textbox", None)
        if not log_box or not log_box.winfo_exists():
            return

        filter_level = getattr(app, "log_filter_var", None)
        selected_filter = filter_level.get() if filter_level else "TODOS"

        if selected_filter != "TODOS" and selected_filter != level:
            return

        log_box.configure(state="normal")
        line = msg if msg.endswith("\n") else f"{msg}\n"

        # Determinar tag visual
        tag = "lvl_tree" if ("├──" in line or "└──" in line) else f"lvl_{level.lower()}"

        try:
            log_box._textbox.insert("end", line, tag)
        except Exception:
            log_box.insert("end", line)

        log_box.see("end")
        log_box.configure(state="disabled")

    @staticmethod
    def _filter_and_render_logs(app):
        """Redibuja el cuadro de logs eliminando el timestamp y mejorando la legibilidad de diccionarios."""
        log_box = getattr(app, "log_textbox", None)
        if not log_box or not log_box.winfo_exists():
            return

        filter_level = getattr(app, "log_filter_var", None)
        selected_filter = filter_level.get() if filter_level else "TODOS"

        log_box.configure(state="normal")
        log_box.delete("1.0", "end")

        raw_textbox = log_box._textbox

        # --- Configuración de etiquetas de estilo ---
        raw_textbox.tag_config("lvl_info", foreground=theme.STATUS_SUCCESS, font=("Consolas", 11))       # Verde
        raw_textbox.tag_config("lvl_warning", foreground=theme.STATUS_WARNING, font=("Consolas", 11))    # Amarillo
        raw_textbox.tag_config("lvl_error", foreground=theme.STATUS_DANGER, font=("Consolas", 11))      # Rojo
        raw_textbox.tag_config("tag_purple", foreground=theme.PRIMARY, font=("Consolas", 11))     # Morado corporativo
        raw_textbox.tag_config("tag_delete", foreground="#F97316", font=("Consolas", 11))     # Naranja
        raw_textbox.tag_config("tree_branch", foreground=theme.TEXT_SUBTLE, font=("Consolas", 11))    # Gris oscuro
        raw_textbox.tag_config("json_key", foreground="#38BDF8", font=("Consolas", 11))       # Cyan para claves ('Artist':)
        raw_textbox.tag_config("json_val", foreground=theme.TEXT_MAIN, font=("Consolas", 11))       # Blanco destacado para valores
        raw_textbox.tag_config("text_body", foreground=theme.TEXT_MUTED, font=("Consolas", 11))      # Blanco/Gris base

        # Pattern para identificar tokens sin incluir horas/fechas
        token_pattern = re.compile(
            r"(\[(?:INFO|WARN|WARNING|ERROR)\])"                # Grp 1: Severidad
            r"|(\[(?:PROCESS|DISCOGS|DETAIL|GRID|DELETE|200 OK)\])" # Grp 2: Sub-etiquetas
            r"|(\s*├──\s*|\s*└──\s*)"                           # Grp 3: Árbol
            r"|('(?:[^'\\]|\\.)*'\s*:)"                          # Grp 4: Claves de diccionario ('Artist':)
            r"|('(?:[^'\\]|\\.)*')"                             # Grp 5: Valores entre comillas ('Bandido')
        )

        for item in list(getattr(app, "log_history", [])):
            if isinstance(item, tuple):
                level, msg = item
            else:
                level = "INFO"
                msg = item

            if selected_filter != "TODOS" and selected_filter != level:
                continue

            # Eliminar fecha y hora iniciales (formato YYYY-MM-DD HH:MM:SS o HH:MM:SS)
            line = re.sub(r"^(\d{4}-\d{2}-\d{2}\s+)?\d{2}:\d{2}:\d{2}\s*", "", msg)
            line = line if line.endswith("\n") else f"{line}\n"

            parts = token_pattern.split(line)

            for part in parts:
                if not part:
                    continue

                if part in ("[INFO]",):
                    tag = "lvl_info"
                elif part in ("[WARN]", "[WARNING]"):
                    tag = "lvl_warning"
                elif part == "[ERROR]":
                    tag = "lvl_error"
                elif part in ("[PROCESS]", "[DISCOGS]", "[DETAIL]", "[GRID]", "[200 OK]"):
                    tag = "tag_purple"
                elif part == "[DELETE]":
                    tag = "tag_delete"
                elif "├──" in part or "└──" in part:
                    tag = "tree_branch"
                elif re.match(r"^'(?:[^'\\]|\\.)*'\s*:$", part):
                    tag = "json_key"
                elif re.match(r"^'(?:[^'\\]|\\.)*'$", part):
                    tag = "json_val"
                else:
                    tag = "text_body"

                try:
                    raw_textbox.insert("end", part, tag)
                except Exception:
                    log_box.insert("end", part)

        log_box.see("end")
        log_box.configure(state="disabled")

    @staticmethod
    def _clear_console(app):
        """Limpia el historial acumulado y la vista."""
        if hasattr(app, "log_history"):
            app.log_history.clear()
        if getattr(app, "log_textbox", None) and app.log_textbox.winfo_exists():
            app.log_textbox.configure(state="normal")
            app.log_textbox.delete("1.0", "end")
            app.log_textbox.configure(state="disabled")

    @staticmethod
    def _copy_logs_to_clipboard(app):
        """Copia los logs que están visibles según el filtro al portapapeles."""
        history = getattr(app, "log_history", [])
        filter_level = getattr(app, "log_filter_var", None)
        selected_filter = filter_level.get() if filter_level else "TODOS"

        filtered_lines = []
        for item in history:
            level, msg = item if isinstance(item, tuple) else ("INFO", item)
            if selected_filter == "TODOS" or selected_filter == level:
                filtered_lines.append(msg)

        if not filtered_lines:
            return

        app.clipboard_clear()
        app.clipboard_append("\n".join(filtered_lines))
        DialogManager.show_themed_dialog(app, "Copiado", "Logs copiados al portapapeles con éxito.", level="success")

    @staticmethod
    def _export_logs_to_file(app):
        """Exporta el historial de logs filtrado a un archivo de texto .txt."""
        history = getattr(app, "log_history", [])
        if not history:
            DialogManager.show_themed_dialog(app, "Exportar", "No hay logs registrados para exportar.", level="warning")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Guardar historial de logs"
        )

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                for item in history:
                    msg = item[1] if isinstance(item, tuple) else item
                    f.write(msg if msg.endswith("\n") else f"{msg}\n")
            DialogManager.show_themed_dialog(app, "Exportar", f"Logs guardados con éxito en:\n{file_path}", level="success")

    @staticmethod
    def close_logs_dialog(app):
        if app.log_window is not None and app.log_window.winfo_exists():
            app.log_window.destroy()
        app.log_window = None
        app.log_textbox = None

    @staticmethod
    def open_unified_catalog_manager(app):
        win = DialogManager._new_modal(app, "Gestor Unificado de Catálogos", 820, 600)

        font_btn = ctk.CTkFont(size=12, weight="bold")

        lbl_header = ctk.CTkLabel(
            win,
            text="Gestión de Catálogos y Relaciones",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_header.pack(anchor="w", padx=16, pady=(16, 4))

        lbl_sub = ctk.CTkLabel(
            win,
            text="Añade o elimina valores y asigna jerarquías entre ellos.",
            text_color=theme.TEXT_MUTED
        )
        lbl_sub.pack(anchor="w", padx=16, pady=(0, 4))

        corp_color = getattr(app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(app, "CORP_HOVER", theme.PRIMARY_HOVER)

        tabview = ctk.CTkTabview(
            win,
            segmented_button_fg_color=theme.BG_INPUT,
            segmented_button_selected_color=corp_color,
            segmented_button_selected_hover_color=corp_hover,
            segmented_button_unselected_color=theme.BG_CARD_HOVER,
            segmented_button_unselected_hover_color=theme.BORDER_FOCUS,
            text_color=theme.TEXT_MAIN
        )
        tabview.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        def prompt_for_value(title, prompt_text, default_value=""):
            result = [None]
            dlg = DialogManager._new_modal(app, title, 400, 150, parent=win)

            ctk.CTkLabel(dlg, text=prompt_text, text_color=theme.TEXT_MAIN, font=ctk.CTkFont(weight="bold")).pack(pady=(15, 5))

            entry = ctk.CTkEntry(dlg, width=320)
            entry.pack(pady=5)
            if default_value:
                entry.insert(0, default_value)

            entry.focus_force()

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

        def delete_value(k, lb, lname):
            selected = lb.curselection()
            if not selected:
                DialogManager.show_themed_dialog(app, "Selección requerida", "Selecciona al menos un valor para eliminar.", level="warning", parent=win)
                return

            values_to_delete = [app.catalog_manager.catalog_values[k][idx] for idx in selected]

            affected_count = 0
            col_info = app.catalog_manager.get_catalog_column_info(k)
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
            DialogManager.show_themed_dialog(app, "Valores eliminados", f"Se eliminaron {len(values_to_delete)} registro(s).", level="success", parent=win)

        # Se incluye únicamente "Comment" en la gestión de catálogos
        ordered_keys = ["Album", "Genre", "Publisher", "Comment"]

        # Si catalog_manager define campos adicionales no incluidos en la lista por defecto, se añaden al final
        for field in getattr(app.catalog_manager, "catalog_fields", ()):
            if field not in ordered_keys:
                ordered_keys.append(field)

        for catalog_key in ordered_keys:
            if catalog_key not in app.catalog_manager.catalog_fields:
                continue

            label_name = app.catalog_manager.catalog_labels.get(catalog_key, catalog_key)
            tab = tabview.add(label_name)

            content_frame = ctk.CTkFrame(tab, fg_color="transparent")
            content_frame.pack(fill="both", expand=True)

            left_panel = ctk.CTkFrame(content_frame, fg_color="transparent")
            left_panel.pack(side="left", fill="both", expand=True, padx=(0, 6))

            listbox_frame = ctk.CTkFrame(left_panel, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CONTROL)
            listbox_frame.pack(fill="both", expand=True, pady=(0, 10))

            lb = tk.Listbox(
                listbox_frame,
                bg=theme.BG_CARD,
                fg=theme.TEXT_MAIN,
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

            ctk.CTkButton(
                btns,
                text="Añadir",
                font=font_btn,
                command=lambda k=catalog_key, l=lb, ln=label_name: add_value(k, l, ln),
                fg_color=app.CORP_COLOR,
                hover_color=app.CORP_HOVER
            ).pack(side="left", expand=True, fill="x", padx=(0, 4))

            ctk.CTkButton(
                btns,
                text="Eliminar",
                font=font_btn,
                command=lambda k=catalog_key, l=lb, ln=label_name: delete_value(k, l, ln),
                fg_color="transparent",
                border_width=1,
                border_color=theme.STATUS_DANGER,
                text_color=theme.TEXT_MAIN,
                hover_color=theme.STATUS_DANGER_HOVER
            ).pack(side="left", expand=True, fill="x", padx=(4, 0))

            refresh_listbox(catalog_key, lb)

            if catalog_key in ("Album", "Genre"):
                right_panel = ctk.CTkFrame(content_frame, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_CONTROL)
                right_panel.pack(side="right", fill="both", expand=True, padx=(6, 0))

                rel_title = "Géneros permitidos para los elementos seleccionados:" if catalog_key == "Album" else "Etiquetas permitidas para los elementos seleccionados:"
                ctk.CTkLabel(right_panel, text=rel_title, font=ctk.CTkFont(size=11, weight="bold"), anchor="w").pack(fill="x", padx=12, pady=(12, 4))

                check_vars = {}
                btn_rel_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
                btn_rel_frame.pack(fill="x", padx=12, pady=(0, 4))

                ctk.CTkButton(btn_rel_frame, text="Sel. Todo", font=font_btn, height=24, fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS, command=lambda cv=check_vars: [v.set(True) for v in cv.values()]).pack(side="left", expand=True, fill="x", padx=(0, 2))
                ctk.CTkButton(btn_rel_frame, text="Desel. Todo", font=font_btn, height=24, fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS, command=lambda cv=check_vars: [v.set(False) for v in cv.values()]).pack(side="left", expand=True, fill="x", padx=(2, 0))

                scroll_rel = ctk.CTkScrollableFrame(right_panel, fg_color="transparent")
                scroll_rel.pack(fill="both", expand=True, padx=8, pady=4)

                def load_relations(event=None, k=catalog_key, listbox=lb, scroll=scroll_rel, cvars=check_vars):
                    for w in scroll.winfo_children():
                        w.destroy()
                    cvars.clear()

                    sel = listbox.curselection()
                    if not sel:
                        ctk.CTkLabel(scroll, text="Selecciona al menos un registro a la izquierda", text_color=theme.TEXT_SUBTLE, font=ctk.CTkFont(size=11)).pack(pady=20)
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
                    DialogManager.show_themed_dialog(app, "Relaciones guardadas", msg, level="success", parent=win)

                lb.bind("<<ListboxSelect>>", load_relations)

                btn_save_rel = ctk.CTkButton(right_panel, text="Guardar Relaciones", font=font_btn, command=save_relations, fg_color=app.CORP_COLOR, hover_color=app.CORP_HOVER, height=32)
                btn_save_rel.pack(fill="x", padx=12, pady=12)
                load_relations()

        # Footer / Salida
        footer_bar = ctk.CTkFrame(win, fg_color="transparent")
        footer_bar.pack(fill="x", padx=16, pady=(0, 16))

        btn_close_panel = ctk.CTkButton(
            footer_bar,
            text="Cerrar Panel",
            font=font_btn,
            command=win.destroy,
            fg_color=theme.BG_CARD_HOVER,
            border_color=theme.BORDER_FOCUS,
            border_width=1,
            text_color=theme.TEXT_MUTED,
            hover_color=theme.BORDER_FOCUS,
            height=32,
            width=120
        )
        btn_close_panel.pack(side="right")
        btn_close_panel.focus_force()

    @staticmethod
    def process_pending_covers_dialog(app, items_to_review):
        if not items_to_review:
            return {}

        dialog = MultiCoverSelectionDialog(app, items_to_review)
        app.wait_window(dialog)
        return dialog.selections

