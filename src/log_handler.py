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
            self.app_instance.after(0, lambda: self.app_instance.append_log_to_dialog(msg))
        except Exception:
            pass

    @staticmethod
    def setup_logger(name="Sonometa", level=logging.INFO):
        """Configura y retorna el logger principal de la aplicación."""
        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Evita duplicar handlers si el logger ya fue configurado previamente
        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger