import base64
import io
import os
import sqlite3
import tempfile
import zipfile
from tkinter import filedialog, messagebox

from mutagen import File
from mutagen.flac import FLAC
from mutagen.id3 import APIC
from PIL import Image


class SQLiteManager:
    """Maneja la creación de la base de datos SQLite y la inserción de tracks/carátulas."""

    @staticmethod
    def create_database(db_path, tracks_data):
        """Crea el esquema SQLite con índices B-Tree e inserta las canciones."""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT,
                artist TEXT,
                title TEXT,
                remix TEXT,
                album TEXT,
                genre TEXT,
                publisher TEXT,
                year TEXT,
                cues INTEGER,
                rating INTEGER,
                cover_blob TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search ON tracks(artist, title, album, genre, publisher);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genre ON tracks(genre);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_album ON tracks(album);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_publisher ON tracks(publisher);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_year ON tracks(year);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_filename ON tracks(filename);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_artist_title ON tracks(artist, title);")

        cursor.executemany("""
            INSERT INTO tracks (filename, artist, title, remix, album, genre, publisher, year, cues, rating, cover_blob)
            VALUES (:filename, :artist, :title, :remix, :album, :genre, :publisher, :year, :cues, :rating, :cover_blob)
        """, tracks_data)

        conn.commit()
        conn.close()


