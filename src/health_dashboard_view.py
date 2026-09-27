import math
import os
import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk
import numpy as np

from dialogs import DialogManager
from stats_dashboard_view import (
    CARD_BG, _new_figure, _embed_canvas, _figure_matches_size, _set_combo_filter,
    _set_toggle_filter, _parse_rating, _parse_cues, _has_cover, _hex_rgb, _tracked_title,
    _build_card_shell, _show_tooltip_near, _format_count,
)
import theme

# Cross-filtering desde los elementos de diagnóstico de completitud: qué control del
# panel de filtro avanzado activar por cada dimensión incompleta.
DIAG_FILTER_ACTIONS = {
    "album": ("combo", "Album", "(Vacío)"),
    "genre": ("combo", "Genre", "(Vacío)"),
    "publisher": ("combo", "Publisher", "(Vacío)"),
    "year": ("toggle", "no_year"),
    "cover": ("toggle", "no_cover"),
    "cues": ("toggle", "no_cues"),
    "rating": ("combo", "Rating", "0★"),
}

# Iconos de línea equivalentes a los SVG de la PWA (DIAG_ICONS en web/js/dashboard.js),
# tomados de la fuente de iconos del sistema (Segoe Fluent Icons en Windows 11,
# Segoe MDL2 Assets en Windows 10: mismos códigos). Mismo color por dimensión que la PWA.
ICON_FONT_CANDIDATES = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
GLYPH_PHOTO = "\uE91B"
GLYPH_STAR = "\uE734"
GLYPH_HEADPHONE = "\uE7F6"
GLYPH_MUSIC = "\uEC4F"
GLYPH_TAG = "\uE8EC"
GLYPH_ALBUM = "\uE93C"
GLYPH_CALENDAR = "\uE787"
GLYPH_GAUGE = "\uEC4A"
GLYPH_WARNING = "\uE7BA"
GLYPH_ERROR = "\uEA39"
GLYPH_VOLUME_LOW = "\uE993"
GLYPH_VOLUME_HIGH = "\uE995"

# (dimensión, icono, color, texto) en el mismo orden que la lista de la PWA. Color por
# gravedad (guía de estilos): un campo que falta es un aviso (ámbar).
DIAG_ITEMS = [
    ("cover", GLYPH_PHOTO, theme.STATUS_WARNING, "sin carátula"),
    ("rating", GLYPH_STAR, theme.STATUS_WARNING, "sin valoración"),
    ("cues", GLYPH_HEADPHONE, theme.STATUS_WARNING, "sin Cue points"),
    ("genre", GLYPH_MUSIC, theme.STATUS_WARNING, "sin género"),
    ("publisher", GLYPH_TAG, theme.STATUS_WARNING, "sin etiqueta"),
    ("album", GLYPH_ALBUM, theme.STATUS_WARNING, "sin álbum"),
    ("year", GLYPH_CALENDAR, theme.STATUS_WARNING, "sin año"),
]

# Avisos de la auditoría técnica que se suman al diagnóstico de la colección:
# (flag, icono, color, texto, clave del resumen de get_health_summary_for_files).
# Solo se listan los que tienen alguna pista; el clic filtra por ese flag.
AUDIT_ITEMS = [
    ("clipping", GLYPH_WARNING, theme.STATUS_DANGER, "con saturación", "clipping_count"),
    ("loudness_low", GLYPH_VOLUME_LOW, theme.STATUS_WARNING, "con volumen bajo", "lufs_low_count"),
    ("loudness_high", GLYPH_VOLUME_HIGH, theme.STATUS_WARNING, "con volumen excesivo", "lufs_high_count"),
    ("bitrate_fake", GLYPH_GAUGE, theme.STATUS_WARNING, "con bitrate falso", "bitrate_fake_count"),
    ("integrity_issue", GLYPH_ERROR, theme.STATUS_DANGER, "corruptos o truncados", "integrity_issue_count"),
]
# Etiqueta con la que se muestra el filtro de calidad en el indicador de filtro global.
AUDIT_FILTER_LABELS = {
    "clipping": "Saturación",
    "loudness_low": "Volumen bajo",
    "loudness_high": "Volumen excesivo",
    "bitrate_fake": "Bitrate falso",
    "integrity_issue": "Corruptos/truncados",
}
# Ejes técnicos del radar, a continuación de los 7 de completitud: % de las pistas
# analizadas que PASAN cada chequeo = 100 - % con el problema. (clave del resumen, etiqueta)
AUDIT_RADAR_AXES = [
    ("integrity_issue_count", "Integridad"),
    ("clipping_count", "Sin saturación"),
    ("lufs_out_of_range_count", "Volumen"),
    ("bitrate_fake_count", "Bitrate real"),
]

