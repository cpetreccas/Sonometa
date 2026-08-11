# Funcionalidades detalladas de Sonometa

Este documento describe, de forma operativa y tecnica, cada funcionalidad visible en la aplicacion.

## 1. Carga de carpeta

Funcion: `browse_folder()` -> `load_audio_files(folder)`

Que hace:

1. Abre selector de carpeta.
2. Guarda ruta seleccionada.
3. Limpia tabla actual.
4. Escanea recursivamente (`os.walk`) todos los subdirectorios.
5. Filtra por extensiones soportadas.
6. Lee metadatos por archivo.
7. Inserta filas en tabla con alternancia visual par/impar.

Validaciones:

- Verifica que la ruta sea carpeta valida.
- Verifica permisos de lectura.

## 2. Extraccion de metadatos

Funcion: `extract_metadata(file_path, filename)`

Campos que recupera:

- Filename
- Title
- Artist
- MixArtist
- Album
- Genre
- Publisher
- Year
- Cover (Si/No)

Comportamiento por formato:

- WAV: lectura de frames ID3 explicitos.
- Otros: lectura easy tags con Mutagen.

Deteccion de caratula:

- APIC/PIC para ID3
- `pictures` para FLAC
- `covr` para MP4

## 3. Tabla editable

Funcion: `on_cell_double_click(event)`

Como funciona:

1. Detecta region/celda.
2. Impide editar columnas protegidas (`Filename`, `Cover`).
3. Crea `Entry` temporal encima de la celda.
4. Guarda con Enter o al perder foco.
5. Si cambio valor, actualiza tabla y guarda tag fisicamente.

Protecciones:

- Valida indice de columna.
- Valida `bbox` existente.
- Evita guardar cambios identicos.

## 4. Panel lateral de detalle

Funcion: `on_row_select(event)`

Que hace al seleccionar fila:

1. Copia campos a entradas laterales.
2. Busca ruta real del archivo.
3. Extrae y muestra caratula.

Nota:

- Si la fila no tiene suficientes columnas, no actualiza el panel para evitar errores.

## 5. Visualizacion de caratula

Funcion: `display_cover_art(file_path_or_bytes)`

Flujo:

1. Acepta bytes directos o ruta de archivo.
2. Si recibe ruta, extrae bytes con `extract_cover_bytes`.
3. Abre imagen con PIL.
4. Convierte modo si no es RGB/RGBA.
5. Redimensiona a 180x180.
6. Asigna imagen a `CTkLabel`.

Fallback:

- Si falla, muestra texto `Sin caratula`.

## 6. Procesamiento con Discogs (boton Procesar)

Funcion: `process_discogs_data()`

### 6.1 Seleccion de filas

- Si hay seleccion: procesa solo seleccion.
- Si no hay seleccion: procesa todas las filas.

### 6.2 Formato y renombrado

- Toma nombre actual.
- Aplica `format_filename_pattern()`.
- Renombra archivo en disco si hay cambios.
- Actualiza ruta interna y columna Filename.

### 6.3 Parseo local de tags

- Quita extension.
- Extrae contenido entre parentesis a `MixArtist`.
- Separa artista/titulo por guion.
- Guarda en tags con `save_single_tag`.

### 6.4 Query a Discogs

Funcion auxiliar: `search_discogs_api(query)`

- Construye query limpia.
- Llama endpoint de busqueda Discogs.
- Filtro aplicado: `format=Vinyl&type=release`.
- Timeout actual: 5 segundos.
- Retorna artista, titulo, year, cover_url.

### 6.5 Ano y portada

- Si hay ano: guarda tag `Year`.
- Si hay portada:
  - descarga bytes (`download_image_bytes`),
  - incrusta (`embed_cover_art`),
  - marca `Cover = Si`,
  - refresca preview.

### 6.6 Progreso y logs

- Actualiza barra de progreso por item.
- Deja trazabilidad por archivo en logger.

## 7. Escritura de tags

Funcion: `save_single_tag(file_path, field_name, new_value)`

Reglas:

- MP3/WAV: usa frames ID3.
- Otros formatos: usa easy tags Mutagen.
- Si valor vacio: elimina frame/campo correspondiente.

## 8. Incrustacion de caratulas

Funcion: `embed_cover_art(file_path, image_bytes)`

Reglas por extension:

- MP3/WAV:
  - elimina APIC existente,
  - añade nuevo APIC tipo cover front.
- FLAC:
  - limpia pictures,
  - añade nueva `Picture`.
- M4A/AAC/MP4:
  - escribe `covr` con `MP4Cover`.

## 9. Ordenacion de tabla

Funcion: `sort_by_column(col)`

- Orden lexicografico case-insensitive.
- Alterna asc/desc en cada click.
- Reasigna colores par/impar tras reordenar.

## 10. Logs y estado

- Logger llamado `Sonometa`.
- Salida simultanea:
  - consola,
  - historial GUI,
  - etiqueta de estado inferior.
- Historial limitado con `deque(maxlen=5000)`.

## 11. Menus y atajos

Menus:

- Archivo: seleccionar carpeta, actualizar, cerrar
- Acciones: procesar con Discogs, limpiar todo
- Ayuda: ver logs, acerca de

Atajos:

- `Ctrl+O`
- `F5`
- `Ctrl+Q`

## 12. Utilidades del repo

### `processor.py`

- Script funcional de procesamiento por carpeta.
- Incluye busqueda Discogs, renombrado, tags y caratula.
- Actualmente no esta conectado al boton principal de GUI.

### `icon_generator.py`

- Herramienta para generar una variante de logo PNG.
- Uso manual para activos graficos.

## 13. Casos de uso recomendados

1. Cargar carpeta de musica.
2. Revisar metadatos en tabla.
3. Corregir manualmente filas puntuales si hace falta.
4. Ejecutar Procesar para completar ano/caratula y normalizar nombres.
5. Revisar preview y logs.
6. Actualizar carpeta para verificar resultado final.

