import tkinter as tk
import customtkinter as ctk

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
        self._search_visible = False
        self._all_tree_items = []

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
            fg_color="#374151",
            hover_color="#1F2937",
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

    def _on_search_text_changed(self, *_args):
        if self._search_visible:
            self.apply_search_filter()

    @staticmethod
    def _build_row_search_text(values):
        searchable_indexes = (0, 1, 2, 3, 4, 5, 6, 7)
        parts = []
        for idx in searchable_indexes:
            if idx < len(values) and values[idx] is not None:
                parts.append(str(values[idx]))
        return " ".join(parts).lower()

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
        query = self.search_var.get().strip().lower()

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