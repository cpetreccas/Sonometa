# Webapp.MD

## 1) Vision General de la Webapp

La carpeta `web/` contiene una webapp frontend ligera tipo SPA/PWA para **Sonometa Cloud**. Su objetivo es autenticar al usuario contra Supabase y permitirle visualizar/supervisar su coleccion de tracks sincronizados mediante:

- Vista de autenticacion (login por email/password).
- Vista de dashboard (KPIs y graficas).
- Vista de tabla (coleccion paginada, filtros y reproductor de preview).
- Soporte PWA basico (manifest + service worker para cache de assets).

No hay backend propio en `web/`; la app consume Supabase directamente desde el cliente.

---

## 2) Stack Tecnologico y Dependencias (`/web`)

### Lenguajes y formato de codigo
- **HTML5** (`web/index.html`)
- **CSS3** (`web/css/styles.css`)
- **JavaScript ES6+ Modules** (`web/js/*.js`) - Arquitectura modular especializada

### Frameworks y librerias
- **Framework frontend**: ninguno (Vanilla JS con arquitectura modular).
- **Charts**: `Chart.js` via CDN (`index.html`).
- **Backend client**: `@supabase/supabase-js` via CDN global (`window.supabase` en `index.html` + `js/supabase.js`).

### Estado, routing y cliente API
- **Estado global centralizado**: objeto mutable `context` en `js/app_context.js` (currentPage, allTracks, filteredTracks, sortState, columnVisibility, currentFilters).
- **Routing**: no hay router (ni React Router/Vue Router); navegacion manual por toggles de secciones del DOM.
- **Cliente HTTP/API**: Supabase JS client (`supabase.from(...).select(...)`, `supabase.auth...`).

### Arquitectura de módulos (POST-REFACTORIZACIÓN)
La aplicación está dividida en **6 módulos especializados** con responsabilidades claras:

1. **`app_context.js`** - Estado global
   - `context`: objeto mutable con estado global
   - `PAGE_SIZE`: constante de paginación (100)
   - `ALL_COLUMNS`: definición de columnas

2. **`data_loader.js`** - Carga de datos
   - `fetchAllTracks()`: paginación automática de Supabase (bloques de 1,000)

3. **`player.js`** - Reproductor de audio
   - `playTrack()`, `playNextTrack()`, `togglePlayPause()`, `updatePlayIcon()`, `toggleShuffle()`, `seekAudio()`, `changeVolume()`

4. **`collection_view.js`** - Vista de tabla y paginación
   - `sortByColumn()`, `sortCollection()`, `loadTableData()`, `updatePaginationUI()`, `toggleColumnPicker()`, `renderColumnPicker()`, `toggleVerDetalle()`, `changePage()`

5. **`filters.js`** - Lógica de filtrado
   - `populateSelectFilters()`, `handleFilterChange()`, `updateFilterSummaryBar()`, `toggleFilterFlag()`, `applyFilters()`, `applyFiltersAndClose()`, `resetAllFilters()`, `openFilterModal()`, `closeFilterModal()`

6. **`app.js`** - Orquestador principal (refactorizado de 778 a 178 líneas)
   - Inicialización PWA, autenticación, inyección de módulos
   - Exposición de funciones en `window` para compatibilidad HTML

### Build, lint, scripts y package manager
- No se detecta `package.json` dentro de `web/`.
- No se detectan lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) dentro de `web/`.
- No se detectan configuraciones de bundler (`vite.config.*`, `webpack.config.*`, etc.).
- No se detectan configuraciones de lint/format (`eslint`, `prettier`) dentro de `web/`.

**Conclusión:** `web/` funciona como frontend estático servido directamente por un host estático, con arquitectura modular ES6 nativa.

---

## 3) Estructura Interna de `/web`

```text
web/
├─ index.html             # Shell principal SPA/PWA (auth + app containers)
├─ manifest.json          # Metadatos PWA
├─ sw.js                  # Service Worker (cache de assets)
├─ css/
│  └─ styles.css          # Estilos globales y responsive
└─ js/
   ├─ app.js              # Orquestador principal (178 líneas)
   ├─ app_context.js      # Estado global centralizado (67 líneas) - NUEVO
   ├─ data_loader.js      # Carga de datos Supabase (35 líneas) - NUEVO
   ├─ player.js           # Lógica del reproductor de audio (174 líneas) - NUEVO
   ├─ collection_view.js  # Renderizado de tabla y paginación (254 líneas) - NUEVO
   ├─ filters.js          # Lógica de filtrado y búsqueda (268 líneas) - NUEVO
   ├─ auth.js             # Login/logout y chequeo de sesion Supabase
   ├─ dashboard.js        # KPIs y graficas Chart.js
   └─ supabase.js         # Inicializacion del cliente Supabase
```

