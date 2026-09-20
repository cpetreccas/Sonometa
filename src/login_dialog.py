import logging
import threading
import customtkinter as ctk
from dialogs import DialogManager
import theme

logger = logging.getLogger("Sonometa")


class LoginDialog(ctk.CTkToplevel):
    """Modal de inicio de sesión para Supabase Cloud siguiendo la estética Sonometa."""

    def __init__(self, parent, supabase_client, on_success_callback=None):
        super().__init__(parent)
        self.app = parent
        self.supabase_client = supabase_client
        self.on_success_callback = on_success_callback

        self.title("Iniciar Sesión - Sonometa Cloud")
        self.geometry("420x460")
        self.resizable(False, False)

        # Atajo ESC para cerrar
        self.bind("<Escape>", lambda event: self.destroy())

        self._setup_ui()

        # Posicionamiento y estilo corporativo unificado de Sonometa
        self.withdraw()
        DialogManager.center_popup_on_parent(self, self.app, width=420, height=460)
        DialogManager.apply_popup_style(self.app, self, is_modal=True, owner=self.app)

        self.after(50, self._set_initial_focus)

    def _set_initial_focus(self):
        self.focus_force()
        if hasattr(self, "entry_email") and self.entry_email.winfo_exists():
            self.entry_email.focus_force()

    def _setup_ui(self):
        corp_color = getattr(self.app, "CORP_COLOR", theme.PRIMARY)
        corp_hover = getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)

        main_frame = ctk.CTkFrame(self, fg_color=theme.BG_CARD)
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        # Header / Título
        lbl_title = ctk.CTkLabel(
            main_frame,
            text="☁️ Sonometa Cloud",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme.TEXT_MAIN,
        )
        lbl_title.pack(anchor="w", padx=5, pady=(5, 2))

        lbl_sub = ctk.CTkLabel(
            main_frame,
            text="Inicia sesión para sincronizar tus metadatos.",
            text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(size=12),
        )
        lbl_sub.pack(anchor="w", padx=5, pady=(0, 20))

        # Formulario
        form_frame = ctk.CTkFrame(main_frame, fg_color=theme.BG_CARD_HOVER, corner_radius=theme.RADIUS_CONTROL)
        form_frame.pack(fill="x", pady=(0, 15), padx=5, ipady=10)

        # Email
        lbl_email = ctk.CTkLabel(
            form_frame,
            text="Correo electrónico:",
            font=ctk.CTkFont(weight="bold"),
            text_color=theme.TEXT_MAIN,
        )
        lbl_email.pack(anchor="w", padx=15, pady=(10, 2))

        self.entry_email = ctk.CTkEntry(
            form_frame,
            placeholder_text="tu@email.com",
            height=36,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_FOCUS,
        )
        self.entry_email.pack(fill="x", padx=15, pady=(0, 10))

        # Password
        lbl_password = ctk.CTkLabel(
            form_frame,
            text="Contraseña:",
            font=ctk.CTkFont(weight="bold"),
            text_color=theme.TEXT_MAIN,
        )
        lbl_password.pack(anchor="w", padx=15, pady=(0, 2))

        self.entry_password = ctk.CTkEntry(
            form_frame,
            placeholder_text="••••••••",
            show="•",
            height=36,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER_FOCUS,
        )
        self.entry_password.pack(fill="x", padx=15, pady=(0, 5))

        # Mensajes de estado / error
        self.lbl_status = ctk.CTkLabel(
            main_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=theme.STATUS_DANGER,
            wraplength=360,
        )
        self.lbl_status.pack(fill="x", pady=(0, 10))

        # Barra de botones
        btn_bar = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom")

        self.btn_login = ctk.CTkButton(
            btn_bar,
            text="Iniciar Sesión",
            fg_color=corp_color,
            hover_color=corp_hover,
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._handle_login,
        )
        self.btn_login.pack(side="right", padx=(8, 0))

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Cancelar",
            fg_color="transparent",
            border_width=1,
            border_color=theme.BORDER_QUIET,
            text_color=theme.TEXT_MAIN,
            hover_color=theme.BG_CARD_HOVER,
            height=36,
            command=self.destroy,
        )
        btn_cancel.pack(side="right")

        # Binds de teclado
        self.entry_email.bind("<Return>", lambda e: self.entry_password.focus_force())
        self.entry_password.bind("<Return>", lambda e: self._handle_login())

    def _handle_login(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()

        if not email or not password:
            self.lbl_status.configure(
                text="Por favor, rellena todos los campos.", text_color=theme.STATUS_DANGER
            )
            return

        # Deshabilitar botón y mostrar estado sin bloquear la ventana
        self.btn_login.configure(state="disabled", text="Autenticando...")
        self.lbl_status.configure(text="Conectando con Supabase...", text_color=theme.PRIMARY_LIGHT)

        # Ejecutar autenticación en background para no bloquear el hilo Tk
        threading.Thread(
            target=self._perform_login_thread,
            args=(email, password),
            daemon=True
        ).start()

    def _try_supabase_login(self, email, password):
        try:
            # Delegar inicio de sesión a SupabaseClientManager para poblar self.user y self.session
            success = self.supabase_client.login(email, password)
            if success:
                user = self.supabase_client.user
                logger.info(f"[SUPABASE] Autenticado como: {user.email if user else email}")
                return True, "OK"
            return False, "Usuario o contraseña incorrectos."
        except Exception as e:
            err = str(e)
            if "Invalid login credentials" in err:
                return False, "Usuario o contraseña incorrectos."
            return False, err

    def _on_success(self):
        # Cerrar modal de forma segura y ejecutar callback diferido en la app.
        callback = self.on_success_callback

        try:
            self.destroy()
        except Exception:
            pass

        if callback:
            self.app.after(150, callback)

    def _perform_login_thread(self, email, password):
        """Ejecuta la autenticación de red fuera del hilo principal de Tkinter."""
        success, message = self._try_supabase_login(email, password)

        # Volver al hilo principal mediante .after() para actualizar la interfaz gráfica
        if self.winfo_exists():
            self.after(0, self._on_login_finished, success, message)

    def _on_login_finished(self, success, message):
        """Callback ejecutado en el hilo UI al finalizar la autenticación."""
        if success:
            self.lbl_status.configure(
                text="¡Sesión iniciada correctamente!", text_color=theme.STATUS_SUCCESS
            )
            self.after(400, self._on_success)
        else:
            self.lbl_status.configure(
                text=f"Error: {message}", text_color=theme.STATUS_DANGER
            )
            self.btn_login.configure(state="normal", text="Iniciar Sesión")