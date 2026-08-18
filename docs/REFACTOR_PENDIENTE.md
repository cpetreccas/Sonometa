1. A grid_panel.py (Operaciones sobre la tabla)
   Estos métodos manipulan directamente los datos, filas o selecciones del Treeview:

sort_by_column(self, col): Ordenamiento de columnas.

select_all_rows(self): Selección masiva de items en el árbol.

row_has_cover(self, row_id) y update_row_cover_status(self, row_id, status): Consulta y actualización del estado de carátula en la fila.

get_row_artist_title(self, row_id): Obtención de artista y título desde la fila.

2. A audio_manager.py o un nuevo controlador de procesamiento (process_manager.py)
   Lógica de negocio pesada relacionada con metadatos y renombrado de ficheros:

process_discogs_data(self): Orquestación del etiquetado, parseo de nombres, rename e integración con Discogs.

clear_metadata_for_rows, clear_selected_metadata, clear_all_loaded_metadata: Limpieza y reseteo de etiquetas de los archivos en disco.

_update_row_from_file_metadata: Reextracción e inserción de metadatos en la fila.

3. A ui_utils.py (Funciones auxiliares y formateo)

build_discogs_query(artist, title, fallback_text): Formateo y limpieza de la cadena de búsqueda.

4. A dialogs.py o log_handler.py

append_log_to_dialog(self, msg): Actualización del texto de logs en la ventana secundaria.