import tkinter.font as tkfont

import customtkinter as ctk
import theme

# Iconos de línea de la fuente del sistema (Segoe Fluent Icons en Windows 11,
# Segoe MDL2 Assets en Windows 10), igual que en la vista de Salud.
ICON_FONT_CANDIDATES = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
VIEW_ICONS = {
    "collection": "\uE90B",  # lista con nota musical
    "dashboard": "\uEB05",   # gráfico circular
    "health": "\uE95E",      # pulso / salud
}


class ViewTabBar(ctk.CTkFrame):
    """Selector de vista segmentado (Colección / Dashboard / Salud) que vive al
    final de la cabecera. Un contenedor tipo input (BG_INPUT, borde, radio 10) con un segmento
    por vista: icono + texto. El activo usa el estilo de "chip activo" de la guía
    (fondo CHIP_ACTIVE_BG, borde morado, texto blanco), igual que el indicador de
    filtro; los inactivos van en gris y se iluminan en hover."""

    def __init__(self, parent, tabs, command):
        """`tabs`: lista de tuplas (key, label). `command(key)` se llama al clicar
        un segmento (no se auto-activa: quien lo use decide llamando a set_active)."""
        super().__init__(
            parent, fg_color=theme.BG_INPUT, corner_radius=10,
            border_width=1, border_color=theme.BORDER_QUIET
        )
        self._command = command
        self._tabs = {}
        self._active_key = None
        self._compact = False

        families = set(tkfont.families())
        icon_family = next((f for f in ICON_FONT_CANDIDATES if f in families), theme.FONT_FAMILY)
        self._font_icon = ctk.CTkFont(family=icon_family, size=14)
        self._font_text = ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")

        for i, (key, label) in enumerate(tabs):
            self._tabs[key] = self._build_segment(key, label, first=(i == 0), last=(i == len(tabs) - 1))

    def _build_segment(self, key, label, first, last):
        # border_width=1 siempre (con el color del fondo cuando está inactivo) para
        # que el segmento no cambie de tamaño al activarse.
        seg = ctk.CTkFrame(
            self, fg_color=theme.BG_INPUT, corner_radius=8,
            border_width=1, border_color=theme.BG_INPUT, cursor="hand2"
        )
        seg.pack(side="left", padx=(4 if first else 2, 4 if last else 2), pady=4)

        icon = ctk.CTkLabel(
            seg, text=VIEW_ICONS.get(key, ""), font=self._font_icon,
            text_color=theme.TEXT_MUTED, width=16, cursor="hand2"
        )
        icon.pack(side="left", padx=(12, 6), pady=4)
        text = ctk.CTkLabel(seg, text=label, font=self._font_text, text_color=theme.TEXT_MUTED, cursor="hand2")
        text.pack(side="left", padx=(0, 14), pady=4)

        for widget in (seg, icon, text):
            widget.bind("<Button-1>", lambda e, k=key: self._command(k))
            widget.bind("<Enter>", lambda e, k=key: self._on_enter(k))
            widget.bind("<Leave>", lambda e, k=key: self._on_leave(k))

        return {"frame": seg, "icon": icon, "text": text}

    def set_compact(self, compact):
        """Modo compacto (ventana estrecha): solo iconos, sin texto."""
        if compact == self._compact:
            return
        self._compact = compact
        for widgets in self._tabs.values():
            if compact:
                widgets["text"].pack_forget()
                widgets["icon"].pack_configure(padx=(10, 10))
            else:
                widgets["icon"].pack_configure(padx=(12, 6))
                widgets["text"].pack(side="left", padx=(0, 14), pady=4)

    def _paint(self, key, state):
        """state: "active" | "hover" | "idle"."""
        widgets = self._tabs[key]
        if state == "active":
            bg, border, text_color, icon_color = theme.CHIP_ACTIVE_BG, theme.PRIMARY, theme.TEXT_ON_PRIMARY, theme.PRIMARY_LIGHT
        elif state == "hover":
            bg, border, text_color, icon_color = theme.BG_CARD_HOVER, theme.BG_CARD_HOVER, theme.TEXT_MAIN, theme.TEXT_MAIN
        else:
            bg, border, text_color, icon_color = theme.BG_INPUT, theme.BG_INPUT, theme.TEXT_MUTED, theme.TEXT_MUTED
        widgets["frame"].configure(fg_color=bg, border_color=border)
        widgets["icon"].configure(text_color=icon_color)
        widgets["text"].configure(text_color=text_color)

    def _on_enter(self, key):
        if key != self._active_key:
            self._paint(key, "hover")

    def _on_leave(self, key):
        if key != self._active_key:
            self._paint(key, "idle")

    def set_active(self, key):
        self._active_key = key
        for tab_key in self._tabs:
            self._paint(tab_key, "active" if tab_key == key else "idle")
