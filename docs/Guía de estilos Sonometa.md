# Guía de Estilos y Sistema de Diseño — Sonometa UI

Este documento define la identidad visual oficial, la paleta de colores, la tipografía y las reglas de diseño para la plataforma **Sonometa** (Escritorio y Web PWA). Sigue estas directrices estrictamente para mantener una coherencia perfecta entre plataformas.

**Fuente de referencia:** la PWA (`web/css/styles.css`, `web/js/dashboard.js`). Los valores de esta guía están tomados de ella; si la PWA cambia, esta guía se actualiza con ella. En escritorio, los tokens se traducen en `src/theme.py` (ver sección 7).

---

## 1. Principios Fundamentales y Estética

* **Dark Mode First (`#1A1A1E`):** estética profesional inspirada en software de audio para DJ (Traktor, rekordbox, Spotify). Fondos oscuros pero no negros: grises neutros ligeramente fríos, con superficies un escalón más claras que el fondo.
* **Identidad de Marca:** morado corporativo (`#8B5CF6`) como acento único de interacción, con rosa (`#EC4899`) solo en degradados de marca y puntos de gráficos.
* **Diseño de Componentes:** tarjetas con esquinas de 12px y borde de 1px (`#363640`), controles de 8px, alto contraste de texto (WCAG AA ≥ 4.5:1) para la gestión densa de metadatos.
* **Jerarquía por luminosidad:** fondo `#1A1A1E` < tarjeta `#24242A` < hover `#2E2E36` / inputs `#2D2D35`. Cada nivel de elevación es un gris más claro, no una sombra más fuerte.

---

## 2. Tipografía

* **Familia Tipográfica Principal:** `-apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
* **Suavizado:** `-webkit-font-smoothing: antialiased`.

### Jerarquía y Escala Tipográfica

| Elemento | Tamaño | Peso | Color | Notas |
| :--- | :--- | :--- | :--- | :--- |
| **KPI / Contador destacado** | `48px` | `800` | `#FFFFFF` | `line-height: 1`, `letter-spacing: -1px`, halo `text-shadow: 0 0 20px rgba(168, 85, 247, 0.3)` |
| **Título de marca** | `18px` | `700` | `#FFFFFF` | Versión al lado en `12px/600` morado |
| **Título de modal / login** | `20px` | `700` | `#FFFFFF` | |
| **Título de hoja / panel** | `14px` | `700` | `#FFFFFF` | |
| **Título de tarjeta** | `11px` | `700` | `--text-subtle` | MAYÚSCULAS, `letter-spacing: 0.8px`, línea inferior `1px --border-color` |
| **Cuerpo / Celdas de tabla** | `12px` | `400` | `--text-main` | |
| **Botones** | `12px` | `600` | según variante | `11px` en la variante pequeña |
| **Cabecera de tabla** | `10px` | `600` | `--text-muted` | MAYÚSCULAS |
| **Leyenda de gráficos** | `11px` | `400` / `600` (cantidad) | `#E4E4E7` / `#FFFFFF` | Cabecera `10px/700` en minúsculas; porcentaje `10px --text-muted` |
| **Etiqueta KPI / subtítulo de marca** | `11px` / `9px` | `600` | `--text-muted` | MAYÚSCULAS, `letter-spacing: 1.5px` / `1.2px` |
| **Pie / textos menores** | `11px` | `400` | `--text-subtle` | |

---

## 3. Paleta de Colores y Variables CSS

Variables globales de la PWA (`:root` en `web/css/styles.css`):

```css
:root {
  /* Superficies */
  --bg-color: #1A1A1E;          /* Fondo general de la aplicación */
  --surface-color: #24242A;     /* Tarjetas, paneles, tablas, modales, menús */
  --surface-hover: #2E2E36;     /* Hover de filas, tarjetas y elementos de lista */
  --input-bg: #2D2D35;          /* Campos de entrada, selects, chips */
  --row-even: #1F1F24;          /* Filas pares de las tablas (zebra) */

  /* Bordes */
  --border-color: #363640;      /* Bordes de tarjetas, divisores, inputs */
  --border-highlight: #4B4B58;  /* Bordes destacados: hover, KPI, menús flotantes */

  /* Acentos de marca */
  --primary-purple: #8B5CF6;    /* Morado corporativo */
  --primary-hover: #7C3AED;     /* Hover de botones principales */

  /* Texto (contraste >= 4.5:1 sobre #1A1A1E y #24242A) */
  --text-main: #F4F4F5;
  --text-muted: #B3B3AD;        /* Secundario: cabeceras, artistas, etiquetas */
  --text-subtle: #8E8E96;       /* Menor: títulos de tarjeta, placeholders, pie */
}
```

