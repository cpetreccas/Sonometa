# Guía de Estilos y Sistema de Diseño — Sonometa UI

Este documento define la identidad visual oficial, la paleta de colores, la tipografía y las reglas de diseño para la plataforma **Sonometa** (Escritorio y Web PWA). Sigue estas directrices estrictamente para mantener una coherencia perfecta entre plataformas.

---

## 1. Principios Fundamentales y Estética

* **Filosofía Dark Mode First (`#121212`):** Estética profesional y corporativa inspirada en software de audio para DJ (como Traktor, rekordbox o Spotify).
* **Identidad de Marca:** Fondos oscuros profundos combinados con acentos morados corporativos (`#8B5CF6`) y una presentación de datos limpia e hiperlegible.
* **Diseño de Componentes:** Esquinas redondeadas, bordes divisores sutiles (`#27272A`) y un alto contraste para la gestión densa de metadatos de audio.

---

## 2. Tipografía

* **Familia Tipográfica Principal:** `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
* **Importación desde Google Fonts:**

  ```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  ```

### Jerarquía y Escala Tipográfica

| Elemento | Tamaño | Peso (`font-weight`) | Altura de Línea | Variable de Color |
| :--- | :--- | :--- | :--- | :--- |
| **KPI / Estadísticas Destacadas** | `28px` (`1.75rem`) | Bold (`700`) | `1.2` | `--text-main` |
| **H1 / Títulos Principales** | `20px` (`1.25rem`) | SemiBold (`600`) | `1.3` | `--text-main` |
| **H2 / Títulos de Tarjetas** | `16px` (`1rem`) | SemiBold (`600`) | `1.4` | `--text-main` |
| **Cuerpo / Celdas de Tabla** | `14px` (`0.875rem`) | Regular (`400`) / Medium (`500`) | `1.5` | `--text-main` |
| **Metadatos / Insignias (Badges)** | `12px` (`0.75rem`) | Regular (`400`) | `1.4` | `--text-muted` |
| **Etiquetas Micro / Auxiliares** | `10px` (`0.625rem`) | Medium (`500`) | `1.2` | `--text-subtle` |

---

## 3. Paleta de Colores y Variables CSS

Copia y pega estas variables personalizadas en tu archivo CSS global (`styles.css` / `variables.css`):

```css
:root {
  /* Tipografía */
  --font-main: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

  /* Superficies Base */
  --bg-main: #121212;          /* Fondo general de la aplicación */
  --bg-card: #18181B;          /* Tarjetas, modales, barra lateral y paneles elevados */
  --bg-card-hover: #27272A;    /* Estado hover para tarjetas y filas de lista */
  --bg-input: #18181B;         /* Fondo de campos de entrada (inputs) */

  /* Bordes y Divisores */
  --border-quiet: #27272A;     /* Líneas divisoras sutiles y bordes de tabla/tarjetas */
  --border-focus: #3F3F46;     /* Bordes para elementos enfocados o activos */

  /* Acentos de Marca */
  --primary: #8B5CF6;          /* Morado corporativo principal */
  --primary-hover: #7C3AED;    /* Morado más oscuro para estado hover en botones */
  --primary-light: #A78BFA;    /* Morado claro para texto activo, iconos y remixes */
  --brand-gradient: linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%);

  /* Colores de Texto */
  --text-main: #F4F4F5;        /* Texto principal de alto contraste */
  --text-muted: #A1A1AA;       /* Texto secundario (artistas, cabeceras de tabla) */
  --text-subtle: #71717A;      /* Textos secundarios menores, placeholders, pie de página */

  /* Estados e Indicadores de Salud de la Colección */
  --status-success: #22C55E;   /* Verde - 100% completo / Salud excelente */
  --status-warning: #F59E0B;   /* Ámbar - Falta algún metadato secundario */
  --status-danger: #EF4444;    /* Rojo - Falta metadato crítico (sin género o carátula) */

  /* Escala Monocromática para Gráficos de Valoración */
  --chart-5-star: #8B5CF6;
  --chart-4-star: #7C3AED;
  --chart-3-star: #6D28D9;
  --chart-2-star: #4C1D95;
  --chart-1-star: #2E1065;
  --chart-0-star: #3F3F46;
}
```

---

## 4. Patrones de Diseño de Componentes

### 1. Tablas de Datos y Listas de Pistas

* **Contenedor:** Fondo `--bg-card` (`#18181B`), borde `--border-quiet` (`#27272A`).
* **Cabecera de Tabla:** Fija arriba (sticky), texto `--text-muted` (`#A1A1AA`), `12px` en mayúsculas con `font-weight: 600`.
* **Efecto Hover en Filas:** `--bg-card-hover` (`#27272A`).
* **Fila Seleccionada / Activa:** Fondo `--primary` (`#8B5CF6`), texto `#FFFFFF`.
* **Campo "Remix / Versión":** Centrado o debajo del título con el color `--primary-light` (`#A78BFA`).

### 2. Botones y Controles

* **Botón Principal:** Fondo `--primary` (`#8B5CF6`), texto `#FFFFFF`, hover `--primary-hover` (`#7C3AED`), radio de borde `8px` (`rounded-lg`).
* **Botón Secundario / Transparente:** Fondo `transparent`, borde `1px solid --border-quiet` (`#27272A`), texto `--text-main` (`#F4F4F5`), hover `--bg-card-hover` (`#27272A`).
* **Botones con Icono Solamente:** Redondos o cuadrados con esquinas de `8px`, área táctil mínima de `36px` a `40px`.

### 3. Tarjetas y Paneles Elevaros

* **Fondo:** `--bg-card` (`#18181B`).
* **Borde:** `1px solid --border-quiet` (`#27272A`).
* **Radio de Esquinas:** `12px` (`rounded-xl`).
* **Relleno Interno (Padding):** `16px` o `20px`.

### 4. Gráficos y Visualización de Datos

* **Valoraciones con Estrellas:** Color morado corporativo o gris apagado (`#3F3F46`) para canciones sin valorar.
* **Gráficos de Barras (Distribución por Valoración):** Utilizar siempre la escala monocromática de morados (`--chart-5-star` hasta `--chart-0-star`) en lugar de colores variados.
* **Anillos de Salud / Salud de la Colección:** Usar el degradado de marca `--brand-gradient` (`#8B5CF6` a `#EC4899`) únicamente para la nota global.

---

## 5. Especificaciones para PWA y Móvil

* **Barra de Estado en iOS:** `black-translucent` sobre el fondo `--bg-main` (`#121212`).
* **Icono de Aplicación:** Fondo sólido `#121212` con la etiqueta morada centrada y el punto interior rellenado en blanco puro `#FFFFFF` (sin transparencias).
* **Reproductor Inferior (Player Bar):** Panel fijo en la parte inferior, fondo `--bg-card` (`#18181B`) con borde superior `--border-quiet` (`#27272A`).