# Cambios realizados en Sonometa v0.02

Resumen de las mejoras implementadas en esta versión.

## 1. Rearranjo del Layout (Panel Lateral → Panel Inferior)

### Antes:
```
┌─────────────────────────────────────┐
│          BARRA SUPERIOR             │
├──────────────────┬─────────────────────┤
│  PANEL LATERAL   │                    │
│  (Scrollable)    │   TABLA TREEVIEW   │
│ ├─ Procesar      │ (Grid de archivos) │
│ ├─ Título        │                    │
│ ├─ Intérprete    │                    │
│ ├─ Remix         │                    │
│ ├─ Álbum         │                    │
│ ├─ Año           │                    │
│ ├─ Género        │                    │
│ ├─ Publisher     │                    │
│ └─ Carátula      │                    │
├──────────────────┴─────────────────────┤
│      BARRA DE PROGRESO Y ESTADO       │
└─────────────────────────────────────┘
```

### Después:
```
┌──────────────────────────────────────────────┐
│           BARRA SUPERIOR                     │
├──────────────────────────────────────────────┤
│                                              │
│           TABLA TREEVIEW                    │
│         (Grid de archivos)                  │
│                                              │
├──────────────────────────────────────────────┤
│ PANEL INFERIOR                               │
│ ┌──────────────┬─────────────────────────┐ │
│ │  Carátula    │  [Botón Procesar]       │ │
│ │  (180x180)   │  ┌───────────────────┐ │ │
│ │              │  │ Año               │ │ │
│ │              │  └───────────────────┘ │ │
│ │              │  ┌────┬────┬────────┐ │ │
│ │              │  │Int │Tít │  Rmx  │ │ │
│ │              │  └────┴────┴────────┘ │ │
│ │              │  ┌────┬────┬────────┐ │ │
│ │              │  │Alb │Gen │ Pub    │ │ │
│ │              │  └────┴────┴────────┘ │ │
│ └──────────────┴─────────────────────────┘ │
├──────────────────────────────────────────────┤
│      BARRA DE PROGRESO Y ESTADO             │
└──────────────────────────────────────────────┘
```

## 2. Reorganización de campos

**Distribución en 3 filas horizontales:**

- **Fila 1 (Arriba)**: Año
- **Fila 2 (Centro)**: Intérprete | Título | Remix
- **Fila 3 (Abajo)**: Álbum | Género | Publisher

**Cambios:**
- Campos más compactos y visibles
- Carátula siempre visible (180x180 px a la izquierda)
- Mejor aprovechamiento del espacio horizontal
- Campos distribuidos en ancho en lugar de vertical

## 3. Nuevas funcionalidades de menú

### Menú Acciones:
- **Procesar con Discogs** (existente)
- **Seleccionar todo (Ctrl+A)** ← NUEVO
- Separador
- **Limpiar todo** (existente)

### Menú Ayuda:
- **Atajos de teclado** ← NUEVO (modal con lista visual)
- **Ver logs** (existente)
- Separador
- **Acerca de Sonometa** (existente)

## 4. Nuevos atajos de teclado

| Atajo | Acción | Ubicación |
|-------|--------|-----------|
| Ctrl+O | Seleccionar carpeta | Menú Archivo |
| F5 | Actualizar lista | Menú Archivo |
| **Ctrl+A** | **Seleccionar todo** | **← NUEVO** |
| Ctrl+Q | Cerrar aplicación | Menú Archivo |

## 5. Modal de Atajos de Teclado

Ventana emergente accesible desde `Menú Ayuda > Atajos de teclado`:

**Contenido:**
- Lista completa de atajos disponibles
- Descripción clara de cada acción
- Diseño limpio con colores corporativos
- Botón "Cerrar" para deshacer modal

**Atajos mostrados:**
- `Ctrl+O` - Seleccionar carpeta
- `F5` - Actualizar lista de archivos
- `Ctrl+A` - Seleccionar todo
- `Ctrl+Q` - Cerrar aplicación
- `Doble-clic` - Editar celda en tabla
- `Enter` - Guardar edición de celda
- `Esc` - Cancelar edición de celda

## 6. Cambios removidos

- ❌ **Campo "Comentario"** eliminado completamente:
  - No se mostraba en el grid de archivos
  - No se guardaba en los tags de audio
  - Panel más limpio sin este campo

## 7. Mejoras técnicas internas

- Reorden de métodos `setup_treeview()` y `setup_tag_panel()` para coherencia visual
- Nuevo método `select_all_rows()` para seleccionar todas las filas del árbol
- Nuevo método `show_keyboard_shortcuts_dialog()` para mostrar modal de atajos
- Grid layout mejorado para campos en el panel inferior
- Mejor manejo de espaciado y proporciones en el panel inferior

## 8. Ventajas del nuevo layout

✅ **Más espacio para la tabla**: El grid principal ahora ocupa toda la zona superior
✅ **Carátula permanente**: Siempre visible en la esquina inferior izquierda
✅ **Campos compactos**: 7 campos distribuidos en 3 filas horizontales
✅ **Mejor UX**: Acceso rápido a funciones clave (Ctrl+A, ver atajos)
✅ **Interfaz más limpia**: Sin campo comentario innecesario
✅ **Escalabilidad**: Panel inferior se adapta al tamaño de la ventana

## 9. Compatibilidad

- ✅ Todas las funcionalidades conservadas
- ✅ Acceso a todos los campos originales
- ✅ Lectura/escritura de metadatos sin cambios
- ✅ Procesamiento Discogs sin cambios
- ✅ Compilación exitosa (sin warnings críticos)

## 10. Cómo usar las nuevas funciones

### Seleccionar todo:
1. Opción 1: Menú `Acciones > Seleccionar todo`
2. Opción 2: Presionar `Ctrl+A`
3. Efecto: Se resaltan todas las filas del grid

### Ver atajos de teclado:
1. Menú `Ayuda > Atajos de teclado`
2. Se abre modal con lista completa
3. Click "Cerrar" para deshacer la ventana

### Panel inferior de tags:
1. Selecciona una fila en el grid
2. Los campos se cargan automáticamente
3. Edita los campos en el panel (cambios se guardan al presionar Enter)
4. Carátula se muestra a la izquierda
5. Botón "Procesar" en la parte superior del panel

