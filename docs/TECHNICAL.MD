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
- `gui.py` usa `assets/logo_relleno.ico` para `iconbitmap` (ventana y dialogos). No se escribe nada junto al ejecutable: en `Program Files` no hay permisos de escritura.
- Algunos modulos acceden rutas relativas directas (`assets/...`), por lo que en build es obligatorio incluir assets en bundle.

## 5. Build del escritorio e instalador (Windows)

El empaquetado tiene dos fases: PyInstaller genera la app en `dist\Sonometa` (modo onedir) e Inno Setup la convierte en un instalador.

### 5.1 Requisitos

- Python con las dependencias de `docs/requirements.txt` (incluye `pyinstaller`).
- Inno Setup 7: `C:\Users\cpetreccas\AppData\Local\Programs\Inno Setup 7\ISCC.exe`.
- `bin\ffmpeg.exe` y `bin\ffprobe.exe` en el proyecto (se empaquetan; los usan el analisis de calidad y las previews).

Ficheros de configuracion:
- `Sonometa.spec`: build de PyInstaller. Incluye `assets`, `scripts` y `bin`.
- `installer/installer_Script.iss`: script de Inno Setup.

### 5.2 Paso a paso

Todos los comandos se ejecutan en PowerShell desde la raiz del proyecto.

**0. Commit de los cambios.** Recomendado, para que cada instalador corresponda a un commit.

**1. Subir la version** (solo si cambia; para recompilar la misma version, saltar este paso) en los cuatro sitios donde aparece:
- `src/gui.py`: titulo de la ventana (`"Sonometa v2.0 - Audio Tag Suite"`).
- `src/header_panel.py`: etiqueta `"v2.0"` de la cabecera.
- `installer/installer_Script.iss`: `#define MyAppVersion` y `OutputBaseFilename=Installer_Sonometa_vX.Y`.

No cambiar nunca el `AppId` del `.iss`: es lo que permite que el instalador actualice la version instalada en vez de crear una segunda.

**2. Cerrar Sonometa y empaquetar:**

```powershell
python -m PyInstaller --noconfirm --clean Sonometa.spec
```

Genera `dist\Sonometa\Sonometa.exe` y `dist\Sonometa\_internal`.

**3. Probar el ejecutable** antes de crear el instalador:

```powershell
.\dist\Sonometa\Sonometa.exe
```

Comprobar:
- Carga de una carpeta y caratulas.
- "Evaluar calidad" funciona y no abre ventanas de consola (usa el ffmpeg de `bin`).
- Vistas Dashboard y Calidad.
- El registro muestra "Token de Discogs activo" y el login en la nube funciona (ver 5.3).
- Ventanas y dialogos con el logo de Sonometa.

**4. Generar el instalador:**

```powershell
& "C:\Users\cpetreccas\AppData\Local\Programs\Inno Setup 7\ISCC.exe" .\installer\installer_Script.iss
```

Deja `Installer_Sonometa_vX.Y.exe` en la raiz del proyecto. El instalador esta cifrado con la contrasena de `Password=` del `.iss`.

**5. Instalar y probar.** Actualiza la version instalada. Los datos de usuario (`%APPDATA%\Sonometa`) no se tocan. Si se subio `ANALYSIS_VERSION` en `audio_health_checker.py`, los analisis de calidad anteriores quedan pendientes y hay que relanzarlos con "Analizar pendientes".

### 5.3 Configuracion en el equipo destino (.env)

`src/app_env.py` carga el `.env` desde, por orden:
1. `%APPDATA%\Sonometa\.env` (app instalada y desarrollo).
2. La raiz del proyecto (solo en desarrollo).

Las variables definidas en el sistema tienen prioridad.

- Supabase funciona sin `.env`: `src/supabase_client.py` incluye la URL y la clave anon (publicas por diseno) como valores por defecto.
- Discogs necesita un token personal, que **no** va en el instalador. Cada usuario lo configura desde la app en *Preferencias > Discogs...*: pega su token (se genera en discogs.com > Ajustes > Desarrolladores), la app lo comprueba contra la API y lo guarda en `%APPDATA%\Sonometa\settings.json`. Si no hay token guardado, se usa `DISCOGS_TOKEN` del entorno o del `.env` (util en desarrollo).

### 5.4 Distribuir sin instalador

Copiar la carpeta `dist\Sonometa` completa (`Sonometa.exe` + `_internal`) funciona en cualquier Windows 10/11 de 64 bits sin instalar Python. El `.exe` solo no arranca. Configuracion y datos se preparan como en 5.3; para llevarse caches y catalogos, copiar tambien `%APPDATA%\Sonometa`.

### 5.5 Problemas conocidos

