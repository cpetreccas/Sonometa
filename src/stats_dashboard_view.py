import math
import tkinter as tk
import tkinter.font as tkfont
from types import SimpleNamespace

import customtkinter as ctk
import matplotlib
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.ticker import MaxNLocator

import theme

# Misma tipografía en los gráficos que en el resto de la UI (Segoe UI como
# equivalente de Inter, ver theme.py). Afecta también a health_dashboard_view.py.
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = [theme.FONT_FAMILY, "DejaVu Sans"]

# Paleta alineada con web/js/dashboard.js (COLORS) y la Guía de Estilos Sonometa.
# Reutilizada también por health_dashboard_view.py (radar/anillo de score).
CHART_COLORS = [
    "#8B5CF6",  # Purple Primary
    "#6366F1",  # Indigo Accent
    "#A855F7",  # Purple Light
    "#EC4899",  # Pink Accent
    "#3B82F6",  # Blue Secondary
    "#7C3AED",  # Purple Dark Hover
    "#C084FC",  # Violet Soft
    "#38BDF8",  # Sky Blue
    "#64748B",  # Neutral Muted
]

# Escala monocromática de la guía (sección 4.4) para la distribución por valoración:
# nunca colores variados, del morado corporativo (5★) al más oscuro (1★). Sin
# valorar (0★) usa el morado corporativo al 35% de opacidad sobre BG_CARD (#24242A) en
# vez del gris --chart-0-star, para que todas las barras sean moradas (igual en la PWA).
RATING_COLORS = {
    5: "#8B5CF6",
    4: "#7C3AED",
    3: "#6D28D9",
    2: "#4C1D95",
    1: "#2E1065",
    0: "#483871",
}

GRID_COLOR = (1, 1, 1, 0.08)

# Debounce del redibujado de matplotlib al redimensionar (ver _embed_canvas).
RESIZE_DEBOUNCE_MS = 180

# CTkScrollableFrame usa yscrollincrement=1px en Windows y desplaza ~20 unidades
# por muesca de rueda (ver ctk_scrollable_frame._mouse_wheel_all) => 20px por clic,
# muy poco frente a tarjetas de 250-300px de alto. Se sube solo el incremento de
# ESTE canvas (no toca el binding global de CustomTkinter ni otras vistas).
SCROLL_INCREMENT_PX = 5

# Fondo de tarjeta - plano e inmutable (no cambia con el ratón).
CARD_BG = theme.BG_CARD

# Línea divisoria bajo títulos de tarjeta y cabeceras de tabla: el color de borde de
# las tarjetas (PWA --border-color), con contraste real sobre BG_CARD.
DIVIDER_COLOR = theme.BORDER_QUIET

# Anatomía de tarjeta calcada de la PWA móvil: título, gráfico a todo el ancho y
# tabla con scroll propio debajo. Alto fijo, independiente del volumen de datos,
# para que dos filas de tarjetas quepan sin scroll a 1080p. Valores en px lógicos
# (se escalan con el factor de CustomTkinter donde se usan widgets Tk puros).
CARD_HEIGHT = 374
CARD_PADDING = 14
CHART_HEIGHT = 136
TABLE_ROW_HEIGHT = 28
TABLE_HEADER_HEIGHT = 24
TABLE_COUNT_COL_W = 72     # borde derecho de "cant." respecto al borde derecho de la tabla
TABLE_PCT_COL_W = 4        # borde derecho de "%"
BAR_MAX_WIDTH_PX = 40      # equivalente a maxBarThickness de Chart.js en la PWA

# Nº de columnas de la rejilla de tarjetas según el ancho disponible (px lógicos).
GRID_BREAKPOINTS = ((1500, 3), (900, 2), (0, 1))

# Cross-filtering: mapeo de key_name de las tarjetas de distribución a la columna
# real de la grilla, y bucket "vacío" por defecto cuando aplica (Album/Genre/Publisher).
KEY_TO_COLUMN = {"album": "Album", "genre": "Genre", "publisher": "Publisher", "year": "Year", "rating": "Rating"}
DEFAULT_BUCKET_LABELS = {"album": "Sin Álbum", "genre": "Sin Género", "publisher": "Sin Etiqueta"}


def _clean_text(value, default_label):
    text = str(value).strip() if value is not None else ""
    return text if text else default_label


def _parse_rating(value):
    text = str(value or "").strip()
    if not text:
        return 0
    digits = "".join(ch for ch in text if ch.isdigit())
    return int(digits) if digits else 0


def _parse_cues(value):
    text = str(value or "").strip()
    return int(text) if text.isdigit() else 0


def _has_cover(value):
    return str(value or "").strip().lower() in ("sí", "si", "yes", "true", "1")


def _rating_label(stars):
    """Mismo texto que la PWA: "0 ★" para sin valorar, "★★★" para 3 estrellas."""
    return "0 ★" if stars == 0 else "★" * stars


def _count_by(tracks, key, default_label, sort_mode="desc"):
    """Réplica de buildChart() en dashboard.js: agrupa por campo y ordena."""
    counts = {}
    for t in tracks:
        label = _clean_text(t.get(key, ""), default_label)
        counts[label] = counts.get(label, 0) + 1

    if sort_mode == "asc":
        labels = sorted(counts.keys(), key=lambda l: (l == default_label, l))
    else:
        labels = sorted(counts.keys(), key=lambda l: counts[l], reverse=True)

    return labels, [counts[l] for l in labels]


