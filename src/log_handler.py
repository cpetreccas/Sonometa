import logging

class LogManager(logging.Handler):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance

    def emit(self, record):
        msg = self.format(record)
        self.app_instance.log_history.append(msg)
        # Programar el update en el hilo de UI evita errores si llega desde callback externo.
        try:
            self.app_instance.after(0, lambda: self.app_instance.label_status.configure(text=record.getMessage()))
            self.app_instance.after(0, lambda: LogManager.append_log_to_dialog(self.app_instance, msg))
        except Exception:
            pass

    @staticmethod
    def setup_logger(app_instance, name="Sonometa", level=logging.INFO):
        """Configura y retorna el logger principal de la aplicación vinculado a la GUI."""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Si ya tiene handlers configurados, evitamos duplicar
        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            # 1. Console Handler (Consola)
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
        if app.log_window is None or app.log_textbox is None:
            return
        if not app.log_window.winfo_exists():
            app.log_window = None
            app.log_textbox = None
            return

        app.log_textbox.configure(state="normal")
        app.log_textbox.insert("end", f"{msg}\n")
        app.log_textbox.see("end")
        app.log_textbox.configure(state="disabled")