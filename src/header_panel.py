import customtkinter as ctk
import theme

class HeaderPanel(ctk.CTkFrame):
    def __init__(self, parent, app, logo_pil):
        # Header con el fondo unificado
        super().__init__(parent, fg_color=theme.BG_CARD, corner_radius=0)
        self.app = app

        self.pack(fill="x", padx=0, pady=0)

        # Contenedor interno con padding exactamente igual al de los paneles inferiores (15px)
        self.inner_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.inner_frame.pack(fill="x", padx=theme.SPACE_MD, pady=6)

        # Ancho ajustado para que coincida exactamente con el panel izquierdo
        # (Si DetailPanel cambia, este valor sincroniza la columna 0)
        self.detail_width = 265

        self.inner_frame.grid_columnconfigure(0, weight=0, minsize=self.detail_width)
        self.inner_frame.grid_columnconfigure(1, weight=1)
        self.inner_frame.grid_columnconfigure(2, weight=0)

        # --- 1. LOGO PRINCIPAL (Columna 0) ---
        if logo_pil:
            orig_w, orig_h = logo_pil.size
            target_height = 38
            target_width = int(orig_w * (target_height / orig_h))

            header_logo = ctk.CTkImage(
                light_image=logo_pil,
                dark_image=logo_pil,
                size=(target_width, target_height)
            )

            lbl_logo = ctk.CTkLabel(self.inner_frame, image=header_logo, text="")
            lbl_logo.grid(row=0, column=0, sticky="w")

        # --- 2. ÁREA DE RUTA Y REFRESCAR (Columna 1 - Exactamente sobre el Grid) ---
        self.path_card = ctk.CTkFrame(
            self.inner_frame,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BORDER_FOCUS,
            corner_radius=theme.RADIUS_CONTROL
        )
        self.path_card.grid(row=0, column=1, sticky="ew", padx=(0, 15), ipady=1)

        # Botón de refrescar
        self.btn_refresh = ctk.CTkButton(
            self.path_card,
            text="↻",
            width=32,
            height=30,
            fg_color=self.app.CORP_COLOR,
            hover_color=self.app.CORP_HOVER,
            font=ctk.CTkFont(size=16, weight="bold"),
            corner_radius=theme.RADIUS_CONTROL,
            command=self.app.refresh_folder
        )
        self.btn_refresh.pack(side="left", padx=(4, 8), pady=3)

        # Icono y etiqueta de la carpeta
        self.lbl_folder_icon = ctk.CTkLabel(
            self.path_card,
            text="📁",
            font=ctk.CTkFont(size=18),
            text_color=theme.TEXT_MUTED
        )
        self.lbl_folder_icon.pack(side="left", padx=(4, 6), pady=(0, 5))

        self.label_folder = ctk.CTkLabel(
            self.path_card,
            text="Haz clic aquí para seleccionar una carpeta...",
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12),
            anchor="w",
            cursor="hand2"
        )
        self.label_folder.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.label_folder.bind("<Button-1>", lambda e: self.app.browse_folder())
        self.lbl_folder_icon.bind("<Button-1>", lambda e: self.app.browse_folder())

        # --- 3. BUSCADOR INTEGRADO (Columna 2) ---
        self.entry_search = ctk.CTkEntry(
            self.inner_frame,
            width=280,
            height=36,
            placeholder_text="🔍  Buscar en la lista...",
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_FOCUS,
            border_width=1,
            text_color=theme.TEXT_MAIN,
            placeholder_text_color=theme.TEXT_SUBTLE,
            corner_radius=theme.RADIUS_CONTROL,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12)
        )
        self.entry_search.grid(row=0, column=2, sticky="e")

        # Configuración de eventos de teclado (ENTER / ESCAPE)
        self.entry_search.bind("<KeyRelease>", self._on_search_key_release)
        self.entry_search.bind("<Return>", self._on_search_submit)
        self.entry_search.bind("<KP_Enter>", self._on_search_submit)
        self.entry_search.bind("<Escape>", self._on_search_cancel)

        # Autoadaptación de ancho al renderizar
        self.bind("<Configure>", self._sync_alignment)

    def _sync_alignment(self, event=None):
        """Ajusta dinámicamente la columna 0 solo si el panel de detalles ya está creado."""
        if hasattr(self.app, "detail_panel") and self.app.detail_panel is not None:
            try:
                real_width = self.app.detail_panel.winfo_width()
                if real_width > 50 and real_width != self.detail_width:
                    self.detail_width = real_width
                    self.inner_frame.grid_columnconfigure(0, minsize=self.detail_width)
            except Exception:
                pass  # Ignora si el componente está en proceso de destrucción o renderizado

    def _on_search_key_release(self, event):
        if event.keysym in ("Return", "Escape", "KP_Enter"):
            return
        self._sync_and_filter()

    def _sync_and_filter(self):
        if hasattr(self.app, "search_manager"):
            text = self.entry_search.get()
            if hasattr(self.app.search_manager, "entry_search"):
                self.app.search_manager.entry_search.delete(0, "end")
                self.app.search_manager.entry_search.insert(0, text)
            self.app.search_manager.apply_search_filter()

    def _on_search_submit(self, event=None):
        self._sync_and_filter()
        self.focus_grid()
        return "break"

    def _on_search_cancel(self, event=None):
        self.entry_search.delete(0, "end")
        self._sync_and_filter()
        self.focus_grid()
        return "break"

    def focus_grid(self):
        if hasattr(self.app, "grid_panel") and hasattr(self.app.grid_panel, "tree"):
            self.app.grid_panel.tree.focus_set()
            children = self.app.grid_panel.tree.get_children()
            if children and not self.app.grid_panel.tree.selection():
                self.app.grid_panel.tree.selection_set(children[0])
                self.app.grid_panel.tree.focus(children[0])

    def set_folder_path(self, path):
        if path:
            self.label_folder.configure(text=path, text_color=theme.TEXT_MAIN)
            self.lbl_folder_icon.configure(text_color=theme.PRIMARY_LIGHT)
        else:
            self.label_folder.configure(text="Haz clic aquí para seleccionar una carpeta...", text_color=theme.TEXT_MUTED)
            self.lbl_folder_icon.configure(text_color=theme.TEXT_MUTED)