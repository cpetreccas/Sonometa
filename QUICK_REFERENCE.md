# 🚀 Quick Reference - Módulos Refactorizados

## 📋 Índice de Módulos

### 1️⃣ app_context.js - Estado Global

**Ubicación**: `web/js/app_context.js`

**¿Qué es?**: Almacén centralizado de estado mutable de la aplicación.

**Cómo usarlo**:
```javascript
import { context, PAGE_SIZE, ALL_COLUMNS } from './app_context.js';

// Acceder al estado
console.log(context.currentPage);          // 0
console.log(context.allTracks.length);     // Cantidad de canciones
console.log(context.filteredTracks);        // Canciones después de filtros
console.log(context.currentFilters.search); // Búsqueda actual

// Modificar estado (es mutable, intencional)
context.currentPage = 1;
context.isShuffle = true;
context.currentFilters.album = 'Dark Side';
```

**Propiedades principales**:
- `currentPage` - Página actual (0-indexed)
- `allTracks` - Todas las canciones sin filtrar
- `filteredTracks` - Canciones después de aplicar filtros
- `currentTrackIndex` - Índice de canción siendo reproducida
- `isShuffle` - Boolean para modo shuffle
- `sortState` - `{ key: 'filename', direction: 'asc' }`
- `columnVisibility` - Objeto con keys de columnas como boolean
- `currentFilters` - Objeto con filtros activos

---

### 2️⃣ data_loader.js - Carga de Datos

**Ubicación**: `web/js/data_loader.js`

**¿Qué es?**: Módulo para fetching de datos desde Supabase.

**Cómo usarlo**:
```javascript
import { fetchAllTracks } from './data_loader.js';
import { context } from './app_context.js';

// Cargar todas las canciones (ASYNC)
const tracks = await fetchAllTracks();
context.allTracks = tracks; // Asignar al estado global

// fetchAllTracks() se encarga de:
// - Paginar en bloques de 1,000
// - Manejar errores de Supabase
// - Retornar array completo
```

**Ejemplo de la estructura retornada**:
```javascript
{
  id: 123,
  filename: "song.mp3",
  artist: "The Artist",
  title: "Song Title",
  mix_artist: null,
  album: "Album Name",
  genre: "House",
  publisher: "Label",
  year: 2023,
  duration: 240,
  cue_count: 3,
  rating: 5,
  cover_url: "https://...",
  preview_audio_url: "https://..."
}
```

---

### 3️⃣ player.js - Reproductor de Audio

**Ubicación**: `web/js/player.js`

**¿Qué es?**: Lógica de reproducción de audio flotante.

**Funciones disponibles**:

```javascript
import { playTrack, togglePlayPause, toggleShuffle, seekAudio, changeVolume } from './player.js';

// Reproducir una canción específica
const track = context.filteredTracks[0];
playTrack(track);
// → Muestra info en playerBar, carga audio, inicia reproducción

// Alternar play/pausa
togglePlayPause();
// → Si está reproduciendo → pausa
// → Si está pausado → reproduce

// Activar/desactivar shuffle
toggleShuffle();
// → Si está en shuffle → desactiva
// → Si no está en shuffle → activa
// → Agrega clase CSS 'active-shuffle' al botón

// Buscar posición en el audio (se usa desde barra de progreso)
// Nota: se limita a máximo 20 segundos (por defecto)
seekAudio(event); // event = click event en la barra de progreso

// Cambiar volumen
changeVolume(0.5); // 0 a 1
```

**De forma automática**:
- Reproducción limitada a 20 segundos
- Al terminar → reproduce siguiente canción (o shuffle si está activo)
- Las estrellas de rating se limitan a 0-5

---

### 4️⃣ collection_view.js - Vista de Tabla

**Ubicación**: `web/js/collection_view.js`

**¿Qué es?**: Renderizado de tabla de tracks con paginación y ordenación.

**Funciones disponibles**:

```javascript
import { 
  sortByColumn, 
  loadTableData, 
  toggleColumnPicker, 
  renderColumnPicker,
  toggleVerDetalle,
  changePage 
} from './collection_view.js';

// Ordenar por columna específica
sortByColumn('artist');
// → Si ya está ordenado por 'artist' → alterna dirección
// → Si no → ordena por 'artist' ascendente

// Cargar y renderizar la tabla
loadTableData();
// → Applica ordenación
// → Pagina los datos (PAGE_SIZE = 100)
// → Renderiza HTML de tabla
// → Actualiza contador de resultados
// → Actualiza UI de paginación

// Cambiar página
changePage(1);  // Avanza 1 página
changePage(-1); // Retrocede 1 página

// Mostrar/ocultar selector de columnas
toggleColumnPicker(event);

// Renderizar dinámicamente el selector de columnas
renderColumnPicker();
// → Se llama después de cambiar modo (detalle/normal)
// → Genera checkboxes para cada columna visible

// Alternar entre vista detalle y normal
toggleVerDetalle();
// → Cambia qué columnas se muestran (normalOnly vs detailOnly)
```

**Notas**:
- Las columnas se filtran según `columnVisibility`
- En modo "detalle": muestra más columnas
- En modo "normal": solo muestra lista simplificada
- Máximo 100 registros por página
- Ordenación no afecta a "cover" (no es sorteable)

---

### 5️⃣ filters.js - Lógica de Filtrado

**Ubicación**: `web/js/filters.js`

**¿Qué es?**: Gestión completa de filtros y búsqueda.

**Funciones principales**:

