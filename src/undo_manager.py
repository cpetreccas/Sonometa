import os
import logging

logger = logging.getLogger("Sonometa")


class HistoryAction:
    """Representa una modificación individual sobre un archivo o campo."""
    def __init__(self, file_path, row_id, field_name, col_index, old_value, new_value, col_name=None):
        self.file_path = file_path
        self.row_id = row_id
        self.field_name = field_name      # Nombre de la etiqueta en Mutagen
        self.col_index = col_index        # Índice de la columna en el Treeview
        self.col_name = col_name or field_name  # Identificador estable de columna para resolver índice en runtime
        self.old_value = old_value
        self.new_value = new_value


class UndoManager:
    """Administra el búfer de estados anteriores para deshacer y rehacer cambios."""

    def __init__(self, app, max_history=50):
        self.app = app
        self.max_history = max_history
        self.undo_stack = []  # Lista de listas de HistoryAction
        self.redo_stack = []

    def record_action(self, actions):
        """Registra una acción simple o un lote de acciones."""
        if not actions:
            return
        if isinstance(actions, HistoryAction):
            actions = [actions]

        self.undo_stack.append(actions)
        if len(self.undo_stack) > self.max_history:
            self.undo_stack.pop(0)

        # Cada nuevo cambio del usuario limpia la pila de rehacer
        self.redo_stack.clear()

    def undo(self, event=None):
        if not self.undo_stack:
            logger.info("[UNDO] No hay cambios para deshacer")
            return "break"

        batch_actions = self.undo_stack.pop()
        for action in reversed(batch_actions):
            self._apply_state(action, use_old_value=True)

        self.redo_stack.append(batch_actions)

        # Formato de log estructurado por acción
        for action in reversed(batch_actions):
            filename = os.path.basename(action.file_path) if action.file_path else "Archivo"
            logger.info(
                f"[UNDO] Deshecha modificación en '{filename}'\n"
                f"  ├── Campo restaurado : {action.field_name}\n"
                f"  ├── Valor revertido  : {action.old_value if action.old_value is not None else 'null'}\n"
                f"  └── Valor descartado : {action.new_value if action.new_value is not None else 'null'}"
            )
        return "break"

    def redo(self, event=None):
        if not self.redo_stack:
            logger.info("[REDO] No hay cambios para rehacer")
            return "break"

        batch_actions = self.redo_stack.pop()
        for action in batch_actions:
            self._apply_state(action, use_old_value=False)

        self.undo_stack.append(batch_actions)

        # Formato de log estructurado por acción
        for action in batch_actions:
            filename = os.path.basename(action.file_path) if action.file_path else "Archivo"
            logger.info(
                f"[REDO] Rehecha modificación en '{filename}'\n"
                f"  ├── Campo reaplicado : {action.field_name}\n"
                f"  ├── Valores previos  : {action.old_value if action.old_value is not None else 'null'}\n"
                f"  └── Nuevo valor      : {action.new_value if action.new_value is not None else 'null'}"
            )
        return "break"

    def _apply_state(self, action: HistoryAction, use_old_value: bool):
        target_value = action.old_value if use_old_value else action.new_value

        # 1. Guardar en el archivo físico de audio
        if action.file_path and os.path.exists(action.file_path):
            self.app.audio_manager.save_single_tag(action.file_path, action.field_name, target_value)

        # 2. Actualizar en la tabla de la interfaz (Treeview)
        if self.app.tree.exists(action.row_id):
            values = list(self.app.tree.item(action.row_id, "values"))
            col_index = None

            if getattr(action, "col_name", None) and hasattr(self.app, "get_tree_column_index"):
                col_index = self.app.get_tree_column_index(action.col_name)

            if col_index is None:
                col_index = action.col_index

            if col_index is not None and col_index < len(values):
                values[col_index] = target_value
                self.app.tree.item(action.row_id, values=values)

            # Refrescar el panel de detalles si la fila sigue seleccionada
            selected = self.app.tree.selection()
            if selected and selected[0] == action.row_id and not self.app._multi_select_mode:
                self.app.detail_panel.on_row_select(None)