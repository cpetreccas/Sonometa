import customtkinter as ctk
from models import AdvancedFilterCriteria
import theme


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
            "Album": ctk.StringVar(value="[ Todos ]"),
            "Genre": ctk.StringVar(value="[ Todos ]"),
            "Publisher": ctk.StringVar(value="[ Todos ]"),
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

        for col_name in ("Artist", "Title", "MixArtist"):
            sub_frame = ctk.CTkFrame(frame_text, fg_color="transparent")
            sub_frame.pack(side="left", expand=True, fill="x", padx=4)

            lbl = ctk.CTkLabel(sub_frame, text=col_name.upper(), font=(theme.FONT_FAMILY, 10, "bold"), text_color=theme.TEXT_MUTED)
            lbl.pack(anchor="w", pady=(0, 2))

            entry = ctk.CTkEntry(
                sub_frame,
                textvariable=self.text_vars[col_name],
                placeholder_text=f"Buscar {col_name}...",
                height=28,
                fg_color=theme.BG_INPUT,
                border_color=theme.BORDER_FOCUS
            )
            entry.pack(fill="x")

            # Guardar referencia explícita del campo Artist para asignarle el foco
            if col_name == "Artist":
                self.entry_artist = entry

            self.text_vars[col_name].trace_add("write", self._on_text_changed)

        # Fila 2: Campos de Catálogo (Combos)
        frame_combos = ctk.CTkFrame(self, fg_color="transparent")
        frame_combos.pack(fill="x", padx=10, pady=4)

        for col_name in ("Album", "Genre", "Publisher"):
            sub_frame = ctk.CTkFrame(frame_combos, fg_color="transparent")
            sub_frame.pack(side="left", expand=True, fill="x", padx=4)

            lbl = ctk.CTkLabel(sub_frame, text=col_name.upper(), font=(theme.FONT_FAMILY, 10, "bold"), text_color=theme.TEXT_MUTED)
            lbl.pack(anchor="w", pady=(0, 2))

            combo = ctk.CTkComboBox(
                sub_frame,
                variable=self.combo_vars[col_name],
                values=["[ Todos ]"],
                height=28,
                fg_color=theme.BG_INPUT,
                button_color=theme.BORDER_FOCUS,
                border_color=theme.BORDER_FOCUS,
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
            text="Sin Año",
            variable=self.toggle_vars["no_year"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_year.pack(side="left", padx=(4, 15))

        sw_cover = ctk.CTkSwitch(
            frame_toggles,
            text="Sin Carátula",
            variable=self.toggle_vars["no_cover"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_cover.pack(side="left", padx=15)

        sw_comment = ctk.CTkSwitch(
            frame_toggles,
            text="Sin Comentarios",
            variable=self.toggle_vars["no_comment"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_comment.pack(side="left", padx=15)

        sw_cues = ctk.CTkSwitch(
            frame_toggles,
            text="Sin Cues",
            variable=self.toggle_vars["no_cues"],
            command=self._trigger_filter,
            progress_color=theme.PRIMARY,
            font=(theme.FONT_FAMILY, 11)
        )
        sw_cues.pack(side="left", padx=15)

        btn_reset = ctk.CTkButton(
            frame_toggles,
            text="Limpiar Filtros",
            width=110,
            height=26,
            fg_color="transparent",
            border_width=1,
            border_color=theme.BORDER_QUIET,
            text_color=theme.TEXT_MAIN,
            hover_color=theme.BG_CARD_HOVER,
            corner_radius=theme.RADIUS_CONTROL,
            command=self.reset_filters
        )
        btn_reset.pack(side="right", padx=4)

    def focus_artist_field(self):
        """Asigna el foco de teclado al campo de entrada de Artist."""
        if hasattr(self, "entry_artist"):
            self.entry_artist.focus_set()

    def toggle_panel(self, event=None):
        """Conmuta la visibilidad del panel sobre la tabla principal y gestiona el foco."""
        grid = getattr(self.app, "grid_panel", None)

        if self.winfo_ismapped():
            # 1. OCULTAR PANEL
            self.pack_forget()
            if grid:
                grid.filter_panel_visible = False

            if grid and hasattr(grid, "tree"):
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
            # 2. MOSTRAR PANEL: insertarlo por encima de la tabla sin tocar el tree_container
            if grid and hasattr(grid, "tree_container"):
                self.pack(side="top", fill="x", padx=6, pady=(6, 2), before=grid.tree_container)
                grid.filter_panel_visible = True
            else:
                self.pack(side="top", fill="x", pady=(0, 5))

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
        manteniendo las opciones por defecto '[ Todos ]' y '[ Vacío ]'.
        """
        grid = getattr(self.app, "grid_panel", None)
        if not grid or not hasattr(grid, "tree"):
            return

        # Mapeo de columnas a sus opciones extraídas
        column_options = {
            "Album": set(),
            "Genre": set(),
            "Publisher": set()
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
            sorted_values = sorted(list(val_set), key=lambda x: x.lower())
            options = ["[ Todos ]", "[ Vacío ]"] + sorted_values

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

        # Reconstruir combos ignorando explícitamente '[ Todos ]'
        active_combos = {}
        for k, v in self.combo_vars.items():
            val = v.get().strip()
            if val and val != "[ Todos ]":
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
        for var in self.text_vars.values():
            var.set("")
        for var in self.combo_vars.values():
            var.set("[ Todos ]")
        for var in self.toggle_vars.values():
            var.set(False)
        self._trigger_filter()