# Alto de las dos tarjetas (Calidad de la colección / Indicadores de calidad). Cabe
# el anillo, hasta 6 filas de diagnóstico (7 campos + 5 avisos técnicos en 2
# columnas) y la fila de cobertura del análisis técnico.
HEALTH_CARD_HEIGHT = 440
RING_SIZE = 120
RING_THICKNESS = 12
RING_TRACK_COLOR = theme.BORDER_QUIET
BRAND_GRADIENT = ("#8B5CF6", "#EC4899")   # --brand-gradient de la guía
RADAR_POINT_COLOR = "#EC4899"

# Por debajo de este ancho (px lógicos) las tarjetas se apilan en una columna.
SINGLE_COLUMN_BELOW = 1000


def _health_status_text(score):
    if score >= 95:
        return "EXCELENTE"
    if score >= 80:
        return "BUENO"
    if score >= 60:
        return "ACEPTABLE"
    if score >= 40:
        return "MEJORABLE"
    return "CRÍTICO"


def _health_status_color(score):
    if score >= 80:
        return theme.STATUS_SUCCESS
    if score >= 40:
        return theme.STATUS_WARNING
    return theme.STATUS_DANGER


def _track_has_data_gap(track):
    """¿Le falta a la pista alguno de los 7 campos de completitud?"""
    return not (
        str(track.get("Album", "")).strip()
        and str(track.get("Genre", "")).strip()
        and str(track.get("Publisher", "")).strip()
        and _parse_cues(track.get("Cues", "")) > 0
        and _parse_rating(track.get("Rating", "")) > 0
        and _has_cover(track.get("Cover", ""))
        and str(track.get("Year", "")).strip()
    )


def _health_has_issue(health, lufs_ok_min, lufs_ok_max):
    """¿Tiene el análisis técnico algún aviso de los que lista la tarjeta?"""
    lufs = health.get("lufs_integrated")
    return bool(
        health.get("has_clipping")
        or health.get("bitrate_fake")
        or health.get("integrity_status") in ("warning", "critical")
        or (lufs is not None and (lufs < lufs_ok_min or lufs > lufs_ok_max))
    )


def _count_clean_tracks(tracks, paths, health_by_path):
    """Pistas sin ningún problema: los 7 campos completos y ningún aviso técnico.
    Las pistas sin análisis técnico vigente cuentan solo por sus datos."""
    from audio_health_checker import LUFS_OK_MIN, LUFS_OK_MAX

    clean = 0
    for track, path in zip(tracks, paths):
        if _track_has_data_gap(track):
            continue
        health = health_by_path.get(path) if path else None
        if health and _health_has_issue(health, LUFS_OK_MIN, LUFS_OK_MAX):
            continue
        clean += 1
    return clean


def _compute_quality(metrics, summary, clean_count):
    """Anillo: % de pistas sin ningún problema (ver _count_clean_tracks). Así se lee
    directamente ("el X % de la colección está perfecta") y un problema frecuente no
    se diluye entre indicadores casi perfectos, como pasaba al promediarlos.
    El radar sigue mostrando cada indicador por separado: los 7 campos y, si hay
    pistas analizadas, los 4 ejes técnicos (% de analizadas que pasan cada chequeo)."""
    total = metrics["total"]
    labels, values = list(metrics["labels"]), list(metrics["values"])
    overall = round(100 * clean_count / total) if total else 0

    analyzed = summary.get("total_analyzed", 0) or 0
    if analyzed:
        labels += [label for _, label in AUDIT_RADAR_AXES]
        values += [
            round(100 * (analyzed - (summary.get(key, 0) or 0)) / analyzed) for key, _ in AUDIT_RADAR_AXES
        ]
    return {"overall": overall, "clean": clean_count, "total": total, "labels": labels, "values": values}

