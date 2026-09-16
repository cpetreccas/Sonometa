# TECHNICAL.MD

Documento tecnico para desarrolladores de Sonometa.

## 1. Vision tecnica

Sonometa es una aplicacion de escritorio Python orientada a metadatos de audio. No usa backend HTTP propio ni base de datos; opera sobre archivos locales y persiste configuraciones/catalogos en JSON.

- UI: `CustomTkinter` + `tkinter/ttk`
- Dominio: lectura/escritura de tags con `mutagen`
- Integracion externa: Discogs
- Observabilidad: logging estructurado hacia consola y UI

## 2. Estructura modular y clases principales

### `src/gui.py` - `App(ctk.CTk)`

Orquestador principal. Inicializa estado global, managers y paneles de UI.

Responsabilidades clave:
- Configuracion de ventana y estilo.
- Inicializacion de servicios (`LogManager`, `UndoManager`, `AudioManager`, `CatalogManager`, `DiscogsClient`, `ProcessManager`).
- Composicion de UI (`ToolPanel`, `HeaderPanel`, `GridPanel`, `DetailPanel`).
- Registro de atajos globales y ciclo de vida (`on_close`).

Patron: coordinador liviano + delegacion en managers/paneles especializados.

### `src/grid_panel.py` - `GridPanel`

Componente de la grilla principal (`ttk.Treeview`).

Incluye:
- Definicion de columnas, estilos y headers.
- Edicion inline con `Entry`/`Combobox` y navegacion tipo hoja de calculo.
- Seleccion multiple, ordenamiento por columna, visibilidad de columnas.
- Estado y aplicacion de filtros avanzados (`apply_advanced_filters`).

Nota de layout importante:
- El panel de filtros avanzados debe mostrarse sobre la grilla con `pack(before=self.tree_container)` para no romper eventos/bindings de filtros.

### `src/advanced_filter_panel.py` - `AdvancedFilterPanel`

Panel desplegable de filtros avanzados.

Incluye:
- Entradas de texto y combos de catalogo.
- Toggles de estado (`sin ano`, `sin caratula`, `sin comentarios`).
- Emision de criterios de filtro hacia callback del `GridPanel`.

Contrato principal:
- No debe recrear ni desempaquetar el contenedor de la tabla para mostrarse/ocultarse.

### `src/detail_panel.py` - `DetailPanel`

Panel lateral para edicion detallada de la fila activa.

Incluye:
- Bind de datos de seleccion actual.
- Edicion de campos y refresco de combos segun catalogos.
- Integracion con reproductor embebido y acciones de proceso.

### `src/process_manager.py` - `ProcessManager`

Pipeline de negocio para procesamiento por lotes.

Flujo simplificado:
1. Toma filas objetivo (seleccion o todo).
2. Ejecuta pipeline en hilo secundario para no bloquear UI.
3. Normaliza/parsea filename y tags base.
4. Consulta Discogs (ano/caratulas).
5. Aplica cambios en disco via `AudioManager`.
6. Actualiza UI + progreso + logs.

Puntos tecnicos:
- Usa `ThreadPoolExecutor` para paralelizar archivos.
- Sincroniza secciones criticas con `threading.Lock`.
- Gestiona revision manual de caratulas con `DialogManager` cuando hay multiples opciones.
- Consume snapshots tipados (`ProcessingSnapshot`) para desacoplar workers del estado UI.

### `src/models.py` - Modelos tipados

Modulo de contratos internos livianos para reducir acoplamiento entre componentes:

- `ProcessingSnapshot`: fotografia inmutable de fila para procesamiento en background.
- `AdvancedFilterCriteria`: contrato de criterios de filtro entre `AdvancedFilterPanel` y `GridPanel`.

### `src/tree_row_utils.py` - Utilidades de filas

Funciones reutilizables para acceso por columna y composicion de filas:

- `build_column_index`
- `get_row_value` / `set_row_value`
- `map_row_values`
- `build_row_values`

Objetivo: evitar logica duplicada de mapeo entre `GridPanel` y `ProcessManager`.

### `src/app_state_adapter.py` - Adaptador de estado App

Puente para que los managers no dependan directamente de toda la superficie de `App`.

- Expone helpers de acceso a `Treeview` (filas, valores, indices de columna).
- Encapsula acceso a `file_paths_map` y escritura de tags.
- Centraliza notificaciones UI (`refresh_catalog_comboboxes`, `on_row_select`).

`CatalogManager` ya utiliza este adaptador para reducir acoplamiento directo.

### `src/audio_manager.py` - `AudioManager`

Capa de I/O de metadatos desacoplada de UI.

Responsabilidades:
- Extraccion de metadata y duracion.
- Escritura de tags por formato (MP3/WAV ID3, FLAC, MP4/M4A).
- Lectura/incrustacion/eliminacion de caratulas.
- Limpieza de metadata manteniendo integridad del archivo.

Soporte observado en escaneo: `.mp3`, `.flac`, `.m4a`, `.aac`, `.wav`, `.ogg`, `.wma`, `.aiff`.

### `src/discogs_client.py` - `DiscogsClient`

Cliente encapsulado para Discogs.

