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
        self._tree_columns_cache = None

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
        if hasattr(self.app, "discogs_client") and hasattr(self.app.discogs_client, "clear_runtime_cache"):
            self.app.discogs_client.clear_runtime_cache()

        target_rows = self.app.tree.selection()
        if not target_rows:
            target_rows = self.app.tree.get_children()

        snapshots = self._build_processing_snapshots(target_rows)

        if not snapshots:
            DialogManager.show_themed_dialog(self.app, "Advertencia", "No hay archivos cargados en la tabla.", level="warning")
            return

        if hasattr(self.app, 'detail_panel') and hasattr(self.app.detail_panel, 'btn_process'):
            self.app.detail_panel.btn_process.configure(state="disabled", text="Procesando...")

        total_files = len(snapshots)
        columns_snapshot = self.app.get_tree_columns() if hasattr(self.app, "get_tree_columns") else list(self.app.tree["columns"])
        self.logger.info(f"Iniciando procesado multihilo para {total_files} archivo(s)...")

        # Lanzar la canalización en un hilo secundario para mantener la interfaz fluida
        threading.Thread(
            target=self._run_processing_pipeline,
            args=(snapshots, total_files, columns_snapshot),
            daemon=True
        ).start()

    def _should_review_covers(self) -> bool:
        """Determina si la opción 'Revisar carátulas' está activa."""
        if hasattr(self.app, "review_covers_var") and self.app.review_covers_var is not None:
            return bool(self.app.review_covers_var.get())
        if hasattr(self.app, "catalog_manager"):
            return bool(getattr(self.app.catalog_manager, "manual_cover_selection", True))
        return True

    def _get_tree_columns(self):
        if self._tree_columns_cache:
            return self._tree_columns_cache
        if hasattr(self.app, "get_tree_columns"):
            return self.app.get_tree_columns()
        return list(self.app.tree["columns"])

    def _build_processing_snapshots(self, row_ids):
        """Toma una foto de filas en hilo UI para procesar sin tocar Tk en workers."""
        snapshots = []
        for row_id in row_ids:
            if not self.app.tree.exists(row_id):
                continue

            file_path = self.app.file_paths_map.get(row_id)
            if not file_path:
                continue

            values = list(self.app.tree.item(row_id, "values"))
            if not values:
                continue

            snapshots.append({
                "row_id": row_id,
                "file_path": file_path,
                "values": values,
            })

        return snapshots

    def _get_col_index(self, col_name):
        cols = self._get_tree_columns()
        return cols.index(col_name) if col_name in cols else None

    def _get_value(self, values, col_name, default=""):
        idx = self._get_col_index(col_name)
        if idx is None or idx >= len(values):
            return default
        val = values[idx]
        return default if val is None else val

    def _set_value(self, values, col_name, new_value):
        idx = self._get_col_index(col_name)
        if idx is None or idx >= len(values):
            return False
        values[idx] = new_value
        return True

    def _parse_row_values(self, row_id, values, file_path):
        row_map = {}
        cols = self._get_tree_columns()
        for idx, col_name in enumerate(cols):
            val = values[idx] if idx < len(values) else ""
            row_map[col_name] = str(val) if val is not None else ""

        filename = os.path.basename(file_path) if file_path else ""
        parsed = {
            "Filename": (row_map.get("Filename") or filename),
            "Artist": row_map.get("Artist", ""),
            "Title": row_map.get("Title", ""),
            "MixArtist": row_map.get("MixArtist", ""),
            "Album": row_map.get("Album", ""),
            "Genre": row_map.get("Genre", ""),
            "Publisher": row_map.get("Publisher", ""),
            "Comment": row_map.get("Comment", ""),
            "Year": row_map.get("Year", ""),
            "Cover": row_map.get("Cover", "") or "No",
        }
        return parsed

    def _run_processing_pipeline(self, snapshots, total_files, columns_snapshot):
        self._tree_columns_cache = list(columns_snapshot or [])
        processed_count = 0
        words_to_omit = [
            r'\bfeat\.\b', r'\bfeat\b',
            r'\bft\.\b', r'\bft\b',
            r'\bpres\.\b', r'\bpres\b',
            r'\bpresents\b'
        ]
        omit_pattern = re.compile('|'.join(words_to_omit), flags=re.IGNORECASE)
        pending_cover_reviews = []
        manual_mode = self._should_review_covers()

        def _process_single_file(snapshot):
            nonlocal processed_count

            row_id = snapshot.get("row_id")
            file_path = snapshot.get("file_path")
            values = list(snapshot.get("values") or [])

            if not file_path or not os.path.exists(file_path) or not values:
                return

            prev_vals = self._parse_row_values(row_id, values, file_path)

            # 1. Validación de campos de catálogo por nombre de columna
            catalog_fields = ("Album", "Genre", "Publisher")
            invalid_catalog_fields = []
            for field_name in catalog_fields:
                current_value = str(self._get_value(values, field_name, "")).strip()
                if not current_value:
                    continue

                normalized_value = CatalogManager.normalize_catalog_text(current_value)
                allowed_values = {
                    CatalogManager.normalize_catalog_text(v)
                    for v in self.app.catalog_values.get(field_name, [])
                    if str(v).strip()
                }
                if normalized_value not in allowed_values:
                    self._set_value(values, field_name, "")
                    self.app.audio_manager.save_single_tag(file_path, field_name, "")
                    invalid_catalog_fields.append(field_name)

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
                    self._set_value(values, "Filename", new_filename)
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
                ("Artist", artist_parsed),
                ("Title", title_parsed),
                ("MixArtist", mixartist_parsed),
            )
            for tag_name, new_value in metadata_mappings:
                self._set_value(values, tag_name, new_value)
                self.app.audio_manager.save_single_tag(file_path, tag_name, new_value)

            cover_val = str(self._get_value(values, "Cover", "No")).strip().lower()
            already_has_cover = cover_val in ("sí", "si", "yes", "true", "1")

            has_year = bool(str(self._get_value(values, "Year", "")).strip())
            all_images = []

            # Modificación de metadatos mediante Discogs
            if already_has_cover and has_year:
                self.logger.info(f"[PROCESS] Omitida consulta Discogs para '{new_filename}' (ya posee carátula y año).")
                self._set_value(values, "Cover", "Sí")
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
                    self._set_value(values, "Year", str(year))
                    self.app.audio_manager.save_single_tag(file_path, "Year", str(year))

                if already_has_cover:
                    self._set_value(values, "Cover", "Sí")
                else:
                    if all_images and not manual_mode:
                        chosen_cover_url = all_images[0]
                        image_data = self.app.discogs_client.download_image_bytes(chosen_cover_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                self._set_value(values, "Cover", "Sí")
                            else:
                                self._set_value(values, "Cover", "No")
                        else:
                            self._set_value(values, "Cover", "No")
                    elif len(all_images) == 1 and manual_mode:
                        chosen_cover_url = all_images[0]
                        image_data = self.app.discogs_client.download_image_bytes(chosen_cover_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                self._set_value(values, "Cover", "Sí")
                            else:
                                self._set_value(values, "Cover", "No")
                        else:
                            self._set_value(values, "Cover", "No")
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
                        self._set_value(values, "Cover", "No")

            new_vals = self._parse_row_values(row_id, values, file_path)

            diff_prev = {k: v for k, v in prev_vals.items() if prev_vals[k] != new_vals[k]}
            diff_new = {k: v for k, v in new_vals.items() if prev_vals[k] != new_vals[k]}

            if diff_new and not (len(all_images) > 1 and manual_mode):
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
                    cover_val = self._get_value(values, "Cover", "No")
                    self.app.grid_panel.update_row_cover_status(row_id, cover_val)

            self.app.after(0, _update_ui)

            with self._lock:
                processed_count += 1
                current_count = processed_count

            if current_count % 10 == 0 or current_count == total_files:
                progress = current_count / total_files
                self.app.after(0, lambda p=progress: self.app.progress_bar.set(p))

        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.map(_process_single_file, snapshots)

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

                    cover_index = self._get_col_index("Cover")
                    if cover_index is None or cover_index >= len(values):
                        continue

                    if chosen_url and chosen_url != "__NO_COVER__":
                        image_data = self.app.discogs_client.download_image_bytes(chosen_url)
                        if image_data:
                            image_data = AudioManager.normalize_cover_image_bytes(image_data)
                            if self.app.audio_manager.embed_cover_art_verified(file_path, image_data):
                                values[cover_index] = "Sí"
                            else:
                                values[cover_index] = "No"
                        else:
                            values[cover_index] = "No"
                    else:
                        values[cover_index] = "No"

                    self.app.tree.item(row_id, values=values)
                    self.app.grid_panel.update_row_cover_status(row_id, values[cover_index])

                    new_vals = self._parse_row_values(row_id, values, file_path)

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
            self._tree_columns_cache = None

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
        """Re-extrae los metadatos desde el archivo en disco y actualiza la fila correspondiente en la grilla."""
        metadata = self.app.audio_manager.extract_metadata(file_path, os.path.basename(file_path))
        metadata["Album"] = CatalogManager.normalize_catalog_text(metadata.get("Album", ""))
        metadata["Genre"] = CatalogManager.normalize_catalog_text(metadata.get("Genre", ""))
        metadata["Publisher"] = CatalogManager.normalize_catalog_text(metadata.get("Publisher", ""))

        row_payload = {
            "Filename": metadata.get("Filename", ""),
            "Artist": metadata.get("Artist", ""),
            "Title": metadata.get("Title", ""),
            "MixArtist": metadata.get("MixArtist", ""),
            "Album": metadata.get("Album", ""),
            "Genre": metadata.get("Genre", ""),
            "Publisher": metadata.get("Publisher", ""),
            "Comment": metadata.get("Comment", ""),
            "Year": metadata.get("Year", ""),
            "Cover": metadata.get("Cover", "No"),
        }

        if hasattr(self.app, "grid_panel") and hasattr(self.app.grid_panel, "build_row_values"):
            self.app.tree.item(row_id, values=self.app.grid_panel.build_row_values(row_payload))
        else:
            cols = self._get_tree_columns()
            self.app.tree.item(row_id, values=tuple(row_payload.get(c, "") for c in cols))

    def clear_metadata_for_rows(self, rows, scope_label="selección"):
        """Limpia las etiquetas editables de los archivos manteniendo intacta la duración y datos de contenedor."""
        if not rows:
            return

        for row_id in rows:
            file_path = self.app.file_paths_map.get(row_id)
            if file_path and os.path.exists(file_path):
                filename = os.path.basename(file_path)
                values = list(self.app.tree.item(row_id, "values"))

                # BORRAR
                print(f"DEBUG Treeview [len={len(values)}]: {values}")

                # Usar el parser centralizado para mapear correctamente las claves
                parsed_prev = self._parse_row_values(row_id, values, file_path)

                # Limpieza física en el archivo de audio
                self.app.audio_manager.clear_audio_file_metadata(file_path)
                self.app.grid_panel.update_row_cover_status(row_id, "No")

                if values:
                    new_values = list(values)
                    # Limpiar columnas editables por nombre, preservando Filename.
                    for col_name in ("Artist", "Title", "MixArtist", "Album", "Genre", "Publisher", "Comment", "Year"):
                        self._set_value(new_values, col_name, "")
                    self._set_value(new_values, "Cover", "No")

                    self.app.tree.item(row_id, values=new_values)

                # Extraer prev_vals excluyendo 'Filename' para el formato del log de limpieza
                log_prev = {k: v for k, v in parsed_prev.items() if k != "Filename"}
                log_new = {
                    "Artist": "",
                    "Title": "",
                    "MixArtist": "",
                    "Album": "",
                    "Genre": "",
                    "Publisher": "",
                    "Comment": "",
                    "Year": "",
                    "Cover": "No"
                }

                log_msg = LogManager.format_tree_log(
                    context="PROCESS",
                    action="Limpiar",
                    filename=filename,
                    prev_vals=log_prev,
                    new_vals=log_new
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
                    self._set_value(values, "Filename", new_filename)
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

    def delete_selected_files(self):
        """Elimina físicamente del disco los archivos seleccionados en la grilla tras confirmación."""
        tree = getattr(self.app, "tree", None)
        if not tree and hasattr(self.app, "grid_panel"):
            tree = self.app.grid_panel.tree

        if not tree:
            return

        selected_rows = tree.selection()
        if not selected_rows:
            DialogManager.show_themed_dialog(
                self.app,
                "Sin selección",
                "Selecciona al menos un archivo para eliminar.",
                level="warning"
            )
            return

        count = len(selected_rows)

        # Diálogo de confirmación
        confirm = DialogManager.show_themed_dialog(
            self.app,
            "Confirmar eliminación",
            f"¿Estás seguro de que deseas eliminar permanentemente {count} archivo(s) del disco?\n\nEsta acción no se puede deshacer.",
            level="warning",
            is_confirm=True,
            parent=self.app
        )

        if not confirm:
            return

        deleted_count = 0

        for row_id in list(selected_rows):
            file_path = self.app.file_paths_map.get(row_id)

            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    self.logger.info(f"[DELETE] Archivo eliminado del disco: {file_path}")
                except Exception as e:
                    self.logger.error(f"[DELETE] Error al eliminar {file_path}: {str(e)}")
                    continue

            # Eliminar la fila del Treeview y del mapa de rutas
            if tree.exists(row_id):
                tree.delete(row_id)
            if row_id in self.app.file_paths_map:
                del self.app.file_paths_map[row_id]

        if deleted_count > 0 and hasattr(self.app, "detail_panel"):
            self.app.detail_panel.on_row_select(None)