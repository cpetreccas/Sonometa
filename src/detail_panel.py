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
from undo_manager import HistoryAction
from audio_player import AudioPlayer
from log_handler import LogManager


class DetailPanel:
    """Panel lateral de metadatos y carátula desacoplado de la ventana principal."""

    def __init__(self, app, parent, logger, get_resource_path, fallback_process_icon=None):
        self.icono_procesar = self.load_process_icon()

        self.app = app
        self.parent = parent
        self.logger = logger
        self.get_resource_path = get_resource_path
        self.fallback_process_icon = fallback_process_icon

        # Guarda el ID de la fila que se estaba editando antes de cambiar de selección
        self._editing_row_id = None

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

        # Componentes del Reproductor de Audio
        self.frame_player = None
        self.btn_play = None
        self.slider_audio = None
        self.lbl_audio_time = None
        self.audio_player = None

        self._setup_tag_panel()
        self.audio_player = AudioPlayer(self)

    def _track_editing_row(self, event=None):
        """Memoriza la fila actualmente seleccionada cuando un campo recibe el foco."""
        selected_rows = self.app.tree.selection()
        if selected_rows and not self.app._multi_select_mode:
            self._editing_row_id = selected_rows[0]
        else:
            self._editing_row_id = None

    def _on_widget_focus_in(self, widget, event=None):
        """Aplica el borde morado corporativo al recibir el foco."""
        self._track_editing_row(event)
        try:
            widget.configure(border_color=self.app.CORP_COLOR, border_width=2)
        except Exception:
            pass

    def _on_widget_focus_out(self, widget, attr_name=None, is_combo=False, event=None):
        """Restaura el borde original al perder el foco y procesa cambios."""
        try:
            if widget == self.btn_clean:
                widget.configure(border_color="#DC2626", border_width=1)
            elif widget == self.btn_process:
                widget.configure(border_color=self.app.CORP_COLOR, border_width=1)
            else:
                widget.configure(border_color="#565B5E", border_width=1)
        except Exception:
            pass

        if attr_name:
            if is_combo:
                catalog_key = self.panel_combo_fields.get(attr_name)
                self.on_panel_catalog_focus_out(attr_name, catalog_key)
            else:
                self.on_panel_text_field_commit(attr_name)

    def _toggle_combo_dropdown(self, combo_widget):
        """Abre o cierra el menú desplegable del CTkComboBox."""
        try:
            combo_widget.focus_set()
            if hasattr(combo_widget, "_dropdown_menu") and combo_widget._dropdown_menu.winfo_ismapped():
                combo_widget._dropdown_menu.withdraw()
            else:
                combo_widget._open_dropdown_menu()
        except Exception:
            pass
        return "break"

    def _on_combo_return(self, combo_widget, attr_name, catalog_key, event=None):
        """Cierra el menú desplegable, confirma el valor y mantiene el foco en el combo."""
        try:
            if hasattr(combo_widget, "_dropdown_menu") and combo_widget._dropdown_menu.winfo_ismapped():
                combo_widget._dropdown_menu.withdraw()
        except Exception:
            pass

        self.on_panel_catalog_selected(attr_name, catalog_key)
        combo_widget.focus_set()
        return "break"

    def _focus_next_widget(self, current_widget, event=None):
        """Salto limpio al siguiente campo ignorando submódulos internos."""
        focused = current_widget.focus_get()
        if focused is None:
            focused = current_widget
        next_w = focused.tk_focusNext()

        if hasattr(current_widget, "_entry") and (next_w == current_widget or next_w == current_widget._entry):
            next_w = next_w.tk_focusNext()

        next_w.focus_set()
        return "break"

    def _focus_prev_widget(self, current_widget, event=None):
        """Salto limpio al campo anterior ignorando submódulos internos."""
        focused = current_widget.focus_get()
        if focused is None:
            focused = current_widget
        prev_w = focused.tk_focusPrev()

        if hasattr(current_widget, "_entry") and (prev_w == current_widget or prev_w == current_widget._entry):
            prev_w = prev_w.tk_focusPrev()

        prev_w.focus_set()
        return "break"

    def _setup_cover_context_menus(self):
        """Inicializa los menús contextuales de la carátula para modo individual y múltiple."""
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
        self._cover_context_menu.add_command(
            label="🖼  Aplicar carátula genérica",
            command=self.apply_generic_cover
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
        self._cover_context_menu_multi.add_command(
            label="🖼  Aplicar carátula genérica a todos los seleccionados",
            command=self.apply_generic_cover
        )
        self._cover_context_menu_multi.add_separator()
        self._cover_context_menu_multi.add_command(
            label="🗑  Eliminar carátula de todos los seleccionados",
            command=self.remove_cover_art
        )

        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        self.label_cover.bind(btn_right, self.show_cover_context_menu)

    def _setup_tag_panel(self):
        self.frame_sidebar = ctk.CTkFrame(self.parent, width=260)
        self.frame_sidebar.pack(side="left", fill="y", padx=(0, 5), pady=0)
        self.frame_sidebar.pack_propagate(False)

        fields = [
            ("Intérprete", "entry_artist"),
            ("Título", "entry_title"),
            ("Remix", "entry_mixartist"),
            ("Año", "entry_year"),
            ("Álbum", "entry_album"),
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
            lbl.pack(fill="x", padx=10, pady=(6, 2))

            field_frame = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
            field_frame.pack(fill="x", padx=10, pady=(0, 2))

            if attr_name in self.panel_combo_fields:
                catalog_key = self.panel_combo_fields[attr_name]
                widget = ctk.CTkComboBox(
                    field_frame,
                    values=self.app.catalog_manager.get_catalog_combo_values(catalog_key),
                    state="readonly",
                    height=26,
                    border_width=1,
                    border_color="#565B5E",
                    font=ctk.CTkFont(family="Inter", size=12),
                    command=lambda _value, _attr=attr_name, _cat=catalog_key: self.on_panel_catalog_selected(_attr, _cat)
                )
                widget.set("")

                widget.bind("<FocusIn>", lambda _e, _w=widget: self._on_widget_focus_in(_w))
                widget.bind("<FocusOut>", lambda _e, _w=widget, _a=attr_name: self._on_widget_focus_out(_w, _a, is_combo=True))

                widget.bind("<Up>", lambda _e, _w=widget: self._toggle_combo_dropdown(_w))
                widget.bind("<Down>", lambda _e, _w=widget: self._toggle_combo_dropdown(_w))
                widget.bind("<Button-1>", lambda _e, _w=widget: self._toggle_combo_dropdown(_w))
                widget.bind("<space>", lambda _e, _w=widget: self._toggle_combo_dropdown(_w))
                widget.bind(
                    "<Return>",
                    lambda _e, _w=widget, _a=attr_name, _c=catalog_key: self._on_combo_return(_w, _a, _c)
                )
            else:
                widget = ctk.CTkEntry(
                    field_frame,
                    height=26,
                    border_width=1,
                    border_color="#565B5E",
                    font=ctk.CTkFont(family="Inter", size=12)
                )
                widget.bind("<FocusIn>", lambda _e, _w=widget: self._on_widget_focus_in(_w))
                widget.bind("<FocusOut>", lambda _e, _w=widget, _a=attr_name: self._on_widget_focus_out(_w, _a, is_combo=False))
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
                border_width=1,
                border_color="#565B5E",
                font=ctk.CTkFont(size=12),
                command=lambda _value, _a=attr_name: self.on_multi_panel_commit(_a)
            )

            multi_widget.bind("<FocusIn>", lambda _e, _w=multi_widget: self._on_widget_focus_in(_w))

            if not is_catalog:
                multi_widget.bind(
                    "<FocusOut>",
                    lambda _e, _w=multi_widget, _a=attr_name: (
                        self._on_widget_focus_out(_w),
                        self.on_multi_panel_commit(_a)
                    )
                )
                multi_widget.bind(
                    "<Return>",
                    lambda _e, _a=attr_name: self.on_multi_panel_commit(_a) or "break"
                )
            else:
                multi_widget.bind("<FocusOut>", lambda _e, _w=multi_widget: self._on_widget_focus_out(_w))
                multi_widget.bind("<Up>", lambda _e, _w=multi_widget: self._toggle_combo_dropdown(_w))
                multi_widget.bind("<Down>", lambda _e, _w=multi_widget: self._toggle_combo_dropdown(_w))
                multi_widget.bind("<space>", lambda _e, _w=multi_widget: self._toggle_combo_dropdown(_w))

            self.multi_entries[attr_name] = multi_widget

        # --- SECCIÓN CARÁTULA ---
        lbl_cover_title = ctk.CTkLabel(
            self.frame_sidebar,
            text="Carátula",
            anchor="w",
            font=ctk.CTkFont(size=11, weight="bold")
        )
        lbl_cover_title.pack(fill="x", padx=10, pady=(6, 2))

        self.label_cover = ctk.CTkLabel(
            self.frame_sidebar,
            text="Sin carátula",
            width=160,
            height=160,
            fg_color="transparent",
            text_color="gray",
            border_color="#6B7280",
            border_width=1,
            cursor="hand2"
        )
        self.label_cover.pack(padx=5, pady=2)
        UiUtils(self.label_cover, "Clic derecho para opciones de carátula")

        # Menús contextuales de carátula
        self._setup_cover_context_menus()

        # --- SECCIÓN MINI REPRODUCTOR DE AUDIO ---
        self.frame_player = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
        self.frame_player.pack(fill="x", padx=10, pady=(12, 6))

        player_top = ctk.CTkFrame(self.frame_player, fg_color="transparent")
        player_top.pack(fill="x")

        self.btn_play = ctk.CTkButton(
            player_top,
            text="▶",
            width=32,
            height=28,
            fg_color=self.app.CORP_COLOR,
            hover_color="#581C87",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.audio_player.toggle_play_pause() if self.audio_player else None
        )
        self.btn_play.pack(side="left", padx=(0, 5))

        self.slider_audio = ctk.CTkSlider(
            player_top,
            from_=0,
            to=1,
            height=14,
            progress_color=self.app.CORP_COLOR,
            button_color="#FFFFFF",
            button_hover_color="#E0E0E0",
            command=lambda val: self.audio_player.on_seek_end(val) if self.audio_player else None
        )
        self.slider_audio.set(0)
        self.slider_audio.pack(side="left", fill="x", expand=True)

        self.lbl_audio_time = ctk.CTkLabel(
            self.frame_player,
            text="00:00 / 00:00",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.lbl_audio_time.pack(fill="x", pady=(2, 0))

        # --- BOTONES DE ACCIÓN ---
        self.btn_process = ctk.CTkButton(
            self.frame_sidebar,
            text="Procesar",
            image=self.app.process_icon,
            compound="left",
            fg_color=self.app.CORP_COLOR,
            hover_color="#6D28D9",
            border_width=2,
            border_color=self.app.CORP_COLOR,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=32,
            command=self.app.process_manager.process_discogs_data
        )
        self.btn_process.pack(fill="x", padx=10, pady=(4, 6))
        UiUtils(self.btn_process, "Busca metadatos y carátulas de los archivos seleccionados")

        # Efectos hover y ejecución por teclado en btn_process
        self.btn_process.bind("<Enter>", lambda _e: self._set_btn_hover(self.btn_process, True))
        self.btn_process.bind("<Leave>", lambda _e: self._set_btn_hover(self.btn_process, False))
        self.btn_process.bind("<Return>", lambda _e: self.app.process_manager.process_discogs_data())
        self.btn_process.bind("<space>", lambda _e: self.app.process_manager.process_discogs_data())

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
            height=32,
            command=lambda: self.app.process_manager.clear_selected_metadata()
        )
        self.btn_clean.pack(fill="x", padx=10, pady=(0, 6))
        UiUtils(self.btn_clean, "Elimina los metadatos de los archivos seleccionados")

        self.btn_clean.bind("<Return>", lambda _e: self.app.process_manager.clear_selected_metadata())
        self.btn_clean.bind("<space>", lambda _e: self.app.process_manager.clear_selected_metadata())

        # --- ENCADENAMIENTO EXPLÍCITO DE TABULACIÓN ---
        self._bind_custom_tab_order()

    def _set_btn_hover(self, btn, is_hover):
        """Aplica visualmente el borde blanco al pasar el ratón por encima."""
        if is_hover:
            btn.configure(border_color="#FFFFFF", border_width=2)
        else:
            btn.configure(border_color=self.app.CORP_COLOR, border_width=2)

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
        if self.audio_player:
            self.audio_player.stop_and_unload()
            self.btn_play.configure(state="disabled", fg_color="gray")
            self.slider_audio.configure(state="disabled")
            self.lbl_audio_time.configure(text="Multiedición activa")

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
                    v for v in self.app.catalog_manager.catalog_values.get(catalog_key, [])
                    if v and v != self.app.CLEAR_OPTION and v != self.app.KEEP_VALUE
                ]
                options = [self.app.KEEP_VALUE, self.app.CLEAR_OPTION] + sorted(catalog_vals, key=lambda x: x.lower())
            else:
                _, col_index = self.app.PANEL_FIELD_COL_MAP[attr_name]
                distinct = sorted({
                    str(self.app.tree.item(r, "values")[col_index]).strip()
                    for r in selected_rows
                    if col_index < len(self.app.tree.item(r, "values"))
                       and self.app.tree.item(r, "values")[col_index]
                })
                options = [self.app.KEEP_VALUE, self.app.CLEAR_OPTION] + [
                    v for v in distinct if v and v not in (self.app.KEEP_VALUE, self.app.CLEAR_OPTION)
                ]

            multi_widget.configure(values=options)
            multi_widget.set(common_value if common_value in options else self.app.KEEP_VALUE)
            multi_widget.pack(fill="x")

        self.app._multi_select_mode = True
        self.display_multi_cover_placeholder(selected_rows=selected_rows)

    def exit_multi_mode(self):
        if self.btn_play:
            self.btn_play.configure(state="normal", fg_color=self.app.CORP_COLOR)
            self.slider_audio.configure(state="normal")
            self.lbl_audio_time.configure(text="00:00 / 00:00")

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

        if raw_value == self.app.CLEAR_OPTION:
            new_value = ""
        elif attr_name in self.panel_combo_fields:
            new_value = self.app.catalog_manager.normalize_catalog_text(raw_value)
        else:
            new_value = raw_value

        self.apply_field_to_all_selected(attr_name, new_value)

    def apply_field_to_all_selected(self, attr_name, new_value):
        if attr_name not in self.app.PANEL_FIELD_COL_MAP:
            return

        field_name, col_index = self.app.PANEL_FIELD_COL_MAP[attr_name]
        selected_rows = self.app.tree.selection()

        batch_actions = []
        updated = 0

        for row_id in selected_rows:
            values = list(self.app.tree.item(row_id, "values"))
            if col_index >= len(values):
                continue

            current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
            if current_value == new_value:
                continue

            file_path = self.app.file_paths_map.get(row_id)

            batch_actions.append(
                HistoryAction(file_path, row_id, field_name, col_index, current_value, new_value)
            )

            values[col_index] = new_value
            self.app.tree.item(row_id, values=values)

            if file_path and os.path.exists(file_path):
                self.app.audio_manager.save_single_tag(file_path, field_name, new_value, app=self.app)
                filename = os.path.basename(file_path)
                log_msg = LogManager.format_tree_log(
                    context="DETAIL",
                    action=f"Modificado campo multi '{field_name}' en",
                    filename=filename,
                    prev_vals={field_name: current_value},
                    new_vals={field_name: new_value}
                )
                self.logger.info(log_msg)
                updated += 1

        if batch_actions:
            self.app.undo_manager.record_action(batch_actions)

    def display_multi_cover_placeholder(self, selected_rows=None):
        selected_rows = list(selected_rows or self.app.tree.selection())
        has_any_cover = any(self.app.grid_panel.row_has_cover(row_id) for row_id in selected_rows)
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
                # Permite cargar imágenes incompletas/truncadas
                from PIL import ImageFile
                ImageFile.LOAD_TRUNCATED_IMAGES = True

                image_stream = io.BytesIO(cover_data)
                img = Image.open(image_stream)

                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                img = img.resize((160, 160), Image.Resampling.LANCZOS)

                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 160))
                self.label_cover.configure(image=ctk_img, text="")
                self.label_cover.image = ctk_img
                return
            except (OSError, SyntaxError, Exception) as e:
                self.logger.warning(f"No se pudo cargar la vista previa de la carátula (posiblemente corrupta): {str(e)}")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None

    def show_cover_context_menu(self, event):
        menu = self._cover_context_menu_multi if self.app._multi_select_mode else self._cover_context_menu
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def refresh_catalog_comboboxes(self):
        """Actualiza las opciones desplegables de los Comboboxes sin modificar ni borrar los datos de la fila."""
        clear_opt = getattr(self.app, "CLEAR_OPTION", "--- Vaciar ---")

        # 1. Álbumes
        album_combo = self.tag_entries.get("entry_album")
        if album_combo:
            allowed_albums = self.app.catalog_manager.get_catalog_combo_values("Album")
            album_combo.configure(values=allowed_albums)

        # 2. Géneros (filtrados por Álbum)
        genre_combo = self.tag_entries.get("entry_genre")
        current_album = album_combo.get().strip() if album_combo else ""

        if genre_combo:
            allowed_genres = self.app.catalog_manager.get_allowed_genres_for_album(current_album)
            combo_genres = allowed_genres + [clear_opt] if allowed_genres else [clear_opt]
            genre_combo.configure(values=combo_genres)

        # 3. Etiquetas (filtradas por Género)
        publisher_combo = self.tag_entries.get("entry_publisher")
        current_genre = genre_combo.get().strip() if genre_combo else ""

        if publisher_combo:
            allowed_publishers = self.app.catalog_manager.get_allowed_publishers_for_genre(current_genre)
            combo_publishers = allowed_publishers + [clear_opt] if allowed_publishers else [clear_opt]
            publisher_combo.configure(values=combo_publishers)

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

    def _get_target_row_id(self):
        if self._editing_row_id and self.app.tree.exists(self._editing_row_id):
            target = self._editing_row_id
            self._editing_row_id = None
            return target

        selected_rows = self.app.tree.selection()
        return selected_rows[0] if selected_rows else None

    def on_panel_catalog_selected(self, attr_name, catalog_key):
        if self.app._multi_select_mode:
            self.on_multi_panel_commit(attr_name)
            return

        row_id = self._get_target_row_id()
        combo = self.tag_entries.get(attr_name)
        if not combo:
            return

        raw_value = combo.get().strip()
        new_value = "" if raw_value == self.app.CLEAR_OPTION else self.app.catalog_manager.normalize_catalog_text(raw_value)

        if row_id:
            col_name, col_index = self.app.PANEL_FIELD_COL_MAP[attr_name]
            values = list(self.app.tree.item(row_id, "values"))
            current_val = str(values[col_index]).strip() if col_index < len(values) and values[col_index] is not None else ""

            if current_val != new_value:
                file_path = self.app.file_paths_map.get(row_id)
                action = HistoryAction(file_path, row_id, col_name, col_index, current_val, new_value)
                self.app.undo_manager.record_action(action)

                if file_path:
                    filename = os.path.basename(file_path)
                    log_msg = LogManager.format_tree_log(
                        context="DETAIL",
                        action=f"Modificado catalogo '{col_name}' en",
                        filename=filename,
                        prev_vals={col_name: current_val},
                        new_vals={col_name: new_value}
                    )
                    self.logger.info(log_msg)

            self.app.catalog_manager.apply_catalog_selection_to_row(row_id, attr_name, catalog_key, new_value)

        self.refresh_catalog_comboboxes()

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

        if self.app._multi_select_mode:
            self.on_multi_panel_commit(attr_name)
            return

        row_id = self._get_target_row_id()
        if not row_id:
            return

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

        file_path = self.app.file_paths_map.get(row_id)
        action = HistoryAction(file_path, row_id, col_name, col_index, current_value, new_value)
        self.app.undo_manager.record_action(action)

        values[col_index] = new_value
        self.app.tree.item(row_id, values=values)

        if file_path and os.path.exists(file_path):
            self.app.audio_manager.save_single_tag(file_path, col_name, new_value, app=self.app)
            filename = os.path.basename(file_path)
            log_msg = LogManager.format_tree_log(
                context="DETAIL",
                action=f"Modificado campo '{col_name}' en",
                filename=filename,
                prev_vals={col_name: current_value},
                new_vals={col_name: new_value}
            )
            self.logger.info(log_msg)

    def clear_fields(self):
        if self.audio_player:
            self.audio_player.stop_and_unload()

        self._editing_row_id = None
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
            if self.audio_player:
                self.audio_player.stop_and_unload()
            return

        item_id = selected[0]
        item = self.app.tree.item(item_id)
        values = item['values']
        if len(values) < 8:
            logger.warning("Fila con metadatos incompletos; se omite actualización de panel.")
            return

        # Carga directa de todos los campos
        self.set_panel_widget_value("entry_artist", values[1])
        self.set_panel_widget_value("entry_title", values[2])
        self.set_panel_widget_value("entry_mixartist", values[3])
        self.set_panel_widget_value("entry_album", values[4])
        self.set_panel_widget_value("entry_genre", values[5])
        self.set_panel_widget_value("entry_publisher", values[6])
        self.set_panel_widget_value("entry_year", values[7])

        # Actualiza las listas de sugerencias de los combos sin sobrescribir lo que se acaba de cargar
        self.refresh_catalog_comboboxes()

        file_path = self.app.file_paths_map.get(item_id)
        if file_path:
            self.display_cover_art(file_path)
            if self.audio_player:
                self.audio_player.load_track(file_path)

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
                        self.app.grid_panel.update_row_cover_status(item_id, "Sí")
                        filename = os.path.basename(file_path)
                        log_msg = LogManager.format_tree_log(
                            context="DETAIL",
                            action="Carátula pegada desde portapapeles en",
                            filename=filename,
                            prev_vals={"Cover": "Original"},
                            new_vals={"Cover": "Clipboard"}
                        )
                        self.logger.info(log_msg)

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo pegar la imagen: {e}")

    def apply_generic_cover(self, event=None):
        generic_bytes = self.app.process_manager._get_default_cover_bytes()
        if not generic_bytes:
            messagebox.showerror("Error", "No se encontró la imagen de carátula por defecto.")
            return

        selected_items = self.app.tree.selection()
        if not selected_items:
            selected_items = self.app.tree.get_children()

        if not selected_items:
            return

        for item_id in selected_items:
            file_path = self.app.file_paths_map.get(item_id)
            if file_path and os.path.exists(file_path):
                self.app.audio_manager.embed_cover_art(file_path, generic_bytes)
                self.app.grid_panel.update_row_cover_status(item_id, "Sí")
                filename = os.path.basename(file_path)
                log_msg = LogManager.format_tree_log(
                    context="DETAIL",
                    action="Aplicada carátula genérica a",
                    filename=filename,
                    prev_vals={"Cover": "Anterior"},
                    new_vals={"Cover": "Genérica"}
                )
                self.logger.info(log_msg)

        if selected_items:
            self.display_cover_art(generic_bytes)

    def remove_cover_art(self):
        selected_rows = self.app.tree.selection()

        if not selected_rows:
            selected_rows = self.app.tree.get_children()

        if not selected_rows:
            return

        for row_id in selected_rows:
            file_path = self.app.file_paths_map.get(row_id)

            if file_path and os.path.exists(file_path):
                self.app.audio_manager.strip_cover_tags(file_path)
                self.app.grid_panel.update_row_cover_status(row_id, "No")
                filename = os.path.basename(file_path)
                log_msg = LogManager.format_tree_log(
                    context="DETAIL",
                    action="Eliminada carátula de",
                    filename=filename,
                    prev_vals={"Cover": "Existente"},
                    new_vals={"Cover": None}
                )
                self.logger.info(log_msg)

        self.display_cover_art(None)

    def load_process_icon(self):
        ruta_logo = UiUtils.get_resource_path("assets/logo_blanco.png")
        if os.path.exists(ruta_logo):
            try:
                img_pil = Image.open(ruta_logo)
                return ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(20, 20))
            except Exception:
                return None
        return None

    def _focus_target(self, widget):
        """Fuerza el foco al widget indicado cancelando la propagación por defecto."""
        widget.focus_set()
        return "break"

    def _bind_custom_tab_order(self):
        """Establece la secuencia exacta de tabulación entre campos y botones."""
        ordered_attrs = [
            "entry_artist",
            "entry_title",
            "entry_mixartist",
            "entry_year",
            "entry_album",
            "entry_genre",
            "entry_publisher"
        ]

        for i in range(len(ordered_attrs)):
            curr_attr = ordered_attrs[i]
            prev_attr = ordered_attrs[i - 1] if i > 0 else None
            next_attr = ordered_attrs[i + 1] if i < len(ordered_attrs) - 1 else None

            curr_w = self.tag_entries[curr_attr]
            curr_multi_w = self.multi_entries[curr_attr]

            if prev_attr:
                prev_w = self.tag_entries[prev_attr]
                prev_multi_w = self.multi_entries[prev_attr]

                curr_w.bind("<Shift-Tab>", lambda _e, w=prev_w: self._focus_target(w))
                curr_multi_w.bind("<Shift-Tab>", lambda _e, w=prev_multi_w: self._focus_target(w))
                if hasattr(curr_w, "_entry"):
                    curr_w._entry.bind("<Shift-Tab>", lambda _e, w=prev_w: self._focus_target(w))
            else:
                curr_w.bind("<Shift-Tab>", lambda _e: self._focus_target(self.btn_clean))
                if hasattr(curr_w, "_entry"):
                    curr_w._entry.bind("<Shift-Tab>", lambda _e: self._focus_target(self.btn_clean))

            if next_attr:
                next_w = self.tag_entries[next_attr]
                next_multi_w = self.multi_entries[next_attr]

                curr_w.bind("<Tab>", lambda _e, w=next_w: self._focus_target(w))
                curr_multi_w.bind("<Tab>", lambda _e, w=next_multi_w: self._focus_target(w))
                if hasattr(curr_w, "_entry"):
                    curr_w._entry.bind("<Tab>", lambda _e, w=next_w: self._focus_target(w))

        last_w = self.tag_entries["entry_publisher"]
        last_multi_w = self.multi_entries["entry_publisher"]

        last_w.bind("<Tab>", lambda _e: self._focus_target(self.btn_process))
        last_multi_w.bind("<Tab>", lambda _e: self._focus_target(self.btn_process))
        if hasattr(last_w, "_entry"):
            last_w._entry.bind("<Tab>", lambda _e: self._focus_target(self.btn_process))

        self.btn_process.bind("<Tab>", lambda _e: self._focus_target(self.btn_clean))
        self.btn_process.bind("<Shift-Tab>", lambda _e: self._focus_target(self.tag_entries["entry_publisher"]))
        self.btn_process.bind("<FocusIn>", lambda _e, w=self.btn_process: self._on_widget_focus_in(w))
        self.btn_process.bind("<FocusOut>", lambda _e, w=self.btn_process: self._on_widget_focus_out(w))

        self.btn_clean.bind("<Tab>", lambda _e: self._focus_target(self.tag_entries["entry_artist"]))
        self.btn_clean.bind("<Shift-Tab>", lambda _e: self._focus_target(self.btn_process))
        self.btn_clean.bind("<FocusIn>", lambda _e, w=self.btn_clean: self._on_widget_focus_in(w))
        self.btn_clean.bind("<FocusOut>", lambda _e, w=self.btn_clean: self._on_widget_focus_out(w))