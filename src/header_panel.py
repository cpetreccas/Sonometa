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
        self.detail_width = 260

        # Columnas: 0 marca (mismo ancho que el panel lateral + su margen, para que
        # la ruta empiece alineada con la tabla) · 1 ruta (se estira) · 2 indicador
        # de filtro · 4 separador · 5 selector de vista, que Ctrl+F sustituye por el
        # buscador (toggle_search). El indicador y el selector los crea App:
        # place_navigation().
        self.inner_frame.grid_columnconfigure(0, weight=0, minsize=self.detail_width + self.SIDEBAR_GAP)
        self.inner_frame.grid_columnconfigure(1, weight=1)
        for col in (2, 3, 4, 5):
            self.inner_frame.grid_columnconfigure(col, weight=0)

        # --- 1. MARCA (Columna 0) ---
        # Igual que la PWA (guía, tipografía): isotipo + "Sonometa" en blanco,
        # versión pequeña en morado y subtítulo en gris con letras espaciadas.
        self._build_brand(logo_pil)

        # --- 2. ÁREA DE RUTA Y REFRESCAR (Columna 1 - Exactamente sobre el Grid) ---
        self.path_card = ctk.CTkFrame(
            self.inner_frame,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BORDER_FOCUS,
            corner_radius=theme.RADIUS_CONTROL
        )
        self.path_card.grid(row=0, column=1, sticky="ew", padx=(0, 12), ipady=1)

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

        # --- 3. BUSCADOR (oculto; sustituye al selector de vista con Ctrl+F) ---
        self.entry_search = ctk.CTkEntry(
            self.inner_frame,
            width=320,
            height=36,
            placeholder_text="🔍  Buscar en la lista…",
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_QUIET,
            border_width=1,
            text_color=theme.TEXT_MAIN,
            placeholder_text_color=theme.TEXT_SUBTLE,
            corner_radius=theme.RADIUS_CONTROL,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12)
        )
        self._search_open = False

        # Teclado: Intro aplica y cierra (el filtro se conserva), Esc limpia y cierra.
        self.entry_search.bind("<KeyRelease>", self._on_search_key_release)
        self.entry_search.bind("<Return>", self._on_search_submit)
        self.entry_search.bind("<KP_Enter>", self._on_search_submit)
        self.entry_search.bind("<Escape>", self._on_search_cancel)

        # Autoadaptación de ancho al renderizar
        self.bind("<Configure>", self._sync_alignment)

    # Margen derecho del panel lateral (gui.App: frame_sidebar.pack(padx=(0, 10))).
    SIDEBAR_GAP = 10
    # Por debajo de este ancho (px lógicos) el selector de vista muestra solo iconos.
    COMPACT_NAV_BELOW = 1450

    def place_navigation(self, view_tab_bar, filter_indicator):
        """Coloca el indicador de filtro global (junto al buscador) y, tras un
        separador vertical, el selector de vista al final de la cabecera."""
        self._view_tab_bar = view_tab_bar
        filter_indicator.grid(row=0, column=2, sticky="e", padx=(0, 12))
        ctk.CTkFrame(self.inner_frame, width=1, height=28, fg_color=theme.BORDER_QUIET, corner_radius=0).grid(
            row=0, column=4, padx=14
        )
        view_tab_bar.grid(row=0, column=5, sticky="e")
        self.inner_frame.bind("<Configure>", self._on_inner_resize, add="+")

    def _on_inner_resize(self, event):
        scale = ctk.ScalingTracker.get_widget_scaling(self)
        self._view_tab_bar.set_compact(event.width / scale < self.COMPACT_NAV_BELOW)

    def _sync_alignment(self, event=None):
        """Ajusta dinámicamente la columna 0 solo si el panel de detalles ya está creado."""
        if hasattr(self.app, "detail_panel") and self.app.detail_panel is not None:
            try:
                real_width = self.app.detail_panel.winfo_width()
                if real_width > 50 and real_width != self.detail_width:
                    self.detail_width = real_width
                    self.inner_frame.grid_columnconfigure(0, minsize=self.detail_width + self.SIDEBAR_GAP)
            except Exception:
                pass  # Ignora si el componente está en proceso de destrucción o renderizado

    # ------------------------------------------------------------------
    # Buscador (Ctrl+F): ocupa el sitio del selector de vista mientras está abierto
    # ------------------------------------------------------------------
    def toggle_search(self, event=None):
        """Ctrl+F: abre el buscador o, si ya está abierto, lo cierra conservando el
        filtro (igual que Intro)."""
        if self._search_open:
            self.close_search(clear=False)
        else:
            self.open_search()
        return "break"

    def open_search(self):
        if not self._search_open:
            tab_bar = getattr(self, "_view_tab_bar", None)
            if tab_bar is not None:
                # Mismo ancho que el selector, para que la cabecera no se mueva.
                width = tab_bar.winfo_width()
                scale = ctk.ScalingTracker.get_widget_scaling(self)
                if width > 1:
                    self.entry_search.configure(width=max(240, round(width / scale)))
                tab_bar.grid_remove()
            self.entry_search.grid(row=0, column=5, sticky="e")
            self._search_open = True
            # El placeholder de CTkEntry se oculta con el foco: la ayuda de teclado
            # va a la barra de estado mientras el buscador está abierto.
            if hasattr(self.app, "label_status"):
                self._status_before_search = self.app.label_status.cget("text")
                self.app.label_status.configure(
                    text="Búsqueda: Intro aplica el filtro y cierra · Esc lo limpia · Ctrl+F cierra"
                )
        self.entry_search.focus_set()
        self.entry_search.select_range(0, "end")

    def close_search(self, clear=False):
        """Oculta el buscador y vuelve a mostrar el selector de vista. Con
        clear=True también borra el texto (y con él el filtro de texto libre)."""
        if clear:
            self.entry_search.delete(0, "end")
            self._push_search_text()
        if self._search_open:
            if hasattr(self.app, "label_status") and getattr(self, "_status_before_search", None) is not None:
                self.app.label_status.configure(text=self._status_before_search)
                self._status_before_search = None
            self.entry_search.grid_remove()
            tab_bar = getattr(self, "_view_tab_bar", None)
            if tab_bar is not None:
                tab_bar.grid()
            self._search_open = False
        self.focus_grid()

    def on_search_text_changed(self, text):
        """Listener de SearchManager: refleja cambios hechos desde otro sitio (panel
        avanzado, botón ✕ del indicador de filtro)."""
        if self.entry_search.get() != text:
            self.entry_search.delete(0, "end")
            if text:
                self.entry_search.insert(0, text)

    def _push_search_text(self):
        if hasattr(self.app, "search_manager"):
            self.app.search_manager.set_search_text(self.entry_search.get())

    def _on_search_key_release(self, event):
        if event.keysym in ("Return", "Escape", "KP_Enter"):
            return
        self._push_search_text()

    def _on_search_submit(self, event=None):
        self._push_search_text()
        self.close_search(clear=False)
        return "break"

    def _on_search_cancel(self, event=None):
        self.close_search(clear=True)
        return "break"

    def focus_grid(self):
        if getattr(self.app, "_active_view", "collection") != "collection":
            self.app.focus_set()
            return
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

    # Ancho (en px del PNG original) de la zona del isotipo dentro de
    # assets/logo_completo.png; el resto de la imagen es el texto, que aquí se
    # dibuja con widgets para poder darle los colores de la guía.
    ISOTYPE_CROP_WIDTH = 540

    def _build_brand(self, logo_pil):
        brand = ctk.CTkFrame(self.inner_frame, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w")

        if logo_pil:
            icon = logo_pil.crop((0, 0, min(self.ISOTYPE_CROP_WIDTH, logo_pil.width), logo_pil.height))
            bbox = icon.getbbox()
            if bbox:
                icon = icon.crop(bbox)
            target_height = 30
            target_width = round(icon.width * target_height / icon.height)
            self._brand_icon = ctk.CTkImage(light_image=icon, dark_image=icon, size=(target_width, target_height))
            ctk.CTkLabel(brand, image=self._brand_icon, text="").pack(side="left", padx=(0, 10))

        text_box = ctk.CTkFrame(brand, fg_color="transparent")
        text_box.pack(side="left")

        title_row = ctk.CTkFrame(text_box, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(
            title_row, text="Sonometa", text_color="#FFFFFF", height=20,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            title_row, text="v2.0", text_color=theme.PRIMARY, height=20,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        ).pack(side="left", padx=(6, 0), pady=(3, 0))

        ctk.CTkLabel(
            text_box, text="\u200A".join("AUDIO TAG SUITE"), text_color=theme.TEXT_MUTED, height=12,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=9, weight="bold")
        ).pack(anchor="w")