### Responsabilidades por módulo

**Orquestación y Estado Global:**
- `app.js`: Entry point, inicialización PWA, autenticación, inyección de módulos, exposición de funciones en `window`
- `app_context.js`: Almacén centralizado de estado mutable (`context`, `ALL_COLUMNS`, `PAGE_SIZE`)

**Datos y Conectividad:**
- `data_loader.js`: Paginación automática desde Supabase (bloques de 1,000 registros)
- `supabase.js`: Configuración e inicialización del cliente Supabase

**UI y Presentación:**
- `player.js`: Reproducción de audio flotante, controles de volumen y seek
- `collection_view.js`: Renderizado de tabla, ordenación, paginación, selector de columnas
- `filters.js`: Lógica de filtrado, búsqueda, dropdowns selectores, aplicación de criterios
- `dashboard.js`: KPIs, gráficas Chart.js basadas en datos filtrados

**Autenticación:**
- `auth.js`: Sesiones Supabase, login/logout, verificación de estado autenticado

---

## 4) Arquitectura y Flujo de Datos

### Patrón general
- Arquitectura **modular por archivos JS con responsabilidades especializadas** (sin framework, sin DI formal).
- `app.js` actua como orquestador principal que inyecta todos los módulos.
- `app_context.js` contiene el estado global centralizado y mutable.
- Flujo UI basado en manipulación directa del DOM con datos reactivos desde `context`.
- **Sin ciclos de importación**: flujo unidireccional de dependencias.

### Matriz de dependencias
```
app_context.js (raíz - sin dependencias de otros módulos)
    ↓
    ├─ player.js (importa context)
    ├─ collection_view.js (importa context)
    └─ filters.js (importa context)
        └─ Consume: loadTableData, renderColumnPicker de collection_view.js

data_loader.js (importa supabase.js)

app.js (orquestador)
    ├─ Importa: auth.js, dashboard.js, app_context.js, data_loader.js
    ├─ Importa: collection_view.js, filters.js, player.js
    └─ Expone en window: todas las funciones públicas de los módulos
```

### Flujo principal de inicialización
1. Carga `index.html` → registra polyfills y módulos globales
2. Importa `app.js` (orquestador)
3. `DOMContentLoaded`: 
   - Registra Service Worker (PWA)
   - Importa módulos especializados
   - Ejecuta `checkSession()` via `auth.js`
4. Si hay sesión válida:
   - `showApp()` → `loadInitialCollection()`:
     - `fetchAllTracks()` pagina desde Supabase (bloques de 1,000)
     - Asigna resultado a `context.allTracks`
     - Inicializa `populateFilterDropdowns()` y `renderColumnPicker()`
     - Ejecuta `applyFilters()` para renderizar tabla inicial
5. Si no hay sesión: muestra formulario login

### Flujo de filtrado y actualización
1. Usuario cambia filtro / búsqueda
2. Evento dispara `handleFilterChange()` o `toggleFilterFlag()` (filters.js)
3. Se actualiza `context.currentFilters`
4. Se ejecuta `applyFilters()`:
   - Filtra `context.allTracks` → `context.filteredTracks`
   - Llama `populateSelectFilters()` (re-calcula opciones dinámicamente)
   - Llama `updateDashboard()` (actualiza KPIs si existen)
   - Resets `context.currentPage = 0`
   - Ejecuta `loadTableData()`:
     - Aplica ordenación via `sortCollection()`
     - Pagina resultados (PAGE_SIZE = 100 por defecto)
     - Renderiza tabla HTML
     - Actualiza `updatePaginationUI()`

### Integracion con Supabase
- `supabase.js`: punto único de inicialización del cliente
- `data_loader.js`: gestiona paginación exhaustiva (1,000 registros por request hasta obtener todos)
- `auth.js`: maneja `supabase.auth.signInWithPassword()`, `getSession()`, `signOut()`
- Filtros y búsqueda ocurren en **memoria local** (no hay nuevas queries a Supabase por cada filtro)
- Dashboard agrega datos sobre `context.filteredTracks` (sin queries SQL adicionales)

