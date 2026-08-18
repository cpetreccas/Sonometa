import os
import sys
import time
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from detail_panel import DetailPanel


class GridPanel:
    def __init__(self, app, parent, logger):
        self.app = app
        self.parent = parent
        self.logger = logger

        # Contenedor principal del grid
        self.frame_grid = ctk.CTkFrame(self.parent)
        self.frame_grid.pack(side="right", fill="both", expand=True, padx=(0, 0), pady=0)

        self._setup_styles()
        self._build_treeview()
        self._setup_context_menu()

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

            self.tree.heading(col, text=title, command=lambda _col=col: self.app.sort_by_column(_col))
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

        self.vsb = ttk.Scrollbar(self.frame_grid, orient="vertical", command=self.tree.yview)
        self.hsb = ttk.Scrollbar(self.frame_grid, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=self._on_tree_y_scroll, xscrollcommand=self._on_tree_x_scroll)

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Configure>", lambda _e: self._update_tree_scrollbars(), add="+")
        self.app.after_idle(self._update_tree_scrollbars)

    def _setup_context_menu(self):
        self._tree_context_menu = tk.Menu(
            self.app, tearoff=0,
            bg="#252526", fg="#FFFFFF",
            activebackground=self.app.CORP_COLOR, activeforeground="#FFFFFF",
            bd=1, relief="flat", font=('Segoe UI', 10)
        )
        self._tree_context_menu.add_command(label="Procesar", command=self.app.process_discogs_data)
        self._tree_context_menu.add_command(label="Limpiar", command=self.app.clear_selected_metadata)

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

    def _on_tree_y_scroll(self, first, last):
        self._update_scrollbar(self.vsb, first, last, side="right", fill="y")

    def _on_tree_x_scroll(self, first, last):
        self._update_scrollbar(self.hsb, first, last, side="bottom", fill="x")

    def _update_scrollbar(self, scrollbar, first, last, side, fill):
        scrollbar.set(first, last)
        needs_scroll = float(first) > 0.0 or float(last) < 1.0
        if needs_scroll and not scrollbar.winfo_ismapped():
            scrollbar.pack(side=side, fill=fill)
        elif not needs_scroll and scrollbar.winfo_ismapped():
            scrollbar.pack_forget()

    def _update_tree_scrollbars(self):
        x_first, x_last = self.tree.xview()
        y_first, y_last = self.tree.yview()
        self._on_tree_x_scroll(x_first, x_last)
        self._on_tree_y_scroll(y_first, y_last)

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

        if self.app.cell_entry:
            self.app.cell_entry.destroy()
            self.app.cell_entry = None

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
        if col_name in managed_grid_fields:
            entry = ttk.Combobox(
                self.tree,
                state="readonly",
                values=self.app.get_catalog_combo_values(col_name),
                style=self.tree_edit_combo_style,
                exportselection=False
            )
        else:
            entry = ttk.Entry(self.tree)

        current_value_str = str(current_value)
        if col_name == "Filename":
            current_stem, _ = os.path.splitext(current_value_str)
            entry.insert(0, current_stem)
        else:
            if col_name in managed_grid_fields:
                current_options = list(self.app.catalog_values.get(col_name, []))
                if current_value_str and current_value_str not in current_options:
                    current_options.append(current_value_str)
                    current_options.sort(key=lambda x: x.lower())
                entry.configure(values=current_options + [self.app.CLEAR_OPTION])
                entry.set(current_value_str)
            else:
                entry.insert(0, current_value_str)

        if col_name not in managed_grid_fields:
            entry.select_range(0, "end")
        entry.focus_set()
        entry.place(x=x, y=y, width=w, height=h)
        if col_name in managed_grid_fields:
            if open_dropdown:
                entry.after(50, lambda w=entry: self._open_tree_combo_dropdown(w) if w.winfo_exists() else None)

        finalized = False

        def save_edit(evt=None):
            nonlocal finalized
            if finalized:
                return True
            finalized = True
            self._close_tree_combo_dropdown(entry)
            new_value = entry.get().strip()
            entry.destroy()
            self.app.cell_entry = None

            if col_name in managed_grid_fields:
                if new_value == self.app.CLEAR_OPTION:
                    new_value = ""
                new_value = self.app.normalize_catalog_text(new_value)

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

                original_filename = current_value_str.strip()
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
                    self.logger.info(f"Renombrado manual: '{original_filename}' -> '{final_filename}'")
                except Exception as e:
                    self.logger.error(f"No se pudo renombrar el archivo '{original_filename}': {str(e)}")
                    self.app.show_themed_dialog("Error al renombrar", f"No se pudo renombrar el archivo:\n{str(e)}", level="error")
                    return False

                return True

            if new_value == current_value_str.strip():
                return True

            if col_name in managed_grid_fields and new_value and new_value not in self.app.catalog_values.get(col_name, []):
                self.app.show_themed_dialog("Valor no permitido", f"El valor '{new_value}' no está en {self.app.catalog_labels[col_name]}.", level="warning")
                return False

            values = list(self.tree.item(row_id, "values"))
            values[col_index] = new_value
            self.tree.item(row_id, values=values)

            self.app.detail_panel.on_row_select(None)

            file_path = self.app.file_paths_map.get(row_id)
            file_path and self.app.save_single_tag(file_path, col_name, new_value)

            return True

        def navigate(direction):
            if save_edit():
                next_target = self._get_next_tree_edit_target(row_id, col_index, direction)
                if next_target:
                    next_row_id, next_col_index = next_target
                    self.app.after_idle(lambda r=next_row_id, c=next_col_index: self._start_tree_cell_edit(r, c, open_dropdown=False))
            return "break"

        def commit_combo_selection(evt=None):
            entry.after_idle(save_edit)
            return "break"

        combo_type_state = {"buffer": "", "last_ts": 0.0, "matches": [], "match_idx": 0}

        def on_combo_type_search(evt=None):
            if col_name not in managed_grid_fields or evt is None:
                return

            if evt.keysym in {"Return", "KP_Enter", "Tab", "ISO_Left_Tab", "Up", "Down", "Left", "Right", "Escape"}:
                return

            values = [str(v) for v in entry.cget("values") if str(v) != self.app.CLEAR_OPTION]
            if not values:
                return "break"

            now = time.monotonic()
            if now - combo_type_state["last_ts"] > 1.0:
                combo_type_state["buffer"] = ""
            combo_type_state["last_ts"] = now

            if evt.keysym == "BackSpace":
                combo_type_state["buffer"] = combo_type_state["buffer"][:-1]
            else:
                char = evt.char or ""
                if not char.isprintable() or char.isspace():
                    return "break"
                combo_type_state["buffer"] += char.lower()

            if not combo_type_state["buffer"]:
                return "break"

            buffer = combo_type_state["buffer"]
            matches = [v for v in values if v.lower().startswith(buffer)] or [v for v in values if buffer in v.lower()]
            combo_type_state["matches"] = matches
            combo_type_state["match_idx"] = 0
            if matches:
                match = matches[0]
                try:
                    idx = list(entry.cget("values")).index(match)
                    entry.current(idx)
                except Exception:
                    entry.set(match)

            return "break"

        def on_combo_cycle(forward=True):
            matches = combo_type_state.get("matches", [])
            if not matches:
                if forward:
                    self._open_tree_combo_dropdown(entry)
                return "break"

            idx = combo_type_state["match_idx"]
            idx = (idx + 1) % len(matches) if forward else (idx - 1) % len(matches)
            combo_type_state["match_idx"] = idx
            match = matches[idx]
            try:
                all_values = list(entry.cget("values"))
                entry.current(all_values.index(match))
            except Exception:
                entry.set(match)
            return "break"

        def clear_combo_value(evt=None):
            if col_name not in managed_grid_fields:
                return
            combo_type_state["buffer"] = ""
            combo_type_state["matches"] = []
            combo_type_state["match_idx"] = 0
            entry.set("")
            save_edit()
            return "break"

        def on_focus_out(evt=None):
            def commit_if_closed():
                if col_name in managed_grid_fields and self._is_tree_combo_dropdown_open(entry):
                    return
                save_edit()

            entry.after(120, commit_if_closed)

        entry.bind("<Return>", lambda _e: navigate("enter"))
        entry.bind("<Shift-Return>", lambda _e: navigate("shift_enter"))
        entry.bind("<Tab>", lambda _e: navigate("tab"))
        entry.bind("<Shift-Tab>", lambda _e: navigate("shift_tab"))
        entry.bind("<ISO_Left_Tab>", lambda _e: navigate("shift_tab"))
        if col_name in managed_grid_fields:
            entry.bind("<<ComboboxSelected>>", commit_combo_selection)
            entry.bind("<KeyPress>", on_combo_type_search)
            entry.bind("<Down>", lambda _e: self._open_tree_combo_dropdown(entry) or "break")
            entry.bind("<space>", lambda _e: self._open_tree_combo_dropdown(entry) or "break")
            entry.bind("<Down>", lambda _e: on_combo_cycle(forward=True))
            entry.bind("<Up>", lambda _e: on_combo_cycle(forward=False))
            entry.bind("<Delete>", clear_combo_value)
            entry.bind("<KP_Delete>", clear_combo_value)
            entry.bind("<BackSpace>", clear_combo_value)
        entry.bind("<FocusOut>", on_focus_out)
        self.app.cell_entry = entry

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