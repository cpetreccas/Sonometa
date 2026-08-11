# Sonometa - Audio Tag Suite

Sonometa es una aplicacion de escritorio en Python para organizar metadatos de archivos de audio, renombrar pistas y enriquecer tags con datos de Discogs (ano + caratula).

Este documento describe el proyecto de forma funcional y tecnica, con foco en uso real y mantenimiento.

## 1. Que hace la aplicacion

- Escanea una carpeta de audio de forma recursiva.
- Muestra archivos y metadatos en una tabla editable.
- Permite editar tags por celda (doble clic).
- Procesa en lote con Discogs:
  - normaliza nombre de archivo,
  - extrae artista/titulo/remix del nombre,
  - consulta Discogs,
  - guarda ano,
  - descarga e incrusta caratula.
- Muestra vista previa de caratula en la barra lateral.
- Guarda historial de logs en memoria (max 5000 lineas).

## 2. Modulos del proyecto

- `gui.py`  
  Aplicacion principal (interfaz, lectura/escritura de tags, consulta Discogs, flujo de procesamiento).

- `processor.py`  
  Procesador alternativo/legacy con flujo similar por funcion (`procesar_carpeta`). Actualmente no se usa desde `gui.py`.

- `icon_generator.py`  
  Script de utilidad para generar variante del logo.

- `Sonometa.spec` y `gui.spec`  
  Configuracion de PyInstaller para crear ejecutable Windows.

## 3. Interfaz y experiencia de usuario

### 3.1 Barra superior

- **Seleccionar Carpeta**: abre dialogo para elegir carpeta.
- **Actualizar**: vuelve a escanear la carpeta actual.
- Etiqueta de ruta activa.

### 3.2 Tabla principal (Treeview)

Columnas:

1. Filename
2. Artist
3. Title
4. MixArtist
5. Album
6. Genre
7. Publisher
8. Year
9. Cover

Comportamiento:

- Click en cabecera: orden asc/desc por columna.
- Doble clic en celda: edicion inline (excepto `Filename` y `Cover`).
- Al guardar edicion: se actualiza GUI y tambien el tag en archivo.

### 3.3 Panel inferior de tags

Panel ubicado debajo del grid de archivos con diseño horizontal:

**Lado izquierdo:**
- Preview de carátula (180x180 px)

**Lado derecho - Campos en 3 filas:**
- **Fila 1**: Año
- **Fila 2**: Intérprete, Título, Remix (3 campos lado a lado)
- **Fila 3**: Album, Genero, Publisher (3 campos lado a lado)
- **Botón Procesar** en la parte superior del panel derecho

### 3.4 Barra inferior

- Barra de progreso.
- Estado actual (texto corto).

### 3.5 Menus

- **Archivo**: seleccionar carpeta, actualizar, cerrar.
- **Acciones**: procesar con Discogs, seleccionar todo, limpiar todo.
- **Ayuda**: atajos de teclado, ver logs, acerca de.

### 3.6 Atajos de teclado

- `Ctrl+O`: seleccionar carpeta
- `F5`: actualizar
- `Ctrl+A`: seleccionar todo
- `Ctrl+Q`: cerrar app

## 4. Flujo detallado del boton "Procesar"

Metodo principal: `App.process_discogs_data()` en `gui.py`.

### Paso 0: seleccionar alcance

- Si hay filas seleccionadas, procesa solo esas.
- Si no hay seleccion, procesa todas las filas cargadas.
- Si no hay filas, muestra advertencia y termina.

### Paso 1: normalizar nombre y renombrar archivo

Para cada archivo:

1. Lee nombre actual.
2. Aplica `format_filename_pattern()`:
   - respeta palabras reservadas en minuscula para contextos de remix (`remix`, `mix`, `edit`, etc.),
   - separa por `" - "` (o `"-"`),
   - ajusta capitalizacion de artista y titulo.
3. Si cambia el nombre, renombra fisicamente en disco.
4. Actualiza mapa interno (`row_id -> file_path`) y columna `Filename`.

### Paso 2: extraer tags desde el nombre

- Quita extension.
- Detecta contenido entre parentesis y lo guarda como `MixArtist`.
- Separa artista/titulo por guion.
- Guarda Artist, Title y MixArtist en tags del archivo con `save_single_tag()`.
- Actualiza tabla en memoria.

