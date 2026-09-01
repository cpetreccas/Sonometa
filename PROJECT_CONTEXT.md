# PROJECT_CONTEXT.md

## Resumen Ejecutivo

**Sonometa** es una aplicación de escritorio para **gestión y automatización de metadatos de audio**.
Su objetivo principal es acelerar el trabajo de catalogación musical (DJ/producers/librerías de audio) mediante:

- Escaneo de carpetas de audio y extracción de tags.
- Edición masiva/individual de metadatos en una grilla.
- Enriquecimiento automático con información de **Discogs** (incluyendo carátulas).
- Gestión de catálogos propios (Album, Genre, Publisher) con relaciones jerárquicas.
- Registro de cambios con **Undo/Redo** y trazabilidad por logs estructurados.

No es una app web ni cliente-servidor tradicional: la lógica principal corre localmente en GUI (Tk/CustomTkinter) y escribe metadatos directamente en archivos de audio.

---

## Stack Tecnológico

### Lenguaje y ejecución
- **Python** (proyecto basado en `pip`).

### UI / Frontend de escritorio
- **customtkinter** (UI principal).
- `tkinter` / `ttk` (widgets base, Treeview, menús, diálogos).

### Audio y metadatos
- **mutagen** (lectura/escritura de tags audio).
- **pygame** (mini reproductor integrado).

### Imágenes y assets
- **Pillow (PIL)** para manipulación/carga de carátulas e iconos.

### Integración externa
- Cliente HTTP a **Discogs API** encapsulado en `discogs_client.py`.

### Logging y utilidades
- `logging` estándar con handler personalizado (`LogManager`).
- Persistencia local en JSON para catálogos/configuración (`CatalogManager`).

### Base de datos
- **No hay base de datos relacional/noSQL** detectada.
- Persistencia principal: **archivos JSON** + metadatos embebidos en los archivos de audio.

---

## Estructura de Carpetas (simplificada)

```text
Proyecto Sonometa/
├─ src/                    # Código fuente principal de la app
│  ├─ gui.py               # Punto de entrada App + orquestación global
│  ├─ *_panel.py           # Componentes visuales (header, grid, detail, tools)
│  ├─ process_manager.py   # Pipeline principal de procesamiento/enriquecimiento
│  ├─ audio_manager.py     # Lectura/escritura de tags de audio
│  ├─ discogs_client.py    # Integración externa con Discogs
│  ├─ catalog_manager.py   # Catálogos y settings persistidos localmente
│  ├─ undo_manager.py      # Historial de acciones undo/redo
│  ├─ log_handler.py       # Logging centralizado + bridge a UI
│  ├─ dialogs.py           # Diálogos modales y ventanas auxiliares
│  ├─ ui_utils.py          # Helpers UI (iconos, tooltips, recursos)
│  ├─ format_filename.py   # Normalización/formato de texto metadatos
│  ├─ search_manager.py    # Lógica de búsqueda/filtrado en grilla
│  ├─ audio_player.py      # Reproductor de audio embebido
│  └─ test_sonometa*.py    # Pruebas unitarias/regresión
├─ assets/                 # Iconos, logos, imágenes y portada fallback
├─ docs/                   # Requisitos y backlog funcional/técnico
└─ Trazas Sonometa.txt     # Archivo de trazas/log histórico del proyecto
```

---

## Módulos Principales (función y estado)

- **`gui.py` (App Orchestrator)**
  - Inicializa servicios (`AudioManager`, `CatalogManager`, `DiscogsClient`, `ProcessManager`, `UndoManager`, `LogManager`).
  - Gestiona estado global de UI (ruta actual, mapa de filas, historial de logs, modo multiselección).
  - **Estado:** núcleo activo y estable de composición de módulos.

- **`grid_panel.py`**
  - Tabla principal con edición inline de celdas y selección múltiple.
  - Punto de edición operativa de metadatos antes de persistencia.
  - **Estado:** funcional; eje de interacción de datos.

- **`detail_panel.py`**
  - Edición detallada por registro, gestión de carátula y mini reproductor.
  - Conecta acciones de usuario con `ProcessManager` y `AudioPlayer`.
  - **Estado:** funcional, con alta concentración de lógica UI.

- **`process_manager.py`**
  - Orquesta pipeline de procesamiento automático (validación + Discogs + aplicación de cambios).
  - Administra tareas por lotes y logging del proceso.
  - **Estado:** funcional; componente crítico de negocio.