### Colores complementarios (usados directamente en componentes)

| Uso | Color |
| :--- | :--- |
| Cabecera de tabla | `#1B1B20` |
| Cabecera de tabla en hover | `#272730` |
| Cabecera de la columna ordenada | fondo `#252033`, texto `--primary-purple` |
| Fila / tarjeta seleccionada | `#2F2643` (+ borde izquierdo `3px --primary-purple` en tablas) |
| Filtro activo (select) | fondo `#272335`, borde y halo `--primary-purple` |
| Chip activo | fondo `#2D2342`, borde `--primary-purple`, texto `#FFFFFF`, halo `0 0 8px rgba(139, 92, 246, 0.3)` |
| Degradado de la tarjeta KPI | `linear-gradient(180deg, #2D243A 0%, --surface-color 100%)` |
| Texto de leyenda | `#E4E4E7` |
| Acción de peligro / error | `#F87171` (texto y borde; fondo `rgba(239, 68, 68, 0.1)` en hover) |
| Éxito ("Colección 100% completada") | `#10B981` |
| Barra del reproductor | fondo `#18181C`, borde superior `#2E2E38` |
| Pista de barras de progreso | `#27272A` |

### Estados e indicadores de salud

| Estado | Color | Uso |
| :--- | :--- | :--- |
| Éxito | `#22C55E` | Salud buena/excelente, chequeo OK |
| Aviso | `#F59E0B` | Metadato secundario ausente, chequeo en aviso |
| Peligro | `#EF4444` | Metadato crítico ausente, chequeo crítico |

### Degradados de marca

* **Nota global de salud (anillo):** `linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)`.
* **Botón play del reproductor:** `linear-gradient(135deg, #6366F1, #8B5CF6)`.
* **Barra de progreso del reproductor:** `linear-gradient(90deg, #6366F1, #EC4899)`.
* **Línea superior de la tarjeta KPI:** `linear-gradient(90deg, transparent, #8B5CF6, transparent)`, 2px.

Fuera de estos casos no se usan degradados.

---

## 4. Patrones de Diseño de Componentes

### 4.1 Tarjetas y paneles

* **Tarjeta estándar (`.chart-card`):** fondo `--surface-color`, borde `1px --border-color`, radio `12px`, padding `16px` (`12px` en móvil), sombra `0 4px 16px rgba(0, 0, 0, 0.15)`.
* **Título de tarjeta:** ver tipografía; separado del cuerpo por una línea `1px --border-color` con `10px` de aire.
* **Tarjeta KPI (`.kpi-card`):** degradado vertical `#2D243A → --surface-color`, borde `1px --border-highlight`, radio `12px`, línea superior morada de 2px desvanecida en los extremos, número y etiqueta centrados, sombra `0 8px 24px rgba(0, 0, 0, 0.25)`.
* **Paneles flotantes (menús, selector de columnas):** fondo `--surface-color`, borde `1px --border-highlight`, radio `10px`, sombra `0 10px 25px rgba(0, 0, 0, 0.5)`.
* **Modal / login:** radio `16px`, borde `--border-highlight`, sombra `0 12px 32px rgba(0, 0, 0, 0.4)`.
* **Barra de resumen de filtros:** fondo `--surface-color`, borde `--border-color`, radio `10px`, padding `8px 12px`.

### 4.2 Botones y controles

* **Principal (`.btn-primary`):** fondo `--primary-purple`, texto blanco `12px/600`, borde `1px rgba(255, 255, 255, 0.1)`, radio `8px`, padding `8px 14px`, sombra `0 2px 8px rgba(139, 92, 246, 0.3)`. Hover `--primary-hover`. Deshabilitado: opacidad `0.5`.
* **Secundario (`.btn-secondary`):** fondo transparente, borde `1px --border-color`, texto `--text-muted`. Hover: texto `#FFFFFF`, borde `--border-highlight`.
* **Restablecer / limpiar (`.btn-reset`):** como el secundario en reposo. Hover: texto y borde `#F87171`, fondo `rgba(239, 68, 68, 0.1)`. El rojo solo aparece al pasar el ratón.
* **Destructivo (borra datos, p. ej. "Limpiar" metadatos en escritorio):** a diferencia del de restablecer, avisa siempre: fondo transparente, borde `1px #EF4444`, texto `--text-main`, hover con fondo `#450A0A`. Solo para acciones que modifican o borran datos del usuario.
* **Pequeño (`.btn-sm`):** padding `5px 10px`, `11px`.
* **Solo icono:** redondos o de esquinas `8px`, área táctil de `36px` a `40px`.

