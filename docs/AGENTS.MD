# AGENTS.MD

Guia compacta para asistentes IA que trabajen en Sonometa.

## 1) Contexto rapido
- Tipo de app: escritorio (sin backend web), basada en `CustomTkinter` + `ttk.Treeview`.
- Dominio: catalogacion y automatizacion de metadatos de audio.
- Entrada principal: `src/gui.py` (`App`).
- Flujo base: escaneo de archivos -> edicion en grilla -> procesamiento Discogs -> persistencia en tags.

## 2) Stack y dependencias
- Python 3.x
- UI: `customtkinter`, `tkinter`, `ttk`
- Audio tags: `mutagen`
- Imagenes: `Pillow`
- API externa: `requests`/`urllib` hacia Discogs (implementado en `src/discogs_client.py`)
- Reproductor embebido: `pygame`
- Build: `pyinstaller`

Dependencias declaradas: `docs/requirements.txt`.

## 3) Arquitectura (mapa mental)
- `src/gui.py`: orquestador principal; crea servicios y paneles, atajos globales, estado app.
- `src/grid_panel.py`: grilla principal, edicion inline, ordenamiento, seleccion, filtros avanzados.
- `src/advanced_filter_panel.py`: UI + estado de filtros avanzados, callback a grilla.
- `src/detail_panel.py`: edicion detallada de fila, portada y acciones por seleccion.
- `src/process_manager.py`: pipeline multihilo de procesamiento y enriquecimiento.
- `src/audio_manager.py`: lectura/escritura de tags y portada.
- `src/discogs_client.py`: cliente Discogs (busqueda y descarga de imagenes).
- `src/catalog_manager.py`: catalogos (Album/Genre/Publisher/Comment) y settings en JSON.
- `src/dialogs.py`: modales y popups centralizados (`DialogManager`).
- `src/search_manager.py`: barra de busqueda y filtrado textual de Treeview.
- `src/log_handler.py`: logging estructurado para consola + UI.
- `src/html_exporter.py`: exportacion a informe HTML con dashboard/tabla.

## 4) Convenciones de codigo observables
- Clases: `CamelCase`; funciones/variables: `snake_case`.
- Metodos internos: prefijo `_`.
- Logger unificado: `logging.getLogger("Sonometa")`.
- Separacion de responsabilidades: `*Manager` (servicios) + `*Panel` (UI).
- Sin base de datos: persistencia local en JSON + tags embebidos en archivos.

## 5) Reglas criticas de UI/layout (evitar regresiones)
- No recrear ni desempaquetar el contenedor de la tabla (`tree_container`) para reordenar paneles.
- Para mostrar paneles sobre la grilla, usar `pack(..., before=self.tree_container)`.
- Evitar romper callbacks de filtrado (`trace_add`, `command`) al tocar layout.
- Mantener la jerarquia de widgets; cambios en foco deben preservar experiencia de teclado.

## 6) Assets y rutas
- Carpeta de recursos: `assets/` en la raiz del proyecto.
- Resolver rutas con `UiUtils.get_resource_path()` cuando sea posible.
- En build PyInstaller, `sys._MEIPASS` se usa para ubicar recursos empaquetados.

## 7) Persistencia y configuracion
- Catalogos: `%APPDATA%/Sonometa/catalogos.json`
- Settings: `%APPDATA%/Sonometa/settings.json`
- Token Discogs: variable de entorno `DISCOGS_TOKEN` (y/o settings).

## 8) Formatos de audio (observado en codigo)
- Escaneo: `.mp3`, `.flac`, `.m4a`, `.aac`, `.wav`, `.ogg`, `.wma`, `.aiff`.
- Escritura especializada: MP3/WAV (ID3), FLAC, M4A/MP4; fallback generico en otros formatos via mutagen.

## 9) Checklist para cambios seguros
- Confirmar que no se rompen atajos globales en `App._bind_shortcuts()`.
- Validar edicion inline y navegacion de celda en `GridPanel` (Tab/Enter/Escape).
- Validar filtros simples (`SearchManager`) y avanzados (`AdvancedFilterPanel`).
- Probar flujo de procesamiento (`ProcessManager`) con y sin revision manual de portada.
- Si tocas assets/rutas, probar en entorno normal y en build empaquetado.

