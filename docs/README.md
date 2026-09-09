# Sonometa

Suite de escritorio para gestionar, limpiar y enriquecer metadatos de audio de forma masiva e individual.

Sonometa esta orientada a flujos reales de catalogacion musical (DJ, productores, curadores de librerias), combinando una grilla editable, procesamiento por lotes y apoyo de Discogs para completar informacion y caratulas.

## Caracteristicas principales

- Escaneo recursivo de carpetas con deteccion de archivos de audio compatibles.
- Extraccion y edicion de metadatos en grilla (`Treeview`) y panel de detalle.
- Integracion con **Discogs API** para busqueda de releases, ano y caratulas.
- Revision manual de caratulas cuando hay multiples resultados.
- Gestion de catalogos locales para `Album`, `Genre`, `Publisher` y `Comment`.
- Reglas jerarquicas de catalogo (album -> generos permitidos, genero -> etiquetas permitidas).
- Historial de cambios y operaciones con soporte **Undo/Redo**.
- Exportacion a **HTML** con vista de coleccion + dashboard visual (Chart.js).
- Reproductor de audio embebido para previsualizacion.

## Formatos de audio soportados

Segun el codigo actual, el escaneo incluye:

- `.mp3`
- `.flac`
- `.m4a`
- `.aac`
- `.wav`
- `.ogg`
- `.wma`
- `.aiff`

La escritura de tags tiene rutas especializadas para MP3/WAV, FLAC y M4A/MP4, con fallback generico en otros formatos cuando mutagen lo permite.

## Arquitectura funcional (resumen)

- `src/gui.py`: orquestador principal de la app (`App`).
- `src/grid_panel.py`: tabla principal, edicion inline, ordenamiento y filtros avanzados.
- `src/detail_panel.py`: editor detallado y acciones sobre la seleccion.
- `src/process_manager.py`: pipeline multihilo de normalizacion + Discogs + escritura.
- `src/audio_manager.py`: lectura/escritura de metadatos y caratulas.
- `src/discogs_client.py`: cliente Discogs.
- `src/catalog_manager.py`: persistencia local de catalogos y configuracion.
- `src/dialogs.py`: sistema de modales y dialogos (`DialogManager`).
- `src/html_exporter.py`: generacion de informe HTML.

## Requisitos

Dependencias declaradas en `docs/requirements.txt`:

- `customtkinter>=5.2.0`
- `Pillow>=10.0.0`
- `mutagen>=1.47.0`
- `requests>=2.31.0`
- `pyinstaller>=6.0.0`
- `pygame`

## Instalacion

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\docs\requirements.txt
```

## Ejecucion en desarrollo

```powershell
python .\src\gui.py
```

## Configuracion de Discogs

Sonometa puede leer token desde la variable de entorno `DISCOGS_TOKEN`.

```powershell
$env:DISCOGS_TOKEN="tu_token_discogs"
python .\src\gui.py
```

Ademas, la app persiste configuracion de usuario en `%APPDATA%\Sonometa\settings.json`.

## Gestion de catalogos

- Persistencia local en `%APPDATA%\Sonometa\catalogos.json`.
- Normalizacion de texto para evitar duplicados por capitalizacion.
- Aplicacion de cambios de catalogo directamente sobre filas y tags fisicos.

## Exportacion

Sonometa puede exportar la grilla a un informe HTML con:

- Tabla filtrable de la coleccion.
- Dashboard con metricas y graficos por album, genero, etiqueta y ano.
- Caratulas embebidas como miniaturas comprimidas.

## Atajos utiles (referencia)

- `Ctrl+O`: seleccionar carpeta
- `F5`: refrescar lista
- `Ctrl+A`: seleccionar todo
- `Ctrl+F`: foco en busqueda
- `Ctrl+Shift+F`: alternar filtros avanzados
- `Ctrl+R`: reemplazo masivo en filename
- `Ctrl+Z` / `Ctrl+Y`: undo / redo
- `Delete`: limpiar metadatos seleccionados

## Build a ejecutable (Windows)

No se detecta un `.spec` versionado en el repo, por lo que el build suele hacerse con comando directo. Ejemplo base:

```powershell
pyinstaller --noconfirm --windowed --name Sonometa --icon .\assets\logo_relleno.ico --add-data ".\assets;assets" --add-data ".\scripts;scripts" .\src\gui.py
```

> Nota: en Windows, `--add-data` usa separador `;`.

## Benchmark rapido (filtros)

Se incluye un harness liviano para estimar el costo del motor de filtros con 4,000 filas sinteticas:

```powershell
python .\scripts\benchmark_filter_engine.py --rows 4000 --iterations 120
```

Pruebas opcionales:

```powershell
python .\scripts\benchmark_filter_engine.py --rows 4000 --iterations 300 --seed 42
python .\scripts\benchmark_filter_engine.py --rows 8000 --iterations 120 --seed 42
```

## Estado del proyecto

El proyecto esta organizado por paneles de UI y managers de dominio, con foco en trazabilidad (logs), productividad de edicion y automatizacion de metadatos. Para contexto rapido de IA, revisar `AGENTS.MD`.