- **"Windows protegio su PC" (SmartScreen):** el ejecutable no esta firmado. Pulsar *Mas informacion > Ejecutar de todas formas*. Si llega en un ZIP descargado: *Propiedades > Desbloquear* antes de descomprimir. Solo se elimina firmando con un certificado de firma de codigo.
- **Defender lo pone en cuarentena:** falso positivo conocido de PyInstaller; se puede enviar a Microsoft Security Intelligence para revision.
- **Ventanas de consola al analizar:** resuelto con `src/subprocess_no_window.py`, que debe seguir siendo el primer import de `gui.py`.
- **Analisis de calidad en paralelo:** el lote usa procesos (`ProcessPoolExecutor`, hasta 3). En el `.exe` esos procesos arrancan el mismo ejecutable; `multiprocessing.freeze_support()` al inicio del bloque `__main__` de `gui.py` es imprescindible o cada proceso abriria otra ventana de la app.
- **Archivos antiguos en `_internal` al actualizar:** el instalador no borra lo que ya no existe en la nueva version. Si da problemas, anadir al `.iss`:

```
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
```

## 6. Despliegue de la PWA (Netlify)

La PWA (`web/`) es estatica y se sirve desde Netlify (`https://sunny-mermaid-d3544a.netlify.app`). La unica parte de servidor es la funcion `netlify/functions/share.mjs`, que genera la pagina publica `/t/<token>` con las etiquetas Open Graph de las pistas compartidas. `netlify.toml` indica que se publica `web` y donde estan las funciones.

**No desplegar arrastrando un zip de `web/`:** ese metodo no publica funciones y los enlaces compartidos darian 404.

### 6.1 Requisitos (una sola vez)

- Node.js (se usa `npx`, no hace falta instalar nada mas).
- Supabase: haber ejecutado `supabase/shared_tracks.sql` en el SQL Editor (tabla `shared_tracks` y funciones `create_track_share` / `get_shared_track`).
- Iniciar sesion y enlazar la carpeta con el sitio:

```powershell
npx netlify-cli login
```

```powershell
npx netlify-cli link
```

En `link`, elegir *Search by full or partial project name* y buscar `sunny-mermaid`. (La opcion *Use current git remote origin* no sirve mientras el sitio no este conectado a GitHub.) Crea la carpeta `.netlify/`, ya ignorada en git.

### 6.2 Paso a paso

**1. Si cambian `index.html`, CSS o JS:** subir la version de `CACHE_NAME` en `web/sw.js` (p. ej. `sonometa-v2.2` -> `sonometa-v2.3`) para que los moviles descarguen los archivos nuevos.

**2. Desplegar a produccion:**

```powershell
npx netlify-cli deploy --prod --no-build
```

`--no-build` evita el paso de build de Netlify, que no hace falta (no hay compilacion) y que falla en algunas redes al consultar las extensiones del sitio. En el resumen debe aparecer `1 functions`.

**3. Comprobar:**
- La PWA carga e inicia sesion.
- Un enlace compartido (`/t/<token>`) muestra la tarjeta. Un token inexistente muestra "Enlace no disponible".
- WhatsApp guarda la vista previa de cada URL: para probar cambios, anadir `?v=N` al enlace o compartir otra pista.

### 6.3 Alternativa: despliegue automatico desde GitHub

En Netlify, *Site configuration > Build & deploy > Link repository* y elegir `cpetreccas/Sonometa`. A partir de ahi cada `git push` a `main` despliega solo (Netlify lee `netlify.toml`). Requiere que `netlify/`, `netlify.toml` y `web/` esten en el repositorio.

## 7. Flujo de datos (resumen operativo)

1. Usuario selecciona carpeta.
2. `AudioManager.scan_audio_files` extrae metadata por archivo.
3. `GridPanel` inserta filas; `DetailPanel` refleja seleccion.
4. Usuario edita metadata/manualmente.
5. `ProcessManager.process_discogs_data` enriquece y persiste.
6. `CatalogManager` mantiene catalogos/settings.
7. `HTMLExporter` puede generar informe de la coleccion.

## 8. Convenciones y guias de mantenimiento

- Nombres: `snake_case` (funciones/atributos), `CamelCase` (clases).
- Logging contextual (`[PROCESS]`, `[DISCOGS]`, `[GRID]`, etc.).
- Evitar mezclar logica de negocio en componentes visuales.
- Priorizar utilidades compartidas para columnas/mapeos de fila.
- En cambios de layout de filtros, preservar `trace_add`, bindings y foco inicial.

## 9. Rutas de persistencia local

- Catalogos: `%APPDATA%\Sonometa\catalogos.json`
- Settings: `%APPDATA%\Sonometa\settings.json`
- Cache (metadatos y analisis de calidad): `%APPDATA%\Sonometa\cache.db`
- Configuracion y tokens: `%APPDATA%\Sonometa\.env` (ver 5.3)

Esto desacopla datos de usuario del codigo fuente y facilita despliegues/actualizaciones.

