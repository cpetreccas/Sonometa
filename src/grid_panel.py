import os
import sys
import time
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from undo_manager import HistoryAction
from log_handler import LogManager


class GridPanel:
    def __init__(self, app, parent, logger):
        self.app = app
        self.parent = parent
        self.logger = logger

        # Pivote para selecciones con Shift estilo Excel
        self._shift_pivot_row = None
        self._last_edited_col = 0  # Rastrear última columna editada

        # Contenedor principal del grid
        self.frame_grid = ctk.CTkFrame(self.parent)
        self.frame_grid.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

        # Configurar grid de 2x2 para Treeview y sus Scrollbars
        self.frame_grid.grid_rowconfigure(0, weight=1)
        self.frame_grid.grid_columnconfigure(0, weight=1)

        self._setup_styles()
        self._build_treeview()
        self._setup_context_menu()
        self.cell_entry = None

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
            fieldbackground="#181818",
            background="#181818",
            foreground="#E0E0E0",
            selectbackground="#181818",
            selectforeground="#E0E0E0",
            arrowcolor="#181818",
            relief="flat",
            borderwidth=0,
            padding=(3, 2)
        )
        style.map(
            self.tree_edit_combo_style,
            fieldbackground=[("readonly", "#181818"), ("focus", "#181818")],
            background=[("readonly", "#181818"), ("focus", "#181818")],
            foreground=[("readonly", "#E0E0E0"), ("focus", "#E0E0E0")],
            selectbackground=[("readonly", "#181818"), ("focus", "#181818")],
            selectforeground=[("readonly", "#E0E0E0"), ("focus", "#E0E0E0")],
            arrowcolor=[("readonly", "#181818"), ("focus", "#181818")]
        )

        style.configure(
            "Treeview",
            background="#181818",
            foreground="#E0E0E0",
            fieldbackground="#181818",
            rowheight=28,
            font=('Segoe UI', 9),
            borderwidth=0,
            relief="flat"
        )

        style.configure("Treeview.Item", borderwidth=0, relief="flat", padding=(4, 0))

        style.configure(
            "Treeview.Heading",
            background="#111111",
            foreground="#FFFFFF",
            font=('Segoe UI', 9, 'bold'),
            borderwidth=0,
            relief="flat",
            padding=(5, 5)
        )
        style.map("Treeview", background=[('selected', self.app.CORP_COLOR)])
        style.map("Treeview.Heading", background=[('active', '#2A2D32')])

    def _build_treeview(self):
        self.columns = ("Filename", "Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year", "Cover")
        self.tree = ttk.Treeview(self.frame_grid, columns=self.columns, show="headings", selectmode="extended")

        col_titles = {
            "Filename": "Nombre de archivo",
            "Artist": "Intérprete",
            "Title": "Título",
            "MixArtist": "Remix",
            "Album": "Álbum",
            "Genre": "Género",
            "Publisher": "Etiqueta",
            "Year": "Año",
            "Cover": "Carátula"
        }

        col_config = {
            "Filename":  {"width": 280, "minwidth": 180, "stretch": True,  "anchor": "w"},
            "Artist":    {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "Title":     {"width": 200, "minwidth": 120, "stretch": True,  "anchor": "w"},
            "MixArtist": {"width": 160, "minwidth": 100, "stretch": True,  "anchor": "w"},
            "Album":     {"width": 100, "minwidth": 70,  "stretch": False, "anchor": "w"},
            "Genre":     {"width": 70,  "minwidth": 50,  "stretch": False, "anchor": "w"},
            "Publisher": {"width": 120, "minwidth": 80,  "stretch": False, "anchor": "w"},
            "Year":      {"width": 45,  "minwidth": 40,  "stretch": False, "anchor": "center"},
            "Cover":     {"width": 55,  "minwidth": 45,  "stretch": False, "anchor": "center"}
        }

        for col in self.columns:
            self.app.sort_directions[col] = False
            title = col_titles.get(col, col)
            cfg = col_config[col]

            self.tree.heading(col, text=title, command=lambda _col=col: self.sort_by_column(_col))
            self.tree.column(
                col,
                width=cfg["width"],
                minwidth=cfg["minwidth"],
                anchor=cfg["anchor"],
                stretch=cfg["stretch"]
            )

        self.tree.tag_configure("even", background="#181818")
        self.tree.tag_configure("odd", background="#1E1E1E")

        self.tree.bind("<<TreeviewSelect>>", lambda event: self.app.detail_panel.on_row_select(event))
        self.tree.bind("<Double-1>", self.on_cell_double_click)
        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.tree.bind(btn_right, self._show_tree_context_menu)

        # Teclas de acción vinculadas al Treeview para cortar la propagación de Tkinter
        self.tree.bind("<Return>", lambda e: self._safe_grid_action(e, self._on_tree_enter_press))
        self.tree.bind("<KP_Enter>", lambda e: self._safe_grid_action(e, self._on_tree_enter_press))

        self.tree.bind("<Delete>", lambda e: self._safe_grid_action(e, self._on_tree_delete_press))
        self.tree.bind("<KP_Delete>", lambda e: self._safe_grid_action(e, self._on_tree_delete_press))

        # Navegación con Tabulador sobre el Treeview
        self.tree.bind("<Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=False))
        self.tree.bind("<Shift-Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=True))
        self.tree.bind("<ISO_Left_Tab>", lambda e: self._safe_grid_action(e, self._on_tree_tab_press, reverse=True))

        # Navegación Arriba/Abajo
        self.tree.bind("<Up>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="up", select_range=False))
        self.tree.bind("<Down>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="down", select_range=False))
        self.tree.bind("<Shift-Up>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="up", select_range=True))
        self.tree.bind("<Shift-Down>", lambda e: self._safe_grid_action(e, self._handle_key_navigation, direction="down", select_range=True))

        # Navegación Inicio/Fin
        self.tree.bind("<Home>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="home", select_range=False))
        self.tree.bind("<End>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="end", select_range=False))
        self.tree.bind("<Shift-Home>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="home", select_range=True))
        self.tree.bind("<Shift-End>", lambda e: self._safe_grid_action(e, self._handle_excel_navigation, move_to="end", select_range=True))

        # Paginación
        self.tree.bind("<Prior>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="up", select_range=False))
        self.tree.bind("<Next>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="down", select_range=False))
        self.tree.bind("<Shift-Prior>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="up", select_range=True))
        self.tree.bind("<Shift-Next>", lambda e: self._safe_grid_action(e, self._handle_page_navigation, direction="down", select_range=True))

        # Crear Scrollbars
        self.vsb = ttk.Scrollbar(self.frame_grid, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.frame_grid, orient="horizontal", command=self.tree.xview)

        self.tree.configure(yscrollcommand=self.vsb.set, xscrollcommand=self.hsb.set)

        # Ubicar elementos mediante grid
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.hsb.grid(row=1, column=0, sticky="ew")

    def _setup_context_menu(self):
        self._tree_context_menu = tk.Menu(
            self.app, tearoff=0,
            bg="#252526", fg="#FFFFFF",
            activebackground=self.app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self._tree_context_menu.add_command(
            label="Procesar",
            command=lambda: self.app.process_manager.process_discogs_data()
        )
        self._tree_context_menu.add_command(
            label="Limpiar",
            command=lambda: self.app.process_manager.clear_selected_metadata()
        )

    def _show_tree_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        selected_rows = self.tree.selection()
        if row_id not in selected_rows:
            self.tree.selection_set(row_id)

        self.tree.focus(row_id)
        self.app.detail_panel.on_row_select(None)

        try:
            self._tree_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._tree_context_menu.grab_release()

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
        editable_cols = [idx for idx, col in enumerate(self.columns) if col != "Cover"]
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
        elif direction == "shift_tab":
            if col_pos > 0:
                return rows[row_pos], editable_cols[col_pos - 1]
            if row_pos > 0:
                return rows[row_pos - 1], editable_cols[-1]
        elif direction == "enter":
            if row_pos < len(rows) - 1:
                return rows[row_pos + 1], col_index
        elif direction == "shift_enter":
            if row_pos > 0:
                return rows[row_pos - 1], col_index

        return None

    def _start_tree_cell_edit(self, row_id, col_index, open_dropdown=True):
        if col_index < 0 or col_index >= len(self.columns):
            return

        col_name = self.columns[col_index]
        if col_name == "Cover":
            return

        self._last_edited_col = col_index

        if self.cell_entry:
            self.cell_entry.destroy()
            self.cell_entry = None

        column_id = f"#{col_index + 1}"
        bbox = self.tree.bbox(row_id, column_id)
        if not bbox:
            return
        x, y, w, h = bbox

        row_values = self.tree.item(row_id, "values")
        if col_index >= len(row_values):
            return
        current_value = row_values[col_index]

        managed_grid_fields = {"Album", "Genre", "Publisher"}

        # Estilo oscuro para el Combobox nativo
        style = ttk.Style()
        style.configure(
            "DarkGrid.TCombobox",
            fieldbackground="#2B2B2B",
            background="#3A3A3A",
            foreground="#FFFFFF",
            darkcolor="#2B2B2B",
            lightcolor="#2B2B2B",
            arrowcolor="#FFFFFF",
            insertcolor="#FFFFFF"
        )
        style.map(
            "DarkGrid.TCombobox",
            fieldbackground=[("readonly", "#2B2B2B")],
            selectbackground=[("readonly", "#7B2CBF")],
            selectforeground=[("readonly", "#FFFFFF")]
        )

        if col_name in managed_grid_fields:
            if col_name == "Publisher":
                current_genre = str(row_values[5]).strip() if len(row_values) > 5 else ""
                if hasattr(self.app.catalog_manager, "get_allowed_publishers_for_genre") and current_genre:
                    base_values = self.app.catalog_manager.get_allowed_publishers_for_genre(current_genre)
                elif hasattr(self.app.catalog_manager, "get_publishers_by_genre") and current_genre:
                    base_values = self.app.catalog_manager.get_publishers_by_genre(current_genre)
                else:
                    base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)
            elif col_name == "Genre":
                current_album = str(row_values[4]).strip() if len(row_values) > 4 else ""
                if hasattr(self.app.catalog_manager, "get_allowed_genres_for_album") and current_album:
                    base_values = self.app.catalog_manager.get_allowed_genres_for_album(current_album)
                elif hasattr(self.app.catalog_manager, "get_genres_by_album") and current_album:
                    base_values = self.app.catalog_manager.get_genres_by_album(current_album)
                else:
                    base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)
            else:
                base_values = self.app.catalog_manager.get_catalog_combo_values(col_name)

            combo_values = list(base_values) if base_values else []

            entry = ttk.Combobox(
                self.tree,
                state="readonly",
                values=combo_values,
                style="DarkGrid.TCombobox",
                exportselection=False
            )

            # Personalizar colores de la lista flotante
            self.app.option_add("*TCombobox*Listbox.background", "#2B2B2B")
            self.app.option_add("*TCombobox*Listbox.foreground", "#FFFFFF")
            self.app.option_add("*TCombobox*Listbox.selectBackground", "#7B2CBF")
            self.app.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")
        else:
            entry = tk.Entry(
                self.tree,
                bg="#2B2B2B",
                fg="#FFFFFF",
                insertbackground="#FFFFFF",
                relief="solid",
                borderwidth=1,
                highlightthickness=1,
                highlightbackground="#7B2CBF",
                highlightcolor="#7B2CBF"
            )

        entry._is_cell_editing = True

        current_value_str = str(current_value).strip() if current_value is not None else ""
        if col_name == "Filename":
            current_stem, _ = os.path.splitext(current_value_str)
            entry.insert(0, current_stem)
        else:
            if col_name in managed_grid_fields:
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

        if col_name not in managed_grid_fields:
            entry.select_range(0, "end")

        entry.focus_set()
        entry.place(x=x, y=y, width=w, height=h)

        if col_name in managed_grid_fields and open_dropdown:
            entry.after(50, lambda: self._open_tree_combo_dropdown(entry) if entry.winfo_exists() else None)

        finalized = False

        def save_edit(evt=None, commit_value=True):
            nonlocal finalized
            if finalized:
                return True
            finalized = True

            self._close_tree_combo_dropdown(entry)

            if not commit_value:
                new_value = current_value_str
            else:
                new_value = entry.get().strip()

            if hasattr(entry, "_is_cell_editing"):
                del entry._is_cell_editing

            entry.destroy()
            self.cell_entry = None

            # Forzar el foco de vuelta explícitamente al Treeview
            self.tree.focus_set()

            active_selection = self.tree.selection()
            if not active_selection:
                if row_id and self.tree.exists(row_id):
                    self.tree.selection_set(row_id)
                    self.tree.focus(row_id)
                    self.tree.see(row_id)

            if not commit_value:
                return True

            if col_name in managed_grid_fields:
                if new_value == self.app.CLEAR_OPTION:
                    new_value = ""
                new_value = self.app.catalog_manager.normalize_catalog_text(new_value)

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

            if col_name in managed_grid_fields and new_value and new_value not in self.app.catalog_manager.catalog_values.get(col_name, []):
                self.app.show_themed_dialog("Valor no permitido", f"El valor '{new_value}' no está en {self.app.catalog_manager.catalog_labels[col_name]}.", level="warning")
                return False

            file_path = self.app.file_paths_map.get(row_id)
            if hasattr(self.app, "undo_manager"):
                action = HistoryAction(file_path, row_id, col_name, col_index, current_value_str, new_value)
                self.app.undo_manager.record_action(action)

            values = list(self.tree.item(row_id, "values"))
            values[col_index] = new_value

            album_idx, genre_idx, pub_idx = 4, 5, 6

            if col_name == "Album":
                current_genre = str(values[genre_idx]).strip() if len(values) > genre_idx else ""
                if new_value and current_genre:
                    if hasattr(self.app.catalog_manager, "get_allowed_genres_for_album"):
                        allowed_genres = self.app.catalog_manager.get_allowed_genres_for_album(new_value)
                    elif hasattr(self.app.catalog_manager, "get_genres_by_album"):
                        allowed_genres = self.app.catalog_manager.get_genres_by_album(new_value)
                    else:
                        allowed_genres = []

                    if allowed_genres and current_genre not in allowed_genres:
                        values[genre_idx] = ""
                        if file_path:
                            self.app.audio_manager.save_single_tag(file_path, "Genre", "")

                        current_pub = str(values[pub_idx]).strip() if len(values) > pub_idx else ""
                        if current_pub:
                            values[pub_idx] = ""
                            if file_path:
                                self.app.audio_manager.save_single_tag(file_path, "Publisher", "")

            elif col_name == "Genre":
                current_pub = str(values[pub_idx]).strip() if len(values) > pub_idx else ""
                if new_value and current_pub:
                    if hasattr(self.app.catalog_manager, "get_allowed_publishers_for_genre"):
                        allowed_pubs = self.app.catalog_manager.get_allowed_publishers_for_genre(new_value)
                    elif hasattr(self.app.catalog_manager, "get_publishers_by_genre"):
                        allowed_pubs = self.app.catalog_manager.get_publishers_by_genre(new_value)
                    else:
                        allowed_pubs = []

                    if allowed_pubs and current_pub not in allowed_pubs:
                        values[pub_idx] = ""
                        if file_path:
                            self.app.audio_manager.save_single_tag(file_path, "Publisher", "")

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

        def cancel_edit(evt=None):
            nonlocal finalized
            if finalized:
                return "break"
            finalized = True

            self._close_tree_combo_dropdown(entry)

            if hasattr(entry, "_is_cell_editing"):
                del entry._is_cell_editing

            entry.destroy()
            self.cell_entry = None
            self.tree.focus_set()
            return "break"

        def execute_navigation(direction):
            is_open = col_name in managed_grid_fields and self._is_tree_combo_dropdown_open(entry)
            commit = not (is_open and "tab" in direction)

            if is_open:
                if "tab" in direction:
                    entry.set(current_value_str)
                self._close_tree_combo_dropdown(entry)

            if save_edit(commit_value=commit):
                next_target = self._get_next_tree_edit_target(row_id, col_index, direction)
                if next_target:
                    next_row_id, next_col_index = next_target
                    self.tree.selection_set(next_row_id)
                    self.tree.focus(next_row_id)
                    self.tree.see(next_row_id)

                    if hasattr(self.app, "detail_panel"):
                        self.app.detail_panel.on_row_select(None)

                    # Iniciar la edición de la siguiente celda asegurando el foco
                    self.app.after(10, lambda r=next_row_id, c=next_col_index: self._start_tree_cell_edit(r, c, open_dropdown=False))

        def navigate(direction, evt=None):
            # Programar la navegación tras el ciclo actual para evitar que Tkinter pierda el foco
            self.app.after_idle(lambda: execute_navigation(direction))
            return "break"

        def on_focus_out(evt=None):
            def commit_if_closed():
                if not entry.winfo_exists():
                    return
                if col_name in managed_grid_fields and self._is_tree_combo_dropdown_open(entry):
                    return
                save_edit()

            entry.after(150, commit_if_closed)

        # Interceptamos en la lista flotante
        if col_name in managed_grid_fields:
            entry.bind("<<ComboboxSelected>>", lambda _e: save_edit())

            def bind_popdown_events(evt=None):
                try:
                    popdown = entry.tk.eval(f"ttk::combobox::PopdownWindow {entry}")
                    listbox = entry.nametowidget(f"{popdown}.f.l")

                    listbox.bind("<Tab>", lambda e: navigate("tab", e))
                    listbox.bind("<Shift-Tab>", lambda e: navigate("shift_tab", e))
                    listbox.bind("<ISO_Left_Tab>", lambda e: navigate("shift_tab", e))
                    listbox.bind("<Return>", lambda e: navigate("enter", e))
                    listbox.bind("<KP_Enter>", lambda e: navigate("enter", e))
                except Exception:
                    pass

            entry.bind("<Map>", bind_popdown_events)

        # Interceptamos en el cuadro de edición estándar
        entry.bind("<Tab>", lambda e: navigate("tab", e))
        entry.bind("<Shift-Tab>", lambda e: navigate("shift_tab", e))
        entry.bind("<ISO_Left_Tab>", lambda e: navigate("shift_tab", e))
        entry.bind("<Return>", lambda e: navigate("enter", e))
        entry.bind("<KP_Enter>", lambda e: navigate("enter", e))
        entry.bind("<Shift-Return>", lambda e: navigate("shift_enter", e))
        entry.bind("<Escape>", cancel_edit)
        entry.bind("<FocusOut>", on_focus_out)

        self.cell_entry = entry

    def filter_rows_by_traktor(self, only_unanalyzed=False, cues_under_2=False):
        """Muestra u oculta filas en función de los estados de Traktor Pro guardados en memoria."""
        visible_count = 0
        total_count = len(self.app.file_paths_map)

        for row_id, file_path in self.app.file_paths_map.items():
            traktor_data = self.app.traktor_cache.get(file_path, {"analizado": False, "num_cues": 0})
            is_analyzed = traktor_data.get("analizado", False)
            num_cues = traktor_data.get("num_cues", 0)

            show = True

            if only_unanalyzed and is_analyzed:
                show = False

            if cues_under_2 and num_cues >= 2:
                show = False

            if show:
                self.tree.reattach(row_id, "", "end")
                tag = "even" if visible_count % 2 == 0 else "odd"
                self.tree.item(row_id, tags=(tag,))
                visible_count += 1
            else:
                self.tree.detach(row_id)

        if only_unanalyzed or cues_under_2:
            self.app.label_status.configure(
                text=f"Filtrado: mostrando {visible_count} de {total_count} canciones"
            )
        else:
            self.app.label_status.configure(text=f"Listo ({total_count} canciones)")

    def on_cell_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell":
            return

        column_id = self.tree.identify_column(event.x)
        col_index = int(column_id.replace("#", "")) - 1
        if col_index < 0 or col_index >= len(self.columns):
            return

        if self.columns[col_index] == "Cover":
            return

        row_id = self.tree.identify_row(event.y)
        if row_id:
            self._start_tree_cell_edit(row_id, col_index)

    def sort_by_column(self, col):
        """Ordena el Treeview al hacer clic en el encabezado de una columna."""
        data = [(self.tree.set(child, col), child) for child in self.tree.get_children('')]
        reverse = self.app.sort_directions.get(col, False)
        data.sort(key=lambda x: str(x[0]).lower(), reverse=reverse)

        for index, item in enumerate(data):
            self.tree.move(item[1], '', index)
            tag = "even" if index % 2 == 0 else "odd"
            self.tree.item(item[1], tags=(tag,))

        self.app.sort_directions[col] = not reverse

    def select_all_rows(self):
        """Selecciona todos los elementos cargados en la tabla."""
        all_items = self.tree.get_children()
        self.tree.selection_set(all_items)
        self.app.detail_panel.refresh_process_button_text(len(all_items))
        self.logger.info(f"Seleccionados todos los {len(all_items)} archivo(s).")

    def row_has_cover(self, row_id) -> bool:
        """Verifica si la fila tiene carátula incrustada (columna 8)."""
        try:
            values = list(self.tree.item(row_id, "values"))
            return len(values) > 8 and str(values[8]).strip().lower() in ("sí", "si", "yes", "true", "1")
        except Exception:
            return False

    def update_row_cover_status(self, row_id, status="Sí"):
        """Actualiza la columna de carátula en la fila especificada."""
        values = list(self.tree.item(row_id, "values"))
        if len(values) > 8:
            values[8] = status
            self.tree.item(row_id, values=values)

    def get_row_artist_title(self, row_id):
        """Devuelve una tupla (artista, título) de la fila."""
        values = list(self.tree.item(row_id, "values"))
        artist = values[1] if len(values) > 1 else ""
        title = values[2] if len(values) > 2 else ""
        return artist, title

    def insert_audio_row(self, metadata, count):
        """Inserta un registro formateado dentro del Treeview aplicando etiquetas alternadas."""
        tag = "even" if count % 2 == 0 else "odd"
        row_id = self.tree.insert("", "end", values=(
            metadata["Filename"],
            metadata["Artist"],
            metadata["Title"],
            metadata["MixArtist"],
            metadata["Album"],
            metadata["Genre"],
            metadata["Publisher"],
            metadata["Year"],
            metadata["Cover"]
        ), tags=(tag,))
        return row_id

    def _on_tree_enter_press(self, event):
        """Al pulsar Intro sobre una fila seleccionada, inicia la edición de la columna Filename (índice 0)."""
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        focused_row = self.tree.focus()
        if not focused_row:
            selected_rows = self.tree.selection()
            if selected_rows:
                focused_row = selected_rows[0]

        if focused_row:
            self._start_tree_cell_edit(focused_row, col_index=0)
            return "break"

    def _on_tree_delete_press(self, event):
        """Al pulsar Suprimir sobre la tabla, ejecuta el mismo borrado de metadatos que el botón de la escoba."""
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        if self.tree.selection():
            self.app.process_manager.clear_selected_metadata()
            return "break"

    def _handle_excel_navigation(self, event, move_to="home", select_range=False):
        """Maneja la navegación y selección rápida estilo Excel (Inicio, Fin, Shift+Inicio, Shift+Fin)."""
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
        """Maneja la navegación con flechas arriba/abajo y selección con Shift."""
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
        """Maneja Re Pág / Av Pág moviendo la vista, el foco y la selección real."""
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
        row_height = 28
        page_step = max(1, tree_height // row_height)

        next_idx = curr_idx - page_step if direction == "up" else curr_idx + page_step
        next_idx = max(0, min(len(all_rows) - 1, next_idx))
        target_row = all_rows[next_idx]

        self._update_tree_selection(target_row, focused_row, all_rows, select_range)
        return "break"

    def _update_tree_selection(self, target_row, current_focused, all_rows, select_range):
        """Aplica la selección (individual o rango con Shift) y sincroniza el foco y la vista."""
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

        self.tree.focus_set()  # Asegura el foco activo en el widget
        self.tree.focus(target_row)
        self.tree.see(target_row)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

    def _safe_grid_action(self, event, action_func, **kwargs):
        """Verifica si el foco está en un campo de texto; si no lo está, enfoca el Treeview
        y ejecuta la navegación sin dobles saltos."""
        try:
            widget_class = event.widget.winfo_class()
        except AttributeError:
            widget_class = ""

        # Si el usuario está interactuando con un control de texto, no interferimos
        if widget_class in ("Entry", "TCombobox", "Text"):
            return

        # Forzar que el Treeview reciba el foco del teclado de la app
        self.tree.focus_set()

        res = action_func(event, **kwargs)
        return "break" if res is None else res

    def _on_tree_tab_press(self, event, reverse=False):
        """Permite reanudar la edición en la siguiente columna al pulsar Tab sobre la tabla."""
        if self.cell_entry and self.cell_entry.winfo_exists():
            return

        focused_row = self.tree.focus()
        if not focused_row:
            selected_rows = self.tree.selection()
            if selected_rows:
                focused_row = selected_rows[0]

        if not focused_row:
            return "break"

        editable_cols = [idx for idx, col in enumerate(self.columns) if col != "Cover"]
        last_col = getattr(self, "_last_edited_col", None)

        if reverse:
            if last_col is not None and last_col in editable_cols:
                col_pos = editable_cols.index(last_col)
                target_col = editable_cols[max(0, col_pos - 1)]
            else:
                target_col = editable_cols[-1]
        else:
            if last_col is not None and last_col in editable_cols:
                col_pos = editable_cols.index(last_col)
                if col_pos < len(editable_cols) - 1:
                    target_col = editable_cols[col_pos + 1]
                else:
                    rows = list(self.tree.get_children())
                    try:
                        row_pos = rows.index(focused_row)
                        if row_pos < len(rows) - 1:
                            next_row = rows[row_pos + 1]
                            self.tree.selection_set(next_row)
                            self.tree.focus(next_row)
                            self.tree.see(next_row)
                            focused_row = next_row
                            target_col = editable_cols[0]
                        else:
                            target_col = editable_cols[-1]
                    except ValueError:
                        target_col = editable_cols[0]
            else:
                target_col = editable_cols[0]

        self._start_tree_cell_edit(focused_row, target_col, open_dropdown=False)
        return "break"