def _icon_font_family():
    families = set(tkfont.families())
    return next((f for f in ICON_FONT_CANDIDATES if f in families), theme.FONT_FAMILY)


def _compute_health_metrics(tracks):
    """Réplica de renderCollectionHealth() en dashboard.js: 7 dimensiones + score global."""
    total = len(tracks)
    if total == 0:
        return None

    has_album = sum(1 for t in tracks if str(t.get("Album", "")).strip())
    has_genre = sum(1 for t in tracks if str(t.get("Genre", "")).strip())
    has_publisher = sum(1 for t in tracks if str(t.get("Publisher", "")).strip())
    has_cues = sum(1 for t in tracks if _parse_cues(t.get("Cues", "")) > 0)
    has_rating = sum(1 for t in tracks if _parse_rating(t.get("Rating", "")) > 0)
    has_cover = sum(1 for t in tracks if _has_cover(t.get("Cover", "")))
    has_year = sum(1 for t in tracks if str(t.get("Year", "")).strip())

    # Orden de los ejes del radar, igual que en la PWA.
    dims = {
        "album": (has_album, "Álbum"),
        "genre": (has_genre, "Género"),
        "publisher": (has_publisher, "Etiqueta"),
        "cues": (has_cues, "Cue Points"),
        "rating": (has_rating, "Rating"),
        "cover": (has_cover, "Carátula"),
        "year": (has_year, "Año"),
    }

    pct = {k: round((v[0] / total) * 100) for k, v in dims.items()}
    overall = round(sum(pct.values()) / len(pct))

    return {
        "overall": overall,
        "labels": [v[1] for v in dims.values()],
        "values": [pct[k] for k in dims],
        "missing": {k: total - v[0] for k, v in dims.items() if v[0] < total},
        "total": total,
    }


class _ScoreRing:
    """Anillo del score global como en la PWA: arco con el degradado de marca
    (--brand-gradient, único uso permitido por la guía), pista gris, extremos
    redondeados, porcentaje en blanco y estado en mayúsculas debajo. El anillo se
    genera con Pillow (Tk no tiene degradados); el texto es de canvas."""

    SUPERSAMPLE = 4

    def __init__(self, parent, scale):
        self._s = scale
        self._size = round(RING_SIZE * scale)
        self.canvas = tk.Canvas(parent, width=self._size, height=self._size, bg=CARD_BG, bd=0, highlightthickness=0)
        self._image = None
        self._score = None

        number_family = "Segoe UI Black" if "Segoe UI Black" in tkfont.families() else theme.FONT_FAMILY
        self._font_number = tkfont.Font(family=number_family, size=-round(25 * scale), weight="bold")
        self._font_status = tkfont.Font(family=theme.FONT_FAMILY, size=-round(10 * scale), weight="bold")

        c = self._size / 2
        self._image_item = self.canvas.create_image(0, 0, anchor="nw")
        self._number_item = self.canvas.create_text(
            c, c - round(5 * scale), text="", fill=theme.TEXT_ON_PRIMARY, font=self._font_number
        )
        self._status_item = self.canvas.create_text(
            c, c + round(17 * scale), text="", fill=theme.TEXT_MUTED, font=self._font_status
        )

    def set_score(self, score, suffix="%"):
        """score=None pinta solo la pista gris con "—" y "SIN ANÁLISIS"."""
        if score is None:
            self.canvas.itemconfigure(self._number_item, text="—")
            self.canvas.itemconfigure(self._status_item, text=_tracked_title("Sin análisis"))
        else:
            self.canvas.itemconfigure(self._number_item, text=f"{score}{suffix}")
            self.canvas.itemconfigure(self._status_item, text=_tracked_title(_health_status_text(score)))
        ring_value = score or 0
        if ring_value != self._score:
            self._score = ring_value
            self._image = self._build_ring(ring_value)
            self.canvas.itemconfigure(self._image_item, image=self._image)

    def _build_ring(self, score):
        from PIL import Image, ImageDraw, ImageTk

        ss = self.SUPERSAMPLE
        size = self._size * ss
        thick = round(RING_THICKNESS * self._s * ss)
        # Pillow dibuja el trazo de ellipse/arc HACIA DENTRO del rectángulo dado (no
        # centrado sobre él): con el rectángulo = lienzo completo, el centro del trazo
        # queda a (size - thick) / 2 del centro, que es donde van los extremos redondos.
        box = (0, 0, size - 1, size - 1)
        radius = (size - thick) / 2

        out = Image.new("RGB", (size, size), CARD_BG)
        draw = ImageDraw.Draw(out)
        draw.ellipse(box, outline=RING_TRACK_COLOR, width=thick)

        if score > 0:
            # Degradado lineal a 135°: morado abajo-izquierda, rosa arriba-derecha.
            start, end = np.array(_hex_rgb(BRAND_GRADIENT[0])), np.array(_hex_rgb(BRAND_GRADIENT[1]))
            yy, xx = np.mgrid[0:size, 0:size]
            t = np.clip((xx + (size - yy)) / (2 * size), 0, 1)[..., None]
            gradient = Image.fromarray((start * (1 - t) + end * t).astype(np.uint8), "RGB")

            mask = Image.new("L", (size, size), 0)
            mdraw = ImageDraw.Draw(mask)
            sweep = 360 * min(score, 100) / 100
            mdraw.arc(box, start=-90, end=-90 + sweep, fill=255, width=thick)
            if score < 100:
                # Extremos redondeados (stroke-linecap: round).
                for angle in (-90, -90 + sweep):
                    a = math.radians(angle)
                    cx = size / 2 + radius * math.cos(a)
                    cy = size / 2 + radius * math.sin(a)
                    mdraw.ellipse((cx - thick / 2, cy - thick / 2, cx + thick / 2, cy + thick / 2), fill=255)
            out.paste(gradient, (0, 0), mask)

        return ImageTk.PhotoImage(out.resize((self._size, self._size), Image.LANCZOS), master=self.canvas)


