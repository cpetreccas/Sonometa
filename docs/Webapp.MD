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
- **JavaScript ES Modules** (`web/js/*.js`)

### Frameworks y librerias
- **Framework frontend**: ninguno (Vanilla JS).
- **Charts**: `Chart.js` via CDN (`index.html`).
- **Backend client**: `@supabase/supabase-js` via CDN global (`window.supabase` en `index.html` + `js/supabase.js`).

### Estado, routing y cliente API
- **Estado global local**: variables JS en `js/app.js` (`currentPage`, `currentFilters`, `chartInstances`).
- **Routing**: no hay router (ni React Router/Vue Router); navegacion manual por toggles de secciones del DOM.
- **Cliente HTTP/API**: Supabase JS client (`supabase.from(...).select(...)`, `supabase.auth...`).

### Build, lint, scripts y package manager
- No se detecta `package.json` dentro de `web/`.
- No se detectan lockfiles (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`) dentro de `web/`.
- No se detectan configuraciones de bundler (`vite.config.*`, `webpack.config.*`, etc.).
- No se detectan configuraciones de lint/format (`eslint`, `prettier`) dentro de `web/`.

**Conclusión:** `web/` funciona como frontend estatico servido directamente por un host estatico.

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
   ├─ app.js              # Orquestacion UI, filtros, tabla, paginacion, reproduccion
   ├─ auth.js             # Login/logout y chequeo de sesion Supabase
   ├─ dashboard.js        # KPIs y graficas Chart.js
   └─ supabase.js         # Inicializacion del cliente Supabase
```

Responsabilidades clave:
- `js/app.js`: entry logic de UI, binding de eventos y ciclo de vida.
- `js/auth.js`: encapsula llamadas de autenticacion.
- `js/dashboard.js`: agrega datos y renderiza graficos.
- `js/supabase.js`: punto unico de conexion a Supabase.

---

## 4) Arquitectura y Flujo de Datos

### Patron general
- Arquitectura **modular por archivos JS** (sin framework, sin DI formal).
- `app.js` actua como orquestador principal.
- Flujo UI basado en manipulación directa del DOM.

### Flujo principal
1. Carga `index.html`.
2. `app.js` registra Service Worker (si soportado).
3. Se verifica sesion con `checkSession()` (`auth.js`).
4. Si hay sesion: muestra app y dispara carga de filtros/tablas/dashboard.
5. Si no hay sesion: muestra formulario login.
6. Cada cambio de filtro reconstruye query Supabase y refresca UI.

### Integracion backend
- Supabase se consume directamente desde frontend:
  - Auth: `signInWithPassword`, `getSession`, `signOut`.
  - Datos: consultas a tabla `tracks`.
- No hay capa BFF dentro de `web/`.

---

## 5) Modelos de Datos y Tipos del Frontend

No hay TypeScript ni interfaces formales; los modelos son implícitos en JS.

### Entidad principal (`tracks`)
Campos inferidos usados por la UI:
- `id`
- `filename`
- `artist`
- `title`
- `remix`
- `album`
- `genre`
- `publisher`
- `year`
- `cues`
- `rating`
- `cover_url`
- `cover_blob`
- `preview_url`

### Estado de filtros (frontend)
```js
{
  search: '',
  album: '',
  genre: '',
  publisher: '',
  year: ''
}
```

### Paginacion
- `currentPage` y `PAGE_SIZE = 100` en `app.js`.

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

Como no hay `package.json`, se puede servir como sitio estatico.

```bash
cd web
python -m http.server 5500
```

Luego abrir:
- `http://localhost:5500`

### Variables de entorno
No se detectan variables `.env` usadas en `web/`.
Actualmente `SUPABASE_URL` y `SUPABASE_ANON_KEY` estan hardcodeadas en `web/js/supabase.js`.

---

## 8) Estilos y Convenciones

### Estilos
- CSS tradicional en `web/css/styles.css`.
- Uso de `:root` con custom properties (tema oscuro y paleta corporativa).
- Layout responsive con media queries (sin Tailwind ni CSS Modules).

### Convenciones de codigo para IA (solo `/web`)
1. Mantener arquitectura actual: modulos ES (`js/*.js`) sin introducir framework nuevo.
2. No mezclar logica de negocio en `index.html`; centralizar en `js/app.js` o modulos especializados.
3. Preservar nomenclatura y estructura de estado actual (`currentFilters`, `currentPage`, etc.).
4. Evitar romper funciones globales expuestas en `window` que usa el HTML.
5. Mantener estilos en `css/styles.css` respetando variables existentes y tema dark.
6. Si se incorporan secretos/config, mover credenciales hardcodeadas de `js/supabase.js` a un mecanismo de configuracion seguro antes de produccion.

---

## Observaciones Tecnicas Relevantes

- `web/` es una webapp estatica y autocontenida.
- La navegacion es de tipo "single-page por toggles" sin router.
- No hay toolchain Node local en esta carpeta.
- El acoplamiento principal esta entre `app.js` y los ids/classes del DOM en `index.html`.

