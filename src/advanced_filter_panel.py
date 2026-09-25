import customtkinter as ctk
from models import AdvancedFilterCriteria
import theme

RATING_OPTIONS = ["Todos", "0★", "1★", "2★", "3★", "4★", "5★"]
# Rótulos del panel en castellano, los mismos que las cabeceras de la tabla.
FIELD_LABELS = {
    "Search": ("BÚSQUEDA LIBRE", "Buscar en toda la lista..."),
    "Artist": ("INTÉRPRETE", "Buscar intérprete..."),
    "Title": ("TÍTULO", "Buscar título..."),
    "MixArtist": ("REMIX", "Buscar remix..."),
    "Album": ("ÁLBUM", None),
    "Genre": ("GÉNERO", None),
    "Publisher": ("ETIQUETA", None),
    "Year": ("AÑO", None),
    "Rating": ("RATING", None),
}



class AdvancedFilterPanel(ctk.CTkFrame):
    def __init__(self, parent, app, on_filter_change_callback, **kwargs):
        super().__init__(parent, **kwargs)
        self.app = app
        self.on_filter_change = on_filter_change_callback

        # Configuración estética del panel
        self.configure(fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD, border_width=1, border_color=theme.BORDER_QUIET)

        # Variables de control
        self.text_vars = {
            "Artist": ctk.StringVar(),
            "Title": ctk.StringVar(),
            "MixArtist": ctk.StringVar(),
        }

        self.combo_vars = {
            "Album": ctk.StringVar(value="Todos"),
            "Genre": ctk.StringVar(value="Todos"),
            "Publisher": ctk.StringVar(value="Todos"),
            "Year": ctk.StringVar(value="Todos"),
            "Rating": ctk.StringVar(value="Todos"),
        }

        self.toggle_vars = {
            "no_year": ctk.BooleanVar(value=False),
            "no_cover": ctk.BooleanVar(value=False),
            "no_comment": ctk.BooleanVar(value=False),
            "no_cues": ctk.BooleanVar(value=False),
        }

        self._filter_debounce_id = None

        self._build_ui()

    def _build_ui(self):
        # Fila 1: Campos de Texto Libre
        frame_text = ctk.CTkFrame(self, fg_color="transparent")
        frame_text.pack(fill="x", padx=10, pady=(8, 4))

        # Búsqueda libre: el mismo texto que el buscador de la cabecera (Ctrl+F). No
        # usa textvariable (rompería el placeholder de CTkEntry): se sincroniza con
        # SearchManager.search_var en connect_search().
        sub_frame = ctk.CTkFrame(frame_text, fg_color="transparent")
        sub_frame.pack(side="left", expand=True, fill="x", padx=4)
        ctk.CTkLabel(
            sub_frame, text=FIELD_LABELS["Search"][0], font=(theme.FONT_FAMILY, 10, "bold"), text_color=theme.TEXT_MUTED
        ).pack(anchor="w", pady=(0, 2))
        self.entry_search = ctk.CTkEntry(
            sub_frame,
            placeholder_text=FIELD_LABELS["Search"][1],
            height=28,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_QUIET
        )
        self.entry_search.pack(fill="x")
        self.entry_search.bind("<KeyRelease>", self._on_search_key_release)

        for col_name in ("Artist", "Title", "MixArtist"):
            sub_frame = ctk.CTkFrame(frame_text, fg_color="transparent")
            sub_frame.pack(side="left", expand=True, fill="x", padx=4)

            lbl = ctk.CTkLabel(sub_frame, text=FIELD_LABELS[col_name][0], font=(theme.FONT_FAMILY, 10, "bold"), text_color=theme.TEXT_MUTED)
            lbl.pack(anchor="w", pady=(0, 2))

            entry = ctk.CTkEntry(
                sub_frame,
                textvariable=self.text_vars[col_name],
                placeholder_text=FIELD_LABELS[col_name][1],
                height=28,
                fg_color=theme.BG_INPUT,
                border_color=theme.BORDER_QUIET
            )
            entry.pack(fill="x")

            # Guardar referencia explícita del campo Artist para asignarle el foco
            if col_name == "Artist":
                self.entry_artist = entry

            self.text_vars[col_name].trace_add("write", self._on_text_changed)

        # Fila 2: Campos de Catálogo (Combos)
        frame_combos = ctk.CTkFrame(self, fg_color="transparent")
        frame_combos.pack(fill="x", padx=10, pady=4)

        for col_name in ("Album", "Genre", "Publisher", "Year", "Rating"):
            sub_frame = ctk.CTkFrame(frame_combos, fg_color="transparent")
            sub_frame.pack(side="left", expand=True, fill="x", padx=4)

            lbl = ctk.CTkLabel(sub_frame, text=FIELD_LABELS[col_name][0], font=(theme.FONT_FAMILY, 10, "bold"), text_color=theme.TEXT_MUTED)
            lbl.pack(anchor="w", pady=(0, 2))

            initial_values = RATING_OPTIONS if col_name == "Rating" else ["Todos"]
            combo = ctk.CTkComboBox(
                sub_frame,
                variable=self.combo_vars[col_name],
                values=initial_values,
                height=28,
                fg_color=theme.BG_INPUT,
                button_color=theme.BORDER_QUIET,
                border_color=theme.BORDER_QUIET,
                state="readonly",
                command=lambda val: self._trigger_filter()
            )
            combo.pack(fill="x")

            # Vincular el clic en el Entry interno para desplegar el menú
            combo._entry.bind("<Button-1>", lambda event, c=combo: self._open_combo_menu(c))

            setattr(self, f"combo_{col_name.lower()}", combo)

        # Fila 3: Toggles rápidos + Botón de Limpiar
        frame_toggles = ctk.CTkFrame(self, fg_color="transparent")
        frame_toggles.pack(fill="x", padx=10, pady=(4, 8))

        sw_year = ctk.CTkSwitch(
            frame_toggles,
            text="Sin año",
            variable=self.toggle_vars["no_year"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_year.pack(side="left", padx=(4, 15))

        sw_cover = ctk.CTkSwitch(
            frame_toggles,
            text="Sin carátula",
            variable=self.toggle_vars["no_cover"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_cover.pack(side="left", padx=theme.SPACE_MD)

        sw_comment = ctk.CTkSwitch(
            frame_toggles,
            text="Sin comentarios",
            variable=self.toggle_vars["no_comment"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_comment.pack(side="left", padx=theme.SPACE_MD)

        sw_cues = ctk.CTkSwitch(
            frame_toggles,
            text="Sin cues",
            variable=self.toggle_vars["no_cues"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_cues.pack(side="left", padx=theme.SPACE_MD)

        btn_reset = theme.style_reset_button(ctk.CTkButton(
            frame_toggles,
            text="Limpiar filtros",
            width=110,
            height=26,
            corner_radius=theme.RADIUS_CONTROL,
            command=self.reset_filters
        ))
        btn_reset.pack(side="right", padx=4)

    def connect_search(self, search_manager):
        """Enlaza el campo de búsqueda libre con SearchManager (se llama cuando
        App ya lo ha creado)."""
        self._search_manager = search_manager
        search_manager.add_text_listener(self._on_search_text_changed)

    def _on_search_key_release(self, _event=None):
        manager = getattr(self, "_search_manager", None)
        if manager is not None:
            manager.set_search_text(self.entry_search.get())

    def _on_search_text_changed(self, text):
        if self.entry_search.get() != text:
            self.entry_search.delete(0, "end")
            if text:
                self.entry_search.insert(0, text)

    def focus_artist_field(self):
        """Foco inicial al abrir el panel: el campo de búsqueda libre."""
        self.entry_search.focus_set()

    def toggle_panel(self, event=None):
        """Conmuta la visibilidad del panel. Está disponible en las 3 vistas: se
        coloca encima de la vista activa (ver App.get_active_page)."""
        grid = getattr(self.app, "grid_panel", None)

        if self.winfo_ismapped():
            # 1. OCULTAR PANEL
            self.pack_forget()
            if grid:
                grid.filter_panel_visible = False

            if grid and hasattr(grid, "tree") and getattr(self.app, "_active_view", "collection") == "collection":
                tree = grid.tree
                tree.focus_set()

                selected = tree.selection()
                if selected:
                    tree.focus(selected[0])
                else:
                    children = tree.get_children('')
                    if children:
                        tree.focus(children[0])
        else:
            # 2. MOSTRAR PANEL: encima de la página activa (Colección, Dashboard o
            # Salud). Las páginas se re-empaquetan al cambiar de vista y quedan
            # siempre detrás de él; el tree_container no se toca.
            page = self.app.get_active_page() if hasattr(self.app, "get_active_page") else None
            if page is not None:
                self.pack(side="top", fill="x", pady=(0, theme.SPACE_SM), before=page)
            else:
                self.pack(side="top", fill="x", pady=(0, theme.SPACE_SM))
            if grid:
                grid.filter_panel_visible = True

            self.update_catalog_options()
            self.after(50, self.focus_artist_field)

        return "break"

    def _open_combo_menu(self, combo_widget):
        """Abre el menú desplegable del CTkComboBox y detiene la propagación del evento."""
        if combo_widget.cget("state") != "disabled":
            combo_widget._open_dropdown_menu()
        return "break"

    def _on_text_changed(self, *args):
        """Manejador explícito para cambios en las variables de texto."""
        if self._filter_debounce_id:
            try:
                self.after_cancel(self._filter_debounce_id)
            except Exception:
                pass

        # Debounce breve para mantener la grilla fluida al escribir.
        self._filter_debounce_id = self.after(120, self._trigger_filter_debounced)

    def _trigger_filter_debounced(self):
        self._filter_debounce_id = None
        self._trigger_filter()

    def update_catalog_options(self):
        """
        Extrae dinámicamente todos los valores distintos presentes en los registros cargados en el Grid,
        manteniendo las opciones por defecto 'Todos' y '(Vacío)'.
        """
        grid = getattr(self.app, "grid_panel", None)
        if not grid or not hasattr(grid, "tree"):
            return

        # Mapeo de columnas a sus opciones extraídas
        column_options = {
            "Album": set(),
            "Genre": set(),
            "Publisher": set(),
            "Year": set()
        }

        # Inspeccionar el estado global de filas cargadas (mapeo maestro)
        all_row_ids = getattr(self.app, "file_paths_map", {}).keys()
        if not all_row_ids:
            all_row_ids = grid.tree.get_children('')

        for row_id in all_row_ids:
            if not grid.tree.exists(row_id):
                continue
            values = grid.tree.item(row_id, "values")
            if not values:
                continue

            row_map = grid.map_row_values(values)
            for col_name in column_options.keys():
                val = str(row_map.get(col_name, "")).strip()
                if val:
                    column_options[col_name].add(val)

        # Actualizar cada widget CTkComboBox
        for col_name, val_set in column_options.items():
            if col_name == "Year":
                # Sin '(Vacío)': para "sin año" ya existe el toggle dedicado.
                sorted_values = sorted(val_set, key=lambda x: (not x.isdigit(), x))
                options = ["Todos"] + sorted_values
            else:
                sorted_values = sorted(val_set, key=lambda x: x.lower())
                options = ["Todos", "(Vacío)"] + sorted_values

            combo_widget = getattr(self, f"combo_{col_name.lower()}", None)
            if combo_widget:
                combo_widget.configure(values=options)

    def _trigger_filter(self):
        if self._filter_debounce_id:
            try:
                self.after_cancel(self._filter_debounce_id)
            except Exception:
                pass
            self._filter_debounce_id = None

        # Reconstruir combos ignorando explícitamente 'Todos'
        active_combos = {}
        for k, v in self.combo_vars.items():
            val = v.get().strip()
            if val and val != "Todos":
                active_combos[k] = val

        active_text = {k: v.get().strip().lower() for k, v in self.text_vars.items() if v.get().strip()}
        active_toggles = {k: v.get() for k, v in self.toggle_vars.items()}

        criteria = AdvancedFilterCriteria(
            text=active_text,
            combo=active_combos,
            toggles=active_toggles,
        )
        self.on_filter_change(criteria)

    def reset_filters(self):
        manager = getattr(self, "_search_manager", None)
        if manager is not None:
            manager.set_search_text("")
        for var in self.text_vars.values():
            var.set("")
        for var in self.combo_vars.values():
            var.set("Todos")
        for var in self.toggle_vars.values():
            var.set(False)
        self._trigger_filter()

        grid = getattr(self.app, "grid_panel", None)
        if grid and hasattr(grid, "clear_health_path_filter"):
            grid.clear_health_path_filter()