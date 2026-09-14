# AGENTS.MD

Guia compacta para asistentes IA que trabajen en Sonometa.

## 1) Contexto rapido
- Tipo de app: escritorio (desktop-first) con sincronizacion cloud activa hacia Supabase, basada en `CustomTkinter` + `ttk.Treeview`.
- Dominio: catalogacion y automatizacion de metadatos de audio.
- Entrada principal: `src/gui.py` (`App`).
- Flujo base: escaneo de archivos -> edicion en grilla -> procesamiento Discogs -> persistencia en tags.

## 2) Stack y dependencias
- Python 3.x
- UI: `customtkinter`, `tkinter`, `ttk`
- Audio tags: `mutagen`
- Imagenes: `Pillow`
- API externa: `requests`/`urllib` hacia Discogs (implementado en `src/discogs_client.py`)
- Cloud DB/Auth/Storage: Supabase (`src/supabase_client.py`)
- Deploy web: flujo legacy desactivado en desktop; `src/netlify_deployer.py` se conserva solo por compatibilidad historica.
- Previews multimedia cloud: `src/preview_generator.py` (`pydub` opcional para audio snippet)
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
- `src/html_exporter.py`: exportador legacy HTML/ZIP para WebApp; desactivado en el flujo principal de desktop durante Fase 2.
- `src/supabase_client.py`: cliente Supabase (auth, storage y upsert masivo de tracks).
- `src/cloud_sync_worker.py`: hilo de sincronizacion en background (local -> Supabase).
- `src/preview_generator.py`: extraccion/normalizacion de portada y snippet de audio para web.
- `src/netlify_deployer.py`: wrapper legacy de deploy HTTP a Netlify; no forma parte del flujo operativo actual.

## 4) Convenciones de codigo observables
- Clases: `CamelCase`; funciones/variables: `snake_case`.
- Metodos internos: prefijo `_`.
- Logger unificado: `logging.getLogger("Sonometa")`.
- Separacion de responsabilidades: `*Manager` (servicios) + `*Panel` (UI).
- Persistencia mixta: JSON + tags embebidos + cache SQLite local.

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
- Cache SQLite: `%APPDATA%/Sonometa/cache.db` (gestion en `src/cache_manager.py`)
- Tablas de cache:
  - `track_cache`: metadatos por archivo (path, mtime, size, tags serializados, `synced`, `updated_at`, `remote_id`)
  - `discogs_cache`: respuestas de Discogs con timestamp para expiracion
- Concurrencia/rendimiento: `CacheManager` usa lock interno + PRAGMA `journal_mode=WAL`.
- Limpieza: soporte de expiracion para cache Discogs y borrado completo de caches.
- Token Discogs: variable de entorno `DISCOGS_TOKEN` (y/o settings).
- Supabase: `SUPABASE_URL` + `SUPABASE_KEY` (si no estan, revisar fallback definido en codigo).
- Netlify: `NETLIFY_SITE_ID` + `NETLIFY_AUTH_TOKEN` solo aplican al flujo legacy y no deben reintroducirse en UI principal sin decision explicita de arquitectura.

### 7.1) SQLite en exportacion web
- `src/html_exporter.py` define `SQLiteManager` para una base de exportacion web legacy.
- Crea tabla `tracks` e indices para filtros/orden en la vista HTML si el flujo legacy se reactiva manualmente.
- Es un uso separado del `cache.db` principal (no compartir rutas por defecto).
- Regla de Fase 2: no conectar nuevas features desktop a este exportador; la PWA/WebApp consume Supabase directo.

### 7.2) Reglas para cambios en SQLite (agentes IA)
- No crear accesos SQLite ad-hoc desde UI: reutilizar `CacheManager` para cache principal.
- Mantener invalidacion por archivo (`mtime` + `file_size`) al tocar `track_cache`.
- Si agregas columnas/tablas, asegurar `CREATE TABLE IF NOT EXISTS` y compatibilidad con instalaciones existentes.
- Evitar bloqueos largos: operaciones de red o parseo pesado fuera de secciones criticas protegidas por lock.
- Si cambias politica de expiracion Discogs, actualizar tambien rutinas de limpieza en `CacheManager`.
- No mezclar la BD de exportacion (`SQLiteManager`) con `%APPDATA%/Sonometa/cache.db`.
- Si mutas tags locales con `mutagen`/`AudioManager`, el registro debe quedar `synced = 0` hasta confirmacion remota.
- Para marcar sincronizacion completada, preferir los metodos de `CacheManager` (`get_unsynced_tracks`, `mark_tracks_as_synced`, compatibilidad `mark_as_synced`).

### 7.3) Sincronizacion cloud (Supabase)
- Flujo actual: `App.on_user_logged_in()` -> `CloudSyncWorker.start()` -> lote de pendientes -> `upsert_tracks_batch()`.
- Fuente local: registros pendientes en cache SQLite con `synced = 0` (metodos de `CacheManager` para unsynced/synced).
- Enriquecimiento cloud: `MediaProcessor` sube portada comprimida; cualquier trabajo pesado debe quedar fuera del hilo UI.
- Post-condicion: solo si el upsert remoto confirma exito/OK, marcar filas locales como sincronizadas.
- Regla operativa: mantener el worker en segundo plano y evitar trabajo pesado en hilo UI.

### 7.4) Estado de migracion web/cloud
- Fase 2 activa: la WebApp/PWA se despliega por pipeline independiente y consume Supabase Cloud directamente.
- La opcion de menu `Exportar Coleccion...` en desktop es solo un punto legacy desactivado; debe mostrar aviso y no disparar deploy real.
- `HTMLExporter.export_grid_to_html()` y `NetlifyDeployer.deploy_zip()` no son parte del flujo soportado por defecto.
- Si se reactiva temporalmente el flujo legacy para pruebas, debe quedar detras de feature flag y fuera del camino principal de usuario.

## 8) Formatos de audio (observado en codigo)
- Escaneo: `.mp3`, `.flac`, `.m4a`, `.aac`, `.wav`, `.ogg`, `.wma`, `.aiff`.
- Escritura especializada: MP3/WAV (ID3), FLAC, M4A/MP4; fallback generico en otros formatos via mutagen.

## 9) Checklist para cambios seguros
- Confirmar que no se rompen atajos globales en `App._bind_shortcuts()`.
- Validar edicion inline y navegacion de celda en `GridPanel` (Tab/Enter/Escape).
- Validar filtros simples (`SearchManager`) y avanzados (`AdvancedFilterPanel`).
- Probar flujo de procesamiento (`ProcessManager`) con y sin revision manual de portada.
- Si tocas assets/rutas, probar en entorno normal y en build empaquetado.

