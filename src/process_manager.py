import os
import re
from dialogs import DialogManager
from catalog_manager import CatalogManager
from audio_manager import AudioManager
from ui_utils import UiUtils

class ProcessManager:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger

    def process_discogs_data(self):
        target_rows = self.app.tree.selection()
        if not target_rows:
            target_rows = self.app.tree.get_children()

        if not target_rows:
            DialogManager.show_themed_dialog(self.app, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

        if hasattr(self.app, 'btn_process'):
            self.app.detail_panel.btn_process.configure(state="disabled", text="Procesando...")
            self.app.update_idletasks()

        try:
            words_to_omit = [
                r'\bfeat\.\b', r'\bfeat\b',
                r'\bft\.\b', r'\bft\b',
                r'\bpres\.\b', r'\bpres\b',
                r'\bpresents\b'
            ]
            omit_pattern = re.compile('|'.join(words_to_omit), flags=re.IGNORECASE)

            total_files = len(target_rows)
            self.logger.info(f"Iniciando procesado para {total_files} archivo(s)...")

            processed = 0
            for row_id in target_rows:
                file_path = self.app.file_paths_map.get(row_id)
                if not file_path or not os.path.exists(file_path):
                    continue

                values = list(self.app.tree.item(row_id, "values"))

                catalog_fields = (("Album", 4), ("Genre", 5), ("Publisher", 6))
                invalid_catalog_fields = []
                for field_name, col_index in catalog_fields:
                    if col_index >= len(values):
                        continue
                    current_value = str(values[col_index]).strip() if values[col_index] is not None else ""
                    if not current_value:
                        continue

                    normalized_value = CatalogManager.normalize_catalog_text(current_value)
                    allowed_values = {
                        CatalogManager.normalize_catalog_text(v)
                        for v in self.app.catalog_values.get(field_name, [])
                        if str(v).strip()
                    }
                    if normalized_value not in allowed_values:
                        values[col_index] = ""
                        self.app.audio_manager.save_single_tag(file_path, field_name, "")
                        invalid_catalog_fields.append(field_name)

                if invalid_catalog_fields:
                    self.app.tree.item(row_id, values=values)
                    self.logger.info(
                        f"Se limpiaron campos fuera de catálogo en '{os.path.basename(file_path)}': "
                        f"{', '.join(invalid_catalog_fields)}"
                    )

                old_filename = os.path.basename(file_path)
                new_filename = self.app.filename_formatter.format_filename_pattern(old_filename)
                dir_name = os.path.dirname(file_path)
                new_file_path = os.path.join(dir_name, new_filename)

                if old_filename != new_filename:
                    try:
                        os.rename(file_path, new_file_path)
                        self.app.file_paths_map[row_id] = new_file_path
                        file_path = new_file_path

                        values[0] = new_filename
                        self.app.tree.item(row_id, values=values)
                        self.logger.info(f"Renombrado archivo: '{old_filename}' -> '{new_filename}'")
                    except Exception as e:
                        self.logger.error(f"No se pudo renombrar el archivo '{old_filename}': {str(e)}")

                clean_name = os.path.splitext(new_filename)[0]

                artist_parsed = ""
                title_parsed = clean_name
                mixartist_parsed = ""

                parentheses = re.findall(r'\((.*?)\)', clean_name)
                if parentheses:
                    mixartist_parsed = " ".join(parentheses).strip()
                    clean_name = re.sub(r'\(.*?\)', '', clean_name).strip()

                if " - " in clean_name:
                    parts = clean_name.split(" - ", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()
                elif "-" in clean_name:
                    parts = clean_name.split("-", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()

                metadata_changes = []
                metadata_mappings = (
                    (1, "Artist", "Autor", artist_parsed),
                    (2, "Title", "Título", title_parsed),
                    (3, "MixArtist", "Remix", mixartist_parsed),
                )
                for col_index, tag_name, label, new_value in metadata_mappings:
                    previous_value = str(values[col_index]).strip() if col_index < len(values) and values[col_index] is not None else ""
                    if col_index < len(values):
                        values[col_index] = new_value
                    self.app.audio_manager.save_single_tag(file_path, tag_name, new_value)

                    if previous_value != new_value:
                        action = "vaciado" if not new_value else "actualizado"
                        metadata_changes.append(
                            f"{label} {action}: '{previous_value}' -> '{new_value}'"
                        )

                self.app.tree.item(row_id, values=values)
                already_has_cover = self.app.grid_panel.row_has_cover(row_id)
                if already_has_cover:
                    self.logger.info(f"Se omite solo la descarga de carátula para '{new_filename}' porque ya tiene una incrustada.")

                query_term = UiUtils.build_discogs_query(
                    values[1] if len(values) > 1 else "",
                    values[2] if len(values) > 2 else "",
                    fallback_text=re.sub(r'^\d+[\s\-_.]*', '', clean_name)
                )
                query_term = omit_pattern.sub('', query_term)
                query_term = query_term.replace('_', ' ')
                query_term = re.sub(r'\s+[._-]\s+', ' ', query_term)
                query_term = re.sub(r'\s+', ' ', query_term).strip()

                self.logger.info(f"Procesando archivo: '{new_filename}' (Búsqueda Discogs: '{query_term}')")

                _, _, year, cover_url = self.app.discogs_client.search_release(query_term)

                if year:
                    values[7] = str(year)
                    self.app.audio_manager.save_single_tag(file_path, "Year", str(year))

                if already_has_cover:
                    values[8] = "Sí"
                    self.app.grid_panel.update_row_cover_status(row_id, "Sí")
                else:
                    # Buscamos todas las imágenes disponibles si el cliente lo soporta
                    all_images = self.app.discogs_client.get_release_images(query_term) if hasattr(self.app.discogs_client, 'get_release_images') else []

                    # Si no hay lista extendida de imágenes, usamos la cover_url principal como fallback
                    if not all_images and cover_url:
                        all_images = [cover_url]

                    chosen_cover_url = None
                    manual_mode = getattr(self.app.catalog_manager, "manual_cover_selection", True)

                    if all_images:
                        if manual_mode:
                            # Se abre el cuadro emergente para seleccionar la carátula manualmente
                            chosen_cover_url = DialogManager.select_discogs_cover_dialog(self.app, all_images)
                        else:
                            # Modo automático: se toma la primera imagen por defecto
                            chosen_cover_url = all_images[0]

                    if chosen_cover_url:
                        self.logger.info(f"Descargando carátula seleccionada desde: {chosen_cover_url}")
                        image_data = self.app.discogs_client.download_image_bytes(chosen_cover_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                values[8] = "Sí"
                                self.logger.info(f"Carátula incrustada con éxito en: {new_filename}")
                                self.app.detail_panel.display_cover_art(image_data)
                                self.app.grid_panel.update_row_cover_status(row_id, "Sí")
                            else:
                                values[8] = "No"
                                self.logger.error(f"La carátula no quedó persistida en el archivo: {new_filename}")
                        else:
                            values[8] = "No"
                            self.logger.warning(f"No se pudieron descargar los bytes de la carátula ({chosen_cover_url})")
                    else:
                        values[8] = "No"
                        self.logger.warning(f"No se seleccionó ninguna carátula para: '{query_term}'")
                        self.app.grid_panel.update_row_cover_status(row_id, "No")

                self.app.tree.item(row_id, values=values)
                if metadata_changes:
                    self.logger.info(f"Metadatos desde nombre -> {' | '.join(metadata_changes)}")
                else:
                    self.logger.info("Metadatos desde nombre -> sin cambios")
                self.logger.info(f"Actualizado Discogs -> Año: '{year}'")

                processed += 1
                self.app.progress_bar.set(processed / total_files)
                self.app.update_idletasks()

            self.app.detail_panel.on_row_select(None)
            self.logger.info("Procesamiento finalizado con éxito.")

        finally:
            if hasattr(self.app, 'btn_process'):
                self.app.detail_panel.btn_process.configure(state="normal", text="Procesar")
                self.app.update_idletasks()

    def update_row_from_file_metadata(self, row_id, file_path):
        metadata = self.app.audio_manager.extract_metadata(file_path, os.path.basename(file_path))
        metadata["Album"] = CatalogManager.normalize_catalog_text(metadata.get("Album", ""))
        metadata["Genre"] = CatalogManager.normalize_catalog_text(metadata.get("Genre", ""))
        metadata["Publisher"] = CatalogManager.normalize_catalog_text(metadata.get("Publisher", ""))

        self.app.tree.item(row_id, values=(
            metadata["Filename"],
            metadata["Artist"],
            metadata["Title"],
            metadata["MixArtist"],
            metadata["Album"],
            metadata["Genre"],
            metadata["Publisher"],
            metadata["Year"],
            metadata["Cover"]
        ))

    def clear_metadata_for_rows(self, target_rows, scope_label="selección"):
        target_rows = list(target_rows)
        if not target_rows:
            DialogManager.show_themed_dialog(
                self.app,
                "Sin archivos",
                "No hay archivos disponibles para limpiar metadatos.",
                level="warning"
            )
            return 0

        if len(target_rows) == 1:
            row_id = target_rows[0]
            file_path = self.app.file_paths_map.get(row_id)
            file_name = os.path.basename(file_path) if file_path else "el archivo seleccionado"
            message = f"¿Eliminar todos los metadatos de:\n{file_name}?"
        else:
            message = (
                f"¿Eliminar todos los metadatos de {len(target_rows)} archivo(s) "
                f"de la {scope_label}?"
            )

        if not DialogManager.show_themed_dialog(self.app, "Confirmar limpieza", message, level="warning", is_confirm=True):
            return 0

        cleaned_count = 0
        failed_count = 0

        for row_id in target_rows:
            file_path = self.app.file_paths_map.get(row_id)
            if not file_path or not os.path.exists(file_path):
                self.logger.warning("Se omite limpieza de metadatos: archivo no encontrado en disco.")
                failed_count += 1
                continue

            if not self.app.audio_manager.clear_audio_file_metadata(file_path):
                failed_count += 1
                continue

            self.update_row_from_file_metadata(row_id, file_path)
            self.logger.info(f"Metadatos eliminados de: {os.path.basename(file_path)}")
            cleaned_count += 1

        if self.app.tree.selection():
            self.app.detail_panel.on_row_select(None)

        self.logger.info(
            f"Limpieza de metadatos completada ({scope_label}) -> OK: {cleaned_count}, Fallos: {failed_count}"
        )
        return cleaned_count

    def clear_selected_metadata(self):
        selected_rows = self.app.tree.selection()
        if not selected_rows:
            DialogManager.show_themed_dialog(
                self.app,
                "Sin selección",
                "Selecciona al menos un archivo en la tabla para limpiar sus metadatos.",
                level="warning"
            )
            return

        scope_label = "selección" if len(selected_rows) > 1 else "archivo seleccionado"
        self.clear_metadata_for_rows(selected_rows, scope_label=scope_label)

    def clear_all_loaded_metadata(self):
        all_rows = self.app.tree.get_children()
        self.clear_metadata_for_rows(all_rows, scope_label="lista cargada")