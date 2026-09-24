import math
import os
import customtkinter as ctk

from dialogs import DialogManager, _build_metric_chip
from stats_dashboard_view import (
    CHART_COLORS, GRID_COLOR, _new_figure, _embed_canvas, _bind_clickable,
    _set_combo_filter, _set_toggle_filter, _parse_rating, _parse_cues, _has_cover,
)
import theme

# Cross-filtering desde los chips de diagnóstico de completitud: qué control del
# panel de filtro avanzado activar por cada dimensión incompleta.
DIAG_FILTER_ACTIONS = {
    "album": ("combo", "Album", "[ Vacío ]"),
    "genre": ("combo", "Genre", "[ Vacío ]"),
    "publisher": ("combo", "Publisher", "[ Vacío ]"),
    "year": ("toggle", "no_year"),
    "cover": ("toggle", "no_cover"),
    "cues": ("toggle", "no_cues"),
    "rating": ("combo", "Rating", "0★"),
}


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

    dims = {
        "album": (has_album, "álbum", "Álbum"),
        "genre": (has_genre, "género", "Género"),
        "publisher": (has_publisher, "etiqueta", "Etiqueta"),
        "cues": (has_cues, "cue points", "Cue Points"),
        "rating": (has_rating, "valoración", "Rating"),
        "cover": (has_cover, "carátula", "Carátula"),
        "year": (has_year, "año", "Año"),
    }

    pct = {k: round((v[0] / total) * 100) for k, v in dims.items()}
    overall = round(sum(pct.values()) / len(pct))

    missing = [
        (k, v[1], total - v[0])
        for k, v in dims.items()
        if v[0] < total
    ]
    labels = [v[2] for v in dims.values()]
    values = [pct[k] for k in dims.keys()]

    return {
        "overall": overall,
        "labels": labels,
        "values": values,
        "missing": missing,
        "total": total,
    }


