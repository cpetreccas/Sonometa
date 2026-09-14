import logging
import threading


class LogManager(logging.Handler):
    def __init__(self, app_instance):
        super().__init__()
        self.app_instance = app_instance
        self._buffer_lock = threading.Lock()
        self._pending_ui_logs = []
        self._flush_after_id = None
        self._flush_interval_ms = 80

        # Inicia un poller en el hilo UI para drenar logs sin tocar Tk desde workers.
        try:
            if threading.current_thread() is threading.main_thread():
                self._flush_after_id = self.app_instance.after(self._flush_interval_ms, self._flush_ui_logs)
        except Exception:
            self._flush_after_id = None

    def emit(self, record):
        try:
            msg = self.format(record)
            if hasattr(self.app_instance, "log_history"):
                self.app_instance.log_history.append((record.levelname, msg))

            # Si la ventana principal no existe o fue destruida, omitir refresco UI
            if not hasattr(self.app_instance, "winfo_exists") or not self.app_instance.winfo_exists():
                return

            message_text = record.getMessage()
            with self._buffer_lock:
                self._pending_ui_logs.append((message_text, record.levelname, msg))

        except Exception:
            pass

    def _flush_ui_logs(self):
        self._flush_after_id = None

        if not hasattr(self.app_instance, "winfo_exists") or not self.app_instance.winfo_exists():
            with self._buffer_lock:
                self._pending_ui_logs.clear()
            return

        with self._buffer_lock:
            batch = list(self._pending_ui_logs)
            self._pending_ui_logs.clear()

        if batch:
            status_msg, _, _ = batch[-1]
            if hasattr(self.app_instance, "label_status") and self.app_instance.label_status:
                try:
                    self.app_instance.label_status.configure(text=status_msg.split('\n')[0])
                except Exception:
                    pass

            for _, level, full_msg in batch:
                LogManager.append_log_to_dialog(self.app_instance, level, full_msg)

        try:
            if hasattr(self.app_instance, "winfo_exists") and self.app_instance.winfo_exists():
                self._flush_after_id = self.app_instance.after(self._flush_interval_ms, self._flush_ui_logs)
        except Exception:
            self._flush_after_id = None

    def _update_ui_log(self, status_msg, level, full_msg):
        """Actualiza la barra de estado y el cuadro de texto del diálogo si existen."""
        if hasattr(self.app_instance, "label_status") and self.app_instance.label_status:
            try:
                first_line = status_msg.split('\n')[0]
                self.app_instance.label_status.configure(text=first_line)
            except Exception:
                pass

        LogManager.append_log_to_dialog(self.app_instance, level, full_msg)

    @staticmethod
    def _format_dict_value(val):
        if val is None:
            return "null"
        if isinstance(val, str):
            return f"'{val}'"
        return str(val)

    @staticmethod
    def dict_to_str(d):
        if not d:
            return "{}"
        items = [f"{k}: {LogManager._format_dict_value(v)}" for k, v in d.items()]
        return "{" + ", ".join(items) + "}"

    @staticmethod
    def format_tree_log(context, action, filename, prev_vals=None, new_vals=None, error_cause=None):
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
        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

            ui_handler = LogManager(app_instance)
            ui_handler.setFormatter(formatter)
            logger.addHandler(ui_handler)

        return logger

    @staticmethod
    def append_log_to_dialog(app, level, msg):
        log_win = getattr(app, "log_window", None)
        log_box = getattr(app, "log_textbox", None)

        if not log_win or not log_box:
            return

        try:
            if not log_win.winfo_exists():
                app.log_window = None
                app.log_textbox = None
                return

            from dialogs import DialogManager
            if hasattr(DialogManager, "append_formatted_log_line"):
                DialogManager.append_formatted_log_line(app, level, msg)
            else:
                log_box.configure(state="normal")
                line_to_insert = msg if msg.endswith("\n") else f"{msg}\n"
                log_box.insert("end", line_to_insert)
                log_box.see("end")
                log_box.configure(state="disabled")
        except Exception:
            try:
                log_box.configure(state="normal")
                line_to_insert = msg if msg.endswith("\n") else f"{msg}\n"
                log_box.insert("end", line_to_insert)
                log_box.see("end")
                log_box.configure(state="disabled")
            except Exception:
                pass