### Flujo de reproducción de audio
1. Usuario click en fila de tabla
2. Dispara `playTrack(track)` (player.js):
   - Actualiza `context.currentTrackIndex`
   - Muestra playerBar flotante
   - Carga `preview_audio_url` en elemento `<audio>`
   - Inicia reproducción automática
3. Audio emite `ontimeupdate`: actualiza progreso visual
4. Al alcanzar 20 segundos (límite): dispara `playNextTrack()`
   - Si shuffle: selecciona aleatorio desde `context.filteredTracks`
   - Si no: reproduce siguiente en orden

### Estado global (`context`)
Ubicado en `app_context.js`, centralizando toda la información mutable:
```javascript
context = {
  currentPage: 0,                           // Página actual (0-indexed)
  allTracks: [],                            // Todos los tracks sin filtrar
  filteredTracks: [],                       // Tracks tras aplicar filtros
  currentTrackIndex: -1,                    // Track siendo reproducido
  isShuffle: false,                         // Estado del shuffle
  sortState: { key: 'filename', direction: 'asc' },  // Ordenación activa
  columnVisibility: { ... },                // Visibilidad de columnas
  currentFilters: {                         // Filtros activos
    search: '', album: '', genre: '', 
    publisher: '', year: '',
    noCues: false, noCover: false, noRating: false
  }
}
```

---

## 5) Modelos de Datos y Tipos del Frontend

No hay TypeScript ni interfaces formales; los modelos son implícitos en JS.

### Entidad principal (`tracks`)
Campos inferidos usados por la UI:
- `id`: identificador único
- `filename`: nombre del archivo
- `artist`: intérprete
- `title`: título de la canción
- `mix_artist`: remix (mezclador)
- `album`: álbum
- `genre`: género musical
- `publisher`: etiqueta/sello discográfico
- `year`: año de lanzamiento
- `duration`: duración en segundos
- `cue_count`: número de cues
- `rating`: calificación (0-5)
- `cover_url`: URL de la carátula
- `cover_blob`: blob de carátula (local)
- `preview_audio_url`: URL del preview de audio

### Estado global (`context`)
Objeto mutable centralizado en `app_context.js`:

```javascript
{
  // Paginación
  currentPage: 0,                              // Página actual (0-indexed)
  
  // Tracks
  allTracks: [],                               // Array de todos los tracks (sin filtrar)
  filteredTracks: [],                          // Array de tracks tras aplicar filtros
  currentTrackIndex: -1,                       // Índice en filteredTracks siendo reproducido
  isShuffle: false,                            // Modo shuffle activado/desactivado
  
  // Ordenación
  sortState: {
    key: 'filename',                           // Columna por la que se ordena
    direction: 'asc'                           // 'asc' | 'desc'
  },
  
  // Visibilidad de columnas
  columnVisibility: {
    cover: true,
    artist: true,
    title: true,
    mix_artist: true,
    album: true,
    genre: true,
    publisher: true,
    year: true,
    cue_count: true,
    rating: true,
    filename: true
  },
  
  // Filtros activos
  currentFilters: {
    search: '',                                // Búsqueda por filename/title/artist
    album: '',                                 // Filtro por álbum (o '__EMPTY__' para sin valor)
    genre: '',                                 // Filtro por género
    publisher: '',                             // Filtro por etiqueta
    year: '',                                  // Filtro por año
    noCues: false,                             // Filtro: solo tracks sin cues
    noCover: false,                            // Filtro: solo tracks sin carátula
    noRating: false                            // Filtro: solo tracks sin rating
  }
}
```

### Definición de columnas (`ALL_COLUMNS`)
Array de configuración de columnas en `app_context.js`:

