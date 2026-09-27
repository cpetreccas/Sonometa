import logging
import threading
import webbrowser

import customtkinter as ctk

from dialogs import DialogManager, SilentTitlebarMixin
import theme

logger = logging.getLogger("Sonometa")

DISCOGS_DEVELOPERS_URL = "https://www.discogs.com/settings/developers"


class DiscogsTokenDialog(SilentTitlebarMixin, ctk.CTkToplevel):
    """Preferencias > Discogs: el usuario pega su token personal de Discogs, se
    comprueba contra la API (/oauth/identity) y se guarda en settings.json
    (CatalogManager.discogs_token, en %APPDATA%\\Sonometa). Sustituye a tener que
    copiar un .env con DISCOGS_TOKEN en cada equipo."""

    WIDTH, HEIGHT = 460, 400

    def __init__(self, app):
        super().__init__(app)
        DialogManager.hide_until_ready(self)
        self.app = app

        self.title("Discogs - Sonometa")
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.resizable(False, False)
        self.bind("<Escape>", lambda event: self.destroy())

        self._setup_ui()

        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=self.WIDTH, height=self.HEIGHT)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)
        self.after(50, self._set_initial_focus)

    def _set_initial_focus(self):
        self.focus_force()
        if self.entry_token.winfo_exists():
            self.entry_token.focus_force()

    def _setup_ui(self):
        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)

        main_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        ctk.CTkLabel(
            main_frame, text="Discogs",
            font=ctk.CTkFont(size=theme.FONT_SIZE_H1, weight="bold"), text_color=theme.TEXT_MAIN,
        ).pack(anchor="w", padx=5, pady=(5, 2))
        ctk.CTkLabel(
            main_frame,
            text="Conecta tu cuenta de Discogs para completar el año y las carátulas al procesar.",
            text_color=theme.TEXT_MUTED, font=ctk.CTkFont(size=12), wraplength=400, justify="left",
        ).pack(anchor="w", padx=5, pady=(0, 16))

        form_frame = ctk.CTkFrame(main_frame, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
        form_frame.pack(fill="x", pady=(0, 12), padx=5, ipady=8)

        ctk.CTkLabel(
            form_frame,
            text="1. En Discogs, abre Ajustes › Desarrolladores y pulsa «Generar nuevo token».",
            text_color=theme.TEXT_MUTED, font=ctk.CTkFont(size=12), wraplength=380, justify="left",
        ).pack(anchor="w", padx=theme.SPACE_MD, pady=(10, 2))
        link = ctk.CTkLabel(
            form_frame, text="Abrir discogs.com/settings/developers ↗",
            text_color=theme.PRIMARY_LIGHT, font=ctk.CTkFont(size=12, underline=True), cursor="hand2",
        )
        link.pack(anchor="w", padx=theme.SPACE_MD, pady=(0, 10))
        link.bind("<Button-1>", lambda e: webbrowser.open(DISCOGS_DEVELOPERS_URL))

        ctk.CTkLabel(
            form_frame, text="2. Pega aquí tu token personal:",
            font=ctk.CTkFont(weight="bold"), text_color=theme.TEXT_MAIN,
        ).pack(anchor="w", padx=theme.SPACE_MD, pady=(0, 2))

        token_row = ctk.CTkFrame(form_frame, fg_color="transparent")
        token_row.pack(fill="x", padx=theme.SPACE_MD, pady=(0, 5))
        self.entry_token = ctk.CTkEntry(
            token_row, show="•", height=36, fg_color=theme.BG_INPUT, border_color=theme.BORDER_QUIET,
            placeholder_text="Token personal de Discogs",
        )
        self.entry_token.pack(side="left", fill="x", expand=True)
        current = getattr(self.app, "discogs_token", "") or ""
        if current:
            self.entry_token.insert(0, current)

        self._shown = False
        self.btn_show = theme.style_secondary_button(ctk.CTkButton(
            token_row, text="Mostrar", width=80, height=36, command=self._toggle_show,
        ))
        self.btn_show.pack(side="left", padx=(8, 0))

        self.lbl_status = ctk.CTkLabel(
            main_frame, text="", font=ctk.CTkFont(size=12), wraplength=400, justify="left", anchor="w",
        )
        self.lbl_status.pack(fill="x", padx=5, pady=(0, 10))
        if current:
            self._set_status("Hay un token configurado. Pulsa «Guardar» para comprobarlo de nuevo.", theme.TEXT_MUTED)

        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        self.btn_save = ctk.CTkButton(
            btn_bar, text="Guardar", fg_color=corp_color, hover_color=corp_hover,
            height=36, font=ctk.CTkFont(weight="bold"), command=self._handle_save,
        )
        self.btn_save.pack(side="right", padx=(8, 0))
        theme.style_secondary_button(ctk.CTkButton(
            btn_bar, text="Cancelar", height=36, command=self.destroy,
        )).pack(side="right")

        if current:
            theme.style_reset_button(ctk.CTkButton(
                btn_bar, text="Desconectar", height=36, command=self._handle_remove,
            )).pack(side="left")

        self.entry_token.bind("<Return>", lambda e: self._handle_save())

    def _set_status(self, text, color):
        self.lbl_status.configure(text=text, text_color=color)

    def _toggle_show(self):
        self._shown = not self._shown
        self.entry_token.configure(show="" if self._shown else "•")
        self.btn_show.configure(text="Ocultar" if self._shown else "Mostrar")

    def _handle_save(self):
        token = self.entry_token.get().strip()
        if not token:
            self._set_status("Pega tu token de Discogs antes de guardar.", theme.STATUS_DANGER)
            return

        self.btn_save.configure(state="disabled", text="Comprobando...")
        self._set_status("Comprobando el token con Discogs...", theme.PRIMARY_LIGHT)
        threading.Thread(target=self._verify_thread, args=(token,), daemon=True).start()

    def _verify_thread(self, token):
        valid, detail = self.app.discogs_client.verify_token(token)
        try:
            if self.winfo_exists():
                self.after(0, self._on_verified, token, valid, detail)
        except Exception:
            pass

    def _on_verified(self, token, valid, detail):
        if valid is False:
            self.btn_save.configure(state="normal", text="Guardar")
            self._set_status(detail, theme.STATUS_DANGER)
            return

        self.app.set_discogs_token(token)
        if valid:
            self._set_status(f"Conectado como {detail}. Token guardado.", theme.STATUS_SUCCESS)
        else:
            # Sin conexión con Discogs: se guarda igualmente para no bloquear al usuario.
            self._set_status(f"Token guardado sin comprobar ({detail}).", theme.STATUS_WARNING)
        self.after(1200, self.destroy)

    def _handle_remove(self):
        self.app.set_discogs_token("")
        self._set_status("Discogs desconectado.", theme.TEXT_MUTED)
        self.after(800, self.destroy)