class _MetricList:
    """Lista icono + número en negrita + texto, como el diagnóstico de la PWA.

    Es una única rejilla de celdas alineadas: en cada grupo de columnas, los iconos
    en una columna, los números alineados a la derecha en otra (así "10" y "2"
    terminan en el mismo punto) y los textos empiezan todos a la misma altura. Los
    grupos van juntos, separados por un hueco fijo, y el bloque se centra en la
    tarjeta (bajo el anillo) en vez de repartirse a lo ancho.

    Widgets Tk simples creados una vez y reutilizados (solo cambia su texto y
    posición al refrescar). Cada elemento con clic llama a on_click(key)."""

    CELLS_PER_GROUP = 4   # icono, número, texto, hueco hasta el grupo siguiente

    def __init__(self, parent, scale, columns, on_click):
        self._on_click = on_click
        self._columns = columns
        self.frame = tk.Frame(parent, bg=CARD_BG, bd=0, highlightthickness=0)

        gap = round(8 * scale)
        for group in range(columns):
            base = group * self.CELLS_PER_GROUP
            self.frame.grid_columnconfigure(base + 1, minsize=round(22 * scale))  # números de 1-2 cifras
            if group < columns - 1:
                self.frame.grid_columnconfigure(base + 3, minsize=round(48 * scale))

        self._font_icon = tkfont.Font(family=_icon_font_family(), size=-round(15 * scale))
        self._font_count = tkfont.Font(family=theme.FONT_FAMILY, size=-round(14 * scale), weight="bold")
        self._font_text = tkfont.Font(family=theme.FONT_FAMILY, size=-round(14 * scale))
        self._pad_y = round(4 * scale)
        self._gap = gap
        self._items = {}

        self._empty_label = tk.Label(
            self.frame, text="", bg=CARD_BG, fg=theme.MODAL_ICON_SUCCESS, anchor="w",
            font=self._font_text
        )

    def _item(self, key):
        if key in self._items:
            return self._items[key]
        icon = tk.Label(self.frame, bg=CARD_BG, font=self._font_icon, bd=0)
        count = tk.Label(self.frame, bg=CARD_BG, fg=theme.TEXT_MAIN, font=self._font_count, bd=0, anchor="e")
        text = tk.Label(self.frame, bg=CARD_BG, fg=theme.TEXT_MUTED, font=self._font_text, bd=0, anchor="w")
        parts = (icon, count, text)
        entry = {"icon": icon, "count": count, "text": text, "parts": parts, "clickable": False}

        def _enter(_e):
            if entry["clickable"]:
                text.configure(fg=theme.TEXT_MAIN)

        def _leave(_e):
            text.configure(fg=theme.TEXT_MUTED)

        def _click(_e):
            if entry["clickable"]:
                self._on_click(key)

        for w in parts:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<Button-1>", _click)
        self._items[key] = entry
        return entry

    def set_items(self, items, empty_text=""):
        """items: [(key, glyph, color, count, text, clickable)] en orden de pantalla
        (se reparten por filas: con 2 columnas, el 1º y el 2º van en la primera fila)."""
        visible = set()
        for i, (key, glyph, color, count, text, clickable) in enumerate(items):
            entry = self._item(key)
            entry["clickable"] = clickable
            entry["icon"].configure(text=glyph, fg=color)
            entry["count"].configure(text=f"{count:,}".replace(",", "."), fg=theme.TEXT_MAIN if count else theme.TEXT_SUBTLE)
            entry["text"].configure(text=text, fg=theme.TEXT_MUTED)
            cursor = "hand2" if clickable else ""
            for w in entry["parts"]:
                w.configure(cursor=cursor)

            row = i // self._columns
            base = (i % self._columns) * self.CELLS_PER_GROUP
            entry["icon"].grid(row=row, column=base, sticky="w", padx=(0, self._gap), pady=self._pad_y)
            entry["count"].grid(row=row, column=base + 1, sticky="e", padx=(0, round(self._gap * 0.75)), pady=self._pad_y)
            entry["text"].grid(row=row, column=base + 2, sticky="w", pady=self._pad_y)
            visible.add(key)

        for key, entry in self._items.items():
            if key not in visible:
                for w in entry["parts"]:
                    w.grid_remove()

        if not items and empty_text:
            self._empty_label.configure(text=empty_text)
            self._empty_label.grid(
                row=0, column=0, columnspan=self._columns * self.CELLS_PER_GROUP, pady=self._pad_y
            )
        else:
            self._empty_label.grid_remove()


