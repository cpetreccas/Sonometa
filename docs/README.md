# Sonometa - Audio Tag Suite v0.04

Sonometa es una aplicación de escritorio en Python para organizar metadatos de audio, renombrar pistas y enriquecer tags con Discogs (año y carátula).

Este README refleja el comportamiento actual implementado en `gui.py`.

## 1) Funcionalidades principales

- Escaneo recursivo de carpetas con detección de formatos de audio compatibles.
- Tabla principal editable con columnas: `Filename`, `Artist`, `Title`, `MixArtist`, `Album`, `Genre`, `Publisher`, `Year`, `Cover`.
- Edición inline por celda con guardado directo en el archivo (mutagen).
- Procesamiento por lotes con Discogs desde botón **Procesar**.
- Vista previa de carátula (180x180) y menú contextual sobre la imagen.
- Catálogos persistentes para `Album`, `Genre` y `Publisher`.
- Configuración persistente del token de Discogs.
- Logs en tiempo real (consola + ventana de historial).

## 2) Interfaz de usuario

### Barra superior
- **Seleccionar Carpeta** (`Ctrl+O`)
- **Actualizar** (`F5`)
- Ruta de la carpeta activa

### Panel lateral izquierdo
- Campos editables: Intérprete, Título, Remix, Álbum, Año, Género, Etiqueta.
- Carátula con vista previa.
- Botón **Procesar**.

### Tabla principal (derecha)
- Ordenación asc/desc al hacer clic en cabeceras.
- Doble clic para editar celdas.
- `Cover` no se edita por celda (se gestiona desde Discogs o menú contextual de carátula).

### Barra inferior
- Barra de progreso de procesamiento.
- Estado de la última operación.

### Menú superior
- **Archivo**: seleccionar carpeta, actualizar, configuración token, cerrar.
- **Acciones**: procesar, seleccionar todo, limpiar todo.
- **Gestionar**: géneros, álbumes, etiquetas.
- **Ayuda**: atajos, logs, acerca de.

## 3) Edición de celdas en el grid

- En `Album`, `Genre` y `Publisher` se usa `ttk.Combobox` con valores de catálogo.
- En el resto de campos editables se usa `Entry`.
- Navegación durante edición:
  - `Enter`: guarda y baja a la siguiente fila (misma columna).
  - `Shift+Enter`: guarda y sube a la fila anterior.
  - `Tab`: guarda y avanza a la siguiente celda editable.
  - `Shift+Tab`: guarda y vuelve a la celda editable anterior.
- En combos de catálogo:
  - búsqueda incremental al teclear,
  - ciclo de coincidencias con `Up/Down`,
  - `Delete`, `KP_Delete` o `BackSpace`: limpia toda la celda y guarda.

## 4) Flujo del botón Procesar (Discogs)

Método principal: `App.process_discogs_data()`.

1. Determina el alcance:
   - si hay selección, procesa solo filas seleccionadas,
   - si no, procesa todas.
2. Normaliza nombre (`format_filename_pattern`) y renombra archivo en disco si aplica.
3. Extrae `Artist`, `Title` y `MixArtist` desde el nombre y los guarda en tags.
4. Si la fila ya tiene carátula (`Cover = Sí`), omite búsqueda Discogs.
5. Construye query y busca en `https://api.discogs.com/database/search` con filtro `format=Vinyl&type=release`.
6. Si hay año, lo guarda (`Year`).
7. Si hay URL de carátula:
   - descarga bytes,
   - normaliza imagen a JPEG,
   - incrusta portada,
   - verifica post-guardado leyendo de nuevo el archivo,
   - marca `Cover = Sí` y refresca preview.
8. Si no hay portada o falla, marca `Cover = No` y deja log explícito.

## 5) Menú contextual de carátula

Sobre la preview de carátula (panel izquierdo):

- Clic derecho (`<Button-3>`, en macOS `<Button-2>`) abre menú contextual.
- **Pegar imagen desde el portapapeles**:
  - usa `PIL.ImageGrab.grabclipboard()`,
  - convierte a JPEG,
  - incrusta en archivo seleccionado,
  - actualiza preview y columna `Cover`.
- **Eliminar carátula**:
  - pide confirmación,
  - borra tags de portada del archivo,
  - limpia preview,
  - actualiza `Cover = No`.

## 6) Gestión de catálogos (Género/Álbum/Etiqueta)

- Catálogos persistidos en `%APPDATA%\Sonometa\catalogos.json`.
- Operaciones desde menú **Gestionar**:
  - añadir valor,
  - modificar valor (con soporte de fusión si ya existe),
  - eliminar valor (vacía el campo en archivos afectados).
- Normalización automática de texto: primera letra en mayúscula y resto en minúscula.

## 7) Configuración del token Discogs

- Ruta de settings: `%APPDATA%\Sonometa\settings.json`.
- Clave guardada: `discogs_token`.
- Carga con `utf-8-sig` para tolerar BOM.
- Fallback: variable de entorno `DISCOGS_TOKEN`.
- Menú: **Archivo -> Configuración (Token Discogs)**.

## 8) Formatos soportados

### Archivos detectados al escanear
- `.mp3`, `.flac`, `.m4a`, `.aac`, `.wav`, `.ogg`, `.wma`, `.aiff`

### Escritura de carátula (soporte fiable)
- `mp3` / `wav`: ID3 `APIC`
- `flac`: `Picture`
- `m4a` / `aac` / `mp4`: `covr` (`MP4Cover`)

## 9) Mapeo de tags

### MP3/WAV (ID3)
- `Title -> TIT2`
- `Artist -> TPE1`
- `MixArtist -> TPE4`
- `Album -> TALB`
- `Genre -> TCON`
- `Publisher -> TPUB`
- `Year -> TDRC`

### Otros formatos (easy tags)
- `Title -> title`
- `Artist -> artist`
- `MixArtist -> mixartist`
- `Album -> album`
- `Genre -> genre`
- `Publisher -> organization`
- `Year -> date`

## 10) Logging

- Logger: `Sonometa`.
- Salida dual: consola y GUI.
- Historial en memoria: `deque(maxlen=5000)`.
- Ventana de logs: **Ayuda -> Ver logs**.

## 11) Instalación y ejecución

### Requisitos
- Python 3.10+
- Windows (plataforma objetivo)

### Instalar dependencias

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Ejecutar

```powershell
python gui.py
```

## 12) Build de ejecutable

```powershell
pyinstaller Sonometa.spec
```

Alternativa:

```powershell
pyinstaller gui.spec
```

Distribuye siempre la carpeta completa generada en `dist/`.

## 13) Estructura del proyecto

- `gui.py`: aplicación principal.
- `icon_generator.py`: utilidad para iconos.
- `Sonometa.spec`, `gui.spec`: build con PyInstaller.
- `docs/FUNCIONALIDADES_DETALLADAS.md`: documentación funcional extendida.

## 14) Limitaciones actuales

- El procesamiento se ejecuta en el hilo de UI.
- Discogs usa el primer resultado sin selector manual.
- Búsqueda Discogs filtrada a vinilo (`format=Vinyl`).
- No hay suite de tests automatizados en el repositorio.

## 15) Verificación rápida de sintaxis

```powershell
python -m py_compile gui.py
python -m py_compile icon_generator.py
```


