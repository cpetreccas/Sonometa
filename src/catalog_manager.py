import json
import logging
import os

logger = logging.getLogger("Sonometa")


class CatalogManager:

    def __init__(self, app_instance):
        self.app = app_instance
        self.manual_cover_selection = True
        self.catalog_fields = ("Genre", "Album", "Publisher")
        self.catalog_labels = {
            "Genre": "Géneros",
            "Album": "Álbumes",
            "Publisher": "Etiquetas",
        }
        self.catalog_values = {field: [] for field in self.catalog_fields}
        self.catalog_file_path = self.get_catalog_file_path()
        self.settings_file_path = self.get_settings_file_path()
        self.load_catalog_values()

    def get_catalog_file_path(self):
        base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(base_dir, "Sonometa")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "catalogos.json")

    def get_settings_file_path(self):
        base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
        app_dir = os.path.join(base_dir, "Sonometa")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "settings.json")

    @staticmethod
    def normalize_catalog_text(value):
        value_str = str(value).strip() if value is not None else ""
        if not value_str:
            return ""
        return value_str[0].upper() + value_str[1:].lower()

    def load_catalog_values(self):
        if not os.path.exists(self.catalog_file_path):
            return
        try:
            with open(self.catalog_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for field in self.catalog_fields:
                raw_values = data.get(field, [])
                if isinstance(raw_values, list):
                    cleaned = []
                    for value in raw_values:
                        value_str = self.normalize_catalog_text(value)
                        if value_str and value_str not in cleaned:
                            cleaned.append(value_str)
                    self.catalog_values[field] = cleaned
        except Exception as e:
            logger.warning(
                f"No se pudieron cargar catálogos persistidos: {str(e)}"
            )

    def save_catalog_values(self):
        try:
            with open(self.catalog_file_path, "w", encoding="utf-8") as f:
                json.dump(self.catalog_values, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"No se pudieron guardar los catálogos: {str(e)}")

    def load_settings(self):
        if not os.path.exists(self.settings_file_path):
            return ""
        try:
            with open(self.settings_file_path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            token = data.get("discogs_token", "").strip()
            self.manual_cover_selection = data.get("manual_cover_selection", True)

            if token:
                logger.info("Token de Discogs cargado desde configuración.")
            else:
                logger.warning("settings.json encontrado pero sin token de Discogs.")
            return token
        except Exception as e:
            logger.warning(f"No se pudo cargar la configuración: {str(e)}")
            return ""

    def save_settings(self, token=""):
        try:
            # Si se le pasa un token explícito, lo usa; si no, preserva el que tenga la app o deja cadena vacía
            current_token = token if token else getattr(self.app, "discogs_token", "")
            data = {
                "discogs_token": current_token,
                "manual_cover_selection": getattr(self, "manual_cover_selection", True)
            }
            with open(self.settings_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"No se pudo guardar la configuración: {str(e)}")

    def refresh_ui_comboboxes(self):
        """Método auxiliar seguro para refrescar los comboboxes en el panel de detalles."""
        if hasattr(self.app, "detail_panel") and hasattr(self.app.detail_panel, "refresh_catalog_comboboxes"):
            self.app.detail_panel.refresh_catalog_comboboxes()

    def add_catalog_value(self, field_name, value, persist=False):
        value_str = self.normalize_catalog_text(value)
        if field_name not in self.catalog_fields or not value_str:
            return False
        if value_str in self.catalog_values[field_name]:
            return False
        self.catalog_values[field_name].append(value_str)
        self.catalog_values[field_name].sort(key=lambda x: x.lower())

        self.refresh_ui_comboboxes()

        if persist:
            self.save_catalog_values()
        return True

    def get_catalog_combo_values(self, catalog_key):
        clear_opt = getattr(self.app, "CLEAR_OPTION", "--- Vaciar ---")
        values = [
            v
            for v in self.catalog_values.get(catalog_key, [])
            if v and v != clear_opt
        ]
        values = sorted(dict.fromkeys(values), key=lambda x: x.lower())
        return values + [clear_opt]

    @staticmethod
    def get_catalog_column_info(catalog_key):
        mapping = {
            "Album": ("Album", 4),
            "Genre": ("Genre", 5),
            "Publisher": ("Publisher", 6),
        }
        return mapping.get(catalog_key)

    def apply_catalog_value_change(self, catalog_key, old_value, new_value):
        info = self.get_catalog_column_info(catalog_key)
        if not info:
            return 0

        col_name, col_index = info
        old_value = self.normalize_catalog_text(old_value)
        new_value = self.normalize_catalog_text(new_value)
        if not old_value:
            return 0

        updated_count = 0
        for row_id in self.app.tree.get_children():
            row_values = list(self.app.tree.item(row_id, "values"))
            if col_index >= len(row_values):
                continue

            current_value = self.normalize_catalog_text(row_values[col_index])
            if current_value != old_value:
                continue

            row_values[col_index] = new_value
            self.app.tree.item(row_id, values=row_values)

            file_path = self.app.file_paths_map.get(row_id)
            if file_path and hasattr(self.app, "audio_manager"):
                self.app.audio_manager.save_single_tag(file_path, col_name, new_value)
            updated_count += 1

        return updated_count

    def rename_catalog_value(self, catalog_key, old_value, new_value):
        if catalog_key not in self.catalog_fields:
            return 0, False

        old_value = self.normalize_catalog_text(old_value)
        new_value = self.normalize_catalog_text(new_value)
        if not old_value or not new_value or old_value == new_value:
            return 0, False

        values = self.catalog_values.get(catalog_key, [])
        if old_value not in values:
            return 0, False

        merged = new_value in values
        updated_count = self.apply_catalog_value_change(
            catalog_key, old_value, new_value
        )

        values.remove(old_value)
        if new_value not in values:
            values.append(new_value)
        values.sort(key=lambda x: x.lower())

        self.refresh_ui_comboboxes()
        self.save_catalog_values()

        if hasattr(self.app, "detail_panel") and hasattr(self.app.detail_panel, "on_row_select"):
            self.app.detail_panel.on_row_select(None)

        return updated_count, merged

    def apply_catalog_selection_to_row(self, row_id, attr_name, catalog_key, new_value):
        """Aplica un valor del catálogo a una fila seleccionada en la tabla y guarda los cambios."""
        column_map = {
            "entry_album": CatalogManager.get_catalog_column_info("Album"),
            "entry_genre": CatalogManager.get_catalog_column_info("Genre"),
            "entry_publisher": CatalogManager.get_catalog_column_info("Publisher"),
        }
        if attr_name not in column_map:
            return

        col_name, col_index = column_map[attr_name]
        values = list(self.app.tree.item(row_id, "values"))
        if col_index >= len(values):
            return
        if CatalogManager.normalize_catalog_text(values[col_index]) == new_value:
            return

        values[col_index] = new_value
        self.app.tree.item(row_id, values=values)

        file_path = self.app.file_paths_map.get(row_id)
        if file_path and hasattr(self.app, "audio_manager"):
            self.app.audio_manager.save_single_tag(file_path, col_name, new_value)

        self.add_catalog_value(catalog_key, new_value, persist=True)

        col_header = self.app.columns[col_index] if hasattr(self.app, "columns") and len(self.app.columns) > col_index else col_name
        logger.info(
            f"Campo '{self.catalog_labels.get(catalog_key, catalog_key)}' actualizado desde panel: "
            f"'{col_header}' -> '{new_value}'"
        )
        if hasattr(self.app, "detail_panel") and hasattr(self.app.detail_panel, "on_row_select"):
            self.app.detail_panel.on_row_select(None)