- Genera headers con token.
- Busca releases (`search_release`).
- Descarga bytes de imagen.
- Obtiene lista de caratulas (`get_release_images`).

### `src/catalog_manager.py` - `CatalogManager`

Gestion de catalogos y settings de usuario.

- Campos de catalogo: `Genre`, `Album`, `Publisher`, `Comment`.
- Normalizacion de texto para consistencia.
- Relaciones jerarquicas:
  - album -> generos permitidos
  - genero -> etiquetas permitidas
- Persistencia JSON en `%APPDATA%\Sonometa\`.

### `src/search_manager.py` - `SearchManager`

Filtrado textual rapido sobre la grilla.

- Usa `StringVar.trace_add` para aplicar filtro en tiempo real.
- Normaliza acentos para mejorar matching.
- Desasocia/reasocia filas (`detach`/`reattach`) segun query.

### `src/log_handler.py` - `LogManager`

Bridge entre `logging` y componentes UI de logs.

- Logger unificado `Sonometa`.
- Formato estructurado para cambios (`format_tree_log`).
- Soporte de historial y render con etiquetas visuales.

### `src/dialogs.py` - `DialogManager`

Sistema centralizado de modales/popups.

## 3. Gestion de dialogos con `DialogManager`

`DialogManager` concentra comportamiento transversal de ventanas secundarias:

- Creacion de popups modales/no modales con estilo consistente.
- Centrados relativos (`center_popup_on_parent`) o a pantalla.
- Barra de titulo oscura en Windows (`apply_dark_title_bar`).
- Control de foco y `grab_set` para modales.
- Catalogo de dialogs de negocio:
  - confirmaciones
  - logs
  - ajustes
  - about/atajos
  - gestor unificado de catalogos
  - seleccion de caratulas
  - reemplazo masivo de texto en filename

Buenas practicas al extenderlo:
- Mantener APIs estaticas con firma `show_xxx(app, ...)`.
- Centralizar estilo/foco en `apply_popup_style`.
- En modales, soportar `Esc` para cerrar/cancelar y devolver foco al host.

## 4. Resolucion de rutas de assets

### Ubicacion fisica
- Recursos versionados en `assets/` (logo, iconos, portada fallback).
- Script de frontend para export HTML: `scripts/chart.min.js`.

### Resolucion en runtime
`UiUtils.get_resource_path(relative_path)`:
- Si existe `sys._MEIPASS`, usa carpeta temporal de bundle (PyInstaller).
- Si no, resuelve sobre el directorio de trabajo actual.

### Patrones de uso
- `UiUtils.load_app_icons(app)` carga iconos principales y devuelve referencias PIL/CTkImage.
- `gui.py` puede generar `app_icon_temp.ico` dinamicamente desde PNG para `iconbitmap`.
- Algunos modulos acceden rutas relativas directas (`assets/...`), por lo que en build es obligatorio incluir assets en bundle.

## 5. Build a ejecutable con PyInstaller

No se observa archivo `.spec` versionado en la raiz. El flujo habitual es CLI directa sobre `src/gui.py`.

### Comando base (Windows, modo windowed)

```powershell
pyinstaller --noconfirm --windowed --name Sonometa --icon .\assets\logo_relleno.ico --paths . --add-data ".\assets;assets" --add-data ".\scripts;scripts" --add-data ".\bin;bin" .\src\gui.py
```

### Puntos a validar en build
- `--add-data` en Windows usa `;` como separador.
- Incluir `assets` y `scripts` para:
  - logos/iconos
  - portada fallback
  - `chart.min.js` en export HTML
- Probar `DialogManager` y carga de imagenes en entorno empaquetado.
- Validar que `UiUtils.get_resource_path` encuentre recursos dentro de `_MEIPASS`.

### Onefile vs onedir
- `--onefile`: distribucion simple, mayor tiempo de arranque.
- `--onedir` (por defecto): mas facil de depurar recursos y rutas durante QA.

## 6. Flujo de datos (resumen operativo)

1. Usuario selecciona carpeta.
2. `AudioManager.scan_audio_files` extrae metadata por archivo.
3. `GridPanel` inserta filas; `DetailPanel` refleja seleccion.
4. Usuario edita metadata/manualmente.
5. `ProcessManager.process_discogs_data` enriquece y persiste.
6. `CatalogManager` mantiene catalogos/settings.
7. `HTMLExporter` puede generar informe de la coleccion.

## 7. Convenciones y guias de mantenimiento

- Nombres: `snake_case` (funciones/atributos), `CamelCase` (clases).
- Logging contextual (`[PROCESS]`, `[DISCOGS]`, `[GRID]`, etc.).
- Evitar mezclar logica de negocio en componentes visuales.
- Priorizar utilidades compartidas para columnas/mapeos de fila.
- En cambios de layout de filtros, preservar `trace_add`, bindings y foco inicial.

## 8. Rutas de persistencia local

- Catalogos: `%APPDATA%\Sonometa\catalogos.json`
- Settings: `%APPDATA%\Sonometa\settings.json`

Esto desacopla datos de usuario del codigo fuente y facilita despliegues/actualizaciones.

