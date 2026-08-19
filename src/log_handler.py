import logging

class LogManager(logging.Handler):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance

    def emit(self, record):
        msg = self.format(record)
        if hasattr(self.app_instance, "log_history"):
            self.app_instance.log_history.append(msg)

        # Si la ventana principal ya fue destruida, evitamos llamar a after()
        if not hasattr(self.app_instance, "winfo_exists") or not self.app_instance.winfo_exists():
            return

        try:
            # Programar la actualización UI en el hilo principal
            message_text = record.getMessage()
            self.app_instance.after(
                0,
                lambda: self._update_ui_log(message_text, msg)
            )
        except Exception:
            pass

    def _update_ui_log(self, status_msg, full_msg):
        """Actualiza la barra de estado y el cuadro de texto del diálogo si existen."""
        if hasattr(self.app_instance, "label_status") and self.app_instance.label_status:
            try:
                self.app_instance.label_status.configure(text=status_msg)
            except Exception:
                pass

        LogManager.append_log_to_dialog(self.app_instance, full_msg)

    @staticmethod
    def setup_logger(app_instance, name="Sonometa", level=logging.INFO):
        """Configura y retorna el logger principal de la aplicación vinculado a la GUI."""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Evitar duplicar handlers en re-inicializaciones
        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            # 1. Console Handler
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            # 2. LogManager Handler (GUI / Historial)
            ui_handler = LogManager(app_instance)
            ui_handler.setFormatter(formatter)
            logger.addHandler(ui_handler)

        return logger

    @staticmethod
    def append_log_to_dialog(app, msg):
        """Agrega una línea de texto al cuadro de texto del diálogo de logs si está abierto."""
        log_win = getattr(app, "log_window", None)
        log_box = getattr(app, "log_textbox", None)

        if not log_win or not log_box:
            return

        try:
            if not log_win.winfo_exists():
                app.log_window = None
                app.log_textbox = None
                return

            log_box.configure(state="normal")
            log_box.insert("end", f"{msg}\n")
            log_box.see("end")
            log_box.configure(state="disabled")
        except Exception:
            pass