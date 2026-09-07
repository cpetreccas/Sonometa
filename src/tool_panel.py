import tkinter as tk
import customtkinter as ctk
from dialogs import DialogManager


class CustomMenuDropdown(ctk.CTkToplevel):
    """Ventana desplegable flotante con estética estilo Bloc de notas (Windows 11)."""

    def __init__(self, parent_panel, items_config, **kwargs):
        super().__init__(parent_panel.app, **kwargs)
        self.parent_panel = parent_panel
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Vincular la ventana al padre
        self.transient(parent_panel.app)

        # Manejo de transparencia para CTkToplevel en Windows
        transparent_key = "#000001"
        self.configure(fg_color=transparent_key)
        try:
            self.wm_attributes("-transparentcolor", transparent_key)
        except Exception:
            self.configure(fg_color="#272727")

        # Contenedor principal con esquinas redondeadas y borde tenue estilo Fluent
        self.frame_border = ctk.CTkFrame(
            self,
            fg_color="#272727",
            border_color="#3A3A3A",
            border_width=1,
            corner_radius=8
        )
        self.frame_border.pack(fill="both", expand=True)

        for item in items_config:
            item_type = item.get("type", "command")

            if item_type == "separator":
                # Contenedor para dar margen vertical sin colapsar el alto de la línea
                sep_container = ctk.CTkFrame(
                    self.frame_border,
                    fg_color="transparent",
                    height=7
                )
                sep_container.pack(fill="x", padx=6, pady=1)
                sep_container.pack_propagate(False)

                # Usar tkinter.Frame evita la máscara/redondeado de CTk y mantiene 1px real visible.
                sep_line = tk.Frame(
                    sep_container,
                    height=1,
                    bg="#454545",
                    bd=0,
                    highlightthickness=0
                )
                sep_line.pack(fill="x", side="top", pady=3)

            elif item_type == "command":
                label_text = item.get("label", "")
                shortcut_text = item.get("accelerator", "")
                cmd = item.get("command", None)
                is_enabled = item.get("enabled", True)

                item_frame = ctk.CTkFrame(
                    self.frame_border,
                    fg_color="transparent",
                    corner_radius=4,
                    height=30
                )
                item_frame.pack(fill="x", padx=4, pady=1)
                item_frame.pack_propagate(False)

                text_color = "#FFFFFF" if is_enabled else "#666666"
                shortcut_color = "#999999" if is_enabled else "#555555"

                lbl_title = ctk.CTkLabel(
                    item_frame,
                    text=label_text,
                    anchor="w",
                    text_color=text_color,
                    font=ctk.CTkFont(family="Segoe UI", size=12)
                )
                lbl_title.pack(side="left", padx=(10, 16), expand=True, fill="x")

                lbl_shortcut = None
                if shortcut_text:
                    lbl_shortcut = ctk.CTkLabel(
                        item_frame,
                        text=shortcut_text,
                        anchor="e",
                        text_color=shortcut_color,
                        font=ctk.CTkFont(family="Segoe UI", size=11)
                    )
                    lbl_shortcut.pack(side="right", padx=(0, 10))

                if is_enabled:
                    hover_bg = "#383838"

                    def _on_enter(e, f=item_frame):
                        f.configure(fg_color=hover_bg)

                    def _on_leave(e, f=item_frame):
                        f.configure(fg_color="transparent")

                    widgets = [item_frame, lbl_title]
                    if lbl_shortcut:
                        widgets.append(lbl_shortcut)

                    for w in widgets:
                        w.bind("<Enter>", _on_enter)
                        w.bind("<Leave>", _on_leave)
                        w.bind("<Button-1>", lambda e, c=cmd: self._execute_command(c))

            elif item_type == "checkbutton":
                label_text = item.get("label", "")
                var = item.get("variable", None)
                cmd = item.get("command", None)

                item_frame = ctk.CTkFrame(
                    self.frame_border,
                    fg_color="transparent",
                    corner_radius=4,
                    height=30
                )
                item_frame.pack(fill="x", padx=4, pady=1)
                item_frame.pack_propagate(False)

                chk = ctk.CTkCheckBox(
                    item_frame,
                    text=label_text,
                    variable=var,
                    height=20,
                    corner_radius=3,
                    checkbox_width=14,
                    checkbox_height=14,
                    border_width=1,
                    fg_color=getattr(self.parent_panel.app, "CORP_COLOR", "#6B21A8"),
                    hover_color=getattr(self.parent_panel.app, "CORP_HOVER", "#581C87"),
                    text_color="#FFFFFF",
                    font=ctk.CTkFont(family="Segoe UI", size=12),
                    command=lambda c=cmd: self._execute_command(c, keep_open=True)
                )
                chk.pack(side="left", padx=(8, 8), pady=5)

    def _execute_command(self, cmd, keep_open=False):
        if callable(cmd):
            cmd()
        if not keep_open:
            self.parent_panel._close_active_menu()


class ToolPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="#1E1E1E", height=28, corner_radius=0, **kwargs)
        self.pack_propagate(False)

        self.app = master
        self.active_dropdown = None
        self.active_button = None
        self.menu_buttons = []

        self._focus_bindings = []
        self._setup_classic_menu_bar()

    def _on_toggle_review_covers(self):
        """Callback al conmutar el checkbox de revisión de carátulas."""
        is_checked = self.app.review_covers_var.get()
        if hasattr(self.app, "catalog_manager"):
            self.app.catalog_manager.manual_cover_selection = is_checked
            self.app.catalog_manager.save_settings()
        if hasattr(self.app, "_on_toggle_manual_cover_review"):
            self.app._on_toggle_manual_cover_review()

    def _setup_classic_menu_bar(self):
        app = self.app

        # Definir/Garantizar variables de control si no existen
        if not hasattr(app, "review_covers_var") or app.review_covers_var is None:
            initial_val = True
            if hasattr(app, "catalog_manager"):
                initial_val = getattr(app.catalog_manager, "manual_cover_selection", True)
            app.review_covers_var = tk.BooleanVar(value=initial_val)

        if not hasattr(app, "show_detail_panel_var") or app.show_detail_panel_var is None:
            app.show_detail_panel_var = tk.BooleanVar(value=False)

        categories = [
            ("Archivo", [
                {"type": "command", "label": "Abrir Carpeta…", "accelerator": "Ctrl+O", "command": app.browse_folder},
                {"type": "separator"},
                {"type": "command", "label": "Salir", "accelerator": "Alt+F4", "command": app.on_close}
            ]),
            ("Edición", [
                {"type": "command", "label": "Deshacer", "accelerator": "Ctrl+Z", "command": app.undo_manager.undo},
                {"type": "command", "label": "Rehacer", "accelerator": "Ctrl+Y", "command": app.undo_manager.redo},
                {"type": "separator"},
                {"type": "command", "label": "Buscar…", "accelerator": "Ctrl+F", "command": lambda: app.focus_header_search()},
                {"type": "command", "label": "Reemplazar…", "accelerator": "Ctrl+R", "command": lambda: app.open_replace_dialog()},
                {"type": "separator"},
                {"type": "command", "label": "Seleccionar Todo", "accelerator": "Ctrl+A", "command": lambda: app.grid_panel.select_all_rows()},
                {"type": "command", "label": "Deseleccionar Todo", "accelerator": "Esc", "command": lambda: app.grid_panel.tree.selection_remove(app.grid_panel.tree.selection())}
            ]),
            ("Acciones", [
                {"type": "command", "label": "Procesar", "accelerator": "", "command": lambda: app.process_manager.process_discogs_data()},
                {"type": "command", "label": "Actualizar", "accelerator": "F5", "command": lambda: app.refresh_folder() if hasattr(app, "refresh_folder") else None},
                {"type": "command", "label": "Limpiar Metadatos Selección", "command": app.clear_all},
            ]),
            ("Ver", [
                {"type": "command", "label": "Aumentar Zoom", "accelerator": "Ctrl++", "command": lambda: app.grid_panel._on_key_zoom_in(None)},
                {"type": "command", "label": "Reducir Zoom", "accelerator": "Ctrl+-", "command": lambda: app.grid_panel._on_key_zoom_out(None)},
                {"type": "command", "label": "Restablecer Zoom", "accelerator": "Ctrl+0", "command": lambda: app.grid_panel._on_key_zoom_reset(None)},
            ]),
            ("Preferencias", [
                {"type": "checkbutton", "label": "Revisar carátulas", "variable": app.review_covers_var, "command": self._on_toggle_review_covers},
                {"type": "checkbutton", "label": "Ver detalles", "variable": app.show_detail_panel_var, "command": app.toggle_detail_panel},
                {"type": "separator"},
                {"type": "command", "label": "Gestión de Catálogos…", "command": lambda: DialogManager.open_unified_catalog_manager(app)}
            ]),
            ("Ayuda", [
                {"type": "command", "label": "Ver logs", "command": lambda: DialogManager.show_logs_dialog(app)},
                {"type": "separator"},
                {"type": "command", "label": "Acerca de Sonometa", "command": lambda: DialogManager.show_about_dialog(app)}
            ])
        ]

        self.menu_buttons.clear()

        for title, items in categories:
            btn = ctk.CTkButton(
                self,
                text=title,
                width=1,
                height=22,
                corner_radius=4,
                fg_color="transparent",
                hover_color="#2A2D32",
                text_color="#CCCCCC",
                font=ctk.CTkFont(family="Segoe UI", size=12)
            )

            btn.configure(command=lambda i=items, b=btn: self._on_button_click(i, b))
            btn.bind("<Enter>", lambda e, i=items, b=btn: self._on_button_hover(i, b))
            btn.pack(side="left", padx=4, pady=2)
            self.menu_buttons.append((btn, items))

    def _on_button_click(self, items, button):
        if self.active_button == button:
            self._close_active_menu()
            return
        self._show_dropdown(items, button)

    def _on_button_hover(self, items, button):
        if self.active_dropdown and self.active_button != button:
            self._show_dropdown(items, button)

    def _destroy_active_dropdown(self):
        if self.active_dropdown:
            try:
                # Ocultar primero la ventana de forma inmediata
                self.active_dropdown.withdraw()
                self.active_dropdown.update_idletasks()
                self.active_dropdown.destroy()
            except Exception:
                pass
            finally:
                self.active_dropdown = None

    def _show_dropdown(self, items, button):
        self._destroy_active_dropdown()

        if self.active_button:
            self.active_button.configure(fg_color="transparent", text_color="#CCCCCC")

        button.configure(fg_color="#2A2D32", text_color="#FFFFFF")

        self.active_button = button
        dropdown = CustomMenuDropdown(self, items)
        self.active_dropdown = dropdown

        dropdown.update_idletasks()
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height() + 2
        dropdown.geometry(f"+{x}+{y}")

        self._setup_app_focus_listeners()

    def _setup_app_focus_listeners(self):
        self._clear_app_focus_listeners()
        app = self.app

        b1 = app.bind_all("<ButtonPress-1>", self._on_global_click, add="+")
        b2 = app.bind("<FocusOut>", lambda e: self._close_active_menu(), add="+")
        b3 = app.bind("<Unmap>", lambda e: self._close_active_menu(), add="+")

        self._focus_bindings = [
            ("bind_all", "<ButtonPress-1>", b1),
            ("bind", "<FocusOut>", b2),
            ("bind", "<Unmap>", b3)
        ]

    def _clear_app_focus_listeners(self):
        for btype, event, bid in self._focus_bindings:
            try:
                if btype == "bind_all":
                    self.app.unbind_all(event)
                else:
                    self.app.unbind(event, bid)
            except Exception:
                pass
        self._focus_bindings.clear()

    def _on_global_click(self, event):
        if not self.active_dropdown:
            return

        x_root = event.x_root
        y_root = event.y_root

        if any(self._is_pointer_inside(btn, x_root, y_root) for btn, _ in self.menu_buttons):
            return

        if self._is_pointer_inside(self.active_dropdown, x_root, y_root):
            return

        self._close_active_menu()

    def _is_pointer_inside(self, widget, x_root, y_root):
        try:
            x1 = widget.winfo_rootx()
            y1 = widget.winfo_rooty()
            x2 = x1 + widget.winfo_width()
            y2 = y1 + widget.winfo_height()
            return x1 <= x_root <= x2 and y1 <= y_root <= y2
        except Exception:
            return False

    def _close_active_menu(self):
        self._clear_app_focus_listeners()
        self._destroy_active_dropdown()

        if self.active_button:
            self.active_button.configure(fg_color="transparent", text_color="#CCCCCC")
            self.active_button = None