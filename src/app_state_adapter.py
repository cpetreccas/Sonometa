from typing import List, Optional


class AppStateAdapter:
    """Adaptador liviano para desacoplar managers del objeto App completo."""

    def __init__(self, app_instance):
        self.app = app_instance

    def get_clear_option(self, default_value: str = "--- Vaciar ---") -> str:
        return getattr(self.app, "CLEAR_OPTION", default_value)

    def get_tree_children(self) -> List[str]:
        tree = getattr(self.app, "tree", None)
        if tree is None:
            return []
        return list(tree.get_children())

    def get_tree_row_values(self, row_id: str):
        tree = getattr(self.app, "tree", None)
        if tree is None or not tree.exists(row_id):
            return []
        return list(tree.item(row_id, "values"))

    def set_tree_row_values(self, row_id: str, values) -> bool:
        tree = getattr(self.app, "tree", None)
        if tree is None or not tree.exists(row_id):
            return False
        tree.item(row_id, values=values)
        return True

    def get_tree_column_index(self, column_name: str) -> Optional[int]:
        if hasattr(self.app, "get_tree_column_index"):
            idx = self.app.get_tree_column_index(column_name)
            return int(idx) if idx is not None else None

        grid_panel = getattr(self.app, "grid_panel", None)
        if grid_panel and hasattr(grid_panel, "get_column_index"):
            idx = grid_panel.get_column_index(column_name)
            return int(idx) if idx is not None else None

        return None

    def get_file_path(self, row_id: str) -> Optional[str]:
        file_map = getattr(self.app, "file_paths_map", {})
        return file_map.get(row_id)

    def save_single_tag(self, file_path: str, field_name: str, value) -> None:
        audio_manager = getattr(self.app, "audio_manager", None)
        if audio_manager and hasattr(audio_manager, "save_single_tag"):
            audio_manager.save_single_tag(file_path, field_name, value)

    def refresh_catalog_comboboxes(self) -> None:
        detail_panel = getattr(self.app, "detail_panel", None)
        if detail_panel and hasattr(detail_panel, "refresh_catalog_comboboxes"):
            detail_panel.refresh_catalog_comboboxes()

    def notify_row_select(self) -> None:
        detail_panel = getattr(self.app, "detail_panel", None)
        if detail_panel and hasattr(detail_panel, "on_row_select"):
            detail_panel.on_row_select(None)