### 4.3 Campos de entrada

* **Inputs y selects:** fondo `--input-bg`, borde `1px --border-color`, radio `8px`, padding `8px 10px`, texto `12px --text-main`.
* **Foco:** borde `--primary-purple`.
* **Filtro activo:** fondo `#272335`, borde `--primary-purple` con halo de 1px del mismo color.

### 4.4 Chips (toggles de filtro)

* **Reposo:** fondo `--input-bg`, borde `1px --border-color`, texto `--text-muted` `11px/600`, radio `20px` (píldora), padding `6px 12px`.
* **Hover:** borde `--border-highlight`, texto `--text-main`.
* **Activo:** ver "Chip activo" en la sección 3.

### 4.5 Tablas de datos y listas de pistas

* **Contenedor:** fondo `--surface-color`, borde `1px --border-color`, radio `12px`.
* **Cabecera:** fondo `#1B1B20`, texto `--text-muted` `10px/600` en MAYÚSCULAS, padding `10px 12px`, borde inferior `--border-color`. Hover `#272730` con texto blanco; columna ordenada con texto morado y fondo `#252033`.
* **Celdas:** `12px`, padding `8px 12px`, borde inferior `1px --border-color`, texto recortado con elipsis.
* **Zebra:** filas pares `--row-even` (`#1F1F24`).
* **Hover de fila:** `--surface-hover`.
* **Fila seleccionada:** fondo `#2F2643` con borde izquierdo `3px --primary-purple`. El texto mantiene su color: no se usa el morado sólido como fondo de selección.
* **Carátula en tabla:** miniatura `38px`, radio `6px`, borde `--border-color`; sin carátula, recuadro `#1B1B20` con texto `--text-subtle`.

### 4.6 Gráficos y visualización de datos

* **Paleta categórica** (álbum, género, etiqueta, en este orden):
  `#8B5CF6`, `#6366F1`, `#A855F7`, `#EC4899`, `#3B82F6`, `#7C3AED`, `#C084FC`, `#38BDF8`, `#64748B`.
* **Valoraciones (barras y leyenda):** siempre la escala monocromática de morados:

  | Estrellas | Color |
  | :--- | :--- |
  | 5★ | `#8B5CF6` |
  | 4★ | `#7C3AED` |
  | 3★ | `#6D28D9` |
  | 2★ | `#4C1D95` |
  | 1★ | `#2E1065` |
  | Sin valorar (0★) | `#483871` (morado corporativo al 35% sobre `--surface-color`) |

* **Serie temporal (años):** línea `#8B5CF6` de 2px suavizada, sin puntos, relleno `rgba(139, 92, 246, 0.25)`. Eje X continuo: los años sin pistas cuentan como 0.
* **Tartas:** borde entre sectores `1px` del color de la tarjeta.
* **Barras:** radio `4px`, grosor máximo limitado cuando hay pocas categorías.
* **Ejes y cuadrícula:** texto de ticks `--text-muted`; líneas de cuadrícula `rgba(255, 255, 255, 0.08)`. El eje Y termina en la primera marca por encima del máximo.
* **Radar (indicadores de salud):** cuadrícula poligonal `rgba(255, 255, 255, 0.18)`, radios `rgba(255, 255, 255, 0.22)`, relleno `rgba(139, 92, 246, 0.3)`, borde `#8B5CF6` de 2px, puntos `#EC4899` con borde blanco. Primer eje arriba y el resto en sentido horario. Etiquetas de eje `#F4F4F5` `11px/600`.
* **Anillo de salud global:** degradado de marca sobre pista `--border-color`, extremos redondeados, porcentaje en blanco y estado en MAYÚSCULAS `--text-muted` debajo.
* **Leyenda personalizada:** tabla nombre / cant. / % con cuadrado de color `8px` (radio `2px`), separadores `rgba(255, 255, 255, 0.03)`, cantidades en negrita blanca, porcentaje con 2 decimales. Scroll propio con barra de `4px` en `--border-highlight`. Hover de fila `--surface-hover`.
* **Diagnóstico de salud:** rejilla de 2 columnas, cada elemento con icono de línea de color, cantidad en `#F4F4F5` `600` y texto `--text-muted`. Colores de icono: carátula `#EC4899`, valoración `#8B5CF6`, cue points `#38BDF8`, género `#A855F7`, etiqueta `#6366F1`, álbum `#C084FC`, año `#3B82F6`.