```javascript
import { 
  populateSelectFilters, 
  handleFilterChange, 
  updateFilterSummaryBar,
  toggleFilterFlag,
  applyFilters, 
  applyFiltersAndClose,
  resetAllFilters,
  openFilterModal,
  closeFilterModal
} from './filters.js';

// Aplicar los filtros actuales
applyFilters();
// → Filtra context.allTracks basado en context.currentFilters
// → Guarda resultado en context.filteredTracks
// → Renderiza tabla nuevamente
// → Actualiza dropdowns de filtros

// Cambiar un valor de filtro
handleFilterChange('album', 'Dark Side');
// → Actualiza context.currentFilters.album
// → Re-popula dropdowns de filtros
// → En desktop (width >= 768) aplica filtros automáticamente

// Alternar un flag especial (sin cues, sin carátula, sin rating)
toggleFilterFlag('noCues');
// → context.currentFilters.noCues = !context.currentFilters.noCues
// → Re-aplica filtros

// Re-popular los selectores de filtros
populateSelectFilters();
// → Genera dinámicamente opciones basadas en tracks actuales
// → Respeta otros filtros aplicados

// Actualizar la barra visual de filtros activos
updateFilterSummaryBar();
// → Actualiza badge de contador
// → Actualiza texto de resumen
// → Actualiza estado de botones toggle

// Resetear todos los filtros
resetAllFilters();
// → Limpia búsqueda
// → Limpia dropdowns
// → Limpia flags especiales
// → Vuelve a aplicar filtros (mostrando todo)

// Modal de filtros (móvil)
openFilterModal();   // Abre modal
closeFilterModal();  // Cierra modal
applyFiltersAndClose(); // Aplica y cierra
```

**Tipos de filtros**:
1. **Búsqueda**: busca en filename, title, artist
2. **Dropdowns**: album, genre, publisher, year
3. **Flags**: noCues, noCover, noRating
4. **Especial**: '__EMPTY__' para campos sin valor

---

### 6️⃣ app.js - Orquestador Principal

**Ubicación**: `web/js/app.js`

**¿Qué es?**: Punto de entrada, inicialización e inyección de módulos.

**Funciones expuestas en window**:

```javascript
// Disponibles desde HTML o consola
window.applyFilters()
window.sortByColumn('filename')
window.playTrack(track)
window.togglePlayPause()
window.changeVolume(0.8)
// ... (ver sección anterior para lista completa)
```

**Flujo de inicialización**:
1. DOMContentLoaded → Registra ServiceWorker
2. checkSession() → Verifica si usuario está logueado
3. Si logueado → showApp() → loadInitialCollection()
4. loadInitialCollection():
   - Llama fetchAllTracks()
   - Asigna a context.allTracks
   - Inicializa UI (filterDropdowns, columnPicker)
   - Llama applyFilters()

---

## 🔗 Dependencias Entre Módulos

```
app_context.js          ← (ninguna dependencia)
     ↑
     ├─ player.js
     ├─ collection_view.js
     └─ filters.js
          │
          ├─ collection_view.js → player.js → app_context.js
          └─ dashboard.js (módulo existente)

data_loader.js → supabase.js (módulo existente)

app.js (importa todo)
```

---

## 💡 Patrón de Uso Típico

### Caso: Agregar nuevo filtro

1. Modificar `context.currentFilters` en `app_context.js`
2. Agregar lógica de filtrado en `filters.js`
3. Listo, sin tocar otros módulos

### Caso: Cambiar presentación de tabla

1. Modificar renderizado en `collection_view.js`
2. Listo, los datos siguen viniendo igual desde otros módulos

### Caso: Nuevo tipo de búsqueda

1. Modificar `applyFilters()` en `filters.js`
2. Listo, no necesitas cambiar ningún otro módulo

---

## 🐛 Debugging Tips

**Ver estado global**:
```javascript
console.log(window.context); // Objeto con todo el estado
console.log(window.context.allTracks.length);
```

**Ver filtros actuales**:
```javascript
console.log(window.context.currentFilters);
```

**Forzar aplicar filtros**:
```javascript
window.applyFilters();
```

**Cargar tabla**:
```javascript
window.loadTableData();
```

**Reproducir primera canción**:
```javascript
window.playTrack(window.context.filteredTracks[0]);
```

---

## 📝 Convenciones Usadas

| Convención | Ejemplo | Significado |
|-----------|---------|-------------|
| `context.*` | `context.currentPage` | Estado mutable global |
| `handle*` | `handleFilterChange` | Manejador de eventos |
| `toggle*` | `toggleShuffle` | Alterna boolean |
| `update*` | `updatePaginationUI` | Actualiza UI |
| `render*` | `renderColumnPicker` | Genera HTML |
| `populate*` | `populateSelectFilters` | Llena elementos del DOM |
| `apply*` | `applyFilters` | Aplica lógica |
| `fetch*` | `fetchAllTracks` | Obtiene datos remotos |
| `show*` | `showApp` | Muestra interfaz |
| `close*` | `closeFilterModal` | Cierra elemento |

---

## ✅ Checklist para Desarrolladores

- [ ] Understand the module structure
- [ ] Know where to find the state (context)
- [ ] Know where to add new logic (which module)
- [ ] Export/import correctly when modifying
- [ ] Test in browser DevTools console
- [ ] Remember: all functions must be in `window` if called from HTML

---

**Última actualización**: 2024
**Versión**: 1.0 (Refactorización Modular)

