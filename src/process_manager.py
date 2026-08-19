import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dialogs import DialogManager
from catalog_manager import CatalogManager
from audio_manager import AudioManager
from ui_utils import UiUtils

class ProcessManager:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger
        self._lock = threading.Lock()  # Sincronización para hilos en recursos compartidos

    def process_discogs_data(self):
        target_rows = self.app.tree.selection()
        if not target_rows:
            target_rows = self.app.tree.get_children()

        if not target_rows:
            DialogManager.show_themed_dialog(self.app, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

        if hasattr(self.app, 'btn_process'):
            self.app.detail_panel.btn_process.configure(state="disabled", text="Procesando...")

        total_files = len(target_rows)
        self.logger.info(f"Iniciando procesado multihilo para {total_files} archivo(s)...")

        # Lanzar el flujo completo en un hilo secundario para evitar congelar la UI
        threading.Thread(
            target=self._run_processing_pipeline,
            args=(target_rows, total_files),
            daemon=True
        ).start()

    def _run_processing_pipeline(self, target_rows, total_files):
        processed_count = 0
        words_to_omit = [
            r'\bfeat\.\b', r'\bfeat\b',
            r'\bft\.\b', r'\bft\b',
            r'\bpres\.\b', r'\bpres\b',
            r'\bpresents\b'
        ]
        omit_pattern = re.compile('|'.join(words_to_omit), flags=re.IGNORECASE)

        # Estructura para almacenar las revisiones de carátula pendientes (fase 2)
        pending_cover_reviews = []

        # Worker ejecutado en paralelo para cada archivo (Fase 1: Parsing, tags y Discogs API)
        def _process_single_file(row_id):
            nonlocal processed_count

            with self._lock:
                file_path = self.app.file_paths_map.get(row_id)
                values = list(self.app.tree.item(row_id, "values")) if self.app.tree.exists(row_id) else None

            if not file_path or not os.path.exists(file_path) or not values:
                return

            # 1. Validación de campos de catálogo
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
                self.logger.info(
                    f"Se limpiaron campos fuera de catálogo en '{os.path.basename(file_path)}': "
                    f"{', '.join(invalid_catalog_fields)}"
                )

            # 2. Parseo y Normalización Local
            old_filename = os.path.basename(file_path)
            ext = os.path.splitext(old_filename)[1]

            parsed_data = None
            if hasattr(self.app.filename_formatter, 'parse_and_format'):
                parsed_data = self.app.filename_formatter.parse_and_format(old_filename)

            if parsed_data:
                artist_parsed = parsed_data.get("artist", "").strip()
                title_parsed = parsed_data.get("title", "").strip()
                mixartist_parsed = parsed_data.get("mixartist", "").strip()
            else:
                new_filename_temp = self.app.filename_formatter.format_filename_pattern(old_filename)
                clean_name_fallback = os.path.splitext(new_filename_temp)[0]
                artist_parsed = ""
                title_parsed = clean_name_fallback
                mixartist_parsed = ""

                parentheses = re.findall(r'\((.*?)\)', clean_name_fallback)
                if parentheses:
                    mixartist_parsed = " ".join(parentheses).strip()
                    clean_name_fallback = re.sub(r'\(.*?\)', '', clean_name_fallback).strip()

                if " - " in clean_name_fallback:
                    parts = clean_name_fallback.split(" - ", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()
                elif "-" in clean_name_fallback:
                    parts = clean_name_fallback.split("-", 1)
                    artist_parsed = parts[0].strip()
                    title_parsed = parts[1].strip()

            new_filename_base = f"{artist_parsed} - {title_parsed}" if artist_parsed else title_parsed
            if mixartist_parsed:
                new_filename_base += f" ({mixartist_parsed})"
            new_filename = f"{new_filename_base}{ext}"

            dir_name = os.path.dirname(file_path)
            new_file_path = os.path.join(dir_name, new_filename)

            if old_filename != new_filename:
                try:
                    os.rename(file_path, new_file_path)
                    with self._lock:
                        self.app.file_paths_map[row_id] = new_file_path
                    file_path = new_file_path
                    values[0] = new_filename
                    self.logger.info(f"Renombrado archivo: '{old_filename}' -> '{new_filename}'")
                except Exception as e:
                    self.logger.error(f"No se pudo renombrar el archivo '{old_filename}': {str(e)}")

            metadata_mappings = (
                (1, "Artist", artist_parsed),
                (2, "Title", title_parsed),
                (3, "MixArtist", mixartist_parsed),
            )
            for col_index, tag_name, new_value in metadata_mappings:
                if col_index < len(values):
                    values[col_index] = new_value
                self.app.audio_manager.save_single_tag(file_path, tag_name, new_value)

            with self._lock:
                already_has_cover = self.app.grid_panel.row_has_cover(row_id)

            has_year = bool(str(values[7]).strip()) if len(values) > 7 else False

            # OPTIMIZACIÓN 1: Si ya tiene año Y carátula, omitir la consulta remota a Discogs
            if already_has_cover and has_year:
                self.logger.info(f"Omitida consulta a Discogs para '{new_filename}': ya dispone de Año y Carátula.")
                values[8] = "Sí"
            else:
                # 3. Consulta a Discogs (solo si falta año o carátula)
                query_term = f"{artist_parsed} {title_parsed}".strip()
                query_term = omit_pattern.sub('', query_term)
                query_term = query_term.replace('_', ' ')
                query_term = re.sub(r'\s+[._-]\s+', ' ', query_term)
                query_term = re.sub(r'\s+', ' ', query_term).strip()

                _, _, year, cover_url = self.app.discogs_client.search_release(query_term)
                all_images = self.app.discogs_client.get_release_images(query_term) if hasattr(self.app.discogs_client, 'get_release_images') else []
                if not all_images and cover_url:
                    all_images = [cover_url]

                if year:
                    values[7] = str(year)
                    self.app.audio_manager.save_single_tag(file_path, "Year", str(year))

                # Gestión de carátulas
                if already_has_cover:
                    values[8] = "Sí"
                else:
                    manual_mode = getattr(self.app.catalog_manager, "manual_cover_selection", True)

                    # OPTIMIZACIÓN 2: Si solo hay 1 imagen, o si el modo manual está desactivado,
                    # se descarga directamente sin abrir diálogo modal.
                    if len(all_images) == 1 or (all_images and not manual_mode):
                        chosen_cover_url = all_images[0]
                        image_data = self.app.discogs_client.download_image_bytes(chosen_cover_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                values[8] = "Sí"
                            else:
                                values[8] = "No"
                        else:
                            values[8] = "No"
                    elif len(all_images) > 1 and manual_mode:
                        # Solo abre modal si hay más de 1 opción
                        with self._lock:
                            pending_cover_reviews.append({
                                "row_id": row_id,
                                "filename": new_filename,
                                "file_path": file_path,
                                "images": all_images,
                                "values": values
                            })
                    else:
                        values[8] = "No"

            def _update_ui():
                if self.app.tree.exists(row_id):
                    self.app.tree.item(row_id, values=values)
                    self.app.grid_panel.update_row_cover_status(row_id, values[8])

            self.app.after(0, _update_ui)

            with self._lock:
                processed_count += 1
                progress = processed_count / total_files
                self.app.after(0, lambda p=progress: self.app.progress_bar.set(p))

        # Ejecución en paralelo de la fase 1 (4 hilos)
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(_process_single_file, target_rows)

        # Fase 2: Gestión de diálogo interactivo de carátulas en el hilo principal
        def _handle_manual_covers_and_finish():
            if pending_cover_reviews:
                self.logger.info(f"Iniciando selección de carátulas para {len(pending_cover_reviews)} archivo(s)...")
                selections = DialogManager.process_pending_covers_dialog(self.app, pending_cover_reviews)

                for item in pending_cover_reviews:
                    row_id = item["row_id"]
                    file_path = item["file_path"]
                    values = item["values"]
                    chosen_url = selections.get(row_id)

                    if chosen_url:
                        image_data = self.app.discogs_client.download_image_bytes(chosen_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                values[8] = "Sí"
                                self.app.tree.item(row_id, values=values)
                                self.app.grid_panel.update_row_cover_status(row_id, "Sí")
                            else:
                                values[8] = "No"
                        else:
                            values[8] = "No"
                    else:
                        values[8] = "No"
                        self.app.tree.item(row_id, values=values)
                        self.app.grid_panel.update_row_cover_status(row_id, "No")

            if hasattr(self.app, 'btn_process'):
                self.app.detail_panel.btn_process.configure(state="normal", text="Procesar")
            self.app.detail_panel.on_row_select(None)
            self.logger.info("Procesamiento multihilo finalizado con éxito.")

        self.app.after(0, _handle_manual_covers_and_finish)

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

    def clear_metadata_for_rows(self, rows, scope_label="selección"):
        if not rows:
            return

        for row_id in rows:
            file_path = self.app.file_paths_map.get(row_id)
            if file_path:
                for col_name in ["Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Year"]:
                    self.app.audio_manager.save_single_tag(file_path, col_name, "")

                self.app.audio_manager.strip_cover_tags(file_path)
                self.app.grid_panel.update_row_cover_status(row_id, "No")

                values = list(self.app.tree.item(row_id, "values"))
                if values:
                    filename = values[0]
                    cover_status = values[8] if len(values) > 8 else "No"
                    new_values = [filename, "", "", "", "", "", "", "", cover_status]
                    self.app.tree.item(row_id, values=new_values)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

        self.logger.info(f"Metadatos limpiados en {len(rows)} archivo(s).")

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