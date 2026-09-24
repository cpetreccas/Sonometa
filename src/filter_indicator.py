import customtkinter as ctk
import theme


class FilterIndicator(ctk.CTkFrame):
    """Píldora de filtro global en la barra de navegación superior, a la derecha de
    las pestañas Colección/Dashboard/Salud. Refleja el estado de filtro único
    (GridPanel._advanced_criteria / _health_filter_paths) sea cual sea la vista
    activa — no hay badges locales duplicados dentro de cada vista — y permite
    limpiarlo con un clic. GridPanel.apply_combined_filters llama a set_summary()
    automáticamente en cada cambio de filtro, así que no requiere refresco manual."""

    def __init__(self, parent, on_clear):
        super().__init__(parent, fg_color="transparent")
        self._on_clear = on_clear
        self._build_inactive()

    def _clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def _build_inactive(self):
        self._clear()
        ctk.CTkLabel(
            self, text="Sin filtros aplicados", text_color=theme.TEXT_SUBTLE,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12)
        ).pack()

    def set_summary(self, parts):
        """`parts`: lista de strings legibles (ej. ["Género: Techno", "Sin Año"]),
        normalmente GridPanel.get_active_filter_summary(). Lista vacía => inactivo."""
        self._clear()
        if not parts:
            self._build_inactive()
            return

        pill = ctk.CTkFrame(
            self, fg_color=theme.BG_CARD_HOVER, corner_radius=20,
            border_width=1, border_color=theme.PRIMARY
        )
        pill.pack()

        ctk.CTkLabel(
            pill, text=f"Filtro: {' · '.join(parts)}", text_color="#FFFFFF",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        ).pack(side="left", padx=(theme.SPACE_MD, theme.SPACE_XS), pady=4)

        ctk.CTkButton(
            pill, text="✕", command=self._on_clear, width=22, height=22,
            fg_color="transparent", hover_color=theme.BORDER_FOCUS, text_color="#FFFFFF",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold"),
            corner_radius=20
        ).pack(side="left", padx=(0, theme.SPACE_SM), pady=4)