class TemplateProvider:
    """Genera las plantillas estáticas para la WebApp desplegable en Netlify."""

    @staticmethod
    def get_index_html():
        return """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Sonometa">
    <title>Sonometa - Mi Colección</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/sql-wasm.js"></script>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="header">
        <div class="brand-container no-select" oncontextmenu="return false;">
            <div class="brand-logo-wrapper">
                <svg class="brand-logo-svg" viewBox="0 0 81 78" fill="none" xmlns="http://www.w3.org/2000/svg" draggable="false">
                    <path d="M27.5926 12.3934C29.8925 9.77124 33.253 8.27092 36.7919 8.27092H56.6772C66.2446 8.27092 74 16.0263 74 25.5937V52.4063C74 61.9737 66.2446 69.7291 56.6772 69.7291H36.7919C33.253 69.7291 29.8925 68.2288 27.5926 65.6066L8.76406 44.1332C6.11281 41.1098 6.11281 36.8902 8.76406 33.8668L27.5926 12.3934Z" stroke="url(#sonometa_grad)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="22.5" cy="39" r="4.5" fill="url(#sonometa_grad)"/>
                    <defs>
                        <linearGradient id="sonometa_grad" x1="74" y1="8.27092" x2="7" y2="69.7291" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stop-color="#6366F1"/>
                            <stop offset="50%" stop-color="#8B5CF6"/>
                            <stop offset="100%" stop-color="#EC4899"/>
                        </linearGradient>
                    </defs>
                </svg>
            </div>
            <div class="brand-text">
                <div class="brand-title-row">
                    <span class="brand-title">Sonometa</span>
                    <span class="brand-version">v1.3</span>
                </div>
                <span class="brand-subtitle">AUDIO TAG SUITE</span>
            </div>
        </div>
        <div class="header-actions">
            <button id="btnDashboard" class="btn-primary btn-header" style="display:none;" onclick="switchView('dashboard')">Ver dashboards</button>
            <button id="btnTable" class="btn-primary btn-header" onclick="switchView('table')">Ver mi colección</button>
        </div>
    </div>

    <!-- BARRA GLOBAL / RESUMEN DE FILTROS EN EL DASHBOARD -->
    <div id="filterSummaryBar" class="filter-summary-bar">
        <div class="filter-summary-info">
            <button class="btn-filter-trigger" onclick="openFilterModal()">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>
                <span>Filtrar colección</span>
                <span id="activeFilterBadge" class="filter-badge" style="display:none;">0</span>
            </button>
            <span id="filterSummaryText" class="filter-summary-text">Sin filtros aplicados</span>
        </div>
        <button id="btnGlobalResetFilters" class="btn-reset-compact" onclick="resetAllFilters()" style="display:none;">✕ Limpiar</button>
    </div>

    <!-- DASHBOARD VIEW -->
    <div id="dashboardView">
        <div class="kpi-card">
            <div class="kpi-value" id="kpiTotalTracks">0</div>
            <div class="kpi-label">CANCIONES EN TU COLECCIÓN</div>
        </div>

        <div class="charts-grid">
            <div class="chart-card">
                <h3>DISTRIBUCIÓN POR ÁLBUM</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-pie-container"><canvas id="albumChart"></canvas></div>
                    <div id="albumLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>DISTRIBUCIÓN POR GÉNERO</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-pie-container"><canvas id="genreChart"></canvas></div>
                    <div id="genreLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>PISTAS POR ETIQUETA</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-bar-container"><canvas id="publisherChart"></canvas></div>
                    <div id="publisherLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>LANZAMIENTOS POR AÑO</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-bar-container"><canvas id="yearChart"></canvas></div>
                    <div id="yearLegend" class="custom-legend"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- TABLE VIEW -->
    <div id="tableView" style="display:none;">
        <div class="controls-panel desktop-only-controls">
            <div class="search-box">
                <input type="text" id="searchInput" class="search-input" placeholder="Buscar canción..." oninput="debouncedSearch()">
            </div>
            <!-- El contenedor de filtros del escritorio -->
            <div id="desktopFilterContainer" class="controls-row-filters"></div>
        </div>

        <div class="table-toolbar">
            <div class="results-text" id="resultsCount">0 resultados</div>
            <div class="toggle-container no-select">
                <span class="toggle-label">Ver detalle</span>
                <label class="switch">
                    <input type="checkbox" id="chkVerDetalle" onchange="toggleVerDetalle()">
                    <span class="slider round"></span>
                </label>
            </div>
        </div>

        <div class="table-container">
            <table id="dataTable">
                <thead id="tableHeader"></thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>

        <div class="pagination-controls" id="paginationControls" style="display:none;">
            <button id="prevBtn" class="btn-primary" onclick="changePage(-1)">Anterior</button>
            <span id="pageInfo">Página 1 de 1</span>
            <button id="nextBtn" class="btn-primary" onclick="changePage(1)">Siguiente</button>
        </div>
    </div>

    <!-- MODAL / BOTTOM SHEET DE FILTROS EN MÓVIL -->
    <div id="filterOverlay" class="filter-overlay" onclick="closeFilterModal()"></div>
    <div id="filterModal" class="filter-bottom-sheet">
        <div class="sheet-header">
            <div class="sheet-drag-handle"></div>
            <h3>Filtrar Colección</h3>
            <button class="sheet-close-btn" onclick="closeFilterModal()">✕</button>
        </div>
        <div class="sheet-body">
            <div class="search-box" style="margin-bottom: 12px;">
                <input type="text" id="searchInputMobile" class="search-input" placeholder="Buscar canción..." oninput="syncMobileSearch(this.value)">
            </div>
            <div id="mobileFilterContainer" class="mobile-filters-grid"></div>
        </div>
        <div class="sheet-footer">
            <button class="btn-reset" onclick="resetAllFilters()">Limpiar todo</button>
            <button class="btn-primary btn-apply" onclick="applyFiltersAndClose()">Aplicar filtros</button>
        </div>
    </div>

    <script src="app.js"></script>
</body>
</html>"""

    @staticmethod
    def get_styles_css():
        return """
:root {
    --bg-color: #1A1A1E;
    --surface-color: #24242A;
    --surface-hover: #2E2E36;
    --border-color: #363640;
    --border-highlight: #4B4B58;
    --primary-purple: #8B5CF6;
    --primary-hover: #7C3AED;
    --text-main: #F4F4F5;
    --text-muted: #A1A1AA;
    --text-subtle: #71717A;
    --row-even: #1F1F24;
    --input-bg: #2D2D35;
}

* { box-sizing: border-box; }

body {
    background-color: var(--bg-color);
    color: var(--text-main);
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    margin: 0;
    padding: 12px;
    -webkit-font-smoothing: antialiased;
}

@media (min-width: 768px) { body { padding: 28px; } }

.no-select {
    -webkit-user-select: none;
    -moz-user-select: none;
    -ms-user-select: none;
    user-select: none;
    -webkit-user-drag: none;
}

.header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
}

.brand-container { display: flex; align-items: center; gap: 10px; cursor: default; }
.brand-logo-wrapper { width: 34px; height: 28px; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.brand-logo-svg { width: 100%; height: 100%; display: block; pointer-events: none; }
.brand-text { display: flex; flex-direction: column; }
.brand-title-row { display: flex; align-items: baseline; gap: 6px; }
.brand-title { font-size: 18px; font-weight: 700; color: #FFFFFF; line-height: 1; }
.brand-version { font-size: 12px; font-weight: 600; color: #8B5CF6; }
.brand-subtitle { font-size: 8px; font-weight: 600; letter-spacing: 1.2px; color: var(--text-muted); margin-top: 2px; }

.header-actions { display: flex; align-items: center; gap: 8px; }

.btn-primary {
    background-color: var(--primary-purple);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 8px 14px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
}
.btn-primary:hover { background-color: var(--primary-hover); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-header {
    width: 140px;
    text-align: center;
    white-space: nowrap;
}

/* BARRA DE RESUMEN DE FILTROS EN CABECERA */
.filter-summary-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 10px;
    padding: 8px 12px;
    margin-bottom: 16px;
    gap: 10px;
}

.filter-summary-info {
    display: flex;
    align-items: center;
    gap: 10px;
    overflow: hidden;
}

.btn-filter-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background-color: var(--input-bg);
    color: var(--text-main);
    border: 1px solid var(--border-highlight);
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
    transition: background-color 0.2s;
}
.btn-filter-trigger:hover { background-color: var(--surface-hover); }

.filter-badge {
    background-color: var(--primary-purple);
    color: white;
    font-size: 10px;
    font-weight: 700;
    border-radius: 10px;
    padding: 1px 6px;
    line-height: 1.2;
}

.filter-summary-text {
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.btn-reset-compact {
    background: transparent;
    border: none;
    color: #EF4444;
    font-size: 11px;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    white-space: nowrap;
}
.btn-reset-compact:hover { background-color: rgba(239, 68, 68, 0.1); }

.btn-reset {
    background-color: transparent;
    color: var(--text-muted);
    border: 1px solid var(--border-color);
    padding: 8px 12px;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
}
.btn-reset:hover {
    color: #EF4444;
    border-color: #EF4444;
    background-color: rgba(239, 68, 68, 0.1);
}

.kpi-card {
    background: linear-gradient(180deg, #2D243A 0%, var(--surface-color) 100%);
    border: 1px solid var(--border-highlight);
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    margin-bottom: 20px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--primary-purple), transparent);
}
.kpi-value {
    font-size: 48px; font-weight: 800; color: #FFFFFF; line-height: 1;
    letter-spacing: -1px; margin-bottom: 6px; text-shadow: 0 0 20px rgba(168, 85, 247, 0.3);
}
.kpi-label { font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: var(--text-muted); font-weight: 600; }

.charts-grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-bottom: 16px; }
@media (min-width: 1024px) { .charts-grid { grid-template-columns: repeat(2, 1fr); } }

.chart-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}
.chart-card h3 {
    margin-top: 0; 
    margin-bottom: 14px; 
    font-size: 11px; 
    font-weight: 700;
    letter-spacing: 0.8px; 
    color: var(--text-subtle);
    text-transform: uppercase;
    border-bottom: 1px solid var(--border-color); 
    padding-bottom: 10px;
}

.chart-flex-wrapper { display: flex; flex-direction: column; gap: 12px; align-items: center; }
@media (min-width: 600px) { .chart-flex-wrapper { flex-direction: row; justify-content: space-between; align-items: center; } }

.canvas-pie-container, .canvas-bar-container { position: relative; height: 180px; width: 100%; max-width: 180px; flex-shrink: 0; }
.canvas-bar-container { max-width: 210px; }

.custom-legend { width: 100%; font-size: 11px; max-height: 180px; overflow-y: auto; padding-right: 4px; }
.custom-legend::-webkit-scrollbar { width: 4px; }
.custom-legend::-webkit-scrollbar-thumb { background: var(--border-highlight); border-radius: 2px; }

.legend-header {
    display: flex; justify-content: space-between; color: var(--text-muted);
    font-size: 10px; font-weight: 700; text-transform: lowercase;
    padding-bottom: 6px; margin-bottom: 4px; border-bottom: 1px solid var(--border-color);
}
.legend-header span:first-child { flex: 1; }
.legend-header span.val-col { width: 65px; text-align: right; margin-right: 12px; }
.legend-header span.pct-col { width: 65px; text-align: right; }

.legend-item { display: flex; align-items: center; padding: 4px 0; color: #E4E4E7; border-bottom: 1px solid rgba(255, 255, 255, 0.03); }
.legend-color { width: 8px; height: 8px; border-radius: 2px; margin-right: 8px; display: inline-block; flex-shrink: 0; }
.legend-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 11px; }
.legend-val { width: 65px; text-align: right; font-weight: 600; color: #FFFFFF; margin-right: 12px; }
.legend-pct { width: 65px; text-align: right; color: var(--text-muted); font-size: 10px; }

/* CONTROLES DE ESCRITORIO */
.controls-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 8px;
}
.search-box { width: 100%; }

@media (max-width: 767px) {
    .desktop-only-controls { display: none; }
}

.controls-row-filters {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.filter-select, .search-input {
    background-color: var(--input-bg);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 8px 10px;
    color: var(--text-main);
    font-size: 12px;
    outline: none;
    width: 100%;
    transition: border-color 0.2s, box-shadow 0.2s;
}

@media (min-width: 768px) {
    .filter-select { flex: 1; min-width: 140px; }
}

.filter-select.active-filter {
    border-color: var(--primary-purple);
    box-shadow: 0 0 0 1px var(--primary-purple);
    background-color: #272335;
}

/* MODAL Y BOTTOM SHEET MÓVIL */
.filter-overlay {
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    background-color: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(2px);
    z-index: 999;
    opacity: 0; pointer-events: none;
    transition: opacity 0.25s ease;
}
.filter-overlay.active { opacity: 1; pointer-events: auto; }

.filter-bottom-sheet {
    position: fixed; bottom: 0; left: 0; right: 0;
    background-color: var(--surface-color);
    border-top-left-radius: 18px;
    border-top-right-radius: 18px;
    border: 1px solid var(--border-highlight);
    border-bottom: none;
    z-index: 1000;
    padding: 16px;
    transform: translateY(100%);
    transition: transform 0.3s cubic-bezier(0.1, 0.9, 0.2, 1);
    max-height: 85vh;
    display: flex;
    flex-direction: column;
}
.filter-bottom-sheet.active { transform: translateY(0); }

.sheet-header {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 12px;
}
.sheet-drag-handle {
    position: absolute; top: -8px; left: 50%; transform: translateX(-50%);
    width: 36px; height: 4px; background-color: var(--border-highlight);
    border-radius: 2px;
}
.sheet-header h3 { margin: 0; font-size: 14px; font-weight: 700; color: #FFFFFF; }
.sheet-close-btn { background: none; border: none; color: var(--text-muted); font-size: 16px; cursor: pointer; padding: 4px; }

.sheet-body { overflow-y: auto; flex: 1; padding-right: 2px; }
.mobile-filters-grid { display: flex; flex-direction: column; gap: 10px; }

.sheet-footer {
    display: flex;
    gap: 10px;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--border-color);
}
.sheet-footer .btn-reset { flex: 1; }
.sheet-footer .btn-apply { flex: 2; text-align: center; }

/* TABLA Y HERRAMIENTAS */
.table-toolbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 6px 10px 6px;
}
.results-text { font-size: 12px; font-weight: 600; color: var(--text-muted); }

.toggle-container { display: flex; align-items: center; gap: 8px; }
.toggle-label { font-size: 12px; font-weight: 500; color: var(--text-main); white-space: nowrap; }
.switch { position: relative; display: inline-block; width: 34px; height: 18px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
    position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
    background-color: #3F3F46; transition: .3s; border-radius: 20px;
}
.slider:before {
    position: absolute; content: ""; height: 12px; width: 12px; left: 3px; bottom: 3px;
    background-color: white; transition: .3s; border-radius: 50%;
}
input:checked + .slider { background-color: var(--primary-purple); }
input:checked + .slider:before { transform: translateX(16px); }

.table-container { background-color: var(--surface-color); border: 1px solid var(--border-color); border-radius: 12px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: left; }
th { background-color: #1B1B20; color: var(--text-muted); font-weight: 600; padding: 10px 12px; border-bottom: 1px solid var(--border-color); font-size: 10px; text-transform: uppercase; white-space: nowrap; }
td { padding: 8px 12px; border-bottom: 1px solid var(--border-color); color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 180px; vertical-align: middle; }
tr:nth-child(even) { background-color: var(--row-even); }
tr { transition: background-color 0.15s ease; cursor: pointer; }
tr:hover { background-color: var(--surface-hover); }
tr.selected-row, tr.selected-row td { background-color: #2F2643 !important; }
tr.selected-row td:first-child { border-left: 3px solid var(--primary-purple); }
tr.selected-row td { border-top: 1px solid rgba(139, 92, 246, 0.4); border-bottom: 1px solid rgba(139, 92, 246, 0.4); }

.th-cover { width: 50px; text-align: center; }
.td-cover { width: 50px; text-align: center; padding: 4px 8px; vertical-align: middle; }
.cover-badge { display: inline-flex; align-items: center; justify-content: center; width: 38px; height: 38px; background-color: #1B1B20; border: 1px solid #363640; border-radius: 6px; color: #52525B; font-size: 10px; font-weight: 600; }
.cover-thumb { width: 38px; height: 38px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color); display: inline-block; vertical-align: middle; transition: transform 0.2s ease, box-shadow 0.2s ease; }
.cover-thumb:hover { transform: scale(1.2); box-shadow: 0 4px 12px rgba(0,0,0,0.5); position: relative; z-index: 2; }

.col-center { text-align: center !important; }
.text-subtle { color: var(--text-subtle) !important; font-weight: 400; }
.pagination-controls { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding: 0 4px; font-size: 12px; }
"""

    @staticmethod
    def get_app_js():
        return """
let db = null;
let currentPage = 0;
const PAGE_SIZE = 100;
const COLORS = ['#10B981', '#F59E0B', '#3B82F6', '#EF4444', '#9333EA', '#EC4899', '#14B8A6', '#8B5CF6', '#64748B'];

let chartInstances = {};

// Estado global de filtros en memoria
let currentFilters = {
    search: '',
    album: '',
    genre: '',
    publisher: '',
    year: ''
};

Chart.defaults.color = '#A1A1AA';
Chart.defaults.borderColor = '#363640';

async function initSQLite() {
    const sqlPromise = initSqlJs({
        locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
    });
    const dataPromise = fetch('data.db').then(res => res.arrayBuffer());
    const [SQL, buf] = await Promise.all([sqlPromise, dataPromise]);
    
    db = new SQL.Database(new Uint8Array(buf));
    populateSelectFilters();
    updateDashboard();
    loadTableData();
}

function renderCustomLegend(containerId, labels, dataVals) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const total = dataVals.reduce((a, b) => a + b, 0);

    let html = `
        <div class="legend-header">
            <span></span>
            <span class="val-col">valores</span>
            <span class="pct-col">porcentaje</span>
        </div>
    `;

    labels.forEach((label, i) => {
        const val = dataVals[i];
        const pct = total > 0 ? ((val / total) * 100).toFixed(2) + '%' : '0%';
        const color = COLORS[i % COLORS.length];

        html += `
            <div class="legend-item">
                <span class="legend-color" style="background-color: ${color};"></span>
                <span class="legend-name" title="${label}">${label}</span>
                <span class="legend-val">${val.toLocaleString('es-ES')}</span>
                <span class="legend-pct">${pct}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Reconstruye o actualiza las gráficas aplicando la condición WHERE de los filtros activos
function updateDashboard() {
    if (!db) return;

    const whereSql = getActiveWhereClauses();

    // Actualizar KPI Total
    const resTotal = db.exec(`SELECT COUNT(*) FROM tracks ${whereSql}`);
    const totalTracks = (resTotal.length && resTotal[0].values.length) ? resTotal[0].values[0][0] : 0;
    const totalElem = document.getElementById('kpiTotalTracks');
    if (totalElem) {
        totalElem.textContent = totalTracks.toLocaleString('es-ES');
    }

    const buildChart = (canvasId, legendId, column, defaultLabel, chartType, sortAsc = false) => {
        const query = `
            SELECT CASE WHEN ${column} IS NULL OR ${column} = '' THEN '${defaultLabel}' ELSE ${column} END as label_name, 
            COUNT(*) as c 
            FROM tracks ${whereSql} 
            GROUP BY 1 
            ORDER BY ${sortAsc ? '1 ASC' : 'c DESC'}
        `;

        let labels = [];
        let dataVals = [];

        try {
            const res = db.exec(query);
            if (res.length && res[0].values) {
                labels = res[0].values.map(v => v[0] || defaultLabel);
                dataVals = res[0].values.map(v => v[1]);
            }
        } catch(err) {
            console.error(`Error calculando gráfica ${canvasId}:`, err);
        }

        const sliceColors = labels.map((_, i) => COLORS[i % COLORS.length]);
        const chartCanvas = document.getElementById(canvasId);
        if (!chartCanvas) return;

        // Destruir instancia previa de Chart si existe para refrescar los datos
        if (chartInstances[canvasId]) {
            chartInstances[canvasId].destroy();
        }

        const chartConfig = {
            type: chartType,
            data: {
                labels: labels,
                datasets: [{
                    data: dataVals,
                    backgroundColor: sliceColors,
                    borderWidth: chartType === 'pie' ? 1 : 0,
                    borderColor: '#24242A',
                    borderRadius: chartType === 'bar' ? 4 : 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        };

        if (chartType === 'bar') {
            chartConfig.options.scales = {
                x: { display: false },
                y: { beginAtZero: true, grid: { color: '#363640' } }
            };
        }

        chartInstances[canvasId] = new Chart(chartCanvas, chartConfig);
        renderCustomLegend(legendId, labels, dataVals);
    };

    buildChart('albumChart', 'albumLegend', 'album', 'Sin Álbum', 'pie');
    buildChart('genreChart', 'genreLegend', 'genre', 'Sin Género', 'pie');
    // Pistas por etiqueta ahora ordenado alfabéticamente (sortAsc = true)
    buildChart('publisherChart', 'publisherLegend', 'publisher', 'Sin Etiqueta', 'bar', true);
    buildChart('yearChart', 'yearLegend', 'year', 'Sin Año', 'bar', true);
}

// Construye la cláusula WHERE usando el objeto de estado currentFilters
function getActiveWhereClauses(excludeKey = null) {
    let whereClauses = [];

    if (currentFilters.search) {
        const searchEscaped = currentFilters.search.replace(/'/g, "''");
        whereClauses.push(`(artist LIKE '%${searchEscaped}%' OR title LIKE '%${searchEscaped}%' OR album LIKE '%${searchEscaped}%' OR filename LIKE '%${searchEscaped}%' OR remix LIKE '%${searchEscaped}%')`);
    }

    const filterMapping = [
        { key: 'album', col: 'album' },
        { key: 'genre', col: 'genre' },
        { key: 'publisher', col: 'publisher' },
        { key: 'year', col: 'year' }
    ];

    filterMapping.forEach(f => {
        if (f.key === excludeKey) return;
        const val = currentFilters[f.key];
        if (!val) return;

        const valEscaped = val.replace(/'/g, "''");
        if (valEscaped === "__EMPTY__") {
            whereClauses.push(`(${f.col} IS NULL OR ${f.col} = '')`);
        } else {
            whereClauses.push(`${f.col} = '${valEscaped}'`);
        }
    });

    return whereClauses.length ? 'WHERE ' + whereClauses.join(' AND ') : '';
}

function populateSelectFilters() {
    const filterDefs = [
        { id: 'albumFilter', key: 'album', col: 'album', defaultLabel: 'Álbum: Todos', emptyLabel: 'Sin Álbum' },
        { id: 'genreFilter', key: 'genre', col: 'genre', defaultLabel: 'Género: Todos', emptyLabel: 'Sin Género' },
        { id: 'publisherFilter', key: 'publisher', col: 'publisher', defaultLabel: 'Etiqueta: Todas', emptyLabel: 'Sin Etiqueta' },
        { id: 'yearFilter', key: 'year', col: 'year', defaultLabel: 'Año: Todos', emptyLabel: 'Sin Año' }
    ];

    const desktopContainer = document.getElementById('desktopFilterContainer');
    const mobileContainer = document.getElementById('mobileFilterContainer');

    if (desktopContainer) desktopContainer.innerHTML = '';
    if (mobileContainer) mobileContainer.innerHTML = '';

    filterDefs.forEach(f => {
        const savedValue = currentFilters[f.key];
        const whereSql = getActiveWhereClauses(f.key);

        const createSelectElem = (selectId) => {
            const select = document.createElement('select');
            select.id = selectId;
            select.className = 'filter-select';
            select.onchange = (e) => handleFilterChange(f.key, e.target.value);

            const optAll = document.createElement('option');
            optAll.value = "";
            optAll.textContent = f.defaultLabel;
            select.appendChild(optAll);

            const emptyQuery = `SELECT COUNT(*) FROM tracks ${whereSql} ${whereSql ? 'AND' : 'WHERE'} (${f.col} IS NULL OR ${f.col} = '')`;
            try {
                const resEmpty = db.exec(emptyQuery);
                if (resEmpty.length && resEmpty[0].values[0][0] > 0) {
                    const optEmpty = document.createElement('option');
                    optEmpty.value = "__EMPTY__";
                    optEmpty.textContent = f.emptyLabel;
                    select.appendChild(optEmpty);
                }
            } catch (err) {}

            const distinctQuery = `SELECT DISTINCT ${f.col} FROM tracks ${whereSql} ${whereSql ? 'AND' : 'WHERE'} ${f.col} IS NOT NULL AND ${f.col} != '' ORDER BY ${f.col} ASC`;
            try {
                const res = db.exec(distinctQuery);
                if (res.length && res[0].values) {
                    res[0].values.forEach(v => {
                        const opt = document.createElement('option');
                        opt.value = v[0];
                        opt.textContent = v[0];
                        select.appendChild(opt);
                    });
                }
            } catch (err) {}

            const exists = Array.from(select.options).some(o => o.value === savedValue);
            select.value = exists ? savedValue : "";
            if (!exists && savedValue) currentFilters[f.key] = "";

            if (savedValue) select.classList.add('active-filter');

            return select;
        };

        if (desktopContainer) desktopContainer.appendChild(createSelectElem(f.id));
        if (mobileContainer) mobileContainer.appendChild(createSelectElem(f.id + '_mobile'));
    });

    updateFilterSummaryBar();
}

function updateFilterSummaryBar() {
    let activeCount = 0;
    let activeNames = [];

    if (currentFilters.search) {
        activeCount++;
        activeNames.push(`"${currentFilters.search}"`);
    }

    const mapping = { album: 'Álbum', genre: 'Género', publisher: 'Etiqueta', year: 'Año' };
    Object.keys(mapping).forEach(k => {
        if (currentFilters[k]) {
            activeCount++;
            const valLabel = currentFilters[k] === '__EMPTY__' ? 'Sin valor' : currentFilters[k];
            activeNames.push(`${mapping[k]}: ${valLabel}`);
        }
    });

    const badge = document.getElementById('activeFilterBadge');
    const summaryText = document.getElementById('filterSummaryText');
    const resetBtn = document.getElementById('btnGlobalResetFilters');

    if (badge) {
        badge.style.display = activeCount > 0 ? 'inline-block' : 'none';
        badge.textContent = activeCount;
    }

    if (summaryText) {
        summaryText.textContent = activeCount > 0 ? activeNames.join(' | ') : 'Sin filtros aplicados';
    }

    if (resetBtn) {
        resetBtn.style.display = activeCount > 0 ? 'inline-block' : 'none';
    }
}

function handleFilterChange(key, value) {
    currentFilters[key] = value;
    populateSelectFilters();
    if (window.innerWidth >= 768) {
        applyFilters();
    }
}

function applyFilters() {
    updateDashboard();
    resetAndSearch();
}

function applyFiltersAndClose() {
    applyFilters();
    closeFilterModal();
}

function syncMobileSearch(val) {
    currentFilters.search = val.trim();
    const searchDesktop = document.getElementById('searchInput');
    if (searchDesktop) searchDesktop.value = val;
    populateSelectFilters();
}

function openFilterModal() {
    const searchMobile = document.getElementById('searchInputMobile');
    if (searchMobile) searchMobile.value = currentFilters.search;

    document.getElementById('filterOverlay').classList.add('active');
    document.getElementById('filterModal').classList.add('active');
}

function closeFilterModal() {
    document.getElementById('filterOverlay').classList.remove('active');
    document.getElementById('filterModal').classList.remove('active');
}

function resetAllFilters() {
    currentFilters = { search: '', album: '', genre: '', publisher: '', year: '' };

    const searchInput = document.getElementById('searchInput');
    if (searchInput) searchInput.value = '';

    const searchInputMobile = document.getElementById('searchInputMobile');
    if (searchInputMobile) searchInputMobile.value = '';

    populateSelectFilters();
    applyFilters();
}

function loadTableData() {
    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const resultsCountElem = document.getElementById('resultsCount');

    if (!chkVerDetalle) return;

    const verDetalle = chkVerDetalle.checked;
    const whereSql = getActiveWhereClauses();

    const countQuery = `SELECT COUNT(*) FROM tracks ${whereSql}`;
    let totalRecords = 0;
    try {
        const countRes = db.exec(countQuery);
        if (countRes.length && countRes[0].values.length) {
            totalRecords = countRes[0].values[0][0];
        }
    } catch (err) {
        console.error("Error al contar registros:", err);
    }

    const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
    if (currentPage >= totalPages && totalPages > 0) {
        currentPage = totalPages - 1;
    }

    const offset = currentPage * PAGE_SIZE;

    const orderBySql = verDetalle 
        ? "ORDER BY LOWER(COALESCE(NULLIF(artist, ''), filename)) ASC, LOWER(title) ASC" 
        : "ORDER BY LOWER(filename) ASC";

    const query = `SELECT cover_blob, filename, artist, title, remix, album, genre, publisher, year, cues, rating FROM tracks ${whereSql} ${orderBySql} LIMIT ${PAGE_SIZE} OFFSET ${offset}`;
    
    let res = [];
    try {
        res = db.exec(query);
    } catch (err) {
        console.error("Error consultando la DB:", err);
        return;
    }
    
    const thead = document.getElementById('tableHeader');
    const tbody = document.getElementById('tableBody');
    if (!thead || !tbody) return;

    tbody.innerHTML = '';

    if (verDetalle) {
        thead.innerHTML = `
            <tr>
                <th class="th-cover">CARÁTULA</th>
                <th>INTÉRPRETE</th>
                <th>TÍTULO</th>
                <th>REMIX</th>
                <th>ÁLBUM</th>
                <th>GÉNERO</th>
                <th>ETIQUETA</th>
                <th class="col-center">AÑO</th>
                <th class="col-center">CUES</th>
                <th class="col-center">RATING</th>
            </tr>
        `;
    } else {
        thead.innerHTML = `
            <tr>
                <th class="th-cover">CARÁTULA</th>
                <th>NOMBRE DE ARCHIVO</th>
            </tr>
        `;
    }

    let recordsInPage = 0;
    if (res && res.length > 0 && res[0].values) {
        recordsInPage = res[0].values.length;
        res[0].values.forEach(row => {
            const tr = document.createElement('tr');
            
            tr.onclick = function() {
                document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected-row'));
                this.classList.add('selected-row');
            };
            
            const coverData = row[0];
            const rawFilename = row[1] || '';
            const artist = row[2] || '';
            const title = row[3] || '';
            const remixVal = row[4] || '';
            const albumVal = row[5] || '';
            const genreVal = row[6] || '';
            const publisherVal = row[7] || '';
            const yearVal = row[8] || '';
            const cuesVal = Number(row[9] || 0) > 0 ? String(row[9]) : '-';
            const ratingNum = Number(row[10] || 0);
            const ratingVal = `${Math.max(0, Math.min(5, Number.isFinite(ratingNum) ? ratingNum : 0))}★`;

            let imgTag = '<span class="cover-badge">N/A</span>';
            if (coverData) {
                if (typeof coverData === 'string' && coverData.trim() !== '') {
                    let srcVal = coverData.trim();
                    if (!srcVal.startsWith('data:')) {
                        srcVal = `data:image/jpeg;base64,${srcVal}`;
                    }
                    imgTag = `<img src="${srcVal}" class="cover-thumb">`;
                } else if (coverData instanceof Uint8Array) {
                    let decoder = new TextDecoder('utf-8');
                    let srcVal = decoder.decode(coverData).trim();
                    if (!srcVal.startsWith('data:')) {
                        srcVal = `data:image/jpeg;base64,${srcVal}`;
                    }
                    imgTag = `<img src="${srcVal}" class="cover-thumb">`;
                }
            }
            
            let cleanFilename = rawFilename.replace(/\\.[^/.]+$/, "");
            
            const renderCell = (val, isCenter = false) => {
                const hasValue = val && val.trim() !== '';
                const displayValue = hasValue ? val : '—';
                const classes = [];
                
                if (!hasValue) classes.push('text-subtle');
                if (isCenter) classes.push('col-center');
                
                const classAttr = classes.length ? `class="${classes.join(' ')}"` : '';
                return `<td ${classAttr} title="${displayValue}">${displayValue}</td>`;
            };

            if (verDetalle) {
                tr.innerHTML = `
                    <td class="td-cover">${imgTag}</td>
                    ${renderCell(artist)}
                    ${renderCell(title)}
                    ${renderCell(remixVal)}
                    ${renderCell(albumVal)}
                    ${renderCell(genreVal)}
                    ${renderCell(publisherVal)}
                    ${renderCell(yearVal, true)}
                    ${renderCell(cuesVal, true)}
                    ${renderCell(ratingVal, true)}
                `;
            } else {
                tr.innerHTML = `
                    <td class="td-cover">${imgTag}</td>
                    <td title="${cleanFilename}">${cleanFilename}</td>
                `;
            }
            tbody.appendChild(tr);
        });
    } else {
        const colSpan = verDetalle ? 10 : 2;
        tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align: center;" class="text-subtle">No se encontraron registros.</td></tr>`;
    }

    if (resultsCountElem) {
        if (totalRecords === 0) {
            resultsCountElem.textContent = '0 resultados';
        } else {
            const startRange = offset + 1;
            const endRange = offset + recordsInPage;
            resultsCountElem.textContent = `${startRange} - ${endRange} de ${totalRecords}`;
        }
    }

    const paginationControls = document.getElementById('paginationControls');
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');

    if (totalRecords > PAGE_SIZE) {
        if (paginationControls) paginationControls.style.display = 'flex';
        if (pageInfo) {
            pageInfo.textContent = `Página ${currentPage + 1} de ${totalPages}`;
        }
        if (prevBtn) prevBtn.disabled = (currentPage === 0);
        if (nextBtn) nextBtn.disabled = (currentPage >= totalPages - 1);
    } else {
        if (paginationControls) paginationControls.style.display = 'none';
    }
}

function toggleVerDetalle() {
    loadTableData();
}

let searchTimeout;
function debouncedSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        currentFilters.search = searchInput.value.trim();
    }
    populateSelectFilters();
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        applyFilters();
    }, 150);
}

function resetAndSearch() {
    currentPage = 0;
    loadTableData();
}

function changePage(delta) {
    currentPage += delta;
    loadTableData();
}

function switchView(view) {
    document.getElementById('dashboardView').style.display = view === 'dashboard' ? 'block' : 'none';
    document.getElementById('tableView').style.display = view === 'table' ? 'block' : 'none';
    document.getElementById('btnDashboard').style.display = view === 'table' ? 'inline-block' : 'none';
    document.getElementById('btnTable').style.display = view === 'dashboard' ? 'inline-block' : 'none';
}

window.onload = initSQLite;
"""


