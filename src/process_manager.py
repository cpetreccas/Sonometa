import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dialogs import DialogManager
from catalog_manager import CatalogManager
from audio_manager import AudioManager
from log_handler import LogManager


class ProcessManager:
    def __init__(self, app):
        self.app = app
        self.logger = app.logger
        self._lock = threading.Lock()  # Sincronización para acceso concurrente

    def _get_default_cover_bytes(self):
        """Obtiene los bytes de la carátula por defecto buscando de forma robusta."""
        default_path = getattr(self.app, "DEFAULT_COVER_PATH", None)

        if not default_path or not os.path.exists(default_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(base_dir, "assets", "no_cover_art.jpg")

        if not os.path.exists(default_path):
            base_dir = os.path.dirname(os.path.abspath(__file__))
            default_path = os.path.join(os.path.dirname(base_dir), "assets", "no_cover_art.jpg")

        if default_path and os.path.exists(default_path):
            try:
                with open(default_path, "rb") as f:
                    return f.read()
            except Exception as e:
                self.logger.error(f"Error leyendo la carátula por defecto '{default_path}': {str(e)}")
        else:
            self.logger.warning("No se encontró el archivo de carátula por defecto en ninguna ruta evaluada.")

        return None

    def process_discogs_data(self):
        target_rows = self.app.tree.selection()
        if not target_rows:
            target_rows = self.app.tree.get_children()

        if not target_rows:
            DialogManager.show_themed_dialog(self.app, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

        if hasattr(self.app, 'detail_panel') and hasattr(self.app.detail_panel, 'btn_process'):
            self.app.detail_panel.btn_process.configure(state="disabled", text="Procesando...")

        total_files = len(target_rows)
        self.logger.info(f"Iniciando procesado multihilo para {total_files} archivo(s)...")

        # Lanzar la canalización en un hilo secundario para mantener la interfaz fluida
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
        pending_cover_reviews = []

        def _process_single_file(row_id):
            nonlocal processed_count

            with self._lock:
                file_path = self.app.file_paths_map.get(row_id)
                values = list(self.app.tree.item(row_id, "values")) if self.app.tree.exists(row_id) else None

            if not file_path or not os.path.exists(file_path) or not values:
                return

            prev_vals = {
                "Filename": str(values[0]) if len(values) > 0 else "",
                "Artist": str(values[1]) if len(values) > 1 else "",
                "Title": str(values[2]) if len(values) > 2 else "",
                "MixArtist": str(values[3]) if len(values) > 3 else "",
                "Album": str(values[4]) if len(values) > 4 else "",
                "Genre": str(values[5]) if len(values) > 5 else "",
                "Publisher": str(values[6]) if len(values) > 6 else "",
                "Year": str(values[7]) if len(values) > 7 else "",
                "Cover": str(values[8]) if len(values) > 8 else "No"
            }

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

            # Si hubo borrado de catálogo, actualizar el Grid e informar en el log
            if invalid_catalog_fields:
                clean_prev = {k: prev_vals[k] for k in invalid_catalog_fields}
                clean_new = {k: "" for k in invalid_catalog_fields}
                log_msg = LogManager.format_tree_log(
                    context="PROCESS",
                    action="Limpieza de Catálogo",
                    filename=os.path.basename(file_path),
                    prev_vals=clean_prev,
                    new_vals=clean_new
                )
                self.logger.info(log_msg)

                for k in invalid_catalog_fields:
                    prev_vals[k] = ""

                def _update_catalog_ui():
                    if self.app.tree.exists(row_id):
                        self.app.tree.item(row_id, values=values)
                self.app.after(0, _update_catalog_ui)

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
                    log_msg = LogManager.format_tree_log(
                        context="PROCESS",
                        action="Renombrado",
                        filename=new_filename,
                        prev_vals={"Filename": old_filename},
                        new_vals={"Filename": new_filename}
                    )
                    self.logger.info(log_msg)
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
            all_images = []

            # Modificación de metadatos mediante Discogs
            if already_has_cover and has_year:
                self.logger.info(f"[PROCESS] Omitida consulta Discogs para '{new_filename}' (ya posee carátula y año).")
                values[8] = "Sí"
            else:
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

                if already_has_cover:
                    values[8] = "Sí"
                else:
                    manual_mode = getattr(self.app.catalog_manager, "manual_cover_selection", True)

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
                        with self._lock:
                            pending_cover_reviews.append({
                                "row_id": row_id,
                                "filename": new_filename,
                                "file_path": file_path,
                                "images": all_images,
                                "values": values,
                                "prev_vals": prev_vals
                            })
                    else:
                        values[8] = "No"

            new_vals = {
                "Filename": str(values[0]) if len(values) > 0 else "",
                "Artist": str(values[1]) if len(values) > 1 else "",
                "Title": str(values[2]) if len(values) > 2 else "",
                "MixArtist": str(values[3]) if len(values) > 3 else "",
                "Album": str(values[4]) if len(values) > 4 else "",
                "Genre": str(values[5]) if len(values) > 5 else "",
                "Publisher": str(values[6]) if len(values) > 6 else "",
                "Year": str(values[7]) if len(values) > 7 else "",
                "Cover": str(values[8]) if len(values) > 8 else "No"
            }

            diff_prev = {k: v for k, v in prev_vals.items() if prev_vals[k] != new_vals[k]}
            diff_new = {k: v for k, v in new_vals.items() if prev_vals[k] != new_vals[k]}

            if diff_new and not (len(all_images) > 1 and getattr(self.app.catalog_manager, "manual_cover_selection", True)):
                log_msg = LogManager.format_tree_log(
                    context="PROCESS",
                    action="Procesado",
                    filename=new_filename,
                    prev_vals=diff_prev,
                    new_vals=diff_new
                )
                self.logger.info(log_msg)

            def _update_ui():
                if self.app.tree.exists(row_id):
                    self.app.tree.item(row_id, values=values)
                    self.app.grid_panel.update_row_cover_status(row_id, values[8])

            self.app.after(0, _update_ui)

            with self._lock:
                processed_count += 1
                progress = processed_count / total_files
                self.app.after(0, lambda p=progress: self.app.progress_bar.set(p))

        # Ejecución paralela con ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(_process_single_file, target_rows)

        def _handle_manual_covers_and_finish():
            if pending_cover_reviews:
                self.logger.info(f"Iniciando revisión única para {len(pending_cover_reviews)} archivo(s)...")
                selections = DialogManager.process_pending_covers_dialog(self.app, pending_cover_reviews)

                for item in pending_cover_reviews:
                    row_id = item["row_id"]
                    file_path = item["file_path"]
                    values = item["values"]
                    prev_vals = item.get("prev_vals", {})
                    chosen_url = selections.get(row_id)

                    if chosen_url and chosen_url != "__NO_COVER__":
                        image_data = self.app.discogs_client.download_image_bytes(chosen_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                values[8] = "Sí"
                            else:
                                values[8] = "No"
                        else:
                            values[8] = "No"
                    else:
                        values[8] = "No"

                    self.app.tree.item(row_id, values=values)
                    self.app.grid_panel.update_row_cover_status(row_id, values[8])

                    new_vals = {
                        "Filename": str(values[0]) if len(values) > 0 else "",
                        "Artist": str(values[1]) if len(values) > 1 else "",
                        "Title": str(values[2]) if len(values) > 2 else "",
                        "MixArtist": str(values[3]) if len(values) > 3 else "",
                        "Album": str(values[4]) if len(values) > 4 else "",
                        "Genre": str(values[5]) if len(values) > 5 else "",
                        "Publisher": str(values[6]) if len(values) > 6 else "",
                        "Year": str(values[7]) if len(values) > 7 else "",
                        "Cover": str(values[8]) if len(values) > 8 else "No"
                    }

                    diff_prev = {k: v for k, v in prev_vals.items() if prev_vals.get(k) != new_vals[k]}
                    diff_new = {k: v for k, v in new_vals.items() if prev_vals.get(k) != new_vals[k]}

                    if diff_new:
                        log_msg = LogManager.format_tree_log(
                            context="PROCESS",
                            action="Procesado con Carátula",
                            filename=os.path.basename(file_path),
                            prev_vals=diff_prev,
                            new_vals=diff_new
                        )
                        self.logger.info(log_msg)

            if hasattr(self.app, 'detail_panel') and hasattr(self.app.detail_panel, 'btn_process'):
                self.app.detail_panel.btn_process.configure(state="normal", text="Procesar")

            if hasattr(self.app, 'detail_panel'):
                self.app.detail_panel.refresh_catalog_comboboxes()
                self.app.detail_panel.on_row_select(None)

            self.logger.info("Procesamiento multihilo finalizado con éxito.")

        self.app.after(0, _handle_manual_covers_and_finish)

    def _apply_default_cover(self, file_path):
        """Lee la imagen por defecto, la incrusta físicamente en el archivo de audio y devuelve el estado."""
        default_bytes = self._get_default_cover_bytes()
        filename = os.path.basename(file_path)
        if default_bytes:
            try:
                normalized_bytes = AudioManager.normalize_cover_image_bytes(default_bytes)
                if self.app.audio_manager.embed_cover_art_verified(file_path, normalized_bytes):
                    log_msg = LogManager.format_tree_log(
                        context="PROCESS",
                        action="Carátula por defecto aplicada",
                        filename=filename,
                        prev_vals={"Cover": "No"},
                        new_vals={"Cover": "Sí"}
                    )
                    self.logger.info(log_msg)
                    return "Sí"
                else:
                    self.logger.error(f"Error al verificar la incrustación de la carátula por defecto en '{filename}'")
            except Exception as e:
                self.logger.error(f"Excepción al procesar la carátula por defecto para '{filename}': {e}")
        else:
            self.logger.warning("No se pudo aplicar la carátula por defecto porque los bytes están vacíos.")

        return "No"

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
        """Limpia los metadatos de los archivos recibidos registrando una sola línea de log por fichero."""
        if not rows:
            return

        for row_id in rows:
            file_path = self.app.file_paths_map.get(row_id)
            if file_path and os.path.exists(file_path):
                filename = os.path.basename(file_path)
                values = list(self.app.tree.item(row_id, "values"))

                prev_vals = {}
                if values:
                    prev_vals = {
                        "Artist": str(values[1]) if len(values) > 1 else "",
                        "Title": str(values[2]) if len(values) > 2 else "",
                        "MixArtist": str(values[3]) if len(values) > 3 else "",
                        "Album": str(values[4]) if len(values) > 4 else "",
                        "Genre": str(values[5]) if len(values) > 5 else "",
                        "Publisher": str(values[6]) if len(values) > 6 else "",
                        "Year": str(values[7]) if len(values) > 7 else "",
                        "Cover": str(values[8]) if len(values) > 8 else "No"
                    }

                # Limpieza total directa para evitar múltiples llamadas e inundación del log
                self.app.audio_manager.clear_audio_file_metadata(file_path)
                self.app.grid_panel.update_row_cover_status(row_id, "No")

                if values:
                    new_values = [values[0], "", "", "", "", "", "", "", "No"]
                    self.app.tree.item(row_id, values=new_values)

                new_vals = {
                    "Artist": "",
                    "Title": "",
                    "MixArtist": "",
                    "Album": "",
                    "Genre": "",
                    "Publisher": "",
                    "Year": "",
                    "Cover": "No"
                }

                log_msg = LogManager.format_tree_log(
                    context="PROCESS",
                    action="Limpiar",
                    filename=filename,
                    prev_vals=prev_vals,
                    new_vals=new_vals
                )
                self.logger.info(log_msg)

        if hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

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

    def apply_filename_replacement(self, row_ids, search_str, replace_str, case_sensitive=False):
        """
        Reemplaza la cadena dada en los nombres de archivo para los IDs recibidos.
        Retorna True si al menos un archivo fue modificado con éxito, False en caso contrario.
        """
        if not search_str or not row_ids:
            return False

        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(re.escape(search_str), flags)

        updated_count = 0

        tree = getattr(self.app, "tree", None)
        if not tree and hasattr(self.app, "grid_panel"):
            tree = self.app.grid_panel.tree

        for row_id in row_ids:
            if not tree or not tree.exists(row_id):
                continue

            file_path = self.app.file_paths_map.get(row_id)
            if not file_path or not os.path.exists(file_path):
                continue

            dir_name, full_filename = os.path.split(file_path)

            if not pattern.search(full_filename):
                continue

            # Evaluar la sustitución sobre el nombre completo (incluida la extensión si corresponde)
            new_filename = pattern.sub(replace_str, full_filename)

            if new_filename == full_filename:
                continue

            target_path = os.path.join(dir_name, new_filename)

            if os.path.normcase(target_path) != os.path.normcase(file_path) and os.path.exists(target_path):
                if hasattr(self, "logger") and self.logger:
                    self.logger.warning(f"Omitido: Ya existe un archivo llamado '{new_filename}'.")
                continue

            try:
                os.rename(file_path, target_path)
                self.app.file_paths_map[row_id] = target_path

                values = list(tree.item(row_id, "values"))
                if values:
                    values[0] = new_filename
                    tree.item(row_id, values=values)

                updated_count += 1

                if hasattr(self, "logger") and self.logger:
                    log_msg = LogManager.format_tree_log(
                        context="REPLACE",
                        action="Renombrado batch",
                        filename=new_filename,
                        prev_vals={"Filename": full_filename},
                        new_vals={"Filename": new_filename}
                    )
                    self.logger.info(log_msg)

            except Exception as e:
                if hasattr(self, "logger") and self.logger:
                    self.logger.error(f"Error al reemplazar nombre en '{full_filename}': {str(e)}")

        if updated_count > 0 and hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)

        return updated_count > 0