### 4.7 Reproductor

* **Barra inferior fija:** alto `64px`, fondo `#18181C`, borde superior `1px #2E2E38`, sombra `0 -4px 20px rgba(0, 0, 0, 0.4)`.
* **Botón play:** círculo `38px` con el degradado `#6366F1 → #8B5CF6`.
* **Progreso:** pista `#27272A` de `6px`, radio `3px`, relleno con el degradado `#6366F1 → #EC4899`.
* **Botones secundarios:** transparentes, texto `--text-muted`; activo (aleatorio) en morado con fondo `rgba(139, 92, 246, 0.15)`.

### 4.8 Movimiento

* Transiciones de color y fondo: `0.15s–0.2s ease`.
* Cambio de vista: fundido con desplazamiento vertical de `8px`, `0.25s ease-out`.
* Hover de carátulas: `scale(1.2)` en tablas, `scale(1.06)` en el reproductor.

---

## 5. Especificaciones para PWA y Móvil

* **Barra de Estado en iOS:** `black-translucent` sobre el fondo `--bg-color`.
* **Icono de Aplicación:** fondo sólido `#121212` con la etiqueta morada centrada y el punto interior rellenado en blanco puro `#FFFFFF` (sin transparencias).
* **Márgenes de página:** `12px` en móvil, `28px` a partir de `768px`.
* **Tablas en móvil:** por debajo de `768px` la tabla se sustituye por tarjetas de pista (fondo `--surface-color`, radio `12px`, carátula `52px`); la seleccionada usa `#2F2643` con borde morado.
* **Filtros en móvil:** hoja inferior (bottom sheet) con radio superior `18px`, borde `--border-highlight` y asa de `36×4px`.
* **Rejilla de gráficos:** 1 columna en móvil, 2 columnas a partir de `1024px`.

---

## 6. Accesibilidad

* Texto secundario ajustado para contraste ≥ 4.5:1 (WCAG AA) sobre `--bg-color` y `--surface-color`: no oscurecer `--text-muted` ni `--text-subtle`.
* Áreas táctiles de al menos `36px`.
* El color nunca es el único indicador: los estados de salud llevan icono (`✓`, `⚠`, `✕`) además del color.

---

## 7. Traducción a Escritorio (CustomTkinter / Tkinter)

Los tokens de la sección 3 viven en `src/theme.py`, que es la única fuente de color de la aplicación de escritorio:

| Token CSS | Constante en `theme.py` |
| :--- | :--- |
| `--bg-color` | `BG_MAIN` |
| `--surface-color` | `BG_CARD` |
| `--surface-hover` | `BG_CARD_HOVER` |
| `--input-bg` | `BG_INPUT` |
| `--row-even` | `BG_CARD_ZEBRA` |
| `--border-color` | `BORDER_QUIET` |
| `--border-highlight` | `BORDER_FOCUS` |
| `--primary-purple` / `--primary-hover` | `PRIMARY` / `PRIMARY_HOVER` |
| `--text-main` / `--text-muted` / `--text-subtle` | `TEXT_MAIN` / `TEXT_MUTED` / `TEXT_SUBTLE` |

Limitaciones conocidas de Tk y cómo se resuelven:

* **Fuente:** Inter no se incluye; se usa `Segoe UI` (y `Segoe UI Black` para el KPI). Solo hay pesos `normal`/`bold`: los pesos intermedios se aproximan a `bold`.
* **Letter-spacing:** no existe; en títulos en MAYÚSCULAS se aproxima intercalando espacios finos (U+200A).
* **Degradados, sombras y halos:** Tk no los soporta. Los degradados imprescindibles (tarjeta KPI, anillo de salud) se generan como imagen con Pillow; las sombras y halos se omiten.
* **Borde izquierdo de la fila seleccionada:** `ttk.Treeview` no permite bordes por fila; la selección usa solo el fondo `#2F2643`.
* **Color de cabecera por columna:** `ttk.Treeview` aplica el mismo estilo a todas las cabeceras; la columna ordenada se indica con la flecha ▲/▼.
* **Hover de botones secundarios:** CustomTkinter solo cambia el fondo en hover; el cambio de color de texto y borde se hace con eventos `<Enter>`/`<Leave>`.
* **Iconos de línea:** en lugar de los SVG de la PWA se usa la fuente de iconos del sistema (Segoe Fluent Icons / Segoe MDL2 Assets) con los mismos colores.