- **`audio_manager.py`**
  - Capa de I/O de metadatos (lectura/escritura/eliminación) desacoplada de UI.
  - Incluye soporte de portada embebida y extracción de información extendida.
  - **Estado:** funcional; backend local principal.

- **`catalog_manager.py`**
  - Mantiene catálogos y reglas jerárquicas (álbum→género→publisher), persiste en JSON.
  - **Estado:** funcional; base de validación y autocompletado.

- **`discogs_client.py`**
  - Encapsula llamadas a Discogs y descarga de recursos (covers/datos release).
  - **Estado:** funcional; dependencia externa sensible a rate-limit/red.

- **`undo_manager.py`**
  - Historial de cambios con stacks `undo/redo` y acciones por lote.
  - **Estado:** funcional; importante para seguridad de edición.

- **`log_handler.py`**
  - Handler custom para log unificado (consola, estado UI, historial visual).
  - **Estado:** funcional; útil para observabilidad operativa.

- **`dialogs.py`**
  - Biblioteca de popups/modales (configuración, logs, catálogos, confirmaciones, ayuda).
  - **Estado:** funcional; con items de UX pendientes en backlog (z-order/estilo).

- **`format_filename.py`**
  - Normalización de texto para estandarizar naming metadata.
  - **Estado:** presente y utilitario; revisar nivel de adopción transversal en pipeline.

- **`test_sonometa*.py`**
  - Pruebas unitarias base para componentes core.
  - **Estado:** existente; recomendable ampliar cobertura en flujos de UI + integración Discogs.

---

## Flujo de Datos y Convenciones

## Flujo de datos (alto nivel)

1. Usuario selecciona carpeta desde UI.
2. `gui.py` delega escaneo a `audio_manager.py`.
3. Metadatos extraídos se renderizan en `grid_panel.py` y sincronizan con `detail_panel.py`.
4. Ediciones de usuario se reflejan en estado UI y se registran vía `undo_manager.py`.
5. Al procesar, `process_manager.py`:
   - toma filas objetivo,
   - consulta `discogs_client.py`,
   - aplica/normaliza datos,
   - persiste cambios en archivos via `audio_manager.py`,
   - reporta progreso vía `log_handler.py`.
6. Catálogos y settings se leen/guardan con `catalog_manager.py`.

## APIs / Integraciones

- **API interna del proyecto:** no se detectan rutas REST internas (no hay backend HTTP propio).
- **Integración externa principal:** Discogs (encapsulada por `discogs_client.py`).
- **Persistencia local:** archivos JSON (catálogos/settings) + tags de audio escritos in-place.

## Convenciones de código detectadas

- **Arquitectura por módulos/servicios** con `App` como orquestador.
- **Nombres en `snake_case`** para funciones/atributos; constantes de clase en mayúsculas.
- Métodos “privados” prefijados con `_` (ej. `_init_services`, `_setup_ui`).
- Logging estructurado con prefijos de contexto (`[UNDO]`, `[REDO]`, `[PROCESS]`, etc.).
- Gestión de estado de UI en objeto `App` y componentes desacoplados por responsabilidad.
- Uso de managers especializados (`*Manager`) para separar UI, dominio y persistencia.

---

## Estado General y Riesgos Técnicos Observables

### Fortalezas
- Buena separación por responsabilidades (UI, proceso, metadata, catálogos, logging).
- Pipeline de negocio explícito y extensible.
- Undo/Redo y trazabilidad bien integrados para operación diaria.

### Riesgos / deuda técnica
- Dependencia de API externa (Discogs) y riesgo de rate-limit en lotes grandes.
- Parte de lógica distribuida entre múltiples componentes UI (posible complejidad de mantenimiento).
- Backlog indica mejoras pendientes de UX/estilo y comportamiento de foco/modales.
- Cobertura de tests ampliable para escenarios multihilo e integración end-to-end.

---

## Referencias rápidas (entrypoints relevantes)

- Arranque app: `src/gui.py`
- Pipeline de procesamiento: `src/process_manager.py`
- I/O metadatos: `src/audio_manager.py`
- Integración Discogs: `src/discogs_client.py`
- Catálogos/settings: `src/catalog_manager.py`
- Logs centralizados: `src/log_handler.py`

