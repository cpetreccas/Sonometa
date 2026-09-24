import customtkinter as ctk
import theme


class ViewTabBar(ctk.CTkFrame):
    """Selector de vista estilo 'pestañas con línea inferior': texto plano, sin
    fondos gruesos ni bordes tipo cápsula. La pestaña activa se marca con el texto
    en color principal y una línea morada de 3px pegada al borde inferior; las
    inactivas van en gris, aclarando a blanco en hover."""

    UNDERLINE_HEIGHT = 3

    def __init__(self, parent, tabs, command):
        """`tabs`: lista de tuplas (key, label). `command(key)` se llama al clicar
        una pestaña (no se auto-activa: quien la use decide llamando a set_active)."""
        super().__init__(parent, fg_color="transparent")
        self._command = command
        self._tabs = {}
        self._active_key = None

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(side="left")

        for key, label in tabs:
            self._tabs[key] = self._build_tab(row, key, label)

    def _build_tab(self, parent, key, label):
        tab = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0)
        tab.pack(side="left", padx=(0, theme.SPACE_LG))

        lbl = ctk.CTkLabel(
            tab, text=label, text_color=theme.TEXT_MUTED, cursor="hand2",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")
        )
        lbl.pack(padx=2, pady=(6, 6))

        underline = ctk.CTkFrame(tab, height=self.UNDERLINE_HEIGHT, fg_color="transparent", corner_radius=0)
        underline.pack(fill="x", side="bottom")

        for widget in (tab, lbl):
            widget.bind("<Button-1>", lambda e, k=key: self._command(k))
            widget.bind("<Enter>", lambda e, k=key: self._on_enter(k))
            widget.bind("<Leave>", lambda e, k=key: self._on_leave(k))

        return {"label": lbl, "underline": underline}

    def _on_enter(self, key):
        if key != self._active_key:
            self._tabs[key]["label"].configure(text_color=theme.TEXT_MAIN)

    def _on_leave(self, key):
        if key != self._active_key:
            self._tabs[key]["label"].configure(text_color=theme.TEXT_MUTED)

    def set_active(self, key):
        self._active_key = key
        for tab_key, widgets in self._tabs.items():
            is_active = tab_key == key
            widgets["label"].configure(text_color=theme.TEXT_MAIN if is_active else theme.TEXT_MUTED)
            widgets["underline"].configure(fg_color=theme.PRIMARY if is_active else "transparent")
