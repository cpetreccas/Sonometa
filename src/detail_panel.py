import io
import os
import sys
import logging as logger
import tkinter as tk
from tkinter import messagebox
from io import BytesIO
import customtkinter as ctk
from mutagen import File as MutagenFile
from PIL import Image, ImageGrab

from ui_utils import UiUtils
from undo_manager import HistoryAction
from audio_player import AudioPlayer
from log_handler import LogManager


class DetailPanel:
    """Panel lateral de metadatos y carátula desacoplado de la ventana principal."""

    BORDER_DEFAULT = "#3F3F46"  # Borde fino sutil para cajas en reposo

    def __init__(self, app, parent, logger, get_resource_path, fallback_process_icon=None):
        self.icono_procesar = self.load_process_icon()

        self.app = app
        self.parent = parent
        self.logger = logger
        self.get_resource_path = get_resource_path
        self.fallback_process_icon = fallback_process_icon

        # Guarda la imagen PIL en memoria para redimensionarla dinámicamente según la altura
        self._current_raw_cover_pil = None
        self._resize_timer = None

        # Guarda el ID de la fila que se estaba editando antes de cambiar de selección
        self._editing_row_id = None
        self._entry_context_menu = None

        self.panel_combo_fields = {
            "entry_album": "Album",
            "entry_genre": "Genre",
            "entry_publisher": "Publisher"
        }
        self.tag_entries = {}
        self.multi_entries = {}

        self.frame_sidebar = None
        self.frame_cover_container = None
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

        self._setup_entry_context_menu()
        self._setup_tag_panel()
        self.audio_player = AudioPlayer(self)

    @staticmethod
    def get_fast_audio_duration(file_path):
        """Lee únicamente el header del archivo sin decodificar audio completo."""
        try:
            audio = MutagenFile(file_path)
            if audio and audio.info and hasattr(audio.info, "length"):
                return float(audio.info.length)
        except Exception:
            pass
        return 0.0

    def handle_space_toggle(self):
        """Maneja el evento global de la tecla Espacio sobre el reproductor de audio."""
        if not self.audio_player:
            return
        selected = self.app.tree.selection()
        if len(selected) == 1:
            file_path = self.app.file_paths_map.get(selected[0])
            if file_path and os.path.exists(file_path):
                if self.audio_player.current_file_path != file_path:
                    self.audio_player.load_track(file_path)
                self.audio_player.toggle_play_pause()

    def _setup_entry_context_menu(self):
        """Crea el menú contextual para las entradas de texto (Copiar, Cortar, Pegar, Seleccionar todo)."""
        self._entry_context_menu = tk.Menu(
            self.app,
            tearoff=0,
            bg="#2B2B2B",
            fg="#FFFFFF",
            activebackground=self.app.CORP_COLOR,
            activeforeground="#FFFFFF",
            bd=1,
            relief="solid",
            font=("Segoe UI", 9)
        )
        self._entry_context_menu.add_command(label="Cortar", command=lambda: self._entry_action("cut"))
        self._entry_context_menu.add_command(label="Copiar", command=lambda: self._entry_action("copy"))
        self._entry_context_menu.add_command(label="Pegar", command=lambda: self._entry_action("paste"))
        self._entry_context_menu.add_separator()
        self._entry_context_menu.add_command(label="Seleccionar todo", command=lambda: self._entry_action("select_all"))

    def _show_entry_context_menu(self, event):
        """Muestra el menú contextual en la posición del puntero para el widget enfocado."""
        widget = event.widget
        widget.focus_set()
        self._entry_target_widget = widget
        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"
        try:
            self._entry_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._entry_context_menu.grab_release()

    def _entry_action(self, action):
        """Ejecuta acciones de edición de texto sobre el widget activo."""
        widget = getattr(self, "_entry_target_widget", None)
        if not widget:
            return
        try:
            if action == "cut":
                widget.event_generate("<<Cut>>")
            elif action == "copy":
                widget.event_generate("<<Copy>>")
            elif action == "paste":
                widget.event_generate("<<Paste>>")
            elif action == "select_all":
                if hasattr(widget, "select_range"):
                    widget.select_range(0, "end")
                    widget.icursor("end")
                else:
                    widget.event_generate("<<SelectAll>>")
        except Exception as e:
            self.logger.debug(f"Error en acción de menú contextual de texto: {e}")

    def update_audio_time_display(self, current_sec, total_sec):
        """Formatea e imprime el estado temporal MM:SS / MM:SS en la etiqueta garantizando valores válidos."""
        def format_time(seconds):
            seconds = max(0, int(seconds or 0))
            mins = seconds // 60
            secs = seconds % 60
            return f"{mins:02d}:{secs:02d}"

        str_current = format_time(current_sec)
        str_total = format_time(total_sec)
        self.lbl_audio_time.configure(text=f"{str_current} / {str_total}")

        # Habilitar slider y ajustar límites para poder adelantar la pista
        if total_sec > 0:
            self.slider_audio.configure(state="normal", from_=0, to=1)
        else:
            self.slider_audio.configure(state="disabled", from_=0, to=1)

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
        """Restaura el borde original (#3F3F46) al perder el foco y procesa cambios."""
        try:
            if widget == self.btn_clean:
                widget.configure(border_color="#DC2626", border_width=1)
            elif widget == self.btn_process:
                widget.configure(border_color=self.app.CORP_COLOR, border_width=1)
            else:
                widget.configure(border_color=self.BORDER_DEFAULT, border_width=1)
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
        """Inicializa los menús contextuales de la carátula con estilo mejorado para modo individual y múltiple."""
        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"

        menu_style = {
            "bg": "#2B2B2B",
            "fg": "#FFFFFF",
            "activebackground": self.app.CORP_COLOR,
            "activeforeground": "#FFFFFF",
            "bd": 1,
            "relief": "solid",
            "font": ("Segoe UI", 9)
        }

        self._cover_context_menu = tk.Menu(self.app, tearoff=0, **menu_style)
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

        self._cover_context_menu_multi = tk.Menu(self.app, tearoff=0, **menu_style)
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

        btn_right = "<Button-2>" if sys.platform == "darwin" else "<Button-3>"

        for idx, (label_text, attr_name) in enumerate(fields):
            top_pad = 8 if idx == 0 else 4
            lbl = ctk.CTkLabel(
                self.frame_sidebar,
                text=label_text,
                anchor="w",
                font=ctk.CTkFont(family="Inter", size=11, weight="bold")
            )
            lbl.pack(fill="x", padx=10, pady=(top_pad, 1))

            field_frame = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
            field_frame.pack(fill="x", padx=10, pady=(0, 4))

            if attr_name in self.panel_combo_fields:
                catalog_key = self.panel_combo_fields[attr_name]
                widget = ctk.CTkComboBox(
                    field_frame,
                    values=self.app.catalog_manager.get_catalog_combo_values(catalog_key),
                    state="readonly",
                    height=26,
                    border_width=1,
                    border_color=self.BORDER_DEFAULT,
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
                    border_color=self.BORDER_DEFAULT,
                    font=ctk.CTkFont(family="Inter", size=12)
                )
                widget.bind("<FocusIn>", lambda _e, _w=widget: self._on_widget_focus_in(_w))
                widget.bind("<FocusOut>", lambda _e, _w=widget, _a=attr_name: self._on_widget_focus_out(_w, _a, is_combo=False))
                widget.bind("<Return>", lambda _e, _attr=attr_name: self.on_panel_text_field_enter(_attr))

                # Asignación de menú contextual en entradas estándar
                widget.bind(btn_right, self._show_entry_context_menu)
                if hasattr(widget, "_entry"):
                    widget._entry.bind(btn_right, self._show_entry_context_menu)

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
                border_color=self.BORDER_DEFAULT,
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
                multi_widget.bind(btn_right, self._show_entry_context_menu)
                if hasattr(multi_widget, "_entry"):
                    multi_widget._entry.bind(btn_right, self._show_entry_context_menu)
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
        lbl_cover_title.pack(fill="x", padx=10, pady=(4, 1))

        self.frame_cover_container = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
        self.frame_cover_container.pack(fill="both", expand=True, padx=10, pady=(2, 2))

        self.label_cover = ctk.CTkLabel(
            self.frame_cover_container,
            text="Sin carátula",
            width=150,
            height=150,
            fg_color="transparent",
            text_color="gray",
            border_color="#6B7280",
            border_width=1,
            cursor="hand2"
        )
        self.label_cover.pack(anchor="center", expand=True)
        UiUtils(self.label_cover, "Clic derecho para opciones de carátula")

        self.frame_cover_container.bind("<Configure>", self._on_cover_container_resize)
        self._setup_cover_context_menus()

        # --- SECCIÓN MINI REPRODUCTOR DE AUDIO ---
        self.frame_player = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
        self.frame_player.pack(fill="x", padx=10, pady=(2, 6))

        player_top = ctk.CTkFrame(self.frame_player, fg_color="transparent")
        player_top.pack(fill="x")

        self.btn_play = ctk.CTkButton(
            player_top,
            text="▶",
            width=30,
            height=26,
            fg_color=self.app.CORP_COLOR,
            hover_color="#581C87",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.audio_player.toggle_play_pause() if self.audio_player else None
        )
        self.btn_play.pack(side="left", padx=(0, 6))

        self.slider_audio = ctk.CTkSlider(
            player_top,
            from_=0,
            to=1,
            height=12,
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
        frame_actions = ctk.CTkFrame(self.frame_sidebar, fg_color="transparent")
        frame_actions.pack(fill="x", side="bottom", padx=10, pady=(4, 8))

        self.btn_process = ctk.CTkButton(
            frame_actions,
            text="Procesar",
            image=self.app.process_icon,
            compound="left",
            fg_color=self.app.CORP_COLOR,
            hover_color="#6D28D9",
            border_width=2,
            border_color=self.app.CORP_COLOR,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=30,
            command=self.app.process_manager.process_discogs_data
        )
        self.btn_process.pack(fill="x", pady=(0, 5))
        UiUtils(self.btn_process, "Busca metadatos y carátulas de los archivos seleccionados")

        self.btn_process.bind("<Enter>", lambda _e: self._set_btn_hover(self.btn_process, True))
        self.btn_process.bind("<Leave>", lambda _e: self._set_btn_hover(self.btn_process, False))
        self.btn_process.bind("<Return>", lambda _e: self.app.process_manager.process_discogs_data())
        self.btn_process.bind("<space>", lambda _e: self.app.process_manager.process_discogs_data())

        self.btn_clean = ctk.CTkButton(
            frame_actions,
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
            height=30,
            command=lambda: self.app.process_manager.clear_selected_metadata()
        )
        self.btn_clean.pack(fill="x")
        UiUtils(self.btn_clean, "Elimina los metadatos de los archivos seleccionados")

        self.btn_clean.bind("<Return>", lambda _e: self.app.process_manager.clear_selected_metadata())
        self.btn_clean.bind("<space>", lambda _e: self.app.process_manager.clear_selected_metadata())

        self._bind_custom_tab_order()

    def _on_cover_container_resize(self, event):
        """Calcula el tamaño óptimo de la carátula basado en el espacio vertical disponible."""
        if self._resize_timer:
            self.app.after_cancel(self._resize_timer)
        self._resize_timer = self.app.after(30, self._apply_dynamic_cover_resize)

    def _apply_dynamic_cover_resize(self):
        """Ajusta la imagen y la caja entre 60px y 230px según el alto libre del contenedor."""
        if not self.frame_cover_container:
            return

        container_h = self.frame_cover_container.winfo_height()
        container_w = self.frame_cover_container.winfo_width()

        if container_h <= 10 or container_w <= 10:
            return

        max_available = min(container_w, container_h)
        target_size = int(max(60, min(230, max_available - 8)))

        self.label_cover.configure(width=target_size, height=target_size)

        if self._current_raw_cover_pil:
            try:
                resized_img = self._current_raw_cover_pil.resize(
                    (target_size, target_size), Image.Resampling.LANCZOS
                )
                ctk_img = ctk.CTkImage(light_image=resized_img, dark_image=resized_img, size=(target_size, target_size))
                self.label_cover.configure(image=ctk_img, text="")
                self.label_cover.image = ctk_img
            except Exception as e:
                self.logger.warning(f"Error al redimensionar carátula responsiva: {e}")

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

            # Preserva la duración de la pista seleccionada en lugar de reiniciarla a cero
            selected = self.app.tree.selection()
            if selected:
                file_path = self.app.file_paths_map.get(selected[0])
                if file_path:
                    total_dur = self.get_fast_audio_duration(file_path)
                    self.update_audio_time_display(0, total_dur)
                else:
                    self.lbl_audio_time.configure(text="00:00 / 00:00")
            else:
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
        self._current_raw_cover_pil = None
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
                from PIL import ImageFile
                ImageFile.LOAD_TRUNCATED_IMAGES = True

                image_stream = io.BytesIO(cover_data)
                img = Image.open(image_stream)

                if img.mode not in ("RGB", "RGBA"):
                    img = img.convert("RGB")

                self._current_raw_cover_pil = img
                self._apply_dynamic_cover_resize()
                return
            except (OSError, SyntaxError, Exception) as e:
                self.logger.warning(f"No se pudo cargar la vista previa de la carátula (posiblemente corrupta): {str(e)}")

        self._current_raw_cover_pil = None
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
        """Limpia la interfaz sin destruir la duración del reproductor para la fila seleccionada."""
        selected = self.app.tree.selection()
        current_file = self.app.file_paths_map.get(selected[0]) if selected else None

        if self.audio_player:
            # Detiene la música pero conserva el archivo/duración si sigue habiendo una fila seleccionada
            self.audio_player.stop_and_unload(keep_duration=bool(current_file))

        self._editing_row_id = None
        self._current_raw_cover_pil = None
        for widget in self.tag_entries.values():
            if isinstance(widget, ctk.CTkComboBox):
                widget.set("")
            else:
                widget.delete(0, "end")

        self.label_cover.configure(image="", text="Sin carátula")
        self.label_cover.image = None

        # Si hay un archivo seleccionado, mantenemos su duración visible y lista para reproducir
        if current_file and os.path.exists(current_file):
            total_duration = self.get_fast_audio_duration(current_file)
            if total_duration > 0:
                if self.audio_player:
                    self.audio_player.load_track(current_file)
                    self.audio_player.total_length = total_duration
                self.update_audio_time_display(0, total_duration)

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
        if file_path and os.path.exists(file_path):
            self.display_cover_art(file_path)

            # 1. Leer la duración exacta directamente de la cabecera del archivo de audio
            total_duration = self.get_fast_audio_duration(file_path)

            # 2. Cargar la pista en el reproductor manteniendo el buffer listo
            if self.audio_player:
                self.audio_player.load_track(file_path)
                if total_duration > 0:
                    self.audio_player.total_length = total_duration

            # 3. Forzar el refresco de la etiqueta de tiempo al final del ciclo
            if total_duration > 0:
                self.update_audio_time_display(0, total_duration)

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