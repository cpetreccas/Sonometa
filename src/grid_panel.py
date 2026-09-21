import os
import sys
import tkinter as tk
import unicodedata
from tkinter import ttk
import customtkinter as ctk
from undo_manager import HistoryAction
from log_handler import LogManager
from advanced_filter_panel import AdvancedFilterPanel
from models import AdvancedFilterCriteria
from tree_row_utils import build_column_index, get_row_value, set_row_value, map_row_values, build_row_values
from ui_utils import UiUtils
import theme


class _CellEditSession:
    """Estado de una edición de celda en curso, compartido entre los pasos de guardado/navegación."""

    __slots__ = (
        "entry", "row_id", "col_index", "col_name", "current_value_str",
        "allowed_values_for_validation", "finalized", "pending_nav",
    )

    def __init__(self, entry, row_id, col_index, col_name, current_value_str, allowed_values_for_validation):
        self.entry = entry
        self.row_id = row_id
        self.col_index = col_index
        self.col_name = col_name
        self.current_value_str = current_value_str
        self.allowed_values_for_validation = allowed_values_for_validation
        self.finalized = False
        self.pending_nav = {"dir": None}


class GridPanel:
    MANAGED_GRID_FIELDS = frozenset({"Album", "Genre", "Publisher"})

    def __init__(self, app, parent, logger):
        self.app = app
        self.parent = parent
        self.logger = logger

        # Pivote para selecciones con Shift estilo Excel
        self._shift_pivot_row = None
        self._last_edited_col = 0

        # Cerrojo unificado para evitar ráfagas de teclado (Auto-repeat debounce)
        self._nav_lock = False

        # Variables para el reordenamiento de columnas por arrastre (Drag & Drop)
        self._drag_col = None
        self._drag_x = 0

        # Fila actualmente resaltada por hover del ratón
        self._hovered_row_id = None
        self._hovered_row_original_tags = ()

        # Estado del Panel de Filtro Avanzado
        self.filter_panel_visible = False
        self.active_filters = {}
        self._advanced_criteria = AdvancedFilterCriteria()

        # Configuración del nivel de zoom base
        self.zoom_level = 1.0
        self.BASE_FONT_SIZE = 9
        self.BASE_ROW_HEIGHT = 28
        self.col_titles = {
            "Filename": "NOMBRE DE ARCHIVO",
            "Artist": "INTÉRPRETE",
            "Title": "TÍTULO",
            "MixArtist": "REMIX",
            "Album": "ÁLBUM",
            "Genre": "GÉNERO",
            "Publisher": "ETIQUETA",
            "Year": "AÑO",
            "Cues": "CUES",
            "Rating": "RATING",
            "Cover": "CARÁTULA"
        }

        # Configuración base de columnas (sin Comment ni Comment2)
        self.base_col_config = {
            "Filename":  {"width": 280, "minwidth": 180, "stretch": True,  "anchor": "w"},
            "Artist":    {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "Title":     {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "MixArtist": {"width": 160, "minwidth": 100, "stretch": True,  "anchor": "w"},
            "Album":     {"width": 100, "minwidth": 70,  "stretch": False, "anchor": "w"},
            "Genre":     {"width": 70,  "minwidth": 50,  "stretch": False, "anchor": "w"},
            "Publisher": {"width": 120, "minwidth": 80,  "stretch": False, "anchor": "w"},
            "Year":      {"width": 40,  "minwidth": 40,  "stretch": False, "anchor": "center"},
            "Comment":   {"width": 0,   "minwidth": 0,   "stretch": False, "anchor": "w"},
            "Cues":      {"width": 58,  "minwidth": 50,  "stretch": False, "anchor": "center"},
            "Rating":    {"width": 64,  "minwidth": 58,  "stretch": False, "anchor": "center"},
            "Cover":     {"width": 73,  "minwidth": 73,  "stretch": False, "anchor": "center"}
        }

        self.frame_grid = ctk.CTkFrame(self.parent, fg_color=theme.BG_CARD)
        self.frame_grid.pack(side="top", fill="both", expand=True, padx=0, pady=0)

        # Usar pack para permitir intercalar el panel desplegable arriba de la grilla
        self._setup_styles()

        # Instanciación del Panel de Filtro Avanzado
        self.filter_panel = AdvancedFilterPanel(
            parent=self.frame_grid,
            app=self.app,
            on_filter_change_callback=self.apply_advanced_filters
        )

        # Contenedor para Treeview y Scrollbars
        self.tree_container = ctk.CTkFrame(self.frame_grid, fg_color="transparent")
        self.tree_container.pack(fill="both", expand=True)
        self.tree_container.grid_rowconfigure(0, weight=1)
        self.tree_container.grid_columnconfigure(0, weight=1)

        self._build_treeview()
        self._setup_context_menu()
        self.cell_entry = None
        self._active_cell_tab_navigator = None
        self._editor_bindtag = "SonometaGridCellEditor"
        self._install_editor_bindtag_guard()
        self._install_global_tab_edit_guard()

    def toggle_filter_panel(self):
        """Muestra u oculta el panel de filtro avanzado sin tocar el contenedor del Treeview."""
        if self.filter_panel_visible:
            self.filter_panel.pack_forget()
            self.filter_panel_visible = False
        else:
            # Insertar el panel justo antes de la tabla para mantener intacta su jerarquia y eventos.
            self.filter_panel.pack(side="top", fill="x", padx=6, pady=(6, 2), before=self.tree_container)

            self.filter_panel_visible = True
            self.filter_panel.update_catalog_options()
            self.filter_panel.after(50, self.filter_panel.focus_artist_field)

        return "break"

    def apply_advanced_filters(self, criteria):
        """Recibe el criterio del panel, sobrescribe el estado previo por completo y filtra."""
        if isinstance(criteria, AdvancedFilterCriteria):
            criteria_obj = criteria
        else:
            criteria_obj = AdvancedFilterCriteria.from_dict(criteria)

        # Sobrescribir estado completo (sin acumular filtros previos)
        self._advanced_criteria = criteria_obj
        self.active_filters = criteria_obj.to_dict()

        self.apply_combined_filters(criteria=criteria_obj)

    @staticmethod
    def _remove_accents(text: str) -> str:
        if not text:
            return ""
        normalized = unicodedata.normalize("NFD", str(text))
        return "".join(c for c in normalized if unicodedata.category(c) != "Mn").lower()

    def _build_row_search_text(self, values, col_index):
        searchable_columns = (
            "Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Comment", "Cues", "Rating"
        )
        parts = []
        for col_name in searchable_columns:
            idx = col_index.get(col_name)
            if idx is None or idx >= len(values):
                continue
            cell_val = values[idx]
            if cell_val is not None:
                parts.append(str(cell_val))
        return self._remove_accents(" ".join(parts))

    def _matches_advanced_criteria(self, values, col_index, criteria_obj: AdvancedFilterCriteria) -> bool:
        text_filters = criteria_obj.text
        combo_filters = criteria_obj.combo
        toggles = criteria_obj.toggles

        cues_raw = str(self.get_value_by_column(values, "Cues", self.get_value_by_column(values, "CUEs", "-"))).strip()
        cues_num = self._parse_cues_value(cues_raw)

        for col_name, search_val in text_filters.items():
            idx = col_index.get(col_name)
            cell_val = str(values[idx]).lower() if idx is not None and idx < len(values) else ""
            if search_val not in cell_val:
                return False

        for col_name, selected_val in combo_filters.items():
            idx = col_index.get(col_name)
            cell_val = str(values[idx]).strip() if idx is not None and idx < len(values) else ""
            if selected_val == "[ Vacío ]":
                if cell_val != "":
                    return False
            elif cell_val != selected_val:
                return False

        if toggles.get("no_year"):
            idx = col_index.get("Year")
            year_val = str(values[idx]).strip() if idx is not None and idx < len(values) else ""
            if year_val not in ("", "0", "None"):
                return False

        if toggles.get("no_cover"):
            idx = col_index.get("Cover")
            cover_val = str(values[idx]).strip().lower() if idx is not None and idx < len(values) else ""
            if cover_val in ("sí", "si", "yes", "true", "1"):
                return False

        if toggles.get("no_comment"):
            idx = col_index.get("Comment")
            comment_val = str(values[idx]).strip() if idx is not None and idx < len(values) else ""
            if comment_val != "":
                return False

        if toggles.get("no_cues") and cues_num > 0:
            return False

        return True

    @staticmethod
    def _parse_cues_value(value: str) -> int:
        raw = str(value or "").strip()
        if raw.isdigit():
            return max(0, int(raw))
        return 0

    @staticmethod
    def _has_active_advanced_filters(criteria_obj: AdvancedFilterCriteria) -> bool:
        if criteria_obj.text or criteria_obj.combo:
            return True
        return any(bool(v) for v in criteria_obj.toggles.values())

    def apply_combined_filters(self, search_query=None, criteria=None):
        """Aplica búsqueda textual y filtro avanzado respetando el orden actual de las columnas."""
        if criteria is not None:
            if isinstance(criteria, AdvancedFilterCriteria):
                criteria_obj = criteria
            else:
                criteria_obj = AdvancedFilterCriteria.from_dict(criteria)
            self._advanced_criteria = criteria_obj
            self.active_filters = criteria_obj.to_dict()
        else:
            criteria_obj = self._advanced_criteria

        if search_query is None:
            raw_query = ""
            if hasattr(self.app, "search_manager") and hasattr(self.app.search_manager, "search_var"):
                raw_query = self.app.search_manager.search_var.get()
            normalized_query = self._remove_accents(str(raw_query).strip())
        else:
            normalized_query = self._remove_accents(str(search_query).strip())

        # 1. Obtener todos los ítems base
        if hasattr(self.app, "file_paths_map") and self.app.file_paths_map:
            all_rows = list(self.app.file_paths_map.keys())
        else:
            all_rows = list(self.tree.get_children(""))

        cols = list(self.tree["columns"])
        col_index = build_column_index(cols)
        visible_rows = []

        # 2. Filtrado de filas
        for row_id in all_rows:
            if not self.tree.exists(row_id):
                continue

            values = self.tree.item(row_id, "values")
            if not values:
                continue

            if normalized_query:
                row_search_text = self._build_row_search_text(values, col_index)
                if normalized_query not in row_search_text:
                    continue

            if not self._matches_advanced_criteria(values, col_index, criteria_obj):
                continue

            visible_rows.append(row_id)

        visible_set = set(visible_rows)
        current_rows = list(self.tree.get_children(""))

        # 3. Ocultar los elementos que no cumplen los filtros
        to_detach = [row_id for row_id in current_rows if row_id not in visible_set]
        if to_detach:
            self.tree.detach(*to_detach)

        # 4. Volver a vincular los visibles que estaban desprendidos
        for row_id in visible_rows:
            if not self.tree.parent(row_id) and row_id not in self.tree.get_children(""):
                self.tree.move(row_id, "", "end")

        # 5. REAPLICAR EL ORDENAMIENTO ACTIVO (SOLUCIÓN CLAVE)
        # Si hay un ordenamiento activo, reaplicarlo respetando su dirección
        self.reapply_current_sort()

        # 6. Re-aplicar colores alternados (zebra striping) tras ordenar
        for idx, row_id in enumerate(self.tree.get_children("")):
            should_tag = "even" if idx % 2 == 0 else "odd"
            self.tree.item(row_id, tags=(should_tag,))

        # 7. Ajustar selección y botones
        current_selection = list(self.tree.selection())
        selected_visible = [row_id for row_id in current_selection if row_id in visible_set]
        if selected_visible != current_selection:
            (self.tree.
             selection_set(selected_visible))

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.refresh_process_button_text(len(selected_visible))
            self.app.detail_panel.on_row_select(None)

        if hasattr(self, "_update_tree_scrollbars"):
            self._update_tree_scrollbars()

        self.logger.info(f"Filtro combinado y ordenación aplicados: {len(visible_rows)} de {len(all_rows)}.")

    def _install_editor_bindtag_guard(self):
        # Captura TAB antes del binding de clase TCombobox/TEntry.
        self.app.bind_class(self._editor_bindtag, "<Tab>", lambda e: self._on_editor_bindtag_tab(e, reverse=False))
        self.app.bind_class(self._editor_bindtag, "<Shift-Tab>", lambda e: self._on_editor_bindtag_tab(e, reverse=True))
        self.app.bind_class(self._editor_bindtag, "<ISO_Left_Tab>", lambda e: self._on_editor_bindtag_tab(e, reverse=True))

    def _on_editor_bindtag_tab(self, event, reverse=False):
        if not (self.cell_entry and self.cell_entry.winfo_exists()):
            return
        if not hasattr(self.cell_entry, "_is_cell_editing"):
            return
        if getattr(self, "_nav_lock", False):
            return "break"

        direction = "shift_tab" if reverse else "tab"
        if callable(self._active_cell_tab_navigator):
            self._active_cell_tab_navigator(direction)
        return "break"

    def _attach_editor_bindtag(self, widget):
        try:
            current = list(widget.bindtags())
            if self._editor_bindtag in current:
                current.remove(self._editor_bindtag)

            if current:
                new_tags = [current[0], self._editor_bindtag] + current[1:]
            else:
                new_tags = [self._editor_bindtag]
            widget.bindtags(tuple(new_tags))
        except Exception:
            pass

    def _install_global_tab_edit_guard(self):
        self.app.bind_all("<KeyPress-Tab>", self._on_global_tab_during_cell_edit, add="+")
        self.app.bind_all("<Shift-KeyPress-Tab>", lambda e: self._on_global_tab_during_cell_edit(e, reverse=True), add="+")
        self.app.bind_all("<ISO_Left_Tab>", lambda e: self._on_global_tab_during_cell_edit(e, reverse=True), add="+")

    def _on_global_tab_during_cell_edit(self, event, reverse=False):
        if not (self.cell_entry and self.cell_entry.winfo_exists()):
            return

        if not hasattr(self.cell_entry, "_is_cell_editing"):
            return

        if getattr(self, "_nav_lock", False):
            return "break"

        direction = "shift_tab" if reverse else "tab"
        if callable(self._active_cell_tab_navigator):
            self._active_cell_tab_navigator(direction)
            return "break"

        return "break"

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        self.tree_edit_combo_style = "Sonometa.TreeEdit.TCombobox"

        try:
            base_layout = style.layout("TCombobox")
            style.layout(self.tree_edit_combo_style, self._remove_combobox_arrow_from_layout(base_layout))
        except Exception:
            pass

        style.configure(
            self.tree_edit_combo_style,
            fieldbackground=theme.BG_CARD,
            background=theme.BG_CARD,
            foreground=theme.TEXT_MAIN,
            selectbackground=theme.BG_CARD,
            selectforeground=theme.TEXT_MAIN,
            arrowcolor=theme.BG_CARD,
            relief="flat",
            borderwidth=0,
            padding=(3, 2)
        )
        style.map(
            self.tree_edit_combo_style,
            fieldbackground=[("readonly", theme.BG_CARD), ("focus", theme.BG_CARD)],
            background=[("readonly", theme.BG_CARD), ("focus", theme.BG_CARD)],
            foreground=[("readonly", theme.TEXT_MAIN), ("focus", theme.TEXT_MAIN)],
            selectbackground=[("readonly", theme.BG_CARD), ("focus", theme.BG_CARD)],
            selectforeground=[("readonly", theme.TEXT_MAIN), ("focus", theme.TEXT_MAIN)],
            arrowcolor=[("readonly", theme.BG_CARD), ("focus", theme.BG_CARD)]
        )

        current_font_size = max(7, int(self.BASE_FONT_SIZE * self.zoom_level))
        current_heading_size = max(8, int(self.BASE_FONT_SIZE * self.zoom_level))
        current_row_height = max(18, int(self.BASE_ROW_HEIGHT * self.zoom_level))

        style.configure(
            "Treeview",
            background=theme.BG_CARD,
            foreground=theme.TEXT_MAIN,
            fieldbackground=theme.BG_CARD,
            rowheight=current_row_height,
            font=(theme.FONT_FAMILY, current_font_size),
            borderwidth=0,
            relief="flat"
        )

        style.configure("Treeview.Item", borderwidth=0, relief="flat", padding=(4, 0))

        style.configure(
            "Treeview.Heading",
            background=theme.BG_MAIN,
            foreground=theme.TEXT_MUTED,
            font=(theme.FONT_FAMILY, current_heading_size, 'bold'),
            borderwidth=1,
            bordercolor=theme.BORDER_QUIET,
            relief="flat",
            padding=(5, 5)
        )

        selection_bg = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        style.map(
            "Treeview",
            background=[('selected', selection_bg)],
            foreground=[('selected', theme.TEXT_ON_PRIMARY)]
        )
        style.map("Treeview.Heading", background=[('active', theme.BG_CARD_HOVER)])

        # Barras de desplazamiento integradas al tema oscuro (en vez del estilo nativo de Windows)
        for orientation in ("Vertical", "Horizontal"):
            scrollbar_style = f"{orientation}.TScrollbar"
            style.configure(
                scrollbar_style,
                background=theme.BORDER_FOCUS,
                troughcolor=theme.BG_CARD,
                bordercolor=theme.BG_CARD,
                arrowcolor=theme.TEXT_MUTED,
                relief="flat",
                borderwidth=0,
                arrowsize=12,
            )
            style.map(
                scrollbar_style,
                background=[("active", theme.PRIMARY_LIGHT), ("pressed", selection_bg)],
                arrowcolor=[("active", theme.TEXT_MAIN)],
            )

    def set_zoom(self, factor):
        if self.cell_entry and self.cell_entry.winfo_exists():
            try:
                self.cell_entry.destroy()
            except Exception:
                pass
            self.cell_entry = None

        self.zoom_level = round(max(0.6, min(2.5, factor)), 2)
        self._setup_styles()

        for col, cfg in self.base_col_config.items():
            new_width = max(20, int(cfg["width"] * self.zoom_level))
            new_minwidth = max(15, int(cfg["minwidth"] * self.zoom_level))
            self.tree.column(
                col,
                width=new_width,
                minwidth=new_minwidth,
                anchor=cfg["anchor"],
                stretch=cfg["stretch"]
            )

    def _on_ctrl_wheel_zoom(self, event):
        if event.delta > 0 or event.num == 4:
            self.set_zoom(self.zoom_level + 0.1)
        elif event.delta < 0 or event.num == 5:
            self.set_zoom(self.zoom_level - 0.1)
        return "break"

    def _on_key_zoom_in(self, event=None):
        self.set_zoom(self.zoom_level + 0.1)
        return "break"

    def _on_key_zoom_out(self, event=None):
        self.set_zoom(self.zoom_level - 0.1)
        return "break"

    def _on_key_zoom_reset(self, event=None):
        self.set_zoom(1.0)
        return "break"

    def _build_treeview(self):
        # Declaramos las columnas internas de datos (incluye columnas ocultas por defecto)
        self.columns = ("Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Comment", "Cues", "Rating", "Cover")

        self.tree = ttk.Treeview(self.tree_container, columns=self.columns, show="headings", selectmode="extended")

        # Ocultamos Comment de la representación visual pero la mantenemos en la tupla
        visible_cols = ("Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Cover")
        self.tree.configure(displaycolumns=visible_cols)

        for col in self.columns:
            self.app.sort_directions[col] = False
            title = self.col_titles.get(col, col)
            cfg = self.base_col_config.get(col, {"width": 100, "minwidth": 50, "stretch": False, "anchor": "w"})

            self.tree.heading(col, text=title, anchor="w", command=lambda _col=col: self.sort_by_column(_col))
            self.tree.column(
                col,
                width=cfg["width"],
                minwidth=cfg["minwidth"],
                anchor=cfg["anchor"],
                stretch=cfg["stretch"]
            )

        self.tree.tag_configure("even", background=theme.BG_CARD)
        self.tree.tag_configure("odd", background=theme.BG_CARD_ZEBRA)
        self.tree.tag_configure("hover", background=theme.BG_CARD_HOVER)

        self.tree.bind("<Motion>", self._on_tree_row_hover, add="+")
        self.tree.bind("<Leave>", self._on_tree_row_hover_leave, add="+")

        self.tree.bind("<ButtonPress-1>", self._on_header_press, add="+")
        self.tree.bind("<B1-Motion>", self._on_header_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_header_release, add="+")

        self.tree.bind("<<TreeviewSelect>>", lambda event: self.app.detail_panel.on_row_select(event))
        self.tree.bind("<Double-1>", self.on_cell_double_click)
        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.tree.bind(btn_right, self._on_tree_right_click)

        self.tree.bind("<Control-MouseWheel>", self._on_ctrl_wheel_zoom)
        self.tree.bind("<Control-Button-4>", self._on_ctrl_wheel_zoom)
        self.tree.bind("<Control-Button-5>", self._on_ctrl_wheel_zoom)
        self.tree.bind("<Control-plus>", self._on_key_zoom_in)
        self.tree.bind("<Control-KP_Add>", self._on_key_zoom_in)
        self.tree.bind("<Control-minus>", self._on_key_zoom_out)
        self.tree.bind("<Control-KP_Subtract>", self._on_key_zoom_out)
        self.tree.bind("<Control-0>", self._on_key_zoom_reset)
        self.tree.bind("<Control-KP_0>", self._on_key_zoom_reset)
        self.tree.bind("<Control-Key-0>", self._on_key_zoom_reset)

        self.tree.bind("<Return>", lambda e: self._safe_grid_action(e, self._on_tree_enter_press))
        self.tree.bind("<KP_Enter>", lambda e: self._safe_grid_action(e, self._on_tree_enter_press))

        self.tree.bind("<Delete>", lambda e: self._safe_grid_action(e, self._on_tree_delete_press))
        self.tree.bind("<KP_Delete>", lambda e: self._safe_grid_action(e, self._on_tree_delete_press))

        self.tree.bind("<Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=False))
        self.tree.bind("<Shift-Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=True))
        self.tree.bind("<ISO_Left_Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=True))

        self.tree.bind("<Up>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="up", select_range=False))
        self.tree.bind("<Down>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="down", select_range=False))
        self.tree.bind("<Shift-Up>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="up", select_range=True))
        self.tree.bind("<Shift-Down>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="down", select_range=True))

        self.tree.bind("<Home>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="home", select_range=False))
        self.tree.bind("<End>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="end", select_range=False))
        self.tree.bind("<Shift-Home>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="home", select_range=True))
        self.tree.bind("<Shift-End>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="end", select_range=True))

        self.tree.bind("<Prior>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="up", select_range=False))
        self.tree.bind("<Next>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="down", select_range=False))
        self.tree.bind("<Shift-Prior>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="up", select_range=True))
        self.tree.bind("<Shift-Next>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="down", select_range=True))

        self.vsb = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.tree_container, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

        self._build_empty_state()
        self.update_empty_state()

    def _build_empty_state(self):
        """Crea el mensaje centrado que se muestra cuando la grilla no tiene filas."""
        self.empty_state_frame = ctk.CTkFrame(self.tree_container, fg_color="transparent")

        lbl_icon = ctk.CTkLabel(
            self.empty_state_frame,
            text="🎵",
            font=ctk.CTkFont(size=40),
            text_color=theme.BORDER_FOCUS,
        )
        lbl_icon.pack(pady=(0, 8))

        lbl_title = ctk.CTkLabel(
            self.empty_state_frame,
            text="No hay ninguna colección cargada",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold"),
            text_color=theme.TEXT_MUTED,
        )
        lbl_title.pack()

        lbl_sub = ctk.CTkLabel(
            self.empty_state_frame,
            text="Abre una carpeta con archivos de audio para empezar.",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE),
            text_color=theme.TEXT_SUBTLE,
        )
        lbl_sub.pack(pady=(2, 0))

        for widget in (self.empty_state_frame, lbl_icon, lbl_title, lbl_sub):
            widget.bind("<Button-1>", lambda e: self.app.browse_folder())
            widget.configure(cursor="hand2")

    def update_empty_state(self):
        """Muestra u oculta el mensaje de estado vacío según si la grilla tiene filas."""
        if not hasattr(self, "empty_state_frame"):
            return
        if self.tree.get_children():
            self.empty_state_frame.place_forget()
        else:
            self.empty_state_frame.place(relx=0.5, rely=0.45, anchor="center")

    def _on_tree_row_hover(self, event):
        """Resalta la fila bajo el cursor (hover) sin afectar la selección activa.

        Sustituye temporalmente los tags de la fila por uno solo ("hover") en vez de
        añadirlo junto a "even"/"odd": con varios tags en la misma fila, Tkinter no
        garantiza que el último de la tupla gane la resolución de color de fondo, así
        que convivir con el tag de rayado podía dejar el hover invisible.
        """
        if self.tree.identify_region(event.x, event.y) != "cell":
            self._clear_row_hover()
            return

        row_id = self.tree.identify_row(event.y)
        if row_id == self._hovered_row_id:
            return

        self._clear_row_hover()

        if row_id and self.tree.exists(row_id):
            self._hovered_row_original_tags = tuple(self.tree.item(row_id, "tags") or ())
            self.tree.item(row_id, tags=("hover",))
            self._hovered_row_id = row_id

    def _on_tree_row_hover_leave(self, event=None):
        self._clear_row_hover()

    def _clear_row_hover(self):
        row_id = self._hovered_row_id
        if row_id and self.tree.exists(row_id):
            original_tags = getattr(self, "_hovered_row_original_tags", ())
            self.tree.item(row_id, tags=original_tags)
        self._hovered_row_id = None
        self._hovered_row_original_tags = ()

    def _on_header_press(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)
            if col_id:
                col_index = int(col_id.replace("#", "")) - 1
                if 0 <= col_index < len(self.columns):
                    display_cols = list(self.tree.cget("displaycolumns"))
                    if display_cols == ["#all"] or not display_cols:
                        display_cols = list(self.columns)

                    self._drag_col = display_cols[col_index] if col_index < len(display_cols) else self.columns[col_index]
                    self._drag_x = event.x

    def _on_header_motion(self, event):
        if self._drag_col:
            region = self.tree.identify_region(event.x, event.y)
            if region == "heading":
                self.tree.config(cursor="sb_h_double_arrow")
            else:
                self.tree.config(cursor="")

    def _on_header_release(self, event):
        if self._drag_col:
            self.tree.config(cursor="")
            region = self.tree.identify_region(event.x, event.y)

            if region == "heading":
                target_col_id = self.tree.identify_column(event.x)
                if target_col_id:
                    target_index = int(target_col_id.replace("#", "")) - 1

                    current_display = list(self.tree.cget("displaycolumns"))
                    if current_display == ["#all"] or not current_display:
                        current_display = list(self.columns)

                    if 0 <= target_index < len(current_display):
                        target_col = current_display[target_index]

                        if target_col != self._drag_col:
                            src_idx = current_display.index(self._drag_col)
                            dst_idx = current_display.index(target_col)

                            current_display.pop(src_idx)
                            current_display.insert(dst_idx, self._drag_col)

                            self.tree.configure(displaycolumns=tuple(current_display))

            self._drag_col = None

    def _setup_context_menu(self):
        self._tree_context_menu = tk.Menu(
            self.app, tearoff=0,
            bg=theme.BG_CARD, fg=theme.TEXT_MAIN,
            activebackground=self.app.CORP_COLOR, activeforeground=theme.TEXT_MAIN,
            bd=1, relief="flat", font=(theme.FONT_FAMILY, 10)
        )
        self._tree_context_menu.add_command(
            label="Procesar",
            command=lambda: self.app.process_manager.process_discogs_data()
        )
        self._tree_context_menu.add_command(
            label="Evaluar salud",
            command=self._evaluate_file_health
        )
        self._health_menu_index = self._tree_context_menu.index("end")
        self._tree_context_menu.add_command(
            label="Campos personalizables",
            command=self._open_custom_tag_picker
        )
        self._tree_context_menu.add_command(
            label="Filtrar...",
            command=self.toggle_filter_panel
        )
        self._tree_context_menu.add_command(
            label="Limpiar",
            command=lambda: self.app.process_manager.clear_selected_metadata()
        )
        self._tree_context_menu.add_separator()
        self._tree_context_menu.add_command(
            label="Eliminar del disco",
            command=lambda: self.app.process_manager.delete_selected_files()
        )

    def _evaluate_file_health(self):
        """'Evaluar salud' del menú contextual. Con 0-1 fila seleccionada, evalúa el
        archivo bajo foco (individual, instantáneo si ya hay caché vigente). Con 2+
        filas, lanza el análisis por lotes (DialogManager.run_batch_health_check),
        que ya se encarga de saltar los archivos con caché válida uno a uno."""
        selected_rows = list(self.tree.selection())

        if len(selected_rows) <= 1:
            row_id = selected_rows[0] if selected_rows else self.tree.focus()
            if not row_id:
                return

            file_path = self.app.file_paths_map.get(row_id)
            if not file_path or not os.path.exists(file_path):
                self.app.show_themed_dialog("Archivo no encontrado", "El archivo ya no existe en disco.", level="error")
                return

            self._evaluate_single_file_health(file_path)
            return

        file_paths = [self.app.file_paths_map.get(rid) for rid in selected_rows]
        file_paths = [p for p in file_paths if p]

        from dialogs import DialogManager
        DialogManager.run_batch_health_check(self.app, file_paths)

    def _evaluate_single_file_health(self, file_path):
        """Si ya hay un resultado cacheado y vigente (el archivo no cambió en disco),
        lo muestra al instante sin volver a analizar; si no, delega el análisis
        (hilo + ProgressDialog + modal) en DialogManager.run_single_health_check."""
        from dialogs import DialogManager, HealthReportModal

        cache_manager = getattr(self.app, "cache_manager", None)
        cached_report = cache_manager.get_cached_health(file_path) if cache_manager else None
        if cached_report is not None:
            HealthReportModal(
                self.app, cached_report,
                on_reanalyze=lambda: DialogManager.run_single_health_check(self.app, file_path)
            )
            return

        DialogManager.run_single_health_check(self.app, file_path)

    def _open_custom_tag_picker(self):
        selected = list(self.tree.selection())
        if not selected:
            return

        comment_col_idx = self.columns.index("Comment")
        union_tags = []
        file_paths = []

        for row_id in selected:
            file_path = self.app.file_paths_map.get(row_id)
            if not file_path:
                continue

            file_paths.append(file_path)

            values = list(self.tree.item(row_id, "values"))
            current_comment = ""
            if len(values) > comment_col_idx and values[comment_col_idx] is not None:
                current_comment = str(values[comment_col_idx]).strip()

            if not current_comment and hasattr(self.app, "audio_manager"):
                current_comment = self.app.audio_manager.get_tag_value(file_path, "Comment") or ""

            tags = [t.strip() for t in current_comment.split(",") if t.strip()]
            for tag in tags:
                if tag not in union_tags:
                    union_tags.append(tag)

        if not file_paths:
            return

        from custom_tag_picker import CustomTagPicker
        CustomTagPicker(
            parent=self.app,
            row_ids=selected,
            file_paths=file_paths,
            union_tags=union_tags,
            on_save=self._on_custom_tags_saved
        )

    def _on_custom_tags_saved(self, row_ids: list, file_paths: list, active_tags: set, removed_tags: set) -> None:
        if not row_ids:
            return

        comment_col_idx = self.columns.index("Comment")

        for row_id in row_ids:
            if not self.tree.exists(row_id):
                continue

            file_path = self.app.file_paths_map.get(row_id)
            if not file_path:
                continue

            values = list(self.tree.item(row_id, "values"))
            if len(values) <= comment_col_idx:
                continue

            prev_comment = str(values[comment_col_idx]).strip() if values[comment_col_idx] is not None else ""
            current_tags = [t.strip() for t in prev_comment.split(",") if t.strip()]

            for tag in active_tags:
                if tag not in current_tags:
                    current_tags.append(tag)

            current_tags = [t for t in current_tags if t not in removed_tags]

            new_comment = ", ".join(current_tags)

            if prev_comment != new_comment:
                if hasattr(self.app, "audio_manager"):
                    self.app.audio_manager.save_single_tag(file_path, "Comment", new_comment, app=self.app)

                values[comment_col_idx] = new_comment
                self.tree.item(row_id, values=values)

                log_msg = LogManager.format_tree_log(
                    context="CUSTOM_TAGS",
                    action="Modificado",
                    filename=os.path.basename(file_path),
                    prev_vals={"Comment": prev_comment},
                    new_vals={"Comment": new_comment}
                )
                self.logger.info(log_msg)

    def _on_tree_right_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            self._show_header_context_menu(event)
        else:
            self._show_tree_context_menu(event)

    def _show_tree_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        selected_rows = self.tree.selection()
        if row_id not in selected_rows:
            self.tree.selection_set(row_id)
            selected_rows = (row_id,)

        self.tree.focus(row_id)
        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

        self._update_health_menu_label(len(selected_rows))

        try:
            self._tree_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._tree_context_menu.grab_release()

    def _update_health_menu_label(self, selection_count):
        label = "Evaluar salud" if selection_count <= 1 else f"Evaluar salud ({selection_count} archivos)"
        self._tree_context_menu.entryconfigure(self._health_menu_index, label=label)

    @staticmethod
    def _remove_combobox_arrow_from_layout(layout):
        cleaned = []
        for item in layout:
            if not isinstance(item, tuple) or len(item) < 2:
                cleaned.append(item)
                continue

            element, options = item[0], item[1]
            if isinstance(element, str) and "downarrow" in element.lower():
                continue

            if isinstance(options, dict):
                new_options = dict(options)
                children = new_options.get("children")
                if children:
                    new_options["children"] = GridPanel._remove_combobox_arrow_from_layout(children)
                cleaned.append((element, new_options))
            else:
                cleaned.append(item)

        return cleaned

    def _open_tree_combo_dropdown(self, widget):
        try:
            widget.focus_set()
            widget.tk.call("ttk::combobox::Post", str(widget))
        except Exception:
            try:
                widget.event_generate("<Down>")
            except Exception:
                pass

    def _close_tree_combo_dropdown(self, widget):
        try:
            widget.tk.call("ttk::combobox::Unpost", str(widget))
        except Exception:
            pass

    def _is_tree_combo_dropdown_open(self, widget):
        try:
            popdown = widget.tk.call("ttk::combobox::PopdownWindow", str(widget))
            return bool(int(widget.tk.call("winfo", "ismapped", popdown)))
        except Exception:
            return False

    def _get_next_tree_edit_target(self, row_id, col_index, direction):
        editable_cols = [idx for idx, col in enumerate(self.columns) if col not in ("Cover", "Comment", "Cues", "Rating")]
        if col_index not in editable_cols:
            return None

        rows = list(self.tree.get_children())
        try:
            row_pos = rows.index(row_id)
            col_pos = editable_cols.index(col_index)
        except ValueError:
            return None

        if direction == "tab":
            if col_pos < len(editable_cols) - 1:
                return rows[row_pos], editable_cols[col_pos + 1]
            if row_pos < len(rows) - 1:
                return rows[row_pos + 1], editable_cols[0]
            if rows:
                return rows[0], editable_cols[0]
        elif direction == "shift_tab":
            if col_pos > 0:
                return rows[row_pos], editable_cols[col_pos - 1]
            if row_pos > 0:
                return rows[row_pos - 1], editable_cols[-1]
            if rows:
                return rows[-1], editable_cols[-1]
        elif direction == "enter":
            if row_pos < len(rows) - 1:
                return rows[row_pos + 1], col_index
        elif direction == "shift_enter":
            if row_pos > 0:
                return rows[row_pos - 1], col_index

        return None

    def _get_tree_columns(self):
        return list(self.tree["columns"])

    def get_column_index(self, col_name):
        return build_column_index(self._get_tree_columns()).get(col_name)

    def get_value_by_column(self, values, col_name, default=""):
        return get_row_value(values, build_column_index(self._get_tree_columns()), col_name, default)

    def set_value_by_column(self, values, col_name, new_value):
        return set_row_value(values, build_column_index(self._get_tree_columns()), col_name, new_value)

    def map_row_values(self, values):
        return map_row_values(values, self._get_tree_columns())

    def build_row_values(self, metadata, current_values=None):
        return build_row_values(metadata, self._get_tree_columns(), current_values=current_values)

    def _start_tree_cell_edit(self, row_id, col_index, open_dropdown=True):
        if col_index < 0 or col_index >= len(self.columns):
            return

        col_name = self.columns[col_index]
        if col_name in ("Cover", "Comment", "Cues", "Rating"):
            return

        self._last_edited_col = col_index

        if self.cell_entry:
            self.cell_entry.destroy()
            self.cell_entry = None

        bbox = self.tree.bbox(row_id, col_name)
        if not bbox:
            return
        x, y, w, h = bbox

        row_values = self.tree.item(row_id, "values")
        if col_index >= len(row_values):
            return
        current_value = row_values[col_index]

        style = ttk.Style()
        style.configure(
            "DarkGrid.TCombobox",
            fieldbackground=theme.BG_INPUT,
            background=theme.BG_CARD_HOVER,
            foreground=theme.TEXT_MAIN,
            darkcolor=theme.BG_INPUT,
            lightcolor=theme.BG_INPUT,
            arrowcolor=theme.TEXT_MAIN,
            insertcolor=theme.TEXT_MAIN
        )
        style.map(
            "DarkGrid.TCombobox",
            fieldbackground=[("readonly", theme.BG_INPUT)],
            selectbackground=[("readonly", theme.PRIMARY)],
            selectforeground=[("readonly", theme.TEXT_MAIN)]
        )

        allowed_values_for_validation = None

        if col_name in self.MANAGED_GRID_FIELDS:
            if col_name == "Publisher":
                current_genre = str(self.get_value_by_column(row_values, "Genre", "")).strip()
                if hasattr(self.app.catalog_manager, "get_allowed_publishers_for_genre") and current_genre:
                    base_values = self.app.catalog_manager.get_allowed_publishers_for_genre(current_genre)
                elif hasattr(self.app.catalog_manager, "get_publishers_by_genre") and current_genre:
                    base_values = self.app.catalog_manager.get_publishers_by_genre(current_genre)
                else:
                    base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)
            elif col_name == "Genre":
                current_album = str(self.get_value_by_column(row_values, "Album", "")).strip()
                if hasattr(self.app.catalog_manager, "get_allowed_genres_for_album") and current_album:
                    base_values = self.app.catalog_manager.get_allowed_genres_for_album(current_album)
                elif hasattr(self.app.catalog_manager, "get_genres_by_album") and current_album:
                    base_values = self.app.catalog_manager.get_genres_by_album(current_album)
                else:
                    base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)
            else:
                base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)

            allowed_values_for_validation = set(base_values) if base_values else set()
            combo_values = list(base_values) if base_values else []

            entry = ttk.Combobox(
                self.tree,
                state="readonly",
                values=combo_values,
                style="DarkGrid.TCombobox",
                exportselection=False
            )

            self.app.option_add("*TCombobox*Listbox.background", theme.BG_INPUT)
            self.app.option_add("*TCombobox*Listbox.foreground", theme.TEXT_MAIN)
            self.app.option_add("*TCombobox*Listbox.selectBackground", theme.PRIMARY)
            self.app.option_add("*TCombobox*Listbox.selectForeground", theme.TEXT_MAIN)
        else:
            entry = tk.Entry(
                self.tree,
                bg=theme.BG_INPUT,
                fg=theme.TEXT_MAIN,
                insertbackground=theme.TEXT_MAIN,
                relief="solid",
                borderwidth=1,
                highlightthickness=1,
                highlightbackground=theme.PRIMARY,
                highlightcolor=theme.PRIMARY
            )

        entry._is_cell_editing = True
        self._attach_editor_bindtag(entry)

        current_value_str = str(current_value).strip() if current_value is not None else ""
        if col_name == "Filename":
            current_stem, _ = os.path.splitext(current_value_str)
            entry.insert(0, current_stem)
        else:
            if col_name in self.MANAGED_GRID_FIELDS:
                current_options = [str(v) for v in entry.cget("values")]

                if current_value_str and current_value_str not in current_options and current_value_str != self.app.CLEAR_OPTION:
                    current_options.append(current_value_str)
                    current_options.sort(key=lambda x: x.lower())

                if self.app.CLEAR_OPTION not in current_options:
                    current_options.append(self.app.CLEAR_OPTION)

                entry.configure(values=current_options)
                entry.set(current_value_str)
            else:
                entry.insert(0, current_value_str)

        if col_name not in self.MANAGED_GRID_FIELDS:
            entry.select_range(0, "end")
            UiUtils.bind_entry_selection_fix(entry)

        entry.focus_set()
        entry.place(x=x, y=y, width=w, height=h)

        if col_name in self.MANAGED_GRID_FIELDS and open_dropdown:
            entry.after(50, lambda: self._open_tree_combo_dropdown(entry) if entry.winfo_exists() else None)

        session = _CellEditSession(
            entry=entry,
            row_id=row_id,
            col_index=col_index,
            col_name=col_name,
            current_value_str=current_value_str,
            allowed_values_for_validation=allowed_values_for_validation,
        )

        if col_name in self.MANAGED_GRID_FIELDS:
            entry.bind("<<ComboboxSelected>>", lambda e: self._cell_edit_on_combo_selected(session, e))

            bind_popdown = lambda e=None: self._cell_edit_bind_popdown_events(session, e)
            bind_popdown()
            entry.bind("<Map>", bind_popdown)
            entry.bind("<Button-1>", bind_popdown, add="+")
            entry.bind("<Down>", bind_popdown, add="+")
            entry.bind("<F4>", bind_popdown, add="+")

        entry.bind("<Tab>", lambda e: (self._cell_edit_queue_nav(session, "tab"), self._cell_edit_navigate(session, "tab", e))[1])
        entry.bind("<Shift-Tab>", lambda e: (self._cell_edit_queue_nav(session, "shift_tab"), self._cell_edit_navigate(session, "shift_tab", e))[1])
        entry.bind("<ISO_Left_Tab>", lambda e: (self._cell_edit_queue_nav(session, "shift_tab"), self._cell_edit_navigate(session, "shift_tab", e))[1])
        entry.bind("<Return>", lambda e: self._cell_edit_navigate(session, "enter", e))
        entry.bind("<KP_Enter>", lambda e: self._cell_edit_navigate(session, "enter", e))
        entry.bind("<Shift-Return>", lambda e: self._cell_edit_navigate(session, "shift_enter", e))
        entry.bind("<Escape>", lambda e: self._cell_edit_cancel(session, e))
        entry.bind("<FocusOut>", lambda e: self._cell_edit_on_focus_out(session, e))

        self.cell_entry = entry
        self._active_cell_tab_navigator = lambda direction: self._cell_edit_navigate_from_global_tab(session, direction)

    def _cell_edit_queue_nav(self, session, direction):
        session.pending_nav["dir"] = direction

    def _cell_edit_save(self, session, evt=None, commit_value=True):
        if session.finalized:
            return True
        session.finalized = True
        self._active_cell_tab_navigator = None

        entry = session.entry
        row_id = session.row_id
        col_index = session.col_index
        col_name = session.col_name
        current_value_str = session.current_value_str

        if not entry.winfo_exists():
            self.cell_entry = None
            return True

        self._close_tree_combo_dropdown(entry)

        if not commit_value:
            new_value = current_value_str
        else:
            try:
                new_value = entry.get().strip()
            except Exception:
                new_value = current_value_str

        if hasattr(entry, "_is_cell_editing"):
            try:
                del entry._is_cell_editing
            except AttributeError:
                pass

        try:
            entry.destroy()
        except Exception:
            pass
        self.cell_entry = None

        # Solo reclamar el foco de teclado para la grilla si nada más lo tomó ya
        # (p. ej. si el usuario hizo click en un campo del Detail Panel mientras se
        # cerraba la edición, ese click ya movió el foco legítimamente y no debe robársele).
        focus_target = self.app.focus_get()
        if focus_target is None or focus_target is self.tree:
            self.tree.focus_set()

        active_selection = self.tree.selection()
        if not active_selection:
            if row_id and row_id in self.tree.get_children():
                self.tree.selection_set(row_id)
                self.tree.focus(row_id)
                self.tree.see(row_id)

        if not commit_value:
            return True

        if col_name in self.MANAGED_GRID_FIELDS:
            if new_value == self.app.CLEAR_OPTION:
                new_value = ""
            else:
                new_value = self.app.catalog_manager.normalize_catalog_text(new_value)

            if new_value:
                valid_set = session.allowed_values_for_validation
                if valid_set is None or len(valid_set) == 0:
                    valid_set = set(self.app.catalog_manager.get_catalog_combo_values(col_name))

                if valid_set and new_value not in valid_set:
                    self.logger.warning(f"Valor '{new_value}' no permitido para la columna {col_name}.")
                    self.app.show_themed_dialog(
                        "Valor no válido",
                        f"El valor '{new_value}' no pertenece al catálogo o a las opciones permitidas para {col_name}.",
                        level="warning"
                    )
                    return False

        if col_name == "Filename":
            if not new_value:
                self.logger.warning("Nombre de archivo vacío: se cancela el renombrado.")
                self.app.show_themed_dialog("Nombre no válido", "El nombre del archivo no puede estar vacío.", level="warning")
                return False

            safe_name = new_value.replace("/", "_").replace("\\", "_").rstrip(".").strip()
            if not safe_name:
                self.logger.warning("Nombre de archivo inválido: se cancela el renombrado.")
                self.app.show_themed_dialog("Nombre no válido", "El nombre del archivo no es válido.", level="warning")
                return False

            original_filename = current_value_str
            _, original_ext = os.path.splitext(original_filename)
            final_filename = f"{safe_name}{original_ext}"

            if final_filename == original_filename:
                return True

            file_path = self.app.file_paths_map.get(row_id)
            if not file_path or not os.path.exists(file_path):
                self.logger.error("No se puede renombrar: archivo no encontrado.")
                self.app.show_themed_dialog("Archivo no encontrado", "No se puede renombrar porque el archivo ya no existe en disco.", level="error")
                return False

            target_path = os.path.join(os.path.dirname(file_path), final_filename)
            if os.path.normcase(target_path) != os.path.normcase(file_path) and os.path.exists(target_path):
                self.logger.warning(f"Ya existe un archivo con ese nombre: {final_filename}")
                self.app.show_themed_dialog("Nombre en uso", f"Ya existe un archivo con el nombre:\n{final_filename}", level="warning")
                return False

            try:
                os.rename(file_path, target_path)
                self.app.file_paths_map[row_id] = target_path

                values = list(self.tree.item(row_id, "values"))
                values[col_index] = final_filename
                self.tree.item(row_id, values=values)
                self.app.detail_panel.on_row_select(None)

                log_msg = LogManager.format_tree_log(
                    context="GRID",
                    action="Renombrado",
                    filename=final_filename,
                    prev_vals={"Filename": original_filename},
                    new_vals={"Filename": final_filename}
                )
                self.logger.info(log_msg)
            except Exception as e:
                self.logger.error(f"No se pudo renombrar el archivo '{original_filename}': {str(e)}")
                self.app.show_themed_dialog("Error al renombrar", f"No se pudo renombrar el archivo:\n{str(e)}", level="error")
                return False

            return True

        if new_value == current_value_str:
            return True

        file_path = self.app.file_paths_map.get(row_id)
        if hasattr(self.app, "undo_manager"):
            action = HistoryAction(
                file_path,
                row_id,
                col_name,
                col_index,
                current_value_str,
                new_value,
                col_name=col_name,
            )
            self.app.undo_manager.record_action(action)

        values = list(self.tree.item(row_id, "values"))
        values[col_index] = new_value

        self.tree.item(row_id, values=values)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

        if file_path:
            self.app.audio_manager.save_single_tag(file_path, col_name, new_value)
            filename = os.path.basename(file_path)
            log_msg = LogManager.format_tree_log(
                context="GRID",
                action="Modificado",
                filename=filename,
                prev_vals={col_name: current_value_str if current_value_str else None},
                new_vals={col_name: new_value if new_value else None}
            )
            self.logger.info(log_msg)

        return True

    def _cell_edit_cancel(self, session, evt=None):
        if session.finalized:
            return "break"
        session.finalized = True
        self._active_cell_tab_navigator = None

        entry = session.entry
        self._close_tree_combo_dropdown(entry)

        if hasattr(entry, "_is_cell_editing"):
            del entry._is_cell_editing

        entry.destroy()
        self.cell_entry = None
        self.tree.focus_set()
        return "break"

    def _cell_edit_execute_navigation(self, session, direction):
        entry = session.entry
        row_id = session.row_id
        col_index = session.col_index
        col_name = session.col_name
        try:
            if not entry.winfo_exists():
                return

            is_open = col_name in self.MANAGED_GRID_FIELDS and self._is_tree_combo_dropdown_open(entry)

            if is_open:
                self._close_tree_combo_dropdown(entry)

            if self._cell_edit_save(session, commit_value=True):
                next_target = self._get_next_tree_edit_target(row_id, col_index, direction)
                if next_target:
                    next_row_id, next_col_index = next_target
                    self.tree.selection_set(next_row_id)
                    self.tree.focus(next_row_id)
                    self.tree.see(next_row_id)

                    if hasattr(self.app, "detail_panel"):
                        self.app.detail_panel.on_row_select(None)

                    self.app.after(10, lambda r=next_row_id, c=next_col_index: self._start_tree_cell_edit(r, c, open_dropdown=False))
        finally:
            session.pending_nav["dir"] = None
            self.app.after(80, lambda: setattr(self, "_nav_lock", False))

    def _cell_edit_navigate(self, session, direction, evt=None):
        if getattr(self, "_nav_lock", False):
            return "break"

        entry = session.entry
        col_name = session.col_name

        if not entry.winfo_exists():
            return "break"

        is_open = col_name in self.MANAGED_GRID_FIELDS and self._is_tree_combo_dropdown_open(entry)

        if col_name in self.MANAGED_GRID_FIELDS and direction in ("enter", "shift_enter"):
            session.pending_nav["dir"] = None
            if is_open:
                self._close_tree_combo_dropdown(entry)
            entry.focus_set()
            return "break"

        self._nav_lock = True
        self.app.after_idle(lambda: self._cell_edit_execute_navigation(session, direction))
        return "break"

    def _cell_edit_navigate_from_global_tab(self, session, direction):
        if direction == "shift_tab":
            self._cell_edit_queue_nav(session, "shift_tab")
            return self._cell_edit_navigate(session, "shift_tab")
        self._cell_edit_queue_nav(session, "tab")
        return self._cell_edit_navigate(session, "tab")

    def _cell_edit_on_focus_out(self, session, evt=None):
        def commit_if_closed():
            entry = session.entry
            if not entry.winfo_exists():
                return

            if getattr(self, "_nav_lock", False):
                return

            pending_direction = session.pending_nav.get("dir")
            if pending_direction:
                self._nav_lock = True
                self.app.after_idle(lambda d=pending_direction: self._cell_edit_execute_navigation(session, d))
                return

            if session.col_name in self.MANAGED_GRID_FIELDS:
                if self._is_tree_combo_dropdown_open(entry):
                    return
                focus_widget = self.app.focus_get()
                if focus_widget is entry:
                    return

            self._cell_edit_save(session)

        session.entry.after(150, commit_if_closed)

    def _cell_edit_on_combo_selected(self, session, _evt=None):
        entry = session.entry
        entry.after(0, lambda: entry.focus_set() if entry.winfo_exists() else None)
        return "break"

    def _cell_edit_bind_popdown_events(self, session, evt=None):
        entry = session.entry
        try:
            popdown = entry.tk.eval(f"ttk::combobox::PopdownWindow {entry}")
            popdown_widget = entry.nametowidget(popdown)
            listbox = entry.nametowidget(f"{popdown}.f.l")

            for target in (listbox, popdown_widget):
                self._attach_editor_bindtag(target)
                target.bind("<Tab>", lambda e: (self._cell_edit_queue_nav(session, "tab"), self._cell_edit_navigate(session, "tab", e))[1])
                target.bind("<KeyPress-Tab>", lambda e: (self._cell_edit_queue_nav(session, "tab"), self._cell_edit_navigate(session, "tab", e))[1])
                target.bind("<Shift-Tab>", lambda e: (self._cell_edit_queue_nav(session, "shift_tab"), self._cell_edit_navigate(session, "shift_tab", e))[1])
                target.bind("<ISO_Left_Tab>", lambda e: (self._cell_edit_queue_nav(session, "shift_tab"), self._cell_edit_navigate(session, "shift_tab", e))[1])
                # Absorbe la rueda del mouse aquí: si el evento llega al bind_all global de
                # customtkinter (CTkScrollableFrame), revienta porque no reconoce este widget
                # interno de ttk::combobox como un widget Python válido.
                target.bind("<MouseWheel>", lambda e: self._cell_edit_popdown_scroll(listbox, e))
        except Exception:
            pass

    def _cell_edit_popdown_scroll(self, listbox, event):
        """Desplaza manualmente la lista del combo y absorbe el evento de rueda del mouse."""
        try:
            listbox.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass
        return "break"

    def select_file_by_row_id(self, row_id):
        if not row_id or row_id not in self.tree.get_children():
            return

        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self.tree.see(row_id)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

    def on_cell_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        col_id = self.tree.identify_column(event.x)
        col_name = self.tree.column(col_id, "id")

        if not col_name or col_name in ("Cover", "Comment"):
            return

        if col_name in ("Cues", "Rating"):
            return

        if col_name in self.columns:
            col_index = self.columns.index(col_name)
            row_id = self.tree.identify_row(event.y)
            if row_id:
                self._start_tree_cell_edit(row_id, col_index)

    def sort_by_column(self, col, toggle_direction=True):
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]

        if toggle_direction:
            reverse = self.app.sort_directions.get(col, False)
            self.app.sort_directions[col] = not reverse
        else:
            reverse = not self.app.sort_directions.get(col, True)

        self._active_sort_col = col
        self._last_sort_reverse = reverse

        data.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        for index, item in enumerate(data):
            self.tree.move(item[1], '', index)
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(item[1], tags=(tag,))

        for c in self.columns:
            base_text = self.col_titles.get(c, c)
            self.tree.heading(c, text=base_text)

        arrow = " ▲" if not reverse else " ▼"

        sorted_title = self.col_titles.get(col, col) + arrow
        self.tree.heading(col, text=sorted_title)

    def reapply_current_sort(self):
        """
        Reaaplica la ordenación actualmente activa sin cambiar de dirección.
        Se usa tras filtrado para mantener el orden respetado por el usuario.

        Si no hay ordenación activa, no hace nada.
        """
        # Verificar si hay un ordenamiento activo
        if not hasattr(self, "_active_sort_col") or not self._active_sort_col:
            return

        if not hasattr(self, "_last_sort_reverse"):
            self._last_sort_reverse = False

        col = self._active_sort_col
        reverse = self._last_sort_reverse

        # Obtener datos actuales (filas visibles)
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]

        if not data:
            return

        # Ordenar usando la dirección guardada
        data.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        # Reposicionar filas en el nuevo orden
        for index, item in enumerate(data):
            self.tree.move(item[1], '', index)
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(item[1], tags=(tag,))

    def get_visible_file_paths(self) -> list:
        """Rutas de archivo de las filas actualmente visibles en la grilla: respeta
        los filtros de búsqueda/avanzados aplicados, ya que las filas ocultas por un
        filtro están 'detached' del árbol y self.tree.get_children("") no las incluye."""
        return [
            self.app.file_paths_map.get(row_id)
            for row_id in self.tree.get_children("")
            if self.app.file_paths_map.get(row_id)
        ]

    def select_all_rows(self):
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        self.app.detail_panel.refresh_process_button_text(len(all_items))
        self.logger.info(f"Seleccionados todos los {len(all_items)} archivo(s).")

    def row_has_cover(self, row_id) -> bool:
        try:
            values = list(self.tree.item(row_id, "values"))
            cover_idx = self.columns.index("Cover")
            return len(values) > cover_idx and str(values[cover_idx]).strip().lower() in ("sí", "si", "yes", "true", "1")
        except Exception:
            return False

    def update_row_cover_status(self, row_id, status="Sí"):
        values = list(self.tree.item(row_id, "values"))
        cover_idx = self.columns.index("Cover")
        if len(values) > cover_idx:
            values[cover_idx] = status
            self.tree.item(row_id, values=values)

    def get_row_artist_title(self, row_id):
        values = list(self.tree.item(row_id, "values"))
        artist = self.get_value_by_column(values, "Artist", "")
        title = self.get_value_by_column(values, "Title", "")
        return artist, title

    def update_row_metadata(self, row_id, new_metadata):
        if not row_id or row_id not in self.tree.get_children():
            return

        current_values = list(self.tree.item(row_id, "values"))
        current_map = self.map_row_values(current_values)

        row_payload = {
            "Filename": new_metadata.get("Filename", current_map.get("Filename", "")),
            "Artist": new_metadata.get("Artist", ""),
            "Title": new_metadata.get("Title", ""),
            "MixArtist": new_metadata.get("MixArtist", ""),
            "Album": new_metadata.get("Album", ""),
            "Genre": new_metadata.get("Genre", ""),
            "Publisher": new_metadata.get("Publisher", ""),
            "Year": new_metadata.get("Year", ""),
            "Comment": new_metadata.get("Comment", current_map.get("Comment", "")),
            "Cues": new_metadata.get("Cues", new_metadata.get("CUEs", current_map.get("Cues", "-"))),
            "Rating": new_metadata.get("Rating", current_map.get("Rating", "0★")),
            "Cover": new_metadata.get("Cover", current_map.get("Cover", "No")),
        }

        self.tree.item(row_id, values=self.build_row_values(row_payload, current_values=current_values))
        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

    @staticmethod
    def _build_audio_row_payload(metadata):
        return {
            "Filename": metadata.get("Filename", ""),
            "Artist": metadata.get("Artist", ""),
            "Title": metadata.get("Title", ""),
            "MixArtist": metadata.get("MixArtist", ""),
            "Album": metadata.get("Album", ""),
            "Genre": metadata.get("Genre", ""),
            "Publisher": metadata.get("Publisher", ""),
            "Year": metadata.get("Year", ""),
            "Comment": metadata.get("Comment", ""),
            "Cues": metadata.get("Cues", metadata.get("CUEs", "-")),
            "Rating": metadata.get("Rating", "0★"),
            "Cover": metadata.get("Cover", "No"),
        }

    def insert_audio_row(self, metadata, count):
        tag = "even" if count % 2 == 0 else "odd"
        row_values = self.build_row_values(self._build_audio_row_payload(metadata))
        row_id = self.tree.insert("", "end", values=row_values, tags=(tag,))
        return row_id

    def insert_audio_rows_batch(self, batch_items, start_count=0):
        """Inserta un bloque de filas minimizando sobrecarga de Python por iteración."""
        inserted = []
        tree_insert = self.tree.insert
        build_values = self.build_row_values

        for offset, item in enumerate(batch_items):
            count = start_count + offset
            tag = "even" if count % 2 == 0 else "odd"
            metadata = item.get("metadata", {})
            row_values = build_values(self._build_audio_row_payload(metadata))
            row_id = tree_insert("", "end", values=row_values, tags=(tag,))
            inserted.append((row_id, item.get("file_path")))

        return inserted

    def _on_tree_delete_press(self, event):
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        if self.tree.selection():
            self.app.process_manager.clear_selected_metadata()
            return "break"

    def _on_tree_enter_press(self, event):
        if getattr(self, "_nav_lock", False):
            return "break"
        if self.cell_entry and self.cell_entry.winfo_exists():
            return "break"

        focused_row = self.tree.focus()
        if not focused_row:
            selected_rows = self.tree.selection()
            if selected_rows:
                focused_row = selected_rows[0]

        if not focused_row:
            return "break"

        editable_cols = [idx for idx, col in enumerate(self.columns) if col not in ("Cover", "Comment", "Cues", "Rating")]
        target_col = editable_cols[0]

        self._start_tree_cell_edit(focused_row, target_col, open_dropdown=True)
        return "break"

    def _on_tree_tab_press(self, event, reverse=False):
        if getattr(self, "_nav_lock", False):
            return "break"

        if self.cell_entry and self.cell_entry.winfo_exists():
            return "break"

        focused_row = self.tree.focus()
        if not focused_row:
            selected_rows = self.tree.selection()
            if selected_rows:
                focused_row = selected_rows[0]

        if not focused_row:
            return "break"

        self._nav_lock = True
        try:
            editable_cols = [idx for idx, col in enumerate(self.columns) if col not in ("Cover", "Comment", "Cues", "Rating")]

            if reverse:
                target_col = editable_cols[-1]
            else:
                target_col = editable_cols[0]

            self._start_tree_cell_edit(focused_row, target_col, open_dropdown=False)
        finally:
            self.app.after(50, lambda: setattr(self, "_nav_lock", False))

        return "break"

    def _handle_excel_navigation(self, event, move_to="home", select_range=False):
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        all_rows = self.tree.get_children()
        if not all_rows:
            return "break"

        focused_row = self.tree.focus()
        if not focused_row:
            selected = self.tree.selection()
            focused_row = selected[0] if selected else all_rows[0]

        target_row = all_rows[0] if move_to == "home" else all_rows[-1]

        if select_range:
            if not self._shift_pivot_row or self._shift_pivot_row not in all_rows:
                self._shift_pivot_row = focused_row

            try:
                start_idx = all_rows.index(self._shift_pivot_row)
                end_idx = all_rows.index(target_row)

                if start_idx <= end_idx:
                    range_rows = all_rows[start_idx : end_idx + 1]
                else:
                    range_rows = all_rows[end_idx : start_idx + 1]

                self.tree.selection_set(range_rows)
            except ValueError:
                self.tree.selection_set((focused_row, target_row))
        else:
            self._shift_pivot_row = None
            self.tree.selection_set(target_row)

        self.tree.focus(target_row)
        self.tree.see(target_row)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

        return "break"

    def _handle_key_navigation(self, event, direction="down", select_range=False):
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        all_rows = self.tree.get_children()
        if not all_rows:
            return "break"

        focused_row = self.tree.focus()
        if not focused_row:
            selected = self.tree.selection()
            focused_row = selected[0] if selected else all_rows[0]

        try:
            curr_idx = all_rows.index(focused_row)
        except ValueError:
            curr_idx = 0

        next_idx = curr_idx - 1 if direction == "up" else curr_idx + 1
        next_idx = max(0, min(len(all_rows) - 1, next_idx))
        target_row = all_rows[next_idx]

        self._update_tree_selection(target_row, focused_row, all_rows, select_range)
        return "break"

    def _handle_page_navigation(self, event, direction="down", select_range=False):
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        all_rows = self.tree.get_children()
        if not all_rows:
            return "break"

        focused_row = self.tree.focus()
        if not focused_row:
            selected = self.tree.selection()
            focused_row = selected[0] if selected else all_rows[0]

        try:
            curr_idx = all_rows.index(focused_row)
        except ValueError:
            curr_idx = 0

        tree_height = self.tree.winfo_height()
        current_row_height = max(18, int(self.BASE_ROW_HEIGHT * self.zoom_level))
        page_step = max(1, tree_height // current_row_height)

        next_idx = curr_idx - page_step if direction == "up" else curr_idx + page_step
        next_idx = max(0, min(len(all_rows) - 1, next_idx))
        target_row = all_rows[next_idx]

        self._update_tree_selection(target_row, focused_row, all_rows, select_range)
        return "break"

    def _update_tree_selection(self, target_row, current_focused, all_rows, select_range):
        if select_range:
            if not self._shift_pivot_row or self._shift_pivot_row not in all_rows:
                self._shift_pivot_row = current_focused

            try:
                start_idx = all_rows.index(self._shift_pivot_row)
                end_idx = all_rows.index(target_row)

                if start_idx <= end_idx:
                    range_rows = all_rows[start_idx : end_idx + 1]
                else:
                    range_rows = all_rows[end_idx : start_idx + 1]

                self.tree.selection_set(range_rows)
            except ValueError:
                self.tree.selection_set((current_focused, target_row))
        else:
            self._shift_pivot_row = None
            self.tree.selection_set(target_row)

        self.tree.focus_set()
        self.tree.focus(target_row)
        self.tree.see(target_row)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

    def _safe_grid_action(self, event, action_func, **kwargs):
        try:
            widget_class = event.widget.winfo_class()
        except AttributeError:
            widget_class = ""

        if widget_class in ("Entry", "TCombobox", "Text"):
            if getattr(event, "keysym", "") in ("Tab", "ISO_Left_Tab", "Return", "KP_Enter"):
                return "break"
            return

        self.tree.focus_set()
        res = action_func(event, **kwargs)
        return "break" if res is None else res

    def _show_header_context_menu(self, event):
        header_menu = tk.Menu(
            self.app, tearoff=0,
            bg=theme.BG_CARD, fg=theme.TEXT_MAIN,
            activebackground=self.app.CORP_COLOR, activeforeground=theme.TEXT_MAIN,
            selectcolor=theme.PRIMARY,
            bd=1, relief="flat", font=(theme.FONT_FAMILY, 10)
        )

        col_titles = dict(self.col_titles)

        display_cols = list(self.tree.cget("displaycolumns"))
        if display_cols == ["#all"] or not display_cols:
            display_cols = [c for c in self.columns if c not in ("Comment", "Cues", "Rating")]

        header_menu.vars = []

        for col in self.columns:
            if col == "Comment":
                continue
            is_visible = col in display_cols
            title = col_titles.get(col, col)

            var = tk.BooleanVar(value=is_visible)
            header_menu.vars.append(var)

            header_menu.add_checkbutton(
                label=title,
                onvalue=True,
                offvalue=False,
                variable=var,
                command=lambda c=col, vis=is_visible: self._toggle_column_visibility(c, vis)
            )

        try:
            header_menu.tk_popup(event.x_root, event.y_root)
        finally:
            header_menu.grab_release()

    def _toggle_column_visibility(self, col_name, current_visible):
        display_cols = list(self.tree.cget("displaycolumns"))
        if display_cols == ["#all"] or not display_cols:
            display_cols = [c for c in self.columns if c not in ("Comment", "Cues", "Rating")]

        if current_visible:
            if len(display_cols) > 1:
                display_cols.remove(col_name)
            else:
                self.logger.warning("No se pueden ocultar todas las columnas del grid.")
                return
        else:
            original_index = self.columns.index(col_name)
            inserted = False
            for idx, col in enumerate(display_cols):
                if self.columns.index(col) > original_index:
                    display_cols.insert(idx, col_name)
                    inserted = True
                    break
            if not inserted:
                display_cols.append(col_name)

        self.tree.configure(displaycolumns=tuple(display_cols))