class _RadarChart:
    """Radar de completitud como el de Chart.js en la PWA: cuadrícula poligonal
    (no circular), primer eje (Álbum) arriba y el resto en sentido horario, relleno
    morado translúcido, borde morado y puntos rosas con borde blanco. Se dibuja en
    unos Axes cartesianos normales para controlar cada detalle."""

    LEVELS = (20, 40, 60, 80, 100)

    def __init__(self, parent, tooltip):
        self._tooltip = tooltip
        self.fig, self.ax = _new_figure(420, 260)
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.canvas, self.widget = _embed_canvas(parent, self.fig, bg=CARD_BG)
        self.widget.pack(fill="both", expand=True)
        self._points = []
        self._labels = []
        self._values = []
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("figure_leave_event", lambda e: self._tooltip.hide())

    def sync_size(self):
        """Ajusta la figura al tamaño del widget. Devuelve True si ha cambiado."""
        w, h = self.widget.winfo_width(), self.widget.winfo_height()
        if w > 1 and h > 1 and not _figure_matches_size(self.fig, w, h):
            from types import SimpleNamespace
            self.canvas.resize(SimpleNamespace(width=w, height=h))
            return True
        return False

    def redraw(self):
        if self._labels:
            self.draw(self._labels, self._values)

    @staticmethod
    def _xy(angle, radius):
        return radius * math.cos(angle), radius * math.sin(angle)

    def draw(self, labels, values, empty_text=None):
        """Con empty_text se dibuja solo la cuadrícula y ese texto en el centro."""
        self._labels, self._values = labels, values
        ax = self.ax
        ax.clear()
        ax.set_axis_off()
        ax.set_aspect("equal")
        n = len(labels)
        angles = [math.pi / 2 - i * 2 * math.pi / n for i in range(n)]

        for level in self.LEVELS:
            ring = [self._xy(a, level) for a in angles] + [self._xy(angles[0], level)]
            ax.plot(*zip(*ring), color=(1, 1, 1), alpha=0.18, linewidth=0.8)
        for a in angles:
            ax.plot(*zip((0, 0), self._xy(a, 100)), color=(1, 1, 1), alpha=0.22, linewidth=0.8)
        for level in self.LEVELS:
            # Desplazadas a la derecha del eje de Álbum para no pisar su punto.
            ax.text(4, level, str(level), color=theme.TEXT_MUTED, fontsize=7, ha="left", va="center")

        if empty_text:
            self._points = []
            ax.text(0, 0, empty_text, color=theme.TEXT_SUBTLE, fontsize=9, ha="center", va="center",
                    bbox=dict(facecolor=CARD_BG, edgecolor="none", pad=4))
        else:
            pts = [self._xy(a, v) for a, v in zip(angles, values)]
            ax.fill(*zip(*pts), color=theme.PRIMARY, alpha=0.3, linewidth=0)
            ax.plot(*zip(*(pts + pts[:1])), color=theme.PRIMARY, linewidth=2)
            ax.scatter(*zip(*pts), s=30, color=RADAR_POINT_COLOR, edgecolors="#FFFFFF", linewidths=1.2, zorder=3)
            self._points = pts

        for a, label in zip(angles, labels):
            x, y = self._xy(a, 116)
            cos, sin = math.cos(a), math.sin(a)
            ha = "center" if abs(cos) < 0.2 else ("left" if cos > 0 else "right")
            va = "center" if abs(sin) < 0.2 else ("bottom" if sin > 0 else "top")
            ax.text(x, y, label, color=theme.TEXT_MAIN, fontsize=8, fontweight="bold", ha=ha, va=va)

        ax.set_xlim(-150, 150)
        ax.set_ylim(-132, 128)
        self.canvas.draw()

    def _on_motion(self, event):
        if event.inaxes != self.ax or event.x is None:
            self._tooltip.hide()
            return
        for (px, py), label, value in zip(self._points, self._labels, self._values):
            sx, sy = self.ax.transData.transform((px, py))
            if (sx - event.x) ** 2 + (sy - event.y) ** 2 < 12 ** 2:
                _show_tooltip_near(self._tooltip, self.widget, event, f"{label}: {value}%")
                return
        self._tooltip.hide()