class HealthDashboardView(ctk.CTkFrame):
    """Vista de salud de la colección: auditoría técnica de audio (puntuación media,
    cobertura de análisis, falsos 320kbps, clipping, corruptos/truncados) Y
    completitud de metadatos (score global, radar por dimensión, campos que faltan).
    Acotada a la vista actual de la grilla (respeta filtros/búsqueda activos, no la
    biblioteca completa). Se embebe como una de las 3 pestañas conmutables de la app
    (ver App.switch_view en gui.py); self.file_paths se recalcula en cada refresh()
    en vez de fijarse una vez, para reflejar siempre el filtro vigente al activar la
    pestaña."""

    def __init__(self, app, parent):
        super().__init__(parent, fg_color=theme.BG_MAIN, corner_radius=0)
        self.app = app
        self.file_paths = []
        self._canvases = []

        self._build_header()

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.pack(fill="both", expand=True, padx=theme.SPACE_MD, pady=(0, theme.SPACE_MD))

        self.refresh()

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=theme.SPACE_MD, pady=theme.SPACE_MD)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            title_box, text="Salud de la Colección", anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H1, weight="bold"),
            text_color=theme.TEXT_MAIN
        ).pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            title_box, text="", anchor="w", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY)
        )
        self.lbl_subtitle.pack(anchor="w", pady=(2, 0))

        btns = ctk.CTkFrame(header, fg_color="transparent")
        btns.pack(side="right")

        ctk.CTkButton(
            btns, text="Actualizar", command=self.refresh, width=110,
            corner_radius=theme.RADIUS_CONTROL,
            fg_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY),
            hover_color=getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)
        ).pack(side="left", padx=(0, theme.SPACE_SM))

        ctk.CTkButton(
            btns, text="Ver Colección", command=lambda: self.app.switch_view("collection"), width=110,
            corner_radius=theme.RADIUS_CONTROL,
            fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_FOCUS, text_color=theme.TEXT_MAIN
        ).pack(side="left")

    def refresh(self):
        """Recalcula y repinta ambas secciones (auditoría técnica + completitud de
        metadatos), siempre sobre la vista actual de la grilla. Se llama al activar
        la pestaña y automáticamente cuando termina un lote de 'Analizar pendientes'."""
        if not self.winfo_exists():
            return

        for canvas, _ in self._canvases:
            try:
                canvas.get_tk_widget().destroy()
            except Exception:
                pass
        self._canvases.clear()

        for widget in self.scroll.winfo_children():
            widget.destroy()

        self.file_paths = self.app.grid_panel.get_visible_file_paths()
        self.lbl_subtitle.configure(
            text=f"Basado en la vista actual de la grilla: {len(self.file_paths)} pista(s) (respeta filtros/búsqueda activos)."
        )

        self._build_audio_health_section()
        self._build_metadata_health_section()

    # ------------------------------------------------------------------
    # Auditoría técnica de audio (falsos 320kbps, clipping, corruptos/truncados)
    # ------------------------------------------------------------------
    def _build_audio_health_section(self):
        cache_manager = getattr(self.app, "cache_manager", None)
        summary = cache_manager.get_health_summary_for_files(self.file_paths) if cache_manager else {}

        section = ctk.CTkFrame(self.scroll, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD)
        section.pack(fill="x", pady=(0, theme.SPACE_MD))

        ctk.CTkLabel(
            section, text="Auditoría Técnica de Audio", anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold"),
            text_color=theme.TEXT_MAIN
        ).pack(anchor="w", padx=theme.SPACE_MD, pady=(theme.SPACE_MD, theme.SPACE_SM))

        kpi_container = ctk.CTkFrame(section, fg_color="transparent")
        kpi_container.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM))

        alerts_container = ctk.CTkFrame(section, fg_color="transparent")
        alerts_container.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_MD))

        self.lbl_status = ctk.CTkLabel(
            section, text="", anchor="w", text_color=theme.TEXT_SUBTLE,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MICRO)
        )
        self.lbl_status.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_SM))

        btns = ctk.CTkFrame(section, fg_color="transparent")
        btns.pack(anchor="w", padx=theme.SPACE_MD, pady=(0, theme.SPACE_MD))
        self.btn_analyze_pending = ctk.CTkButton(
            btns, text="Analizar pendientes", command=self._analyze_pending, width=180,
            corner_radius=theme.RADIUS_CONTROL,
            fg_color=getattr(self.app, "CORP_COLOR", theme.PRIMARY),
            hover_color=getattr(self.app, "CORP_HOVER", theme.PRIMARY_HOVER)
        )
        self.btn_analyze_pending.pack(side="left")

        total_library = summary.get("total_library", 0)
        total_analyzed = summary.get("total_analyzed", 0)
        avg_score = summary.get("avg_health_score")
        coverage_pct = round((total_analyzed / total_library) * 100) if total_library else 0

        score_color = theme.STATUS_SUCCESS
        if avg_score is not None:
            if avg_score < 50:
                score_color = theme.STATUS_DANGER
            elif avg_score < 80:
                score_color = theme.STATUS_WARNING

        score_box = ctk.CTkFrame(kpi_container, fg_color="transparent")
        score_box.pack(side="left", padx=(0, theme.SPACE_LG))
        ctk.CTkLabel(
            score_box, text=(f"{avg_score}/100" if avg_score is not None else "—"),
            text_color=score_color,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_KPI, weight="bold")
        ).pack()
        ctk.CTkLabel(
            score_box, text="Salud media", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        ).pack()

        coverage_box = ctk.CTkFrame(kpi_container, fg_color="transparent")
        coverage_box.pack(side="left")
        ctk.CTkLabel(
            coverage_box, text=f"{total_analyzed} de {total_library} pistas ({coverage_pct}%)",
            text_color=theme.TEXT_MAIN,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold")
        ).pack(anchor="w")
        ctk.CTkLabel(
            coverage_box, text="Cobertura de análisis", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        ).pack(anchor="w")

        for flag_key, label, count, color in (
            ("bitrate_fake", "Falsos 320kbps", summary.get("bitrate_fake_count", 0), theme.STATUS_WARNING),
            ("clipping", "Clipping", summary.get("clipping_count", 0), theme.STATUS_DANGER),
            ("integrity_issue", "Corruptos/truncados", summary.get("integrity_issue_count", 0), theme.STATUS_DANGER),
        ):
            chip = _build_metric_chip(alerts_container, label, count, color)
            chip.pack(side="left", padx=(0, theme.SPACE_SM))
            if count > 0:
                _bind_clickable(chip, lambda fk=flag_key, lb=label: self._filter_by_health_flag(fk, lb))

        pending_count = max(0, total_library - total_analyzed)
        if pending_count > 0:
            self.lbl_status.configure(text=f"{pending_count} pista(s) sin analizar todavía.")
            self.btn_analyze_pending.configure(state="normal", text=f"Analizar pendientes ({pending_count})")
        else:
            has_visible = total_library > 0
            self.lbl_status.configure(
                text="Todas las pistas visibles tienen análisis de salud." if has_visible
                else "No hay pistas visibles en la tabla (revisa los filtros aplicados)."
            )
            self.btn_analyze_pending.configure(state="disabled", text="Analizar pendientes")

    def _filter_by_health_flag(self, flag_key, label):
        """Cross-filtering: clic en un chip de alerta filtra la grilla a las pistas
        (de self.file_paths, la vista actual) que tienen ese problema de salud."""
        cache_manager = getattr(self.app, "cache_manager", None)
        grid = getattr(self.app, "grid_panel", None)
        if cache_manager is None or grid is None:
            return

        paths = cache_manager.get_paths_by_health_flag(self.file_paths, flag_key)
        if not paths:
            return

        grid.apply_health_path_filter(paths, f"{label} ({len(paths)})")
        self.app.switch_view("collection")

    def _analyze_pending(self):
        cache_manager = getattr(self.app, "cache_manager", None)
        if cache_manager is None:
            return

        pending_paths = [
            p for p in cache_manager.get_paths_pending_health_analysis(self.file_paths) if os.path.exists(p)
        ]
        if not pending_paths:
            DialogManager.show_themed_dialog(
                self.app, "Sin pendientes", "Todas las pistas visibles ya tienen un análisis de salud.",
                level="info", parent=self
            )
            return

        DialogManager.run_batch_health_check(
            self.app, pending_paths, parent=self, on_complete=lambda results, cancelled: self.refresh()
        )

    # ------------------------------------------------------------------
    # Completitud de metadatos (score global, radar por dimensión, diagnóstico)
    # ------------------------------------------------------------------
    def _build_metadata_health_section(self):
        tracks = self.app.grid_panel.get_visible_tracks_data()
        metrics = _compute_health_metrics(tracks)
        if metrics is None:
            return

        section = ctk.CTkFrame(self.scroll, fg_color=theme.BG_CARD, corner_radius=theme.RADIUS_CARD)
        section.pack(fill="x", pady=(0, theme.SPACE_MD))

        ctk.CTkLabel(
            section, text="Completitud de Metadatos", anchor="w",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_H2, weight="bold"),
            text_color=theme.TEXT_MAIN
        ).pack(anchor="w", padx=theme.SPACE_MD, pady=(theme.SPACE_MD, theme.SPACE_SM))

        body = ctk.CTkFrame(section, fg_color="transparent")
        body.pack(fill="x", padx=theme.SPACE_MD, pady=(0, theme.SPACE_MD))

        # Anillo de score
        score_box = ctk.CTkFrame(body, fg_color="transparent")
        score_box.pack(side="left", padx=(0, theme.SPACE_LG))
        self._build_score_ring(score_box, metrics["overall"])

        # Radar de completitud
        radar_box = ctk.CTkFrame(body, fg_color="transparent")
        radar_box.pack(side="left", padx=(0, theme.SPACE_LG))
        self._build_radar_chart(radar_box, metrics["labels"], metrics["values"])

        # Chips de diagnóstico
        diag_box = ctk.CTkFrame(body, fg_color="transparent")
        diag_box.pack(side="left", fill="both", expand=True, anchor="n")

        if not metrics["missing"]:
            ctk.CTkLabel(
                diag_box, text="✨ Colección 100% completada", text_color=theme.STATUS_SUCCESS,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, weight="bold")
            ).pack(anchor="w", pady=theme.SPACE_SM)
        else:
            chips_wrap = ctk.CTkFrame(diag_box, fg_color="transparent")
            chips_wrap.pack(anchor="w", pady=theme.SPACE_SM)
            row = None
            for i, (dim_key, label, count) in enumerate(metrics["missing"]):
                if i % 2 == 0:
                    row = ctk.CTkFrame(chips_wrap, fg_color="transparent")
                    row.pack(anchor="w", pady=(0, theme.SPACE_XS))
                chip = _build_metric_chip(row, f"sin {label}", count, theme.STATUS_WARNING)
                chip.pack(side="left", padx=(0, theme.SPACE_SM))
                _bind_clickable(chip, lambda k=dim_key: self._apply_diag_filter(k))

    def _build_score_ring(self, parent, score):
        color = _health_status_color(score)
        fig, ax = _new_figure(200, 200, polar=False)
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        remainder = max(0, 100 - score)
        if score <= 0:
            ax.pie([1], colors=[theme.BG_CARD_HOVER], wedgeprops=dict(width=0.28, edgecolor=theme.BG_CARD))
        else:
            ax.pie(
                [score, remainder] if remainder > 0 else [score],
                colors=[color, theme.BG_CARD_HOVER] if remainder > 0 else [color],
                startangle=90, counterclock=False,
                wedgeprops=dict(width=0.28, edgecolor=theme.BG_CARD)
            )
        ax.text(0, 0.12, f"{score}%", ha="center", va="center", color=theme.TEXT_MAIN,
                 fontsize=20, fontweight="bold")
        ax.text(0, -0.25, _health_status_text(score), ha="center", va="center", color=color,
                 fontsize=10, fontweight="bold")
        ax.set_aspect("equal")

        canvas, widget = _embed_canvas(parent, fig)
        widget.pack()
        self._canvases.append((canvas, fig))

        ctk.CTkLabel(
            parent, text="Score global", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        ).pack(pady=(theme.SPACE_XS, 0))

    def _build_radar_chart(self, parent, labels, values):
        n = len(labels)
        angles = [i / n * 2 * math.pi for i in range(n)]
        angles += angles[:1]
        plot_values = values + values[:1]

        fig, ax = _new_figure(320, 240, polar=True)
        fig.subplots_adjust(left=0.08, right=0.92, top=0.88, bottom=0.12)

        ax.plot(angles, plot_values, color=CHART_COLORS[0], linewidth=2)
        ax.fill(angles, plot_values, color=CHART_COLORS[0], alpha=0.3)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(labels, color=theme.TEXT_MAIN, fontsize=8, fontweight="bold")
        ax.set_ylim(0, 100)
        ax.set_yticks([20, 40, 60, 80, 100])
        ax.set_yticklabels(["20", "40", "60", "80", "100"], color=theme.TEXT_MUTED, fontsize=7)
        ax.spines["polar"].set_color(GRID_COLOR[:3])
        ax.grid(True, color=GRID_COLOR[:3], alpha=0.6)

        canvas, widget = _embed_canvas(parent, fig)
        widget.pack()
        self._canvases.append((canvas, fig))

        ctk.CTkLabel(
            parent, text="Completitud por dimensión", text_color=theme.TEXT_MUTED,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BADGE)
        ).pack(pady=(theme.SPACE_XS, 0))

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
        # A diferencia del Dashboard, la Salud sí vuelve a Colección al filtrar: aquí
        # no tiene sentido "quedarse" (esta pestaña no muestra listados de pistas).
        self.app.switch_view("collection")