```javascript
[
  { key: 'cover', label: 'Carátula', detailOnly: false },
  { key: 'filename', label: 'Nombre de Archivo', detailOnly: false, normalOnly: true },
  { key: 'artist', label: 'Intérprete', detailOnly: true },
  { key: 'title', label: 'Título', detailOnly: true },
  { key: 'mix_artist', label: 'Remix', detailOnly: true },
  { key: 'album', label: 'Álbum', detailOnly: true },
  { key: 'genre', label: 'Género', detailOnly: true },
  { key: 'publisher', label: 'Etiqueta', detailOnly: true },
  { key: 'year', label: 'Año', detailOnly: true },
  { key: 'cue_count', label: 'Cues', detailOnly: true },
  { key: 'rating', label: 'Rating', detailOnly: true }
]
```
- `detailOnly`: columna solo visible en modo "Detalle"
- `normalOnly`: columna solo visible en modo "Normal"

### Constantes
```javascript
PAGE_SIZE = 100              // Registros por página en tabla
```

---

## 6) Rutas y Navegacion

No existe enrutamiento por URL; es una SPA de vistas por secciones:

- `#authContainer` -> pantalla de login.
- `#appContainer` -> app autenticada.
- Dentro de app:
  - `#dashboardView` (dashboards)
  - `#tableView` (coleccion)

Navegacion via funciones globales (`window.switchView(...)`) y botones `onclick`.

---

## 7) Comandos de Ejecucion e Integracion

> Directorio de trabajo: `web/`

Como no hay `package.json`, se puede servir como sitio estático.

### Servidor local de desarrollo
```bash
cd web
python -m http.server 5500
```

Luego abrir:
- `http://localhost:5500`

### Verificación de módulos
Después de cualquier cambio en `web/js/`, verificar en DevTools que no hay errores:
```javascript
// En Console (F12):
console.log(window.context)        // Debe mostrar estado global
console.log(window.applyFilters)   // Debe existir
console.log(window.playTrack)      // Debe existir
// ... etc. para cada función expuesta
```

### Variables de entorno
Actualmente no se detectan archivos `.env` usados en `web/`.
**Credenciales hardcodeadas** en `web/js/supabase.js`:
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`

**Acción recomendada antes de producción**: Mover a un mecanismo seguro (variables de ambiente, servidor de configuración, etc.).

---

## 8) Estilos y Convenciones

### Estilos
- CSS tradicional en `web/css/styles.css`.
- Uso de `:root` con custom properties (tema oscuro y paleta corporativa).
- Layout responsive con media queries (sin Tailwind ni CSS Modules).

### Convenciones de código para IA (solo `/web`) - POST REFACTORIZACIÓN

#### Arquitectura modular
1. **Estado centralizado**: Todos los datos mutables viven en `context` (`app_context.js`).
2. **Módulos especializados**: Cada módulo tiene UNA responsabilidad:
   - Datos → `data_loader.js`
   - Audio → `player.js`
   - Tabla/Paginación → `collection_view.js`
   - Filtrado → `filters.js`
   - Estado → `app_context.js`
   - Orquestación → `app.js`

3. **Sin ciclos de importación**: Las dependencias fluyen en un único sentido (DAG válido).

#### Cambios en módulos especializados
- **No mezclar responsabilidades**: Si necesitas agregar lógica:
  - ¿Es filtrado? → `filters.js`
  - ¿Es reproducción de audio? → `player.js`
  - ¿Es renderizado de tabla? → `collection_view.js`
  - ¿Es carga de datos? → `data_loader.js`
  - ¿Es estado global? → `app_context.js`

- **Tipos de funciones**:
  - Públicas (exportadas): Nombrar descriptivamente (`playTrack`, `applyFilters`, `loadTableData`).
  - Privadas (internas): Usar comentarios indicando que son internas.
  - Event handlers: `handle*`, `toggle*`, `update*`, `render*` según patrón.

- **Importaciones**: Siempre importar `context` desde `app_context.js` para acceder/modificar estado.

#### Exposición en window
- `app.js` expone automáticamente todas las funciones públicas en `window.*` mediante statements explícitos.
- Esto permite que HTML antiguo con `onclick="playTrack(...)"` continúe funcionando.
- **Nunca agregar funciones directamente a `window`** en otros módulos; hacerlo en `app.js` exclusivamente.

#### Nombres y patrones
```javascript
// Estado
context.currentPage, context.allTracks, context.filterTracks, ...

// Funciones de lectura
sortCollection(tracks)        // Devuelve array ordenado

// Funciones de actualización UI
loadTableData()               // Lee context, actualiza DOM
updatePaginationUI()          // Actualiza solo controles de paginación
renderColumnPicker()          // Genera checkboxes dinámicamente