class QualitySection:
    """Tarjetas "Calidad de la colección" e "Indicadores de calidad", que encabezan
    el Dashboard (StatsDashboardView las coloca bajo el contador y encima de las
    gráficas de distribución). Antes eran una pestaña propia ("Calidad").

    La calidad combina completitud de datos (7 campos) y auditoría técnica de audio
    (integridad, saturación, volumen, bitrate real): en el anillo la técnica pesa la
    mitad en proporción a la cobertura del análisis (ver _compute_quality), la lista
    suma a los campos que faltan los avisos técnicos, y el radar tiene un eje por
    cada uno. Al pie de la primera tarjeta, la cobertura del análisis técnico y el
    botón "Analizar pendientes".

    Clic en un elemento de la lista filtra la colección sin cambiar de pestaña:
    campos que faltan -> filtro avanzado (DIAG_FILTER_ACTIONS); avisos técnicos ->
    filtro por rutas (GridPanel.apply_health_path_filter). El Dashboard se recalcula
    sobre las pistas filtradas y el filtro se ve en el indicador de la cabecera.

    No es un widget: construye sus tarjetas en `self.frame` (que coloca el host) y
    expone compute()/render() para que el host decida cuándo pintar."""

    def __init__(self, app, parent, scale, tooltip, host):
        self.app = app
        self._host = host
        self._scale = scale
        self._tooltip = tooltip
        self.file_paths = []
        self._single_column = None

        self.frame = tk.Frame(parent, bg=theme.BG_MAIN, bd=0, highlightthickness=0)
        self._grid = self.frame
        self._grid.bind("<Configure>", self._on_grid_configure)
        self._build_collection_health_card()
        self._build_indicators_card()
        self._layout_cards(single_column=False)

    # ------------------------------------------------------------------
    # Construcción (una sola vez)
    # ------------------------------------------------------------------
    def _build_collection_health_card(self):
        s = self._scale
        self._health_card, content = _build_card_shell(
            self._grid, "Calidad de la colección", s, height=HEALTH_CARD_HEIGHT
        )
        self._ring = _ScoreRing(content, s)
        self._ring.canvas.pack(pady=(round(10 * s), round(4 * s)))
        self._clean_text = tk.Label(
            content, bg=CARD_BG, fg=theme.TEXT_MUTED,
            font=tkfont.Font(family=theme.FONT_FAMILY, size=-round(13 * s))
        )
        self._clean_text.pack(pady=(0, round(10 * s)))
        self._diag_list = _MetricList(content, s, columns=2, on_click=self._on_diag_click)
        self._diag_list.frame.pack()  # centrado bajo el anillo

        # Cobertura del análisis técnico en una sola línea: texto · barra · botón.
        coverage_row = tk.Frame(content, bg=CARD_BG, bd=0, highlightthickness=0)
        coverage_row.pack(side="bottom", fill="x")
        coverage_row.grid_columnconfigure(1, weight=1)
        self._coverage_text = tk.Label(
            coverage_row, bg=CARD_BG, fg=theme.TEXT_MUTED, anchor="w",
            font=tkfont.Font(family=theme.FONT_FAMILY, size=-round(13 * s))
        )
        self._coverage_text.grid(row=0, column=0, sticky="w")
        self._coverage_bar = ctk.CTkProgressBar(
            coverage_row, height=6, corner_radius=3, fg_color=theme.BG_CARD_HOVER,
            progress_color=theme.PRIMARY, bg_color=CARD_BG
        )
        self._coverage_bar.grid(row=0, column=1, sticky="ew", padx=round(12 * s))
        self.btn_analyze_pending = ctk.CTkButton(
            coverage_row, text="Analizar pendientes", command=self._analyze_pending, height=30,
            corner_radius=theme.RADIUS_CONTROL, bg_color=CARD_BG,
            fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, text_color=theme.TEXT_ON_PRIMARY,
            text_color_disabled=theme.TEXT_SUBTLE,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")
        )
        self.btn_analyze_pending.grid(row=0, column=2, sticky="e")

    def _build_indicators_card(self):
        self._indicators_card, content = _build_card_shell(
            self._grid, "Indicadores de calidad", self._scale, height=HEALTH_CARD_HEIGHT
        )
        area = tk.Frame(content, bg=CARD_BG, bd=0, highlightthickness=0)
        area.pack(fill="both", expand=True, pady=(round(8 * self._scale), 0))
        self._radar = _RadarChart(area, self._tooltip)

    # ------------------------------------------------------------------
    # Rejilla responsive
    # ------------------------------------------------------------------
    def _on_grid_configure(self, event):
        single = (event.width / self._scale) < SINGLE_COLUMN_BELOW
        if single != self._single_column:
            self._layout_cards(single)

    def _layout_cards(self, single_column):
        self._single_column = single_column
        gap = round(theme.SPACE_SM * self._scale)
        self._grid.grid_columnconfigure(0, weight=1, uniform="health")
        cards = (self._health_card, self._indicators_card)
        if single_column:
            self._grid.grid_columnconfigure(1, weight=0, uniform="")
            cells = [(card, i, 0, 1) for i, card in enumerate(cards)]
        else:
            self._grid.grid_columnconfigure(1, weight=1, uniform="health")
            cells = [(card, i // 2, i % 2, 1) for i, card in enumerate(cards)]
        for card, row, col, span in cells:
            card.grid(row=row, column=col, columnspan=span, sticky="nsew", padx=gap, pady=gap)

    # ------------------------------------------------------------------
    # Datos y pintado (los decide el host)
    # ------------------------------------------------------------------
    def compute(self, tracks, file_paths):
        """(métricas de completitud, resumen de la auditoría, nº de pistas sin
        problemas) de las pistas visibles."""
        self.file_paths = file_paths
        metrics = _compute_health_metrics(tracks)
        cache_manager = getattr(self.app, "cache_manager", None)
        summary = cache_manager.get_health_summary_for_files(file_paths) if cache_manager else {}

        aligned_paths = self.app.grid_panel.get_visible_paths_aligned()
        health_by_path = cache_manager.get_health_fields_for_files(file_paths) if cache_manager else {}
        clean_count = _count_clean_tracks(tracks, aligned_paths, health_by_path)
        return metrics, summary, clean_count

    def render(self, metrics, summary, clean_count):
        quality = _compute_quality(metrics, summary, clean_count)
        self._ring.set_score(quality["overall"])
        self._clean_text.configure(
            text=f"{_format_count(quality['clean'])} de {_format_count(quality['total'])} pistas sin problemas"
        )

        missing = metrics["missing"]
        items = [
            (key, glyph, color, missing[key], text, True)
            for key, glyph, color, text in DIAG_ITEMS if key in missing
        ]
        for key, glyph, color, text, summary_key in AUDIT_ITEMS:
            count = summary.get(summary_key, 0) or 0
            if count:
                items.append((key, glyph, color, count, text, True))
        self._diag_list.set_items(items, empty_text="✨ Colección 100% completada")

        self._radar.sync_size()
        self._radar.draw(quality["labels"], quality["values"])

        self._render_coverage(summary)

    def resync(self):
        """Tras asentarse el layout: redibuja el radar si su tamaño cambió."""
        if self._radar.sync_size():
            self._radar.redraw()

    def _render_coverage(self, summary):
        total_library = summary.get("total_library", 0)
        total_analyzed = summary.get("total_analyzed", 0)
        coverage = (total_analyzed / total_library) if total_library else 0

        self._coverage_text.configure(
            text=f"{total_analyzed} de {total_library} analizadas ({round(coverage * 100)}%)"
        )
        # CTkProgressBar dibuja un punto de color incluso a 0: se oculta el color.
        self._coverage_bar.configure(progress_color=theme.PRIMARY if coverage > 0 else theme.BG_CARD_HOVER)
        self._coverage_bar.set(coverage)

        pending_count = max(0, total_library - total_analyzed)
        if pending_count > 0:
            self.btn_analyze_pending.configure(
                state="normal", text=f"Analizar pendientes ({pending_count})", fg_color=theme.PRIMARY
            )
        else:
            # CTkButton no cambia de fondo al desactivarse: sin esto el texto gris
            # queda ilegible sobre el morado.
            self.btn_analyze_pending.configure(
                state="disabled", text="Todas analizadas", fg_color=theme.BG_CARD_HOVER
            )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _on_diag_click(self, key):
        """Campos que faltan -> filtro avanzado; avisos técnicos -> filtro por flag."""
        if key in DIAG_FILTER_ACTIONS:
            self._apply_diag_filter(key)
        else:
            self._filter_by_health_flag(key)

    def _filter_by_health_flag(self, flag_key):
        """Cross-filtering: clic en un aviso técnico filtra la grilla a
        las pistas (de self.file_paths, la vista actual) que lo tienen."""
        cache_manager = getattr(self.app, "cache_manager", None)
        grid = getattr(self.app, "grid_panel", None)
        if cache_manager is None or grid is None:
            return

        paths = cache_manager.get_paths_by_health_flag(self.file_paths, flag_key)
        if not paths:
            return

        grid.apply_health_path_filter(paths, f"{AUDIT_FILTER_LABELS[flag_key]} ({len(paths)})")

    def _analyze_pending(self):
        cache_manager = getattr(self.app, "cache_manager", None)
        if cache_manager is None:
            return

        pending_paths = [
            p for p in cache_manager.get_paths_pending_health_analysis(self.file_paths) if os.path.exists(p)
        ]
        if not pending_paths:
            DialogManager.show_themed_dialog(
                self.app, "Sin pendientes", "Todas las pistas visibles ya tienen un análisis de calidad.",
                level="info", parent=self._host
            )
            return

        DialogManager.run_batch_health_check(
            self.app, pending_paths, parent=self._host, on_complete=lambda results, cancelled: self._host.refresh()
        )

    def _apply_diag_filter(self, dim_key):
        action = DIAG_FILTER_ACTIONS.get(dim_key)
        if not action:
            return
        if action[0] == "combo":
            _, field, value = action
            _set_combo_filter(self.app, field, value)
        else:
            _, toggle_key = action
            _set_toggle_filter(self.app, toggle_key)
