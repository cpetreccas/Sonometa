import tkinter as tk
import customtkinter as ctk
from dialogs import DialogManager


class CustomTagPicker(ctk.CTkToplevel):
    """Modal para la selección y gestión de etiquetas personalizadas (Custom Tags)."""

    def __init__(
            self,
            parent,
            row_id=None,
            file_path=None,
            current_tags=None,
            current_comment=None,
            available_tags=None,
            on_save=None,
            on_apply=None,
            **kwargs
    ):
        super().__init__(parent)
        self.app = parent.app if hasattr(parent, "app") else parent
        self.row_id = row_id
        self.file_path = file_path
        self.on_save = on_save or on_apply

        # Capturar etiquetas desde 'current_tags' o 'current_comment' indistintamente
        raw_comment = current_tags if current_tags is not None else current_comment

        if isinstance(raw_comment, str):
            self.current_tags = [t.strip() for t in raw_comment.split(",") if t.strip()]
        elif isinstance(raw_comment, (list, tuple, set)):
            self.current_tags = [str(t).strip() for t in raw_comment if str(t).strip()]
        else:
            self.current_tags = []

        # Recopilar etiquetas disponibles de forma segura
        if available_tags:
            self.available_tags = [str(t).strip() for t in available_tags if str(t).strip()]
        else:
            self.available_tags = self._fetch_tags_from_catalog()

        # Set para comprobación rápida de tags seleccionadas
        self.selected_tags = set(self.current_tags)

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

        # 1. Intentar varios métodos conocidos de obtención
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

        # 2. Intentar lectura directa mediante atributos o diccionarios del CatalogManager
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
        main_frame = ctk.CTkFrame(self, fg_color="#1E1E1E")
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        corp_color = getattr(self.app, "CORP_COLOR", "#6B21A8")
        corp_hover = getattr(self.app, "CORP_HOVER", "#581C87")
        font_btn = ctk.CTkFont(size=12, weight="bold")

        # Cabecera
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="Etiquetas Personalizadas",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#F3F4F6"
        )
        lbl_title.pack(anchor="w", padx=5, pady=(0, 2))

        lbl_sub = ctk.CTkLabel(
            main_frame,
            text="Añade o selecciona las etiquetas que deseas aplicar al archivo.",
            text_color="#9CA3AF"
        )
        lbl_sub.pack(anchor="w", padx=5, pady=(0, 10))

        # Entrada para nueva etiqueta
        add_frame = ctk.CTkFrame(main_frame, fg_color="#262626", corner_radius=8)
        add_frame.pack(fill="x", pady=(0, 10), padx=5, ipady=4)

        lbl_add = ctk.CTkLabel(
            add_frame,
            text="Nueva etiqueta:",
            font=ctk.CTkFont(weight="bold"),
            text_color="#E5E7EB"
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
            text_color="#D1D5DB"
        )
        lbl_list.pack(anchor="w", padx=5, pady=(4, 4))

        self.scroll_tags = ctk.CTkScrollableFrame(main_frame, fg_color="#181818", corner_radius=8)
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
            border_color="#6B7280",
            text_color="#E5E7EB",
            hover_color="#374151",
            command=self.destroy
        )
        btn_cancel.pack(side="right")

    def _render_tag_list(self):
        """Redibuja la lista de tags en el contenedor scrollable y fuerza la selección visual."""
        for child in self.scroll_tags.winfo_children():
            child.destroy()

        corp_color = getattr(self.app, "CORP_COLOR", "#6B21A8")
        corp_hover = getattr(self.app, "CORP_HOVER", "#581C87")

        # Fusionar disponibles y seleccionadas asegurando limpieza de cadenas
        clean_available = [str(t).strip() for t in self.available_tags if str(t).strip()]
        clean_selected = [str(t).strip() for t in self.selected_tags if str(t).strip()]

        all_tags = sorted(list(set(clean_available + clean_selected)))

        if not all_tags:
            lbl_empty = ctk.CTkLabel(
                self.scroll_tags,
                text="No hay etiquetas creadas. Añade una arriba.",
                text_color="#6B7280",
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

            # Forzar explícitamente el estado visual en CustomTkinter
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
        # Generar lista ordenada manteniendo formato
        final_tags = sorted(list(self.selected_tags))
        comment_str = ", ".join(final_tags)

        if callable(self.on_save):
            try:
                self.on_save(self.row_id, self.file_path, comment_str)
            except TypeError:
                try:
                    target = self.row_id if self.row_id is not None else self.file_path
                    self.on_save(target, comment_str)
                except TypeError:
                    try:
                        self.on_save(comment_str)
                    except TypeError:
                        self.on_save()

        self.grab_release()
        self.destroy()