// Filtrado y búsqueda
applyFilters()                // Filtra context.allTracks → context.filteredTracks
handleFilterChange()          // Maneja evento de cambio de selector
toggleFilterFlag()            // Alterna boolean de filtro especial

// Reproducción
playTrack(track)              // Inicia reproducción
playNextTrack()               // Pasa al siguiente (privado, desde playTrack)
togglePlayPause()             // Pausa/reanuda
seekAudio(e)                  // Busca posición desde click de barra
changeVolume(val)             // Cambia volumen
toggleShuffle()               // Alterna modo shuffle

// Ordenación
sortByColumn(key)             // Click en header, alterna dirección si es mismo column
sortCollection(tracks)        // Ordena array según sortState
```

#### Licencia de cambios futuros
- **OK**: Agregar nuevas columnas a `ALL_COLUMNS` en `app_context.js`.
- **OK**: Agregar nuevos filtros a `currentFilters` en `app_context.js` + lógica en `filters.js`.
- **OK**: Crear nuevos módulos especializados manteniendo la arquitectura (imports limpios).
- **NO**: Crear dependencias circulares entre módulos.
- **NO**: Hardcodear datos en `app.js` que deberían estar en `app_context.js`.
- **NO**: Llamar a funciones locales de un módulo en HTML; usar `window.*` desde `app.js`.

#### Testing y debugging
- Acceder al estado global desde console: `window.context`
- Ejecutar funciones manualmente: `window.applyFilters()`, `window.playTrack(...)`
- Verificar imports correctos: `console.log(window)` debe mostrar todas las funciones listadas.

---

## Observaciones Tecnicas Relevantes

- `web/` es una webapp estática y autocontenida.
- La navegacion es de tipo "single-page por toggles" sin router.
- **Arquitectura modular reciente** (Septiembre 2026):
  - `app.js` refactorizado de 778 → 178 líneas (77% reducción)
  - 5 módulos nuevos especializados: `app_context.js`, `data_loader.js`, `player.js`, `collection_view.js`, `filters.js`
  - Estado centralizado en `context` (`app_context.js`)
  - Sin ciclos de importación (arquitectura DAG válida)
  - 100% compatible con HTML existente (funciones en `window`)
- No hay toolchain Node local en esta carpeta.
- El acoplamiento principal está entre `app.js` (orquestador) y los módulos especializados + `index.html` (ids/classes del DOM).
- Credenciales de Supabase actualmente hardcodeadas en `web/js/supabase.js` (mover a variables de entorno antes de producción).
- Documentación disponible en `docs/REFACTORING_SUMMARY.md`, `docs/QUICK_REFERENCE.md`, `docs/TESTING_CHECKLIST.md` (generada post-refactorización).

---

## Apéndice: Refactorización Modular (Septiembre 2026)

### ¿Qué cambió?

**Antes**: Monolito en `app.js` (778 líneas)
- Todas las responsabilidades mezcladas en un único archivo
- Difícil de mantener, testear y extender
- Alto acoplamiento entre lógica

**Después**: Arquitectura modular (6 archivos, 976 líneas totales)
- Cada módulo con responsabilidad única
- Bajo acoplamiento, fácil testear independientemente
- Mejor documentación y mantenibilidad

### Distribución de módulos

| Módulo | Líneas | Responsabilidad |
|--------|--------|---|
| `app_context.js` | 67 | Estado global centralizado |
| `data_loader.js` | 35 | Paginación de Supabase |
| `player.js` | 174 | Reproducción de audio |
| `collection_view.js` | 254 | Tabla, paginación, ordenación |
| `filters.js` | 268 | Filtrado y búsqueda |
| `app.js` | 178 | Orquestación (antes 778) |

### Compatibilidad
- ✅ 100% compatible con HTML existente
- ✅ Todas las funciones expuestas en `window`
- ✅ Sin breaking changes funcionales
- ✅ Misma lógica de negocio preservada

### Documentación generada
Para desarrolladores posteriores, ver:
- `docs/00_START_HERE.md` - Resumen ejecutivo
- `docs/QUICK_REFERENCE.md` - Guía rápida
- `docs/MODULE_VERIFICATION.md` - Verificación técnica
- `docs/TESTING_CHECKLIST.md` - Plan de QA completo

