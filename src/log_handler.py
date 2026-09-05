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
                # Si es un log multilínea con árbol, tomamos solo la primera línea para la barra de estado
                first_line = status_msg.split('\n')[0]
                self.app_instance.label_status.configure(text=first_line)
            except Exception:
                pass

        LogManager.append_log_to_dialog(self.app_instance, full_msg)

    @staticmethod
    def _format_dict_value(val):
        """Formatea los valores individuales estilo JSON/Python estandarizado para logs."""
        if val is None:
            return "null"
        if isinstance(val, str):
            return f"'{val}'"
        return str(val)

    @staticmethod
    def dict_to_str(d):
        """Convierte un diccionario a string con formato {Key: 'Value', Key2: null}."""
        if not d:
            return "{}"
        items = [f"{k}: {LogManager._format_dict_value(v)}" for k, v in d.items()]
        return "{" + ", ".join(items) + "}"

    @staticmethod
    def format_tree_log(context, action, filename, prev_vals=None, new_vals=None, error_cause=None):
        """
        Construye el mensaje multilínea con estructura de árbol ASCII.

        Ejemplos de salidas generadas:
        [DETAIL] Modificado 'pista.mp3'
          ├── Valores previos : {Year: 1995}
          └── Valores nuevos  : {Year: 1996}
        """
        header = f"[{context.upper()}] {action} '{filename}'"

        if error_cause:
            tree = f"  └── Causa : {error_cause}"
            return f"{header}\n{tree}"

        str_prev = LogManager.dict_to_str(prev_vals or {})
        str_new = LogManager.dict_to_str(new_vals or {})

        tree = (
            f"  ├── Valores previos : {str_prev}\n"
            f"  └── Valores nuevos  : {str_new}"
        )
        return f"{header}\n{tree}"

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
        """Agrega una línea de texto al cuadro de texto del diálogo de logs aplicando formato si está abierto."""
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

            # Intentar delegar el formateo enriquecido a DialogManager si está disponible
            from dialogs import DialogManager
            if hasattr(DialogManager, "append_formatted_log_line"):
                DialogManager.append_formatted_log_line(log_box, msg)
            else:
                line_to_insert = msg if msg.endswith("\n") else f"{msg}\n"
                log_box.insert("end", line_to_insert)

            log_box.see("end")
            log_box.configure(state="disabled")
        except Exception:
            try:
                # Fallback seguro en caso de fallo durante el formateo
                line_to_insert = msg if msg.endswith("\n") else f"{msg}\n"
                log_box.insert("end", line_to_insert)
                log_box.see("end")
                log_box.configure(state="disabled")
            except Exception:
                pass