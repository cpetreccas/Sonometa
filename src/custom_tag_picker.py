import tkinter as tk
import customtkinter as ctk
from dialogs import DialogManager
import theme


class CustomTagPicker(ctk.CTkToplevel):
    """Modal para la selección y gestión de etiquetas personalizadas (Custom Tags) con soporte multiselección."""

    def __init__(
            self,
            parent,
            row_id=None,
            file_path=None,
            current_tags=None,
            current_comment=None,
            row_ids=None,
            file_paths=None,
            union_tags=None,
            available_tags=None,
            on_save=None,
            on_apply=None,
            **kwargs
    ):
        super().__init__(parent)
        self.app = parent.app if hasattr(parent, "app") else parent
        self.on_save = on_save or on_apply

        # Soporte para múltiples filas/archivos
        if row_ids is not None:
            self.row_ids = row_ids
            self.file_paths = file_paths or []
        elif row_id is not None:
            self.row_ids = [row_id]
            self.file_paths = [file_path] if file_path else []
        else:
            self.row_ids = []
            self.file_paths = []

        # Determinar etiquetas iniciales (Unión de todas las etiquetas de los archivos seleccionados)
        if union_tags is not None:
            raw_comment = union_tags
        else:
            raw_comment = current_tags if current_tags is not None else current_comment

        if isinstance(raw_comment, str):
            init_tags = [t.strip() for t in raw_comment.split(",") if t.strip()]
        elif isinstance(raw_comment, (list, tuple, set)):
            init_tags = [str(t).strip() for t in raw_comment if str(t).strip()]
        else:
            init_tags = []

        # Mantener registro de la unión original para saber qué tags fueron desmarcados explicitamente
        self.initial_union_tags = set(init_tags)
        self.selected_tags = set(init_tags)

        # Recopilar etiquetas disponibles desde el catálogo
        if available_tags:
            self.available_tags = [str(t).strip() for t in available_tags if str(t).strip()]
        else:
            self.available_tags = self._fetch_tags_from_catalog()

        self.title("Selección de Etiquetas Personalizadas - Sonometa")
        self.geometry("520x480")
        self.minsize(460, 400)

        self._setup_ui()

        # Atajo ESC para cerrar
        self.bind("<Escape>", lambda event: self.destroy())

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=520, height=480)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)

        self.after(50, self._set_initial_focus)

    def _fetch_tags_from_catalog(self):
        """Intenta extraer las etiquetas de Comment probando los métodos/atributos de CatalogManager."""
        cm = getattr(self.app, "catalog_manager", None)
        if not cm:
            return []

        tags = set()

        for method_name in ["get_catalog_values", "get_catalog_combo_values", "get_catalog", "get_values", "get_items", "get_options"]:
            if hasattr(cm, method_name) and callable(getattr(cm, method_name)):
                getter = getattr(cm, method_name)
                try:
                    res = getter("Comment")
                    if res:
                        tags.update(res if isinstance(res, (list, tuple, set)) else [res])
                except Exception:
                    pass
                if tags:
                    return sorted([str(t).strip() for t in tags if t and t != getattr(self.app, "CLEAR_OPTION", "--- Vaciar ---")])

        for attr_name in ["catalog_values", "catalogs", "catalog", "data", "categories", "_catalogs", "_data"]:
            cat_data = getattr(cm, attr_name, None)
            if isinstance(cat_data, dict):
                val = cat_data.get("Comment")
                if isinstance(val, (list, tuple, set)):
                    tags.update(val)
                elif isinstance(val, dict):
                    tags.update(val.keys())

        clear_opt = getattr(self.app, "CLEAR_OPTION", "--- Vaciar ---")
        return sorted([str(t).strip() for t in tags if t and t != clear_opt])

    def _set_initial_focus(self):
        self.focus_force()
        if hasattr(self, "entry_new_tag") and self.entry_new_tag.winfo_exists():
            self.entry_new_tag.focus_force()

    def _setup_ui(self):
        main_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)
        font_btn = ctk.CTkFont(size=12, weight="bold")

        # Cabecera
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Etiquetas Personalizadas",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_title.pack(anchor="w", padx=5, pady=(0, 2))

        count_files = len(self.row_ids)
        sub_text = (
            f"Añade o selecciona etiquetas a aplicar en los {count_files} archivos seleccionados."
            if count_files > 1 else
            "Añade o selecciona las etiquetas que deseas aplicar al archivo."
        )

        lbl_sub = ctk.CTkLabel(
            main_frame,
            text=sub_text,
            text_color=theme.TEXT_MUTED
        )
        lbl_sub.pack(anchor="w", padx=5, pady=(0, 10))

        # Entrada para nueva etiqueta
        add_frame = ctk.CTkFrame(main_frame, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
        add_frame.pack(fill="x", pady=(0, 10), padx=5, ipady=4)

        lbl_add = ctk.CTkLabel(
            add_frame,
            text="Nueva etiqueta:",
            font=ctk.CTkFont(weight="bold"),
            text_color=theme.TEXT_MAIN
        )
        lbl_add.pack(side="left", padx=(10, 8))

        self.entry_new_tag = ctk.CTkEntry(
            add_frame,
            placeholder_text="Escribe y pulsa Enter o Añadir..."
        )
        self.entry_new_tag.pack(side="left", fill="x", expand=True, padx=(0, 8), pady=6)
        self.entry_new_tag.bind("<Return>", lambda event: self._add_custom_tag())

        btn_add = ctk.CTkButton(
            add_frame,
            text="Añadir",
            width=80,
            font=font_btn,
            fg_color=corp_color,
            hover_color=corp_hover,
            command=self._add_custom_tag
        )
        btn_add.pack(side="right", padx=(0, 10))

        # Panel Scrollable con las etiquetas
        lbl_list = ctk.CTkLabel(
            main_frame,
            text="Etiquetas disponibles:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.TEXT_MUTED
        )
        lbl_list.pack(anchor="w", padx=5, pady=(4, 4))

        self.scroll_tags = ctk.CTkScrollableFrame(main_frame, fg_color=theme.BG_INPUT, corner_radius=theme.RADIUS_CONTROL)
        self.scroll_tags.pack(fill="both", expand=True, padx=5, pady=(0, 12))

        self.checkbox_vars = {}
        self._render_tag_list()

        # Botones Inferiores
        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        btn_apply = ctk.CTkButton(
            btn_bar,
            text="Aplicar",
            font=font_btn,
            fg_color=corp_color,
            hover_color=corp_hover,
            command=self._on_apply
        )
        btn_apply.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancelar",
            font=font_btn,
            fg_color="transparent",
            border_width=1,
            border_color=theme.BORDER_QUIET,
            text_color=theme.TEXT_MAIN,
            hover_color=theme.BG_CARD_HOVER,
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def _render_tag_list(self):
        """Redibuja la lista de tags en el contenedor scrollable."""
        for child in self.scroll_tags.winfo_children():
            child.destroy()

        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)

        clean_available = [str(t).strip() for t in self.available_tags if str(t).strip()]
        clean_selected = [str(t).strip() for t in self.selected_tags if str(t).strip()]

        all_tags = sorted(list(set(clean_available + clean_selected)))

        if not all_tags:
            lbl_empty = ctk.CTkLabel(
                self.scroll_tags,
                text="No hay etiquetas creadas. Añade una arriba.",
                text_color=theme.TEXT_SUBTLE,
                font=ctk.CTkFont(size=11)
            )
            lbl_empty.pack(pady=20)
            return

        for tag in all_tags:
            is_checked = tag in self.selected_tags
            var = tk.BooleanVar(value=is_checked)
            self.checkbox_vars[tag] = var

            chk_frame = ctk.CTkFrame(self.scroll_tags, fg_color="transparent")
            chk_frame.pack(fill="x", padx=8, pady=3)

            chk = ctk.CTkCheckBox(
                chk_frame,
                text=tag,
                variable=var,
                font=ctk.CTkFont(size=12),
                fg_color=corp_color,
                hover_color=corp_hover,
                command=lambda t=tag, v=var: self._toggle_tag(t, v)
            )

            if is_checked:
                chk.select()
            else:
                chk.deselect()

            chk.pack(side="left", anchor="w")

    def _toggle_tag(self, tag, var):
        if var.get():
            self.selected_tags.add(tag)
        else:
            self.selected_tags.discard(tag)

    def _add_custom_tag(self):
        new_tag = self.entry_new_tag.get().strip()
        if not new_tag:
            return

        if new_tag not in self.available_tags:
            self.available_tags.append(new_tag)

        self.selected_tags.add(new_tag)
        self.entry_new_tag.delete(0, tk.END)

        cm = getattr(self.app, "catalog_manager", None)
        if cm:
            for method_name in ["add_catalog_value", "add_value", "add_item"]:
                if hasattr(cm, method_name) and callable(getattr(cm, method_name)):
                    try:
                        getattr(cm, method_name)("Comment", new_tag, persist=True, is_user_action=True)
                        break
                    except TypeError:
                        try:
                            getattr(cm, method_name)("Comment", new_tag)
                            break
                        except Exception:
                            pass

        self._render_tag_list()

    def _on_apply(self):
        active_tags = set(self.selected_tags)
        removed_tags = self.initial_union_tags - active_tags

        if callable(self.on_save):
            # Probar primero la firma para multiselección (row_ids, file_paths, active_tags, removed_tags)
            try:
                self.on_save(
                    row_ids=self.row_ids,
                    file_paths=self.file_paths,
                    active_tags=active_tags,
                    removed_tags=removed_tags
                )
            except TypeError:
                # Fallback para firmas simples un solo archivo (row_id, file_path, comment_str)
                final_tags = sorted(list(active_tags))
                comment_str = ", ".join(final_tags)
                r_id = self.row_ids[0] if self.row_ids else None
                f_path = self.file_paths[0] if self.file_paths else None

                try:
                    self.on_save(r_id, f_path, comment_str)
                except TypeError:
                    try:
                        self.on_save(r_id or f_path, comment_str)
                    except TypeError:
                        self.on_save(comment_str)

        self.grab_release()
        self.destroy()