def _smooth_series(values, samples_per_segment=12):
    """Interpolación cúbica monótona (Fritsch-Carlson) sobre índices 0..n-1: curva
    suavizada como la `tension` de Chart.js en la PWA, pero sin rebasar los puntos
    reales (nunca baja de 0 ni inventa picos que no existen)."""
    n = len(values)
    y = np.asarray(values, dtype=float)
    if n < 3:
        return np.arange(n, dtype=float), y

    d = np.diff(y)
    m = np.empty(n)
    m[0], m[-1] = d[0], d[-1]
    m[1:-1] = (d[:-1] + d[1:]) / 2
    m[1:-1][d[:-1] * d[1:] <= 0] = 0
    for k in range(n - 1):
        if d[k] == 0:
            m[k] = m[k + 1] = 0
        else:
            a, b = m[k] / d[k], m[k + 1] / d[k]
            s = a * a + b * b
            if s > 9:
                t = 3 / math.sqrt(s)
                m[k], m[k + 1] = t * a * d[k], t * b * d[k]

    t = np.linspace(0, 1, samples_per_segment, endpoint=False)
    h00 = 2 * t**3 - 3 * t**2 + 1
    h10 = t**3 - 2 * t**2 + t
    h01 = -2 * t**3 + 3 * t**2
    h11 = t**3 - t**2
    xs, ys = [], []
    for k in range(n - 1):
        xs.append(k + t)
        ys.append(h00 * y[k] + h10 * m[k] + h01 * y[k + 1] + h11 * m[k + 1])
    xs.append([n - 1])
    ys.append([y[-1]])
    return np.concatenate(xs), np.concatenate(ys)


def _style_axes(ax):
    ax.set_facecolor("none")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=theme.TEXT_MUTED, labelsize=8, length=0, pad=4)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
    ax.grid(True, axis="y", color=GRID_COLOR[:3], alpha=GRID_COLOR[3])
    ax.set_axisbelow(True)


def _set_nice_ylim(ax, vmax):
    """Eje Y de 0 a la primera marca >= máximo (como Chart.js): la barra o el pico
    más alto nunca sobresale por encima de la última línea de la cuadrícula."""
    ticks = MaxNLocator(nbins=5, integer=True).tick_values(0, max(vmax, 1))
    top = next((t for t in ticks if t >= vmax), ticks[-1])
    ax.set_ylim(0, top)


def _apply_pixel_margins(fig, left, right, top, bottom):
    """subplots_adjust en píxeles en vez de fracciones: los márgenes para las
    etiquetas de los ejes no cambian al ensanchar la tarjeta."""
    w, h = fig.get_size_inches() * fig.dpi
    if w <= left + right + 10 or h <= top + bottom + 10:
        return
    fig.subplots_adjust(left=left / w, right=1 - right / w, top=1 - top / h, bottom=bottom / h)


def _new_figure(width_px=340, height_px=220, polar=False):
    dpi = 100
    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_alpha(0)
    ax = fig.add_subplot(111, polar=polar)
    ax.set_facecolor("none")
    fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.18)
    return fig, ax


def _figure_matches_size(fig, width, height):
    w, h = fig.get_size_inches() * fig.dpi
    return abs(w - width) < 1 and abs(h - height) < 1


def _embed_canvas(parent, fig, debounce_ms=RESIZE_DEBOUNCE_MS, bg=theme.BG_CARD_HOVER):
    """Crea el FigureCanvasTkAgg de `fig`. El backend de matplotlib redimensiona Y
    REDIBUJA la figura en cada <Configure> de su propio widget (auto-resize al
    tamaño del contenedor) — arrastrar el borde de la ventana dispara docenas de
    esos eventos por segundo, uno por cada gráfico visible, lo que se nota como
    lag/tirones. Se sustituye ese binding único por una versión debounced: solo se
    redimensiona/redibuja una vez, `debounce_ms` después de que el usuario deja de
    mover el ratón, en vez de en cada micro-cambio intermedio. El resto del
    comportamiento (motion/leave para tooltips, etc., bindeados aparte por
    matplotlib) no se toca. `bg` por defecto mantiene el tono usado por
    health_dashboard_view.py (anillo de score / radar); las tarjetas de
    distribución de este archivo pasan CARD_BG explícitamente para que el canvas
    se funda con la tarjeta en vez de verse como un recuadro aparte.

    Si el <Configure> llega con el mismo tamaño que ya tiene la figura (p. ej. al
    volver a mostrar una pestaña, o porque la vista ya la dimensionó a mano) se
    ignora: el resize de matplotlib BORRA la imagen del canvas y la repinta en
    diferido, lo que se veía como gráficos en blanco que aparecían a trozos."""
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    widget = canvas.get_tk_widget()
    widget.configure(bg=bg, highlightthickness=0)

    original_resize = canvas.resize
    pending = {"job": None}

    def _do_resize(event):
        pending["job"] = None
        if widget.winfo_exists() and not _figure_matches_size(fig, event.width, event.height):
            original_resize(event)

    def _on_configure(event):
        if pending["job"] is not None:
            widget.after_cancel(pending["job"])
        pending["job"] = widget.after(debounce_ms, lambda: _do_resize(event))

    widget.unbind("<Configure>")
    widget.bind("<Configure>", _on_configure)

    return canvas, widget


def _bind_clickable(widget, callback):
    """Bindea clic + cursor de mano sobre un widget y sus hijos directos.
    Compartido por los chips de diagnóstico/alerta de salud
    (health_dashboard_view.py). Sin efecto hover asociado — solo detecta el clic."""
    widget.configure(cursor="hand2")
    widget.bind("<Button-1>", lambda e: callback())
    for child in widget.winfo_children():
        child.configure(cursor="hand2")
        child.bind("<Button-1>", lambda e: callback())


def _set_combo_filter(app, field, value):
    """Aplica un filtro sobre el motor de la grilla (panel de filtro avanzado,
    src/advanced_filter_panel.py) SIN cambiar de pestaña — quien llama decide si
    navega o no. Compartido por StatsDashboardView (leyendas, se queda en
    Dashboard) y HealthDashboardView (chips de diagnóstico, vuelve a Colección)."""
    panel = app.advanced_filter_panel
    panel.combo_vars[field].set(value)
    panel._trigger_filter()
    if not panel.winfo_ismapped():
        panel.toggle_panel()
    app.logger.info(f"Filtro aplicado desde el dashboard: {field} = {value}.")


def _set_toggle_filter(app, toggle_key):
    panel = app.advanced_filter_panel
    panel.toggle_vars[toggle_key].set(True)
    panel._trigger_filter()
    if not panel.winfo_ismapped():
        panel.toggle_panel()
    app.logger.info(f"Filtro aplicado desde el dashboard: {toggle_key}.")


class _ChartTooltip:
    """Tooltip flotante compartido por todos los gráficos de una vista: un único
    Toplevel reutilizado (crear/destruir una ventana en cada movimiento de ratón
    sería caro), fondo oscuro y borde morado, reposicionado y con el texto
    actualizado según qué porción/barra/punto detecta el hit-test de cada gráfico."""

    def __init__(self, master):
        self._master = master
        self._win = None
        self._label = None

    def _ensure_window(self):
        if self._win is not None and self._win.winfo_exists():
            return
        self._win = tk.Toplevel(self._master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        frame = tk.Frame(self._win, bg=theme.BG_CARD, highlightbackground=theme.PRIMARY, highlightthickness=1, bd=0)
        frame.pack()
        self._label = tk.Label(
            frame, bg=theme.BG_CARD, fg=theme.TEXT_MAIN,
            font=(theme.FONT_FAMILY, 10), padx=8, pady=4
        )
        self._label.pack()

    def show(self, x_root, y_root, text):
        try:
            self._ensure_window()
            self._label.configure(text=text)
            self._win.geometry(f"+{x_root + 14}+{y_root + 14}")
            self._win.deiconify()
        except Exception:
            pass

    def hide(self):
        try:
            if self._win is not None and self._win.winfo_exists():
                self._win.withdraw()
        except Exception:
            pass

    def destroy(self):
        try:
            if self._win is not None and self._win.winfo_exists():
                self._win.destroy()
        except Exception:
            pass
        self._win = None


def _show_tooltip_near(tooltip, widget, event, text):
    x_root = widget.winfo_rootx() + int(event.x)
    y_root = widget.winfo_rooty() + int(widget.winfo_height() - event.y)
    tooltip.show(x_root, y_root, text)


def _attach_pie_tooltip(canvas, ax, wedges, labels, values, tooltip, widget):
    def _on_motion(event):
        if event.inaxes != ax:
            tooltip.hide()
            return
        for i, wedge in enumerate(wedges):
            if wedge.contains(event)[0]:
                _show_tooltip_near(tooltip, widget, event, f"{labels[i]}: {values[i]}")
                return
        tooltip.hide()

    motion_cid = canvas.mpl_connect("motion_notify_event", _on_motion)
    leave_cid = canvas.mpl_connect("figure_leave_event", lambda e: tooltip.hide())
    return motion_cid, leave_cid


def _attach_bar_tooltip(canvas, ax, bars, labels, values, tooltip, widget):
    def _on_motion(event):
        if event.inaxes != ax:
            tooltip.hide()
            return
        for i, rect in enumerate(bars):
            if rect.contains(event)[0]:
                _show_tooltip_near(tooltip, widget, event, f"{labels[i]}: {values[i]}")
                return
        tooltip.hide()

    motion_cid = canvas.mpl_connect("motion_notify_event", _on_motion)
    leave_cid = canvas.mpl_connect("figure_leave_event", lambda e: tooltip.hide())
    return motion_cid, leave_cid


def _attach_line_tooltip(canvas, ax, labels, values, tooltip, widget, threshold_px=12):
    def _on_motion(event):
        if event.inaxes != ax or event.x is None:
            tooltip.hide()
            return
        best_i, best_dist = None, threshold_px
        for i, v in enumerate(values):
            px, py = ax.transData.transform((i, v))
            dist = ((px - event.x) ** 2 + (py - event.y) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_i = i
        if best_i is not None:
            _show_tooltip_near(tooltip, widget, event, f"{labels[best_i]}: {values[best_i]}")
        else:
            tooltip.hide()

    motion_cid = canvas.mpl_connect("motion_notify_event", _on_motion)
    leave_cid = canvas.mpl_connect("figure_leave_event", lambda e: tooltip.hide())
    return motion_cid, leave_cid


class _LegendTable:
    """Tabla nombre / cant. / % de cada tarjeta, dibujada sobre un único tk.Canvas
    (texto + rectángulos) en vez de un CTkFrame + 4 CTkLabel por fila: con los
    datos de producción una tarjeta puede tener 60+ filas, y cada widget de
    CustomTkinter es a su vez un canvas con su propio redibujado diferido — era lo
    que hacía que las leyendas aparecieran como bloques vacíos antes de rellenarse.
    Aquí actualizar los datos es borrar y redibujar items de un canvas: instantáneo
    y atómico. Scroll propio (rueda + barra fina) como la tabla de la PWA."""

    def __init__(self, parent, scale, on_click):
        self._on_click = on_click
        self._rows = []  # (label, count, pct_text, color)
        self._s = scale
        self._row_h = round(TABLE_ROW_HEIGHT * scale)

        self._font_head = tkfont.Font(family=theme.FONT_FAMILY, size=-round(11 * scale), weight="bold")
        self._font_row = tkfont.Font(family=theme.FONT_FAMILY, size=-round(12 * scale))
        self._font_count = tkfont.Font(family=theme.FONT_FAMILY, size=-round(12 * scale), weight="bold")
        self._font_pct = tkfont.Font(family=theme.FONT_FAMILY, size=-round(11 * scale))

        self.frame = tk.Frame(parent, bg=CARD_BG, bd=0, highlightthickness=0)
        self._header = tk.Canvas(
            self.frame, height=round(TABLE_HEADER_HEIGHT * scale), bg=CARD_BG, bd=0, highlightthickness=0
        )
        self._header.pack(fill="x")
        tk.Frame(self.frame, height=1, bg=DIVIDER_COLOR, bd=0).pack(fill="x")

        body = tk.Frame(self.frame, bg=CARD_BG, bd=0, highlightthickness=0)
        body.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(
            body, bg=CARD_BG, bd=0, highlightthickness=0,
            yscrollincrement=self._row_h
        )
        self._scrollbar = ctk.CTkScrollbar(
            body, orientation="vertical", width=8, command=self._canvas.yview,
            fg_color=CARD_BG, bg_color=CARD_BG,
            button_color="#52525B", button_hover_color=theme.TEXT_SUBTLE
        )
        self._canvas.configure(yscrollcommand=self._on_yscroll)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scrollbar_visible = False
        self._hover_index = None

        self._canvas.bind("<Configure>", lambda e: self._render())
        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", lambda e: self._set_hover(None))
        self._canvas.bind("<Button-1>", self._on_button)
        self._canvas.bind("<MouseWheel>", self._on_wheel)

    def set_rows(self, rows):
        self._rows = rows
        self._hover_index = None
        self._canvas.yview_moveto(0)
        self._render()

    # --- Dibujo -------------------------------------------------------
    def _columns(self, width):
        s = self._s
        x_count = width - round(TABLE_COUNT_COL_W * s)
        x_pct = width - round(TABLE_PCT_COL_W * s)
        x_name = round(18 * s)
        name_max = x_count - round(44 * s) - x_name
        return x_name, x_count, x_pct, name_max

    def _truncate(self, text, max_px):
        if max_px <= 0 or self._font_row.measure(text) <= max_px:
            return text
        while text and self._font_row.measure(text + "…") > max_px:
            text = text[:-1]
        return text + "…"

    def _render(self):
        c = self._canvas
        width = c.winfo_width()
        if width <= 1:
            return
        s = self._s
        row_h = self._row_h
        x_name, x_count, x_pct, name_max = self._columns(width)

        # Cabecera alineada con las columnas del cuerpo (que puede ser más estrecho
        # que el marco si la barra de scroll está visible).
        h = self._header
        h.delete("all")
        hy = h.winfo_reqheight() / 2
        h.create_text(0, hy, text="nombre", anchor="w", fill=theme.TEXT_MUTED, font=self._font_head)
        h.create_text(x_count, hy, text="cant.", anchor="e", fill=theme.TEXT_MUTED, font=self._font_head)
        h.create_text(x_pct, hy, text="%", anchor="e", fill=theme.TEXT_MUTED, font=self._font_head)

        c.delete("all")
        c.create_rectangle(0, 0, 0, 0, fill=theme.BG_CARD_HOVER, outline="", state="hidden", tags="hover")
        swatch = round(4 * s)
        for i, (label, count, pct_text, color) in enumerate(self._rows):
            y0 = i * row_h
            yc = y0 + row_h / 2
            c.create_rectangle(
                round(2 * s), yc - swatch, round(2 * s) + 2 * swatch, yc + swatch, fill=color, outline=""
            )
            c.create_text(
                x_name, yc, text=self._truncate(label, name_max), anchor="w",
                fill=theme.TEXT_MAIN, font=self._font_row
            )
            c.create_text(x_count, yc, text=str(count), anchor="e", fill=theme.TEXT_ON_PRIMARY, font=self._font_count)
            c.create_text(x_pct, yc, text=pct_text, anchor="e", fill=theme.TEXT_MUTED, font=self._font_pct)
            c.create_line(0, y0 + row_h - 1, width, y0 + row_h - 1, fill=theme.BORDER_QUIET)

        content_h = len(self._rows) * row_h
        c.configure(scrollregion=(0, 0, width, content_h))
        self._update_scrollbar(content_h)
        if self._hover_index is not None:
            self._set_hover(self._hover_index)

    def _update_scrollbar(self, content_h):
        needs = content_h > self._canvas.winfo_height() + 1
        if needs and not self._scrollbar_visible:
            self._scrollbar.pack(side="right", fill="y", padx=(round(4 * self._s), 0), before=self._canvas)
            self._scrollbar_visible = True
        elif not needs and self._scrollbar_visible:
            self._scrollbar.pack_forget()
            self._scrollbar_visible = False

    def _on_yscroll(self, first, last):
        self._scrollbar.set(first, last)

    # --- Interacción --------------------------------------------------
    def _row_at(self, y):
        i = int(self._canvas.canvasy(y) // self._row_h)
        return i if 0 <= i < len(self._rows) else None

    def _set_hover(self, index):
        self._hover_index = index
        c = self._canvas
        if index is None:
            c.itemconfigure("hover", state="hidden")
            c.configure(cursor="")
            return
        y0 = index * self._row_h
        c.coords("hover", 0, y0, c.winfo_width(), y0 + self._row_h - 1)
        c.itemconfigure("hover", state="normal")
        c.tag_lower("hover")
        c.configure(cursor="hand2")

    def _on_motion(self, event):
        index = self._row_at(event.y)
        if index != self._hover_index:
            self._set_hover(index)

    def _on_button(self, event):
        index = self._row_at(event.y)
        if index is not None:
            self._on_click(self._rows[index][0])

    def _on_wheel(self, event):
        # "break" solo si la tabla tiene algo que desplazar: así la rueda sobre una
        # tabla corta sigue moviendo el scroll general de la vista (bind_all de
        # CTkScrollableFrame), y sobre una larga no mueve ambos a la vez.
        if not self._scrollbar_visible or not event.delta:
            return None
        steps = -2 if event.delta > 0 else 2
        self._canvas.yview_scroll(steps, "units")
        self._on_motion(event)
        return "break"


def _autohide_scrollbar(scrollable):
    """La barra de scroll de un CTkScrollableFrame solo aparece cuando el contenido
    no cabe (CustomTkinter la muestra siempre, aunque el thumb ocupe todo el alto).
    Compartido por el Dashboard y la vista de Salud."""
    scrollbar = scrollable._scrollbar
    canvas = scrollable._parent_canvas

    def _on_yscroll(first, last):
        scrollbar.set(first, last)
        if float(first) <= 0.0 and float(last) >= 1.0:
            scrollbar.grid_remove()
        else:
            scrollbar.grid()

    canvas.configure(yscrollcommand=_on_yscroll)


def _build_card_shell(parent, title, scale, height=None):
    """Tarjeta estándar de las vistas de estadísticas (guía, sección 4.3): fondo
    BG_CARD, borde 1px, radio 12, título pequeño en mayúsculas espaciadas y línea
    divisoria. Con `height` la tarjeta tiene alto fijo. Devuelve (card, content):
    `content` es el contenedor donde va el cuerpo, bajo el divisor."""
    kwargs = {"height": height} if height else {}
    card = ctk.CTkFrame(
        parent, fg_color=CARD_BG, corner_radius=theme.RADIUS_CARD,
        border_width=1, border_color=theme.BORDER_QUIET, **kwargs
    )
    if height:
        card.pack_propagate(False)

    content = ctk.CTkFrame(card, fg_color=CARD_BG, corner_radius=0)
    content.pack(fill="both", expand=True, padx=CARD_PADDING, pady=CARD_PADDING)

    ctk.CTkLabel(
        content, text=_tracked_title(title), anchor="w", height=18,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold"),
        text_color=theme.TEXT_MUTED
    ).pack(fill="x")
    tk.Frame(content, height=1, bg=DIVIDER_COLOR, bd=0).pack(fill="x", pady=(round(10 * scale), 0))
    return card, content


class _LoadingOverlay:
    """Capa que tapa una vista mientras se prepara ("Preparando …" + spinner), para
    no enseñar nunca gráficos a medio dibujar o redimensionar."""

    def __init__(self, parent, scale, text):
        self._parent = parent
        self.frame = ctk.CTkFrame(parent, fg_color=theme.BG_MAIN, corner_radius=0)
        box = ctk.CTkFrame(self.frame, fg_color=theme.BG_MAIN, corner_radius=0)
        box.place(relx=0.5, rely=0.4, anchor="center")

        size = round(36 * scale)
        self._spinner = tk.Canvas(box, width=size, height=size, bg=theme.BG_MAIN, bd=0, highlightthickness=0)
        self._spinner.pack()
        pad = round(3 * scale)
        self._spinner.create_oval(pad, pad, size - pad, size - pad, outline=theme.BORDER_QUIET, width=pad)
        self._arc = self._spinner.create_arc(
            pad, pad, size - pad, size - pad, start=90, extent=100,
            style="arc", outline=theme.PRIMARY, width=pad
        )
        ctk.CTkLabel(
            box, text=text, text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        ).pack(pady=(theme.SPACE_SM, 0))

        self._angle = 90
        self._job = None

    def show(self):
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frame.lift()
        if self._job is None:
            self._spin()

    def hide(self):
        self.frame.place_forget()
        if self._job is not None:
            self._parent.after_cancel(self._job)
            self._job = None

    def _spin(self):
        self._angle = (self._angle - 12) % 360
        self._spinner.itemconfigure(self._arc, start=self._angle)
        self._job = self._parent.after(30, self._spin)


# (key_name, título, tipo de gráfico) — mismo orden y textos que la PWA móvil.
CHART_DEFS = [
    ("album", "Distribución por Álbum", "pie"),
    ("genre", "Distribución por Género", "pie"),
    ("publisher", "Distribución por Etiqueta", "bar"),
    ("year", "Distribución por Año de Lanzamiento", "line"),
    ("rating", "Distribución por Valoración", "bar"),
]


def _tracked_title(title):
    """Mayúsculas con espaciado entre letras (letter-spacing de la PWA): Tk no lo
    soporta, se aproxima intercalando espacios finos (U+200A)."""
    return "\u200A".join(title.upper())


def _format_count(n):
    """Como toLocaleString('es-ES') en la PWA: separador de miles solo desde 10.000."""
    return f"{n:,}".replace(",", ".") if n >= 10000 else str(n)


def _hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


class _HeroCounter:
    """Contador destacado de la cabecera del dashboard, calcado del KPI de la PWA:
    tarjeta con degradado vertical teñido de morado, línea superior en color
    corporativo que se desvanece hacia los bordes, número grande y etiqueta en
    mayúsculas espaciadas. Tk no tiene degradados ni esquinas redondeadas en un
    canvas, así que el fondo se genera con Pillow (supersampling x3 para suavizar
    las esquinas) y solo cuando cambia el ancho; número y etiqueta son texto de
    canvas, así que actualizar la cifra no regenera la imagen."""

    HEIGHT = 96
    RADIUS = 12
    SUPERSAMPLE = 3
    TOP_COLOR = "#2D243A"          # degradado de .kpi-card en la PWA
    BOTTOM_COLOR = theme.BG_CARD
    BORDER_COLOR = theme.BORDER_FOCUS  # PWA --border-highlight

    def __init__(self, parent, scale, label_text):
        self._s = scale
        self._height = round(self.HEIGHT * scale)
        self.canvas = tk.Canvas(parent, height=self._height, bg=theme.BG_MAIN, bd=0, highlightthickness=0)
        self._bg_image = None
        self._bg_width = None
        self._resize_job = None

        family = "Segoe UI Black" if "Segoe UI Black" in tkfont.families() else theme.FONT_FAMILY
        self._font_number = tkfont.Font(family=family, size=-round(40 * scale), weight="bold")
        self._font_label = tkfont.Font(family=theme.FONT_FAMILY, size=-round(11 * scale), weight="bold")

        self._bg_item = self.canvas.create_image(0, 0, anchor="nw")
        self._number_item = self.canvas.create_text(
            0, 0, text="0", fill=theme.TEXT_ON_PRIMARY, font=self._font_number, anchor="center"
        )
        self._label_item = self.canvas.create_text(
            0, 0, text=_tracked_title(label_text), fill=theme.TEXT_MUTED, font=self._font_label, anchor="center"
        )
        self.canvas.bind("<Configure>", self._on_configure)

    def set_value(self, n):
        self.canvas.itemconfigure(self._number_item, text=_format_count(n))

    def _on_configure(self, event):
        # Texto recolocado al instante; la imagen de fondo, debounced (arrastrar el
        # borde de la ventana dispara muchos <Configure> seguidos).
        self._place_text(event.width)
        if self._resize_job is not None:
            self.canvas.after_cancel(self._resize_job)
        self._resize_job = self.canvas.after(60, self.render_now)

    def _place_text(self, width):
        cx = width / 2
        self.canvas.coords(self._number_item, cx, self._height * 0.43)
        self.canvas.coords(self._label_item, cx, self._height * 0.80)

    def render_now(self):
        self._resize_job = None
        width = self.canvas.winfo_width()
        if width <= 1:
            return
        self._place_text(width)
        if width == self._bg_width:
            return
        self._bg_width = width
        self._bg_image = self._build_background(width, self._height)
        self.canvas.itemconfigure(self._bg_item, image=self._bg_image)

    def _build_background(self, width, height):
        from PIL import Image, ImageDraw, ImageTk

        ss = self.SUPERSAMPLE
        w, h = width * ss, height * ss
        radius = round(self.RADIUS * self._s * ss)
        line_h = max(2 * ss, round(2 * self._s * ss))

        # Degradado vertical del cuerpo de la tarjeta.
        top, bottom = np.array(_hex_rgb(self.TOP_COLOR)), np.array(_hex_rgb(self.BOTTOM_COLOR))
        t = np.linspace(0, 1, h)[:, None]
        column = (top * (1 - t) + bottom * t).astype(np.uint8)
        body = np.repeat(column[:, None, :], w, axis=1)

        # Línea superior morada, opaca en el centro y desvanecida en los extremos.
        x = np.linspace(-1, 1, w)
        alpha = np.clip(1.15 - np.abs(x) ** 3, 0.25, 1.0)[:, None]
        primary = np.array(_hex_rgb(theme.PRIMARY))
        body[:line_h] = (primary * alpha + body[:line_h] * (1 - alpha)).astype(np.uint8)

        card = Image.fromarray(body, "RGB")
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)

        # Borde fino: se pinta el color de borde y encima el cuerpo, 1px más dentro.
        out = Image.new("RGB", (w, h), theme.BG_MAIN)
        border = Image.new("RGB", (w, h), self.BORDER_COLOR)
        out.paste(border, (0, 0), mask)
        inner_mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(inner_mask).rounded_rectangle(
            (ss, ss, w - 1 - ss, h - 1 - ss), radius=max(radius - ss, 0), fill=255
        )
        # La línea superior cubre también el borde superior (como border-top en CSS).
        inner_mask.paste(mask.crop((0, 0, w, line_h)), (0, 0))
        out.paste(card, (0, 0), inner_mask)

        return ImageTk.PhotoImage(out.resize((width, height), Image.LANCZOS), master=self.canvas)


class StatsDashboardView(ctk.CTkFrame):
    """Vista de estadísticas de la colección: gráficas de distribución (álbum,
    género, etiqueta, año, valoración), réplica de escritorio del dashboard de la
    PWA (web/js/dashboard.js). Cada tarjeta copia la anatomía de la versión móvil
    (título, gráfico a todo el ancho, tabla con scroll debajo) y el escritorio solo
    las reparte en una rejilla de 3/2/1 columnas según el ancho. La auditoría de
    salud vive en la pestaña Salud (health_dashboard_view.py). Acotada a la vista
    actual de la grilla (respeta filtros/búsqueda activos). Filtrar desde aquí
    (clic en una fila de tabla) NO cambia de pestaña: el filtro se aplica sobre el
    motor de la grilla y GridPanel.apply_combined_filters llama a self.refresh().

    Pintado sin tirones:
      - La estructura (tarjetas, figuras de matplotlib, tablas) se construye UNA
        vez en __init__; refresh() reutiliza cada Axes y redibuja la tabla sobre
        su canvas.
      - Si los datos y el ancho no han cambiado desde el último pintado, refresh()
        no hace nada: volver a la pestaña es instantáneo.
      - Refresco en sitio (filtro con la pestaña ya visible): todo se dibuja de
        forma síncrona dentro del mismo callback, así Tk pinta el resultado final
        de una vez en vez de gráfico a gráfico.
      - Al mostrar la pestaña con datos nuevos (refresh(reveal=True), desde
        App.switch_view) la geometría aún no está resuelta: se tapa la vista con
        un overlay "Preparando dashboard…", se deja asentar el layout, se
        dimensiona y dibuja cada gráfico a su tamaño final y solo entonces se
        destapa."""

    def __init__(self, app, parent):
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0)
        self.app = app
        self._tooltip = _ChartTooltip(self)
        self._scale = ctk.ScalingTracker.get_widget_scaling(self)

        self._rendered_signature = None
        self._rendered_width = None
        self._pending_data = None
        self._render_generation = 0
        self._grid_columns = None

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=theme.SPACE_SM, pady=theme.SPACE_SM)
        try:
            self.scroll._parent_canvas.configure(yscrollincrement=SCROLL_INCREMENT_PX)
            _autohide_scrollbar(self.scroll)
        except Exception:
            pass

        self._empty_label = ctk.CTkLabel(
            self.scroll, text="No hay pistas visibles en la tabla (revisa los filtros aplicados).",
            text_color=theme.TEXT_SUBTLE, font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY)
        )
        self._hero = _HeroCounter(self.scroll, self._scale, "Pistas en la vista actual")

        self._build_distribution_shell()
        self._overlay = _LoadingOverlay(self, self._scale, "Preparando dashboard…")

        self.refresh()

    def _apply_legend_filter(self, key_name, label):
        field = KEY_TO_COLUMN.get(key_name)
        if not field:
            return
        if key_name in DEFAULT_BUCKET_LABELS and label == DEFAULT_BUCKET_LABELS[key_name]:
            value = "[ Vacío ]"
        elif key_name == "rating":
            stars = 0 if label.startswith("0") else label.count("★")
            value = f"{stars}★"
        else:
            value = label
        _set_combo_filter(self.app, field, value)

    # ------------------------------------------------------------------
    # Construcción (una sola vez)
    # ------------------------------------------------------------------
    def _build_distribution_shell(self):
        # tk.Frame (no CTkFrame): su <Configure> decide cuántas columnas caben.
        self._grid = tk.Frame(self.scroll, bg=theme.BG_MAIN, bd=0, highlightthickness=0)
        self._grid.bind("<Configure>", self._on_grid_configure)

        self._cards = []
        self._chart_slots = {}
        for key_name, title, chart_type in CHART_DEFS:
            card, content = _build_card_shell(self._grid, title, self._scale, height=CARD_HEIGHT)
            self._cards.append(card)
            self._chart_slots[key_name] = self._build_chart_card_shell(content, key_name, chart_type)

        self._layout_cards(3)

    def _build_chart_card_shell(self, content, key_name, chart_type):
        chart_area = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=0, height=CHART_HEIGHT)
        chart_area.pack_propagate(False)
        chart_area.pack(fill="x", pady=(8, 8))

        no_data_label = ctk.CTkLabel(
            chart_area, text="Sin datos", text_color=theme.TEXT_SUBTLE,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        )

        fig, ax = _new_figure(300, CHART_HEIGHT, polar=False)
        # bg=CARD_BG: el propio canvas de matplotlib se pinta del mismo color que la
        # tarjeta, para que no se vea como un recuadro aparte.
        canvas, widget = _embed_canvas(chart_area, fig, bg=CARD_BG)
        widget.pack(fill="both", expand=True)

        table = _LegendTable(content, self._scale, lambda label, k=key_name: self._apply_legend_filter(k, label))
        table.frame.pack(fill="both", expand=True)

        slot = {
            "chart_type": chart_type,
            "fig": fig,
            "ax": ax,
            "canvas": canvas,
            "widget": widget,
            "no_data_label": no_data_label,
            "table": table,
            "bars": None,
            "motion_cid": None,
            "leave_cid": None,
        }
        # Márgenes en px y ancho de barra se recalculan en cada resize de la figura
        # (el ResizeEvent de matplotlib se procesa antes de su redibujado).
        canvas.mpl_connect("resize_event", lambda e, s=slot: self._fit_to_size(s))
        return slot

    # ------------------------------------------------------------------
    # Rejilla responsive
    # ------------------------------------------------------------------
    def _on_grid_configure(self, event):
        logical_width = event.width / self._scale
        columns = next(cols for min_w, cols in GRID_BREAKPOINTS if logical_width >= min_w)
        if columns != self._grid_columns:
            self._layout_cards(columns)

    def _layout_cards(self, columns):
        self._grid_columns = columns
        for col in range(3):
            if col < columns:
                self._grid.grid_columnconfigure(col, weight=1, uniform="cards")
            else:
                self._grid.grid_columnconfigure(col, weight=0, uniform="")
        gap = round(theme.SPACE_SM * self._scale)
        for i, card in enumerate(self._cards):
            card.grid(row=i // columns, column=i % columns, sticky="nsew", padx=gap, pady=gap)

    # ------------------------------------------------------------------
    # Refresco (actualiza datos sobre la estructura ya construida)
    # ------------------------------------------------------------------
    def refresh(self, reveal=False):
        """reveal=True cuando la pestaña se acaba de mostrar (App.switch_view): si
        hay que repintar, se hace tapado por el overlay y por pasos."""
        if not self.winfo_exists():
            return

        self._tooltip.hide()
        self._render_generation += 1

        tracks = self.app.grid_panel.get_visible_tracks_data()
        if not tracks:
            self._overlay.hide()
            self._hero.canvas.pack_forget()
            self._grid.pack_forget()
            self._empty_label.pack(pady=theme.SPACE_XL)
            self._rendered_signature = None
            return

        data = self._compute_chart_data(tracks)
        signature = (len(tracks), repr(data))
        width = self.master.winfo_width()
        if signature == self._rendered_signature and width == self._rendered_width:
            self._overlay.hide()
            return

        self._empty_label.pack_forget()
        self._hero.set_value(len(tracks))
        gap = round(theme.SPACE_SM * self._scale)
        self._hero.canvas.pack(fill="x", padx=gap, pady=(gap, 0))
        self._grid.pack(fill="both", expand=True)
        self._pending_data = (signature, data)

        if reveal:
            self._overlay.show()
            generation = self._render_generation
            self.after(40, lambda: self._render_step(generation, 0))
        else:
            for key_name in data:
                self._render_slot(key_name, data[key_name])
            self._finish_render()

    def _render_step(self, generation, index):
        """Pintado por pasos tras el overlay: un gráfico por vuelta del mainloop,
        para que el spinner siga girando y la geometría termine de asentarse."""
        if generation != self._render_generation or not self.winfo_exists():
            return
        if index == 0:
            self.update_idletasks()
        _, data = self._pending_data
        keys = list(data)
        if index < len(keys):
            self._render_slot(keys[index], data[keys[index]])
            self.after(1, lambda: self._render_step(generation, index + 1))
            return
        # Última pasada: si el layout aún se movió mientras se dibujaba, corregir
        # tamaños antes de destapar (nunca mostrar un gráfico a medio redimensionar).
        self.update_idletasks()
        self._hero.render_now()
        for slot in self._chart_slots.values():
            if self._sync_figure_size(slot):
                slot["canvas"].draw()
        self._finish_render()

    def _finish_render(self):
        signature, _ = self._pending_data
        self._rendered_signature = signature
        self._rendered_width = self.master.winfo_width()
        self._overlay.hide()

    def _compute_chart_data(self, tracks):
        """{key: (labels, values, colors, series)} en el orden en que se muestran.
        labels/values/colors alimentan la tabla (y el gráfico si series es None);
        series=(labels, values) cuando el gráfico necesita otra serie distinta."""
        album_labels, album_values = _count_by(tracks, "Album", "Sin Álbum")
        genre_labels, genre_values = _count_by(tracks, "Genre", "Sin Género")
        pub_labels, pub_values = _count_by(tracks, "Publisher", "Sin Etiqueta")

        def categorical(n):
            return [CHART_COLORS[i % len(CHART_COLORS)] for i in range(n)]

        year_counts = {}
        for t in tracks:
            year_raw = str(t.get("Year", "")).strip()
            if year_raw.isdigit():
                year_counts[int(year_raw)] = year_counts.get(int(year_raw), 0) + 1
        sorted_years = sorted(year_counts.keys())
        year_labels = [str(y) for y in sorted_years]
        year_values = [year_counts[y] for y in sorted_years]
        # El gráfico usa todos los años del rango (0 en los que no tienen pistas):
        # así el eje X es proporcional al tiempo. La tabla solo lista los que tienen.
        year_series = None
        if sorted_years:
            full_range = range(sorted_years[0], sorted_years[-1] + 1)
            year_series = ([str(y) for y in full_range], [year_counts.get(y, 0) for y in full_range])

        # Solo las valoraciones con pistas (como la PWA), de 0 a 5 estrellas.
        rating_counts = {}
        for t in tracks:
            stars = min(max(_parse_rating(t.get("Rating", "")), 0), 5)
            rating_counts[stars] = rating_counts.get(stars, 0) + 1
        rating_stars = sorted(rating_counts)

        return {
            "album": (album_labels, album_values, categorical(len(album_labels)), None),
            "genre": (genre_labels, genre_values, categorical(len(genre_labels)), None),
            "publisher": (pub_labels, pub_values, categorical(len(pub_labels)), None),
            # Año: una sola serie → un solo color, no uno por punto.
            "year": (year_labels, year_values, [CHART_COLORS[0]] * len(year_labels), year_series),
            "rating": (
                [_rating_label(s) for s in rating_stars],
                [rating_counts[s] for s in rating_stars],
                [RATING_COLORS[s] for s in rating_stars],
                None,
            ),
        }

    # ------------------------------------------------------------------
    # Dibujo de una tarjeta
    # ------------------------------------------------------------------
    def _sync_figure_size(self, slot):
        """Ajusta la figura al tamaño real de su widget. Devuelve True si cambió."""
        widget = slot["widget"]
        w, h = widget.winfo_width(), widget.winfo_height()
        if w <= 1 or h <= 1 or _figure_matches_size(slot["fig"], w, h):
            return False
        slot["canvas"].resize(SimpleNamespace(width=w, height=h))
        return True

    def _fit_to_size(self, slot):
        fig = slot["fig"]
        s = self._scale
        chart_type = slot["chart_type"]
        if chart_type == "pie":
            _apply_pixel_margins(fig, 4 * s, 4 * s, 4 * s, 4 * s)
        elif chart_type == "line":
            _apply_pixel_margins(fig, 36 * s, 8 * s, 8 * s, 34 * s)
        else:
            _apply_pixel_margins(fig, 36 * s, 4 * s, 8 * s, 8 * s)
            self._fit_bar_width(slot)

    def _fit_bar_width(self, slot):
        bars = slot["bars"]
        if not bars:
            return
        fig, ax = slot["fig"], slot["ax"]
        axes_px = ax.get_position().width * fig.get_size_inches()[0] * fig.dpi
        slot_px = axes_px / max(len(bars), 1)
        frac = min(0.7, (BAR_MAX_WIDTH_PX * self._scale) / slot_px) if slot_px > 0 else 0.7
        for i, rect in enumerate(bars):
            rect.set_width(frac)
            rect.set_x(i - frac / 2)

    def _render_slot(self, key_name, chart_data):
        labels, values, colors, series = chart_data
        chart_labels, chart_values = series or (labels, values)
        slot = self._chart_slots[key_name]
        ax = slot["ax"]
        canvas = slot["canvas"]
        ax.clear()
        slot["bars"] = None

        if slot["motion_cid"] is not None:
            canvas.mpl_disconnect(slot["motion_cid"])
            canvas.mpl_disconnect(slot["leave_cid"])
            slot["motion_cid"] = slot["leave_cid"] = None

        if not labels or not any(values):
            slot["widget"].pack_forget()
            slot["no_data_label"].pack(expand=True)
        else:
            slot["no_data_label"].pack_forget()
            slot["widget"].pack(fill="both", expand=True)
            self._sync_figure_size(slot)
            self._draw_chart(slot, chart_labels, chart_values, colors)
            self._fit_to_size(slot)
            # draw() síncrono (no draw_idle): la imagen queda lista en este mismo
            # callback y Tk la pinta junto con el resto de la vista.
            canvas.draw()

        total = sum(values) or 1
        slot["table"].set_rows([
            (label, value, f"{value / total * 100:.2f}%", color)
            for label, value, color in zip(labels, values, colors)
        ])

    def _draw_chart(self, slot, labels, values, colors):
        ax = slot["ax"]
        canvas = slot["canvas"]
        widget = slot["widget"]
        chart_type = slot["chart_type"]

        if chart_type == "pie":
            wedges, _ = ax.pie(
                values, colors=colors, startangle=90, counterclock=False, radius=1,
                wedgeprops=dict(edgecolor=CARD_BG, linewidth=1)
            )
            ax.set_aspect("equal")
            slot["motion_cid"], slot["leave_cid"] = _attach_pie_tooltip(
                canvas, ax, wedges, labels, values, self._tooltip, widget
            )
        elif chart_type == "line":
            color = colors[0]
            xs, ys = _smooth_series(values)
            ax.plot(xs, ys, color=color, linewidth=1.8, solid_capstyle="round")
            ax.fill_between(xs, ys, color=color, alpha=0.25, linewidth=0)
            ax.set_xlim(0, max(len(labels) - 1, 1))
            # ~12 años rotulados como máximo, girados 45° como en la PWA.
            step = max(1, math.ceil(len(labels) / 12))
            tick_idx = list(range(0, len(labels), step))
            ax.set_xticks(tick_idx)
            ax.set_xticklabels(
                [labels[i] for i in tick_idx], rotation=45, ha="right", rotation_mode="anchor"
            )
            _style_axes(ax)
            _set_nice_ylim(ax, max(values))
            ax.grid(True, axis="x", color=GRID_COLOR[:3], alpha=GRID_COLOR[3])
            slot["motion_cid"], slot["leave_cid"] = _attach_line_tooltip(
                canvas, ax, labels, values, self._tooltip, widget
            )
        else:  # bar — sin etiquetas en el eje X, el detalle vive en la tabla.
            bars = ax.bar(range(len(labels)), values, color=colors, width=0.7)
            ax.set_xlim(-0.6, len(labels) - 0.4)
            ax.set_xticks([])
            _style_axes(ax)
            _set_nice_ylim(ax, max(values))
            slot["bars"] = bars
            slot["motion_cid"], slot["leave_cid"] = _attach_bar_tooltip(
                canvas, ax, bars, labels, values, self._tooltip, widget
            )