class HTMLExporter:
    """Clase principal orquestadora del proceso de exportación."""

    @staticmethod
    def _compress_image_to_jpeg_bytes(image_bytes, max_size=(80, 80), quality=60):
        """Comprime la carátula y la devuelve como un string Base64 Data-URI."""
        if not image_bytes:
            return None
        try:
            img = Image.open(io.BytesIO(image_bytes))
            img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return f"data:image/jpeg;base64,{encoded}"
        except Exception:
            return None

    @staticmethod
    def _extract_cover_from_audio(audio_path):
        if not audio_path or not os.path.exists(audio_path):
            return None
        try:
            if audio_path.lower().endswith(".flac"):
                try:
                    flac = FLAC(audio_path)
                    if flac.pictures:
                        return HTMLExporter._compress_image_to_jpeg_bytes(flac.pictures[0].data)
                except Exception:
                    pass

            audio = File(audio_path)
            if audio is not None:
                if hasattr(audio, "tags") and audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            return HTMLExporter._compress_image_to_jpeg_bytes(tag.data)
                if hasattr(audio, "pictures") and audio.pictures:
                    return HTMLExporter._compress_image_to_jpeg_bytes(audio.pictures[0].data)
        except Exception:
            pass
        return None

    @staticmethod
    def _resolve_audio_path(app, item_id, row_vals, file_idx):
        """Resuelve ruta absoluta del audio priorizando el mapa interno de la app."""
        file_map = getattr(app, "file_paths_map", {})
        mapped = file_map.get(item_id) if isinstance(file_map, dict) else None
        if mapped and os.path.exists(mapped):
            return mapped

        if file_idx != -1 and file_idx < len(row_vals):
            candidate = str(row_vals[file_idx]).strip()
            if candidate and os.path.exists(candidate):
                return candidate

        return None

    @staticmethod
    def export_grid_to_html(app):
        """Orquesta la generación de la DB SQLite y el empaquetado final en un archivo .zip listo para Netlify."""
        grid = getattr(app, "grid_panel", None)
        if not grid or not hasattr(grid, "tree"):
            messagebox.showerror("Error", "No se encontró el grid de datos.")
            return

        tree = grid.tree
        all_cols = list(tree["columns"])
        col_index = {name: idx for idx, name in enumerate(all_cols)}

        def get_col_value(values, key, default=""):
            idx = col_index.get(key)
            if idx is None or idx >= len(values):
                return default
            raw = values[idx]
            return "" if raw is None else str(raw).strip()

        def parse_cues(raw_value):
            text = str(raw_value or "").strip()
            return int(text) if text.isdigit() else 0

        def parse_rating(raw_value):
            text = str(raw_value or "").strip().replace("★", "")
            if not text.isdigit():
                return 0
            return max(0, min(5, int(text)))

        tracks_data = []
        for item_id in tree.get_children():
            values = tree.item(item_id, "values")

            b64_cover = None
            file_idx = col_index.get("Filename", 0)
            audio_path = HTMLExporter._resolve_audio_path(app, item_id, values, file_idx)
            if audio_path:
                b64_cover = HTMLExporter._extract_cover_from_audio(audio_path)

            cues_raw = get_col_value(values, "Cues", get_col_value(values, "CUEs", "-"))
            rating_raw = get_col_value(values, "Rating", "0★")

            tracks_data.append({
                "filename": get_col_value(values, "Filename"),
                "artist": get_col_value(values, "Artist"),
                "title": get_col_value(values, "Title"),
                "remix": get_col_value(values, "MixArtist"),
                "album": get_col_value(values, "Album"),
                "genre": get_col_value(values, "Genre"),
                "publisher": get_col_value(values, "Publisher"),
                "year": get_col_value(values, "Year"),
                "cues": parse_cues(cues_raw),
                "rating": parse_rating(rating_raw),
                "cover_blob": b64_cover if isinstance(b64_cover, str) and b64_cover.strip() else None
            })

        if not tracks_data:
            messagebox.showwarning("Exportar WebApp", "No hay datos para exportar.")
            return

        zip_path = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("Archivo ZIP", "*.zip")],
            title="Guardar WebApp para Netlify (.zip)"
        )
        if not zip_path:
            return

        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                db_file_path = os.path.join(tmp_dir, "data.db")
                SQLiteManager.create_database(db_file_path, tracks_data)

                with open(os.path.join(tmp_dir, "index.html"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_index_html())
                with open(os.path.join(tmp_dir, "styles.css"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_styles_css())
                with open(os.path.join(tmp_dir, "app.js"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_app_js())

                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
                    for filename in ["index.html", "styles.css", "app.js", "data.db"]:
                        file_full_path = os.path.join(tmp_dir, filename)
                        zip_out.write(file_full_path, arcname=filename)

            messagebox.showinfo("Exportación exitosa", f"Paquete ZIP generado en:\n{zip_path}\n\nListo para arrastrar a Netlify Drop.")
        except Exception as e:
            messagebox.showerror("Error al exportar", f"Ocurrió un fallo durante la exportación:\n{str(e)}")