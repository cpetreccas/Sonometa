import tkinter as tk
import customtkinter as ctk
import unicodedata
import theme

def remove_accents(text: str) -> str:
    """Normaliza y elimina tildes/diacríticos de una cadena de texto."""
    if not text:
        return ""
    normalized = unicodedata.normalize('NFD', str(text))
    return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()

class SearchManager:
    def __init__(self, app, tree, frame_bottom_ref, detail_panel, grid_panel):
        """
        Gestiona la barra de búsqueda y el filtrado sobre el Treeview.

        :param app: Instancia principal de App
        :param tree: Instancia del ttk.Treeview
        :param frame_bottom_ref: Referencia a frame_bottom para posicionar el panel
        :param detail_panel: Referencia al DetailPanel para refrescar la UI al filtrar
        :param grid_panel: Referencia al GridPanel para actualizar barras de desplazamiento
        """
        self.app = app
        self.tree = tree
        self.frame_bottom_ref = frame_bottom_ref
        self.detail_panel = detail_panel
        self.grid_panel = grid_panel

        self.search_var = tk.StringVar()
        self._search_trace_id = None
        # Widgets que muestran el texto libre (buscador de la cabecera, campo del
        # panel de filtro avanzado): se les avisa cuando search_var cambia desde otro
        # sitio para que todos enseñen lo mismo.
        self._text_listeners = []
        self._search_visible = False
        self._all_tree_items = []
        self._debounce_after_id = None

        self._setup_search_bar()

    def _setup_search_bar(self):
        """Construye la interfaz gráfica de la barra de búsqueda."""
        self.frame_search = ctk.CTkFrame(self.app)

        self.entry_search = ctk.CTkEntry(
            self.frame_search,
            textvariable=self.search_var,
            placeholder_text="Buscar por archivo, artista, titulo, album, genero...",
            height=30
        )
        self.entry_search.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=6)

        self.btn_close_search = ctk.CTkButton(
            self.frame_search,
            text="X",
            width=32,
            height=30,
            fg_color=theme.BG_CARD_HOVER,
            hover_color=theme.BORDER_FOCUS,
            command=self.hide_search_bar
        )
        self.btn_close_search.pack(side="right", padx=(0, 10), pady=6)

        self.entry_search.bind("<Escape>", lambda _e: self.hide_search_bar() or "break")
        self._search_trace_id = self.search_var.trace_add("write", self._on_search_text_changed)

    def toggle_search_bar(self, event=None):
        if self._search_visible:
            self.hide_search_bar()
        else:
            self.show_search_bar()
        return "break"

    def show_search_bar(self):
        if self._search_visible:
            self.entry_search.focus_set()
            return
        self.frame_search.pack(fill="x", padx=15, pady=(0, 2), before=self.frame_bottom_ref)
        self._search_visible = True
        self.entry_search.focus_set()
        self.apply_search_filter()

    def hide_search_bar(self):
        if self._debounce_after_id:
            try:
                self.app.after_cancel(self._debounce_after_id)
            except Exception:
                pass
            self._debounce_after_id = None

        if self._search_visible:
            self.frame_search.pack_forget()
            self._search_visible = False
        if self.search_var.get():
            self.search_var.set("")
        self.apply_search_filter()
        self.app.focus_set()

    def on_escape_pressed(self, event=None):
        if self._search_visible:
            self.hide_search_bar()
            return "break"
        return None

    def add_text_listener(self, callback):
        """`callback(text)` se llama cada vez que cambia el texto libre."""
        self._text_listeners.append(callback)

    def set_search_text(self, text):
        """Fija el texto libre (lo usan los campos que lo editan)."""
        if self.search_var.get() != text:
            self.search_var.set(text)

    @property
    def search_text(self):
        return self.search_var.get()

    def _on_search_text_changed(self, *_args):
        text = self.search_var.get()
        for callback in self._text_listeners:
            try:
                callback(text)
            except Exception:
                pass

        if self._debounce_after_id:
            try:
                self.app.after_cancel(self._debounce_after_id)
            except Exception:
                pass

        # Debounce para reducir costo de detach/reattach por pulsacion.
        self._debounce_after_id = self.app.after(140, self._apply_search_filter_debounced)

    def _apply_search_filter_debounced(self):
        self._debounce_after_id = None
        self.apply_search_filter()

    def _build_row_search_text(self, values):
        columns = list(self.tree["columns"])
        searchable_columns = [
            col for col in columns
            if col in ("Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Comment", "Cues", "Rating")
        ]
        parts = []
        for col_name in searchable_columns:
            idx = columns.index(col_name) if col_name in columns else None
            if idx is None or idx >= len(values):
                continue
            if values[idx] is not None:
                parts.append(str(values[idx]))
        return remove_accents(" ".join(parts))

    def sync_all_tree_items(self):
        """Sincroniza la lista de IDs originales cargados en el árbol."""
        existing_ids = [row_id for row_id in self._all_tree_items if self.tree.exists(row_id)]
        for row_id in self.tree.get_children(""):
            if row_id not in existing_ids:
                existing_ids.append(row_id)
        self._all_tree_items = existing_ids

    def reset_all_tree_items(self):
        """Limpia el registro de ítems registrados al vaciar la lista."""
        self._all_tree_items = []

    def _retag_visible_rows(self):
        for index, row_id in enumerate(self.tree.get_children("")):
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(row_id, tags=(tag,))

    def apply_search_filter(self):
        self.sync_all_tree_items()
        query = remove_accents(self.search_var.get().strip())

        if self.grid_panel and hasattr(self.grid_panel, "apply_combined_filters"):
            self.grid_panel.apply_combined_filters(search_query=query)
            return

        matching_rows = []
        for row_id in self._all_tree_items:
            if not self.tree.exists(row_id):
                continue
            values = self.tree.item(row_id, "values")
            if not query or query in self._build_row_search_text(values):
                matching_rows.append(row_id)

        current_rows = self.tree.get_children("")
        if current_rows:
            self.tree.detach(*current_rows)

        for row_id in matching_rows:
            if self.tree.exists(row_id):
                self.tree.reattach(row_id, "", "end")

        self._retag_visible_rows()

        visible_set = set(self.tree.get_children(""))
        selected_visible = [row_id for row_id in self.tree.selection() if row_id in visible_set]
        self.tree.selection_set(selected_visible)

        if self.detail_panel:
            self.detail_panel.refresh_process_button_text(len(selected_visible))
            self.detail_panel.on_row_select(None)

        if self.grid_panel and hasattr(self.grid_panel, "_update_tree_scrollbars"):
            self.grid_panel._update_tree_scrollbars()

    @property
    def is_visible(self):
        return self._search_visible