### Paso 3: preparar query y buscar en Discogs

- Limpia ruido del nombre para mejorar matching:
  - quita prefijos numericos,
  - elimina `feat`, `ft`, `pres`, etc.,
  - normaliza espacios y separadores.
- Llama a `search_discogs_api(query)`.
- API usada: `https://api.discogs.com/database/search` con filtro `format=Vinyl&type=release`.

### Paso 4: aplicar resultado Discogs

- Si hay `year`, lo guarda en tag (`Year`) y en tabla.
- Si hay `cover_url`:
  - descarga bytes de imagen,
  - incrusta caratula segun formato de audio,
  - marca `Cover = Si`,
  - muestra preview en panel lateral.

### Paso 5: progreso y cierre

- Actualiza barra de progreso por archivo.
- Al final, refresca panel de detalle y deja log de cierre.

## 5. Formatos de audio soportados

Constante en `gui.py`:

- `.mp3`
- `.flac`
- `.m4a`
- `.aac`
- `.wav`
- `.ogg`
- `.wma`
- `.aiff`

## 6. Mapeo de metadatos

### 6.1 Lectura

- WAV: via `mutagen.wave.WAVE` + frames ID3 (`TIT2`, `TPE1`, `TPE4`, `TALB`, `TCON`, `TPUB`, `TDRC`).
- Resto: via `mutagen.File(..., easy=True)` (`title`, `artist`, `mixartist`, `album`, `genre`, `organization/publisher`, `date/year`).

### 6.2 Escritura

**MP3/WAV (ID3):**

- Title -> `TIT2`
- Artist -> `TPE1`
- MixArtist -> `TPE4`
- Album -> `TALB`
- Genre -> `TCON`
- Publisher -> `TPUB`
- Year -> `TDRC`

**Otros formatos (easy tags):**

- Title -> `title`
- Artist -> `artist`
- MixArtist -> `mixartist`
- Album -> `album`
- Genre -> `genre`
- Publisher -> `organization`
- Year -> `date`

### 6.3 Caratulas

`embed_cover_art()` segun extension:

- MP3/WAV: frame `APIC` (ID3)
- FLAC: `Picture`
- M4A/AAC/MP4: `MP4Cover`
- Otros: fallback generico (`covr` si existe)

## 7. Instalacion y ejecucion

## 7.1 Requisitos

- Python 3.10+ recomendado
- Windows (objetivo principal del proyecto)

## 7.2 Instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 7.3 Ejecutar en desarrollo

```powershell
python gui.py
```

## 8. Build de ejecutable (.exe)

### Opcion recomendada

```powershell
pyinstaller Sonometa.spec
```

Salida esperada: `dist/Sonometa/Sonometa.exe`.

### Opcion alternativa

```powershell
pyinstaller gui.spec
```

Salida esperada: `dist/gui/gui.exe`.

Nota: distribuye la carpeta completa generada por PyInstaller, no solo el `.exe`.

## 9. Logging y estado

- Logger principal: `Sonometa`.
- Salida a consola y a GUI.
- Historial en memoria: `deque(maxlen=5000)`.
- Ventana de logs desde menu Ayuda.

## 10. Limitaciones actuales (codigo actual)

- Procesamiento principal en hilo UI (en lotes grandes puede notarse bloqueo visual).
- Busqueda Discogs forzada a formato vinyl.
- Se usa primer resultado de Discogs sin selector manual.
- No hay suite de tests automatizados en el repo.
- `processor.py` no esta integrado en flujo GUI (modulo legacy).

## 11. Ideas de mejora recomendadas

1. Mover `process_discogs_data()` a worker thread + cola de eventos UI.
2. Añadir cache simple de queries Discogs para acelerar lotes.
3. Crear tests unitarios para `format_filename_pattern()` y parseo de nombre.
4. Unificar o retirar `processor.py` para evitar duplicidad de logica.
5. Añadir validaciones de negocio (ano, tags vacios, conflictos de nombre).

## 12. Desarrollo rapido

Comprobacion de sintaxis:

```powershell
python -m py_compile gui.py
python -m py_compile processor.py
python -m py_compile icon_generator.py
```

## 13. Licencia

No se ha definido archivo de licencia en este repositorio.

