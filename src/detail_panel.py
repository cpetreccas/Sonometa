import io
import os
import sys
import logging as logger
import tkinter as tk
from tkinter import messagebox
from io import BytesIO
import customtkinter as ctk
from ui_utils import UiUtils
from PIL import Image, ImageGrab

from ui_utils import UiUtils


class DetailPanel:
    """Panel lateral de metadatos y caratula desacoplado de la ventana principal."""

    def __init__(self, app, parent, logger, get_resource_path, fallback_process_icon=None):
        self.icono_procesar = self.load_process_icon()

        self.app = app
        self.parent = parent
        self.logger = logger
        self.get_resource_path = get_resource_path
        self.fallback_process_icon = fallback_process_icon

        self.panel_combo_fields = {
            "entry_album": "Album",
            "entry_genre": "Genre",
            "entry_publisher": "Publisher"
        }
        self.tag_entries = {}
        self.multi_entries = {}

        self.frame_sidebar = None
        self.label_cover = None
        self._cover_context_menu = None
        self._cover_context_menu_multi = None
        self.btn_process = None
        self.btn_clean = None

        self._setup_tag_panel()

    def _setup_tag_panel(self):
        self.frame_sidebar = ctk.CTkFrame(self.parent, width=260)
        self.frame_sidebar.pack(side="left", fill="y", padx=(0, 5), pady=0)
        self.frame_sidebar.pack_propagate(False)

        fields = [
            ("Intérprete", "entry_artist"),
            ("Título", "entry_title"),
            ("Remix", "entry_mixartist"),
            ("Álbum", "entry_album"),
            ("Año", "entry_year"),
            ("Género", "entry_genre"),
            ("Etiqueta", "entry_publisher")
        ]

        for label_text, attr_name in fields:
            lbl = ctk.CTkLabel(
                self.frame_sidebar,
                text=label_text,
                anchor="w",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold")
            )
            lbl.pack(fill="x", padx=10, pady=(8, 2))

            field_frame = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
            field_frame.pack(fill="x", padx=10, pady=(0, 4))

            if attr_name in self.panel_combo_fields:
                catalog_key = self.panel_combo_fields[attr_name]
                widget = ctk.CTkComboBox(
                    field_frame,
                    values=self.app.catalog_manager.get_catalog_combo_values(catalog_key),
                    state="readonly",
                    height=26,
                    font=ctk.CTkFont(family="Inter", size=12),
                    command=lambda _value, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_selected(_attr, _cat)
                )
                widget.set("")
                widget.bind("<Button-1>", lambda _e, _w=widget: self.on_panel_combo_click(_w))
                widget.bind(
                    "<FocusOut>",
                    lambda _e, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_focus_out(_attr, _cat)
                )
                widget.bind(
                    "<Return>",
                    lambda _e, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_enter(_attr, _cat)
                )
            else:
                widget = ctk.CTkEntry(field_frame, height=26, font=ctk.CTkFont(family="Inter", size=12))
                widget.bind("<FocusOut>", lambda _e, _attr=attr_name: self.on_panel_text_field_commit(_attr))
                widget.bind("<Return>", lambda _e, _attr=attr_name: self.on_panel_text_field_enter(_attr))

            widget.pack(fill="x")
            self.tag_entries[attr_name] = widget

            is_catalog = attr_name in self.panel_combo_fields
            multi_state = "readonly" if is_catalog else "normal"
            multi_widget = ctk.CTkComboBox(
                field_frame,
                values=[self.app.KEEP_VALUE],
                state=multi_state,
                height=26,
                font=ctk.CTkFont(size=12),
                command=lambda _value, _a=attr_name: self.on_multi_panel_commit(_a)
            )
            if not is_catalog:
                multi_widget.bind(
                    "<Return>",
                    lambda _e, _a=attr_name: self.on_multi_panel_commit(_a) or "break"
                )
                multi_widget.bind(
                    "<FocusOut>",
                    lambda _e, _a=attr_name: self.app.after(80, lambda: self.on_multi_panel_commit(_a))
                )
            self.multi_entries[attr_name] = multi_widget

        lbl_cover_title = ctk.CTkLabel(
            self.frame_sidebar,
            text="Carátula",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_cover_title.pack(fill="x", padx=5, pady=(8, 2))

        self.label_cover = ctk.CTkLabel(
            self.frame_sidebar,
            text="Sin carátula",
            width=180,
            height=180,
            fg_color="transparent",
            text_color="gray",
            border_color="#6B7280",
            border_width=1,
            cursor="hand2"
        )
        self.label_cover.pack(padx=5, pady=5)
        UiUtils(self.label_cover, "Clic derecho para opciones de carátula")

        self._cover_context_menu = tk.Menu(
            self.app,
            tearoff=0,
            bg="#1E1E1E",
            fg="#E0E0E0",
            activebackground=self.app.CORP_COLOR,
            activeforeground="#FFFFFF",
            bd=0,
            activeborderwidth=0,
            relief="flat",
            font=("Segoe UI", 10)
        )
        self._cover_context_menu.add_command(
            label="📋  Pegar imagen desde el portapapeles",
            command=self.paste_cover_from_clipboard
        )
        self._cover_context_menu.add_separator()
        self._cover_context_menu.add_command(
            label="🗑  Eliminar carátula",
            command=self.remove_cover_art
        )

        self._cover_context_menu_multi = tk.Menu(
            self.app,
            tearoff=0,
            bg="#252526",
            fg="#FFFFFF",
            activebackground=self.app.CORP_COLOR,
            activeforeground="#FFFFFF",
            bd=1,
            relief="flat",
            font=("Segoe UI", 10)
        )
        self._cover_context_menu_multi.add_command(
            label="📋  Pegar imagen a todos los seleccionados",
            command=self.paste_cover_from_clipboard
        )
        self._cover_context_menu_multi.add_separator()
        self._cover_context_menu_multi.add_command(
            label="🗑  Eliminar carátula de todos los seleccionados",
            command=self.remove_cover_art
        )

        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.label_cover.bind(btn_right, self.show_cover_context_menu)

        logo3_path = self.get_resource_path("logo_blanco.png")
        btn_icon = None
        if os.path.exists(logo3_path):
            try:
                img_logo3 = Image.open(logo3_path)
                btn_icon = ctk.CTkImage(light_image=img_logo3, dark_image=img_logo3, size=(22, 22))
            except Exception as e:
                self.logger.error(f"Error al cargar logo_blanco.png para el botón Procesar: {str(e)}")

        self.btn_process = ctk.CTkButton(
            self.frame_sidebar,
            text="Procesar",
            image=btn_icon if btn_icon else self.fallback_process_icon,
            compound="left",
            fg_color=self.app.CORP_COLOR,
            hover_color=self.app.CORP_HOVER,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            command=self.app.process_discogs_data
        )
        self.btn_process.pack(fill="x", padx=5, pady=(6, 10))
        UiUtils(self.btn_process, "Busca metadatos y carátulas de los archivos seleccionados")

        self.btn_clean = ctk.CTkButton(
            self.frame_sidebar,
            text="Limpiar",
            image=self.app.broom_icon,
            compound="left",
            fg_color="transparent",
            border_color="#DC2626",
            border_width=1,
            text_color="#FFFFFF",
            hover_color=("#FEE2E2", "#450A0A"),
            corner_radius=8,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=34,
            command=self.app.clear_selected_metadata
        )
        self.btn_clean.pack(fill="x", padx=5, pady=(0, 10))
        UiUtils(self.btn_clean, "Elimina los metadatos de los archivos seleccionados")

    def compute_common_panel_values(self, selected_rows):
        result = {}
        for attr_name, (_, col_index) in self.app.PANEL_FIELD_COL_MAP.items():
            values_across_rows = []
            for row_id in selected_rows:
                vals = self.app.tree.item(row_id, "values")
                v = str(vals[col_index]).strip() if col_index < len(vals) and vals[col_index] is not None else ""
                values_across_rows.append(v)
            unique = set(values_across_rows)
            result[attr_name] = values_across_rows[0] if len(unique) == 1 else self.app.KEEP_VALUE
        return result

    def enter_multi_mode(self, selected_rows):
        if not self.multi_entries:
            return

        common = self.compute_common_panel_values(selected_rows)

        for attr_name, multi_widget in self.multi_entries.items():
            normal_widget = self.tag_entries.get(attr_name)
            if normal_widget:
                normal_widget.pack_forget()

            common_value = common.get(attr_name, self.app.KEEP_VALUE)
            is_catalog = attr_name in self.panel_combo_fields

            if is_catalog:
                catalog_key = self.panel_combo_fields[attr_name]
                catalog_vals = [
                    v for v in self.app.catalog_values.get(catalog_key, [])
                    if v and v != self.app.CLEAR_OPTION
                ]
                options = [self.app.KEEP_VALUE] + sorted(catalog_vals, key=lambda x: x.lower())
            else:
                _, col_index = self.app.PANEL_FIELD_COL_MAP[attr_name]
                distinct = sorted({
                    str(self.app.tree.item(r, "values")[col_index]).strip()
                    for r in selected_rows
                    if col_index < len(self.app.tree.item(r, "values"))
                       and self.app.tree.item(r, "values")[col_index]
                })
                options = [self.app.KEEP_VALUE] + [v for v in distinct if v]

            multi_widget.configure(values=options)
            multi_widget.set(common_value if common_value in options else self.app.KEEP_VALUE)
            multi_widget.pack(fill="x")

        self.app._multi_select_mode = True
        self.display_multi_cover_placeholder(selected_rows=selected_rows)

    def exit_multi_mode(self):
        if not self.multi_entries:
            return

        for attr_name, multi_widget in self.multi_entries.items():
            multi_widget.pack_forget()
            normal_widget = self.tag_entries.get(attr_name)
            if normal_widget:
                normal_widget.pack(fill="x")

        self.app._multi_select_mode = False

    def on_multi_panel_commit(self, attr_name):
        if not self.app._multi_select_mode:
            return

        multi_widget = self.multi_entries.get(attr_name)
        if not multi_widget:
            return

        raw_value = multi_widget.get().strip()
        if raw_value == self.app.KEEP_VALUE or raw_value == "":
            return

        if attr_name in self.panel_combo_fields:
            new_value = self.app.catalog_manager.normalize_catalog_text(raw_value) if raw_value != self.app.CLEAR_OPTION else ""
        else:
            new_value = raw_value

        self.apply_field_to_all_selected(attr_name, new_value)

    def apply_field_to_all_selected(self, attr_name, new_value):
        if attr_name not in self.app.PANEL_FIELD_COL_MAP:
            return

        field_name, col_index = self.app.PANEL_FIELD_COL_MAP[attr_name]
        selected_rows = self.app.tree.selection()

        updated = 0
        for row_id in selected_rows:
            values = list(self.app.tree.item(row_id, "values"))
            if col_index >= len(values):
                continue
            if str(values[col_index]).strip() == new_value:
                continue

            values[col_index] = new_value
            self.app.tree.item(row_id, values=values)

            file_path = self.app.file_paths_map.get(row_id)
            if file_path and os.path.exists(file_path):
                self.app.audio_manager.save_single_tag(file_path, field_name, new_value)
                updated += 1

        if updated:
            self.logger.info(
                f"Campo '{field_name}' aplicado a {updated} archivo(s) seleccionado(s): '{new_value}'"
            )

    def display_multi_cover_placeholder(self, selected_rows=None):
        selected_rows = list(selected_rows or self.app.tree.selection())
        has_any_cover = any(self.app.row_has_cover(row_id) for row_id in selected_rows)
        text = "Mantener carátulas" if has_any_cover else "Sin carátula"
        self.label_cover.configure(image="", text=text, text_color="gray")
        self.label_cover.image = None

    def refresh_process_button_text(self, selected_count=None):
        if selected_count is None:
            selected_count = len(self.app.tree.selection())
        button_text = "Procesar selección" if selected_count > 1 else "Procesar"
        self.btn_process.configure(text=button_text)

    def display_cover_art(self, file_path_or_bytes):
        cover_data = None

        if isinstance(file_path_or_bytes, (bytes, bytearray)):
            cover_data = file_path_or_bytes
        elif isinstance(file_path_or_bytes, str) and os.path.exists(file_path_or_bytes):
            cover_data = self.app.audio_manager.extract_cover_bytes(file_path_or_bytes)

        if cover_data:
            try:
                image_stream = io.BytesIO(cover_data)
                img = Image.open(image_stream)

                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                img = img.resize((180, 180), Image.Resampling.LANCZOS)

                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(180, 180))
                self.label_cover.configure(image=ctk_img, text="")
                self.label_cover.image = ctk_img
                return
            except Exception as e:
                self.logger.error(f"Error procesando vista previa de la carátula: {str(e)}")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None

    def show_cover_context_menu(self, event):
        menu = self._cover_context_menu_multi if self.app._multi_select_mode else self._cover_context_menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def refresh_catalog_comboboxes(self):
        for attr_name, catalog_key in self.panel_combo_fields.items():
            combo = self.tag_entries.get(attr_name)
            if not combo:
                continue
            current_value = combo.get().strip()
            allowed_values = self.app.catalog_manager.get_catalog_combo_values(catalog_key)
            combo.configure(values=allowed_values)
            if current_value in allowed_values:
                combo.set(current_value)
            else:
                combo.set("")

    def set_panel_widget_value(self, attr_name, value):
        widget = self.tag_entries.get(attr_name)
        if not widget:
            return

        value_str = str(value) if value else ""
        if attr_name in self.panel_combo_fields:
            catalog_key = self.panel_combo_fields[attr_name]
            normalized_value = self.app.catalog_manager.normalize_catalog_text(value_str)
            self.app.catalog_manager.add_catalog_value(catalog_key, normalized_value, persist=False)
            widget.set(normalized_value)
            return

        widget.delete(0, "end")
        widget.insert(0, value_str)

    def on_panel_catalog_selected(self, attr_name, catalog_key):
        selected_rows = self.app.tree.selection()
        if not selected_rows:
            self.logger.info(
                f"Selección de catálogo ignorada ({self.app.catalog_labels.get(catalog_key, catalog_key)}): no hay fila seleccionada."
            )
            return

        if self.app._multi_select_mode:
            self.on_multi_panel_commit(attr_name)
            return

        row_id = selected_rows[0]
        combo = self.tag_entries.get(attr_name)
        if not combo:
            return

        raw_value = combo.get().strip()
        new_value = "" if raw_value == self.app.CLEAR_OPTION else self.app.catalog_manager.normalize_catalog_text(raw_value)
        self.app._apply_catalog_selection_to_row(row_id, attr_name, catalog_key, new_value)

    @staticmethod
    def on_panel_combo_click(combo_widget):
        try:
            combo_widget.focus_set()
            combo_widget._open_dropdown_menu()
        except Exception:
            pass
        return "break"

    def on_panel_catalog_enter(self, attr_name, catalog_key):
        self.on_panel_catalog_selected(attr_name, catalog_key)
        return "break"

    def on_panel_catalog_focus_out(self, attr_name, catalog_key):
        self.app.after(50, lambda a=attr_name, c=catalog_key: self.on_panel_catalog_selected(a, c))

    def on_panel_text_field_enter(self, attr_name):
        self.on_panel_text_field_commit(attr_name)
        return "break"

    def on_panel_text_field_commit(self, attr_name):
        text_column_map = {
            "entry_artist": ("Artist", 1),
            "entry_title": ("Title", 2),
            "entry_mixartist": ("MixArtist", 3),
            "entry_year": ("Year", 7),
        }
        if attr_name not in text_column_map:
            return

        selected_rows = self.app.tree.selection()
        if not selected_rows:
            return

        if self.app._multi_select_mode:
            self.on_multi_panel_commit(attr_name)
            return

        row_id = selected_rows[0]
        widget = self.tag_entries.get(attr_name)
        if not widget:
            return

        new_value = widget.get().strip()
        col_name, col_index = text_column_map[attr_name]
        values = list(self.app.tree.item(row_id, "values"))
        if col_index >= len(values):
            return

        current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
        if current_value == new_value:
            return

        values[col_index] = new_value
        self.app.tree.item(row_id, values=values)

        file_path = self.app.file_paths_map.get(row_id)
        if file_path:
            self.app.audio_manager.save_single_tag(file_path, col_name, new_value)

        self.logger.info(f"Campo '{col_name}' actualizado desde panel izquierdo: '{current_value}' -> '{new_value}'")

    def clear_fields(self):
        for widget in self.tag_entries.values():
            if isinstance(widget, ctk.CTkComboBox):
                widget.set("")
            else:
                widget.delete(0, "end")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None

    def on_row_select(self, event):
        selected = self.app.tree.selection()
        self.refresh_process_button_text(len(selected))

        if len(selected) > 1:
            self.enter_multi_mode(selected)
            return

        if self.app._multi_select_mode:
            self.exit_multi_mode()

        if not selected:
            return

        item_id = selected[0]
        item = self.app.tree.item(item_id)
        values = item['values']
        if len(values) < 8:
            logger.warning("Fila con metadatos incompletos; se omite actualización de panel.")
            return

        self.set_panel_widget_value("entry_artist", values[1])
        self.set_panel_widget_value("entry_title", values[2])
        self.set_panel_widget_value("entry_mixartist", values[3])
        self.set_panel_widget_value("entry_album", values[4])
        self.set_panel_widget_value("entry_genre", values[5])
        self.set_panel_widget_value("entry_publisher", values[6])
        self.set_panel_widget_value("entry_year", values[7])

        file_path = self.app.file_paths_map.get(item_id)
        if file_path:
            self.display_cover_art(file_path)

    def paste_cover_from_clipboard(self, event=None):
        try:
            image = ImageGrab.grabclipboard()

            if image is None:
                messagebox.showwarning("Portapapeles vacío", "No hay ninguna imagen en el portapapeles.")
                return

            buffer = BytesIO()
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            image.save(buffer, format="JPEG")
            image_bytes = buffer.getvalue()

            self.display_cover_art(image_bytes)

            selected_items = self.app.tree.selection()
            if selected_items:
                for item_id in selected_items:
                    file_path = self.app.file_paths_map.get(item_id)
                    if file_path:
                        self.app.audio_manager.embed_cover_art(file_path, image_bytes)
                        self.app.update_row_cover_status(item_id, "Sí")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo pegar la imagen: {e}")

    def remove_cover_art(self):
        selected_rows = self.app.tree.selection()

        if not selected_rows:
            selected_rows = self.app.tree.get_children()

        if not selected_rows:
            return

        for row_id in selected_rows:
            # Obtener la ruta del archivo usando el ID de la fila en el diccionario map
            file_path = self.app.file_paths_map.get(row_id)

            if file_path and os.path.exists(file_path):
                # 1. Eliminar la carátula físicamente del archivo de audio
                self.app.audio_manager.strip_cover_tags(file_path)

                # 2. Actualizar el estado de la fila en la tabla a "No"
                self.app.update_row_cover_status(row_id, "No")

        # 3. Limpiar la vista previa del panel de detalles
        self.display_cover_art(None)
        self.logger.info("Carátula eliminada correctamente.")

    def load_process_icon(self):
        """Carga el icono para el botón de procesar si el recurso existe."""
        ruta_logo = UiUtils.get_resource_path("assets/logo_blanco.png")
        if os.path.exists(ruta_logo):
            try:
                img_pil = Image.open(ruta_logo)
                return ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(20, 20))
            except Exception:
                return None
        return None