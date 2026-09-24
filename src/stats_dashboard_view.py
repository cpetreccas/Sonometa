import tkinter as tk
import customtkinter as ctk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

import theme

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

GRID_COLOR = (1, 1, 1, 0.08)
LEGEND_MAX_ROWS = 10

# Debounce del redibujado de matplotlib al redimensionar (ver _embed_canvas).
RESIZE_DEBOUNCE_MS = 180

# CTkScrollableFrame usa yscrollincrement=1px en Windows y desplaza ~20 unidades
# por muesca de rueda (ver ctk_scrollable_frame._mouse_wheel_all) => 20px por clic,
# muy poco frente a tarjetas de 250-300px de alto. Se sube solo el incremento de
# ESTE canvas (no toca el binding global de CustomTkinter ni otras vistas).
SCROLL_INCREMENT_PX = 5

# Fondo de tarjeta - plano e inmutable (no cambia con el ratón).
CARD_BG = theme.BG_CARD

# Fondo de la Hero Card: un punto más claro que las tarjetas normales, para que
# destaque como elemento propio (no es una tarjeta de gráfico más).
HERO_BG = "#1F1F23"

# rgba(255, 255, 255, 0.08) mezclado sobre BG_CARD: línea divisoria bajo títulos de
# tarjeta y cabeceras de leyenda, con contraste real (no un gris casi idéntico al
# fondo).
DIVIDER_COLOR = "#313135"

# Mapeo de rating numérico a estrellas de texto, tal como pide el diseño.
RATING_STAR_LABELS = {
    0: "Sin valoración",
    1: "★",
    2: "★★",
    3: "★★★",
    4: "★★★★",
    5: "★★★★★",
}

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


def _style_axes(ax):
    ax.set_facecolor("none")
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(colors=theme.TEXT_MUTED, labelsize=8)
    ax.grid(True, axis="y", color=GRID_COLOR[:3], alpha=GRID_COLOR[3])


def _new_figure(width_px=340, height_px=220, polar=False):
    dpi = 100
    fig = Figure(figsize=(width_px / dpi, height_px / dpi), dpi=dpi)
    fig.patch.set_alpha(0)
    ax = fig.add_subplot(111, polar=polar)
    ax.set_facecolor("none")
    fig.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.18)
    return fig, ax


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
    se funda con la tarjeta en vez de verse como un recuadro aparte."""
    canvas = FigureCanvasTkAgg(fig, master=parent)
    canvas.draw()
    widget = canvas.get_tk_widget()
    widget.configure(bg=bg, highlightthickness=0)

    original_resize = canvas.resize
    pending = {"job": None}

    def _do_resize(event):
        pending["job"] = None
        if widget.winfo_exists():
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
    Compartido por las leyendas de distribución (aquí) y los chips de diagnóstico/
    alerta de salud (health_dashboard_view.py). Sin efecto hover asociado (ver nota
    en _build_legend_rows) — solo detecta el clic."""
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


# (key_name, título, tipo, mostrar etiquetas eje X, fila, columna, colspan,
#  posición de la leyenda, pesos de columna [gráfico, leyenda] si posición="side")
# Grid de 6 columnas: fila 0 = Álbum/Género/Rating (2 columnas cada una), fila 1 =
# Etiqueta/Año (3 columnas cada una).
CHART_DEFS = [
    ("album", "Distribución por Álbum", "pie", True, 0, 0, 2, "side", (45, 55)),
    ("genre", "Distribución por Género", "pie", True, 0, 2, 2, "side", (45, 55)),
    ("rating", "Distribución por Rating", "bar", True, 0, 4, 2, "side", (75, 25)),
    # Etiqueta: nombres largos y numerosos — se ocultan del eje X, el detalle vive
    # en la leyenda.
    ("publisher", "Pistas por Etiqueta", "bar", False, 1, 0, 3, "side", (45, 55)),
    # Año: leyenda debajo (no al lado) para dar más aire horizontal a la serie
    # temporal.
    ("year", "Pistas por Año", "line", True, 1, 3, 3, "bottom", None),
]


class StatsDashboardView(ctk.CTkFrame):
    """Vista de estadísticas de la colección: gráficas de distribución (álbum,
    género, etiqueta, año, rating), réplica de escritorio del dashboard web
    (web/js/dashboard.js). La auditoría de salud (score, radar de completitud,
    diagnóstico) vive en la pestaña Salud (health_dashboard_view.py), no aquí.
    Acotada a la vista actual de la grilla (respeta filtros/búsqueda activos, no la
    biblioteca completa). Se embebe como una de las 3 pestañas conmutables de la app
    (ver App.switch_view en gui.py). Filtrar desde aquí (leyendas) NO cambia de
    pestaña: el filtro se aplica sobre el motor de la grilla (single source of
    truth) y esta vista se refresca sola — GridPanel.apply_combined_filters llama a
    self.refresh() automáticamente cuando esta es la pestaña activa, así que no hay
    botón "Actualizar" manual.

    Rendimiento: la estructura de las 5 tarjetas (título, divisor, figuras de
    matplotlib, caja de leyenda) se construye UNA sola vez en __init__. refresh() no
    destruye ni recrea esos widgets — crear un FigureCanvasTkAgg implica renderizar
    a un buffer Agg y crear una PhotoImage de Tk, la parte realmente cara de esta
    vista — sino que reutiliza cada Axes (ax.clear() + redibuja) y pide un
    canvas.draw_idle() (redibujado diferido al próximo instante libre, no
    bloqueante) en vez de canvas.draw(). Solo las filas de leyenda, que son
    widgets de Tkinter triviales, se siguen reconstruyendo por filtro.

    Sin efectos hover: ni las tarjetas ni las filas de leyenda cambian de color al
    pasar el ratón (antes las filas de leyenda sí lo hacían, pero al reconstruirse
    en cada refresco podían quedar "atascadas" en el color de hover si un refresco
    llegaba mientras el puntero seguía encima — se retiró por completo en vez de
    parchear la condición de carrera, y de paso se ahorra el bind de dos eventos
    por fila)."""

    def __init__(self, app, parent):
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0)
        self.app = app
        self._tooltip = _ChartTooltip(self)

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=theme.SPACE_MD)
        try:
            self.scroll._parent_canvas.configure(yscrollincrement=SCROLL_INCREMENT_PX)
        except Exception:
            pass

        self._empty_label = ctk.CTkLabel(
            self.scroll, text="No hay pistas visibles en la tabla (revisa los filtros aplicados).",
            text_color=theme.TEXT_SUBTLE, font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY)
        )

        self._build_hero_banner_shell()
        self._build_distribution_shell()

        self.refresh()

    def _apply_legend_filter(self, key_name, label):
        field = KEY_TO_COLUMN.get(key_name)
        if not field:
            return
        if key_name in DEFAULT_BUCKET_LABELS and label == DEFAULT_BUCKET_LABELS[key_name]:
            value = "[ Vacío ]"
        elif key_name == "rating":
            value = f"{label.count('★')}★"
        else:
            value = label
        _set_combo_filter(self.app, field, value)

    # ------------------------------------------------------------------
    # Construcción (una sola vez)
    # ------------------------------------------------------------------
    def _build_hero_banner_shell(self):
        self._hero_banner = ctk.CTkFrame(
            self.scroll, fg_color=HERO_BG, corner_radius=12,
            border_width=1, border_color=theme.PRIMARY
        )

        self._hero_count_label = ctk.CTkLabel(
            self._hero_banner, text="0",
            text_color="#FFFFFF", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=36, weight="bold")
        )
        self._hero_count_label.pack(pady=(theme.SPACE_LG, 0))

        ctk.CTkLabel(
            self._hero_banner, text="PISTAS EN LA VISTA ACTUAL", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        ).pack(pady=(0, theme.SPACE_LG))

    def _build_distribution_shell(self):
        self._grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        for col in range(6):
            self._grid.grid_columnconfigure(col, weight=1, uniform="cards")

        self._chart_slots = {}
        for key_name, title, chart_type, show_x_labels, row, col, colspan, legend_pos, col_weights in CHART_DEFS:
            # fg_color fijo, sin border_width/hover: la tarjeta no cambia de color.
            card = ctk.CTkFrame(self._grid, fg_color=CARD_BG, corner_radius=theme.RADIUS_CARD)
            card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=theme.SPACE_SM, pady=theme.SPACE_SM)
            self._chart_slots[key_name] = self._build_chart_card_shell(
                card, title, chart_type, show_x_labels, legend_pos, col_weights
            )

    def _build_chart_card_shell(self, card, title, chart_type, show_x_labels, legend_position, col_weights):
        ctk.CTkLabel(
            card, text=title.upper(), anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold"),
            text_color=theme.TEXT_MUTED
        ).pack(fill="x", padx=theme.SPACE_SM, pady=(theme.SPACE_SM, 10))
        # Línea divisoria bajo el título (equivalente a border-bottom + padding-bottom
        # + margin-bottom). height=2, no 1: un CTkFrame de 1px de alto no pinta nada
        # en esta versión de CustomTkinter (confirmado con una prueba controlada).
        ctk.CTkFrame(card, height=2, fg_color=DIVIDER_COLOR, corner_radius=0).pack(
            fill="x", padx=theme.SPACE_SM, pady=(0, 12)
        )

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=theme.SPACE_SM, pady=(0, theme.SPACE_SM))

        canvas_frame = ctk.CTkFrame(body, fg_color="transparent", corner_radius=theme.RADIUS_CONTROL)
        legend_col = ctk.CTkFrame(body, fg_color="transparent")

        if legend_position == "bottom":
            # Gráfico arriba (ocupa las 2 columnas internas), leyenda debajo — usado
            # por "Pistas por Año" para dar más aire horizontal a la serie temporal.
            body.grid_columnconfigure(0, weight=1)
            body.grid_columnconfigure(1, weight=1)
            body.grid_rowconfigure(0, weight=3)
            body.grid_rowconfigure(1, weight=1)
            canvas_frame.grid(row=0, column=0, columnspan=2, sticky="nsew", pady=(0, theme.SPACE_SM))
            legend_col.grid(row=1, column=0, columnspan=2, sticky="nsew")
        else:
            weight_chart, weight_legend = col_weights
            body.grid_columnconfigure(0, weight=weight_chart)
            body.grid_columnconfigure(1, weight=weight_legend)
            body.grid_rowconfigure(0, weight=1)
            canvas_frame.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACE_SM))
            legend_col.grid(row=0, column=1, sticky="nsew")

        no_data_label = ctk.CTkLabel(
            canvas_frame, text="Sin datos", text_color=theme.TEXT_SUBTLE,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        )

        fig, ax = _new_figure(230, 210, polar=False)
        # bg=CARD_BG: el propio canvas de matplotlib se pinta del mismo color que la
        # tarjeta, para que no se vea como un recuadro aparte.
        canvas, widget = _embed_canvas(canvas_frame, fig, bg=CARD_BG)
        widget.pack(fill="both", expand=True)

        # Leyenda: contenedor plano, mismo color que la tarjeta (sin caja ni borde
        # propios); se conserva únicamente la línea divisoria bajo la cabecera de la
        # tabla para mantener la estructura. fg_color sólido (no "transparent"): un
        # CTkFrame hijo con height=2 dentro de un padre "transparent" no pinta en
        # CustomTkinter (confirmado por muestreo de píxeles), así que la divisoria
        # quedaría invisible pese a existir si este contenedor fuera transparente.
        legend_inner = ctk.CTkFrame(legend_col, fg_color=CARD_BG, corner_radius=0)
        legend_inner.pack(fill="both", expand=True, padx=16, pady=12)

        header = ctk.CTkFrame(legend_inner, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(
            header, text="nombre", anchor="w", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold")
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(
            header, text="cant.", anchor="e", text_color=theme.TEXT_MUTED, width=36,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold")
        ).pack(side="left")
        ctk.CTkLabel(
            header, text="%", anchor="e", text_color=theme.TEXT_MUTED, width=50,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold")
        ).pack(side="left")
        # Única línea divisoria que se conserva (height=2, ver nota arriba).
        ctk.CTkFrame(legend_inner, height=2, fg_color=DIVIDER_COLOR, corner_radius=0).pack(
            fill="x", pady=(6, 4)
        )

        rows_container = ctk.CTkFrame(legend_inner, fg_color="transparent")
        rows_container.pack(fill="both", expand=True)

        return {
            "chart_type": chart_type,
            "show_x_labels": show_x_labels,
            "fig": fig,
            "ax": ax,
            "canvas": canvas,
            "widget": widget,
            "no_data_label": no_data_label,
            "rows_container": rows_container,
            "motion_cid": None,
            "leave_cid": None,
        }

    # ------------------------------------------------------------------
    # Refresco (actualiza datos sobre la estructura ya construida)
    # ------------------------------------------------------------------
    def refresh(self):
        if not self.winfo_exists():
            return

        self._tooltip.hide()

        tracks = self.app.grid_panel.get_visible_tracks_data()

        if not tracks:
            self._hero_banner.pack_forget()
            self._grid.pack_forget()
            self._empty_label.pack(pady=theme.SPACE_XL)
            return

        self._empty_label.pack_forget()
        self._hero_banner.pack(fill="x", pady=(0, theme.SPACE_MD))
        self._grid.pack(fill="both", expand=True)
        self._hero_count_label.configure(text=f"{len(tracks):,}".replace(",", "."))

        for key_name, (labels, values) in self._compute_chart_data(tracks).items():
            self._update_chart_slot(key_name, labels, values)

    def _compute_chart_data(self, tracks):
        album_labels, album_values = _count_by(tracks, "Album", "Sin Álbum")
        genre_labels, genre_values = _count_by(tracks, "Genre", "Sin Género")
        pub_labels, pub_values = _count_by(tracks, "Publisher", "Sin Etiqueta")

        year_counts = {}
        for t in tracks:
            year_raw = str(t.get("Year", "")).strip()
            if year_raw.isdigit():
                year_counts[int(year_raw)] = year_counts.get(int(year_raw), 0) + 1
        sorted_years = sorted(year_counts.keys())
        year_labels = [str(y) for y in sorted_years]
        year_values = [year_counts[y] for y in sorted_years]

        # Estrellas de texto ("Sin valoración", "★".."★★★★★") en vez de "N ★"; el
        # valor de filtro se deriva contando los "★" (ver _apply_legend_filter).
        rating_labels = [RATING_STAR_LABELS[n] for n in range(6)]
        rating_counts = {r: 0 for r in rating_labels}
        for t in tracks:
            r = RATING_STAR_LABELS.get(_parse_rating(t.get("Rating", "")), RATING_STAR_LABELS[0])
            rating_counts[r] += 1
        rating_values = [rating_counts[r] for r in rating_labels]

        return {
            "album": (album_labels, album_values),
            "genre": (genre_labels, genre_values),
            "publisher": (pub_labels, pub_values),
            "year": (year_labels, year_values),
            "rating": (rating_labels, rating_values),
        }

    def _update_chart_slot(self, key_name, labels, values):
        slot = self._chart_slots[key_name]
        ax = slot["ax"]
        canvas = slot["canvas"]
        ax.clear()

        if slot["motion_cid"] is not None:
            canvas.mpl_disconnect(slot["motion_cid"])
            canvas.mpl_disconnect(slot["leave_cid"])
            slot["motion_cid"] = slot["leave_cid"] = None

        if not labels or not any(values):
            slot["widget"].pack_forget()
            slot["no_data_label"].pack(pady=theme.SPACE_XL)
        else:
            slot["no_data_label"].pack_forget()
            slot["widget"].pack(fill="both", expand=True)

            chart_type = slot["chart_type"]
            colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(labels))]

            if chart_type == "pie":
                # Márgenes casi a cero: por defecto _new_figure deja hueco para
                # ejes/ticks que una tarta no usa, así que se veía pequeña dentro de
                # su columna. radius>1 aprovecha además el alto sobrante de la celda.
                slot["fig"].subplots_adjust(left=0.02, right=0.98, top=0.98, bottom=0.02)
                wedges, _ = ax.pie(
                    values, colors=colors, startangle=90, counterclock=False, radius=1.15,
                    wedgeprops=dict(edgecolor=CARD_BG, linewidth=1)
                )
                ax.set_aspect("equal")
                slot["motion_cid"], slot["leave_cid"] = _attach_pie_tooltip(
                    canvas, ax, wedges, labels, values, self._tooltip, slot["widget"]
                )
            elif chart_type == "line":
                ax.plot(labels, values, color=CHART_COLORS[0], linewidth=2, marker="o", markersize=3)
                ax.fill_between(range(len(labels)), values, color=CHART_COLORS[0], alpha=0.25)
                # Solo años múltiplos de 5 en el eje, horizontales (sin rotación) —
                # con el paso de 5 en 5 caben de sobra sin solaparse.
                tick_idx = [i for i, l in enumerate(labels) if l.isdigit() and int(l) % 5 == 0]
                if not tick_idx:
                    tick_idx = list(range(len(labels)))
                ax.set_xticks(tick_idx)
                ax.set_xticklabels([labels[i] for i in tick_idx], rotation=0, ha="center", fontsize=7)
                slot["fig"].subplots_adjust(bottom=0.15)
                _style_axes(ax)
                slot["motion_cid"], slot["leave_cid"] = _attach_line_tooltip(
                    canvas, ax, labels, values, self._tooltip, slot["widget"]
                )
            else:  # bar
                # width<1 limita el grosor máximo de cada barra (equivalente a
                # maxBarThickness), independientemente de cuántas categorías haya.
                bars = ax.bar(range(len(labels)), values, color=colors, width=0.6)
                if slot["show_x_labels"]:
                    ax.set_xticks(range(len(labels)))
                    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
                    slot["fig"].subplots_adjust(bottom=0.32)
                else:
                    ax.set_xticks([])
                _style_axes(ax)
                slot["motion_cid"], slot["leave_cid"] = _attach_bar_tooltip(
                    canvas, ax, bars, labels, values, self._tooltip, slot["widget"]
                )

            # draw_idle() en vez de draw(): pospone el redibujado real al próximo
            # instante libre del mainloop en vez de bloquear la UI ahora mismo.
            canvas.draw_idle()

        for widget in slot["rows_container"].winfo_children():
            widget.destroy()
        self._build_legend_rows(slot["rows_container"], labels, values, key_name)

    def _build_legend_rows(self, parent, labels, values, key_name):
        # Las categorías con 0 pistas (p.ej. una valoración sin ninguna pista) no
        # aportan nada en la leyenda: se ocultan, aunque la barra siga en el gráfico.
        nonzero = [(l, v) for l, v in zip(labels, values) if v > 0]
        total = sum(v for _, v in nonzero) or 1

        if key_name == "year":
            pairs = sorted(nonzero, key=lambda p: int(p[0]))
        elif key_name == "rating":
            pairs = sorted(nonzero, key=lambda p: p[0].count("★"), reverse=True)
        else:
            pairs = sorted(nonzero, key=lambda p: p[1], reverse=True)

        shown = pairs[:LEGEND_MAX_ROWS]
        remaining = len(pairs) - len(shown)
        # Año: un único color monocromo (el de la línea), no uno distinto por punto
        # — son la misma serie, no categorías independientes.
        monochrome = key_name == "year"

        for label, val in shown:
            color = CHART_COLORS[0] if monochrome else CHART_COLORS[labels.index(label) % len(CHART_COLORS)]
            pct = (val / total) * 100
            # Sin hover: las filas se reconstruyen en cada refresco, y bindear
            # <Enter>/<Leave> aquí dejaba filas "atascadas" en el color de hover
            # cuando un refresco llegaba mientras el puntero seguía encima. Solo
            # queda el clic (cursor de mano) para el cross-filtering.
            row = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=theme.RADIUS_CONTROL)
            row.pack(fill="x", pady=3)
            ctk.CTkFrame(row, fg_color=color, width=10, height=10, corner_radius=2).pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                row, text=label, anchor="w", text_color=theme.TEXT_MAIN,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO)
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                row, text=str(val), anchor="e", text_color="#FFFFFF", width=36,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO, weight="bold")
            ).pack(side="left")
            ctk.CTkLabel(
                row, text=f"{pct:.1f}%", anchor="e", text_color=theme.TEXT_MUTED, width=50,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO)
            ).pack(side="left")
            _bind_clickable(row, lambda k=key_name, l=label: self._apply_legend_filter(k, l))

        if remaining > 0:
            ctk.CTkLabel(
                parent, text=f"+{remaining} más", text_color=theme.TEXT_SUBTLE,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO)
            ).pack(anchor="w", pady=(4, 0))
