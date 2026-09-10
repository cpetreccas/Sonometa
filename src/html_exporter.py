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

        # 1. Crear tabla de tracks (cover_blob definido como TEXT para Base64)
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
                cover_blob TEXT
            )
        """)

        # 2. Crear índices B-Tree para optimizar búsquedas y consultas SQL en WASM
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_search ON tracks(artist, title, album, genre, publisher);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_genre ON tracks(genre);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_album ON tracks(album);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_publisher ON tracks(publisher);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_year ON tracks(year);")

        # 3. Inserción masiva
        cursor.executemany("""
            INSERT INTO tracks (filename, artist, title, remix, album, genre, publisher, year, cover_blob)
            VALUES (:filename, :artist, :title, :remix, :album, :genre, :publisher, :year, :cover_blob)
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
                <svg class="brand-logo-svg" viewBox="0 0 102 78" fill="none" xmlns="http://www.w3.org/2000/svg" draggable="false">
                    <path d="M53.4074 12.3934C51.1075 9.77124 47.747 8.27092 44.2081 8.27092H24.3228C14.7554 8.27092 7 16.0263 7 25.5937V52.4063C7 61.9737 14.7554 69.7291 24.3228 69.7291H44.2081C47.747 69.7291 51.1075 68.2288 53.4074 65.6066L72.2359 44.1332C74.8872 41.1098 74.8872 36.8902 72.2359 33.8668L53.4074 12.3934Z" stroke="url(#sonometa_grad)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="58.5" cy="39" r="4.5" fill="url(#sonometa_grad)"/>
                    <defs>
                        <linearGradient id="sonometa_grad" x1="7" y1="8.27092" x2="74" y2="69.7291" gradientUnits="userSpaceOnUse">
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
                    <span class="brand-version">v0.17</span>
                </div>
                <span class="brand-subtitle">AUDIO TAG SUITE</span>
            </div>
        </div>
        <div>
            <button id="btnDashboard" class="btn-primary" style="display:none;" onclick="switchView('dashboard')">Dashboard</button>
            <button id="btnTable" class="btn-primary" onclick="switchView('table')">Ver mi colección</button>
        </div>
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
        <div class="controls-panel">
            <div class="controls-row">
                <div class="search-box">
                    <input type="text" id="searchInput" class="search-input" placeholder="Buscar canción..." oninput="debouncedSearch()">
                </div>
                <label class="checkbox-label no-select">
                    <input type="checkbox" id="chkVerDetalle" onchange="toggleVerDetalle()">
                    <span>Ver detalle</span>
                </label>
            </div>
            <div class="controls-row">
                <select id="albumFilter" class="filter-select" onchange="resetAndSearch()"><option value="">Álbum: Todos</option></select>
                <select id="genreFilter" class="filter-select" onchange="resetAndSearch()"><option value="">Género: Todos</option></select>
                <select id="publisherFilter" class="filter-select" onchange="resetAndSearch()"><option value="">Etiqueta: Todas</option></select>
                <select id="yearFilter" class="filter-select" onchange="resetAndSearch()"><option value="">Año: Todos</option></select>
            </div>
        </div>

        <div class="table-container">
            <table id="dataTable">
                <thead id="tableHeader"></thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>

        <div class="pagination-controls">
            <button id="prevBtn" class="btn-primary" onclick="changePage(-1)">Anterior</button>
            <span id="pageInfo">Página 1</span>
            <button id="nextBtn" class="btn-primary" onclick="changePage(1)">Siguiente</button>
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
    padding: 16px;
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
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border-color);
}

.brand-container { display: flex; align-items: center; gap: 12px; cursor: default; }
.brand-logo-wrapper { width: 38px; height: 30px; display: flex; align-items: center; justify-content: center; pointer-events: none; }
.brand-logo-svg { width: 100%; height: 100%; display: block; pointer-events: none; }
.brand-text { display: flex; flex-direction: column; }
.brand-title-row { display: flex; align-items: baseline; gap: 8px; }
.brand-title { font-size: 20px; font-weight: 700; color: #FFFFFF; line-height: 1; }
.brand-version { font-size: 13px; font-weight: 600; color: #8B5CF6; }
.brand-subtitle { font-size: 9px; font-weight: 600; letter-spacing: 1.5px; color: var(--text-muted); margin-top: 3px; }

.btn-primary {
    background-color: var(--primary-purple);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 9px 18px;
    border-radius: 8px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s ease;
    box-shadow: 0 2px 8px rgba(139, 92, 246, 0.3);
}
.btn-primary:hover { background-color: var(--primary-hover); }

.kpi-card {
    background: linear-gradient(180deg, #2D243A 0%, var(--surface-color) 100%);
    border: 1px solid var(--border-highlight);
    border-radius: 12px;
    padding: 28px 20px;
    text-align: center;
    margin-bottom: 24px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, transparent, var(--primary-purple), transparent);
}
.kpi-value {
    font-size: 60px; font-weight: 800; color: #FFFFFF; line-height: 1;
    letter-spacing: -1.5px; margin-bottom: 8px; text-shadow: 0 0 20px rgba(168, 85, 247, 0.3);
}
.kpi-label { font-size: 12px; text-transform: uppercase; letter-spacing: 2px; color: var(--text-muted); font-weight: 600; }

.charts-grid { display: grid; grid-template-columns: 1fr; gap: 20px; margin-bottom: 20px; }
@media (min-width: 1024px) { .charts-grid { grid-template-columns: repeat(2, 1fr); } }

.chart-card {
    background-color: var(--surface-color);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}
.chart-card h3 {
    margin-top: 0; margin-bottom: 16px; font-size: 13px; font-weight: 600;
    letter-spacing: 0.5px; color: var(--text-main); text-transform: uppercase;
    border-bottom: 1px solid var(--border-color); padding-bottom: 10px;
}

.chart-flex-wrapper { display: flex; flex-direction: column; gap: 16px; align-items: center; }
@media (min-width: 600px) { .chart-flex-wrapper { flex-direction: row; justify-content: space-between; align-items: center; } }

.canvas-pie-container, .canvas-bar-container { position: relative; height: 210px; width: 100%; max-width: 210px; flex-shrink: 0; }
.canvas-bar-container { max-width: 240px; }

.custom-legend { width: 100%; font-size: 12px; max-height: 210px; overflow-y: auto; padding-right: 4px; }
.custom-legend::-webkit-scrollbar { width: 4px; }
.custom-legend::-webkit-scrollbar-thumb { background: var(--border-highlight); border-radius: 2px; }

.legend-header {
    display: flex; justify-content: space-between; color: var(--text-muted);
    font-size: 11px; font-weight: 700; text-transform: lowercase;
    padding-bottom: 8px; margin-bottom: 6px; border-bottom: 1px solid var(--border-color);
}
.legend-header span:first-child { flex: 1; }
.legend-header span.val-col { width: 55px; text-align: right; }
.legend-header span.pct-col { width: 65px; text-align: right; }

.legend-item { display: flex; align-items: center; padding: 4px 0; color: #E4E4E7; border-bottom: 1px solid rgba(255, 255, 255, 0.03); }
.legend-color { width: 10px; height: 10px; border-radius: 2px; margin-right: 10px; display: inline-block; flex-shrink: 0; }
.legend-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 12px; }
.legend-val { width: 55px; text-align: right; font-weight: 600; color: #FFFFFF; }
.legend-pct { width: 65px; text-align: right; color: var(--text-muted); font-size: 11px; }

.controls-panel { display: flex; flex-direction: column; gap: 12px; background-color: var(--surface-color); border: 1px solid var(--border-color); border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.controls-row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.search-box { flex: 1; min-width: 200px; }

.checkbox-label {
    display: flex; align-items: center; gap: 8px; font-size: 13px;
    color: var(--text-main); font-weight: 500; cursor: pointer;
    background-color: var(--input-bg); padding: 10px 14px;
    border-radius: 8px; border: 1px solid var(--border-color);
}
.checkbox-label input[type="checkbox"] {
    accent-color: var(--primary-purple); width: 16px; height: 16px; cursor: pointer;
}

.filter-select, .search-input { background-color: var(--input-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px 12px; color: var(--text-main); font-size: 13px; outline: none; flex: 1; min-width: 140px; }

.table-container { background-color: var(--surface-color); border: 1px solid var(--border-color); border-radius: 12px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }
th { background-color: #1B1B20; color: var(--text-muted); font-weight: 600; padding: 12px 16px; border-bottom: 1px solid var(--border-color); font-size: 11px; text-transform: uppercase; }
td { padding: 10px 16px; border-bottom: 1px solid var(--border-color); color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 220px; }
tr:nth-child(even) { background-color: var(--row-even); }
tr:hover { background-color: var(--surface-hover); }

/* Estilo para los badges/botones N/A de Carátula */
.col-cover { width: 80px; text-align: right; }
.cover-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 42px;
    height: 42px;
    background-color: #1B1B20;
    border: 1px solid #363640;
    border-radius: 8px;
    color: #52525B;
    font-size: 11px;
    font-weight: 600;
}
.cover-thumb { width: 42px; height: 42px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border-color); display: inline-block; }

.pagination-controls { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; padding: 0 4px; }
"""

    @staticmethod
    def get_app_js():
        return """
let db = null;
let currentPage = 0;
const PAGE_SIZE = 50;
const COLORS = ['#10B981', '#F59E0B', '#3B82F6', '#EF4444', '#9333EA', '#EC4899', '#14B8A6', '#8B5CF6', '#64748B'];

Chart.defaults.color = '#A1A1AA';
Chart.defaults.borderColor = '#363640';

async function initSQLite() {
    const sqlPromise = initSqlJs({
        locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.8.0/${file}`
    });
    const dataPromise = fetch('data.db').then(res => res.arrayBuffer());
    const [SQL, buf] = await Promise.all([sqlPromise, dataPromise]);
    
    db = new SQL.Database(new Uint8Array(buf));
    initDashboard();
    populateSelectFilters();
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
                <span class="legend-val">${val}</span>
                <span class="legend-pct">${pct}</span>
            </div>
        `;
    });

    container.innerHTML = html;
}

function initDashboard() {
    const resTotal = db.exec("SELECT COUNT(*) FROM tracks");
    const totalTracks = (resTotal.length && resTotal[0].values.length) ? resTotal[0].values[0][0] : 0;
    const totalElem = document.getElementById('kpiTotalTracks');
    if (totalElem) {
        totalElem.textContent = totalTracks.toLocaleString('es-ES');
    }

    const buildChart = (canvasId, legendId, sqlQuery, chartType) => {
        const res = db.exec(sqlQuery);
        if (!res.length || !res[0].values) return;

        const labels = res[0].values.map(v => v[0] || 'Desconocido');
        const dataVals = res[0].values.map(v => v[1]);
        const sliceColors = labels.map((_, i) => COLORS[i % COLORS.length]);

        const chartCanvas = document.getElementById(canvasId);
        if (!chartCanvas) return;

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

        new Chart(chartCanvas, chartConfig);
        renderCustomLegend(legendId, labels, dataVals);
    };

    buildChart('albumChart', 'albumLegend', "SELECT CASE WHEN album IS NULL OR album = '' THEN 'Sin Álbum' ELSE album END, COUNT(*) as c FROM tracks GROUP BY 1 ORDER BY c DESC", 'pie');
    buildChart('genreChart', 'genreLegend', "SELECT CASE WHEN genre IS NULL OR genre = '' THEN 'Sin Género' ELSE genre END, COUNT(*) as c FROM tracks GROUP BY 1 ORDER BY c DESC", 'pie');
    buildChart('publisherChart', 'publisherLegend', "SELECT CASE WHEN publisher IS NULL OR publisher = '' THEN 'Sin Etiqueta' ELSE publisher END, COUNT(*) as c FROM tracks GROUP BY 1 ORDER BY c DESC", 'bar');
    buildChart('yearChart', 'yearLegend', "SELECT CASE WHEN year IS NULL OR year = '' THEN 'Sin Año' ELSE year END, COUNT(*) as c FROM tracks GROUP BY 1 ORDER BY c DESC", 'bar');
}

function populateSelectFilters() {
    const populate = (selectId, colName, emptyLabel) => {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        const optEmpty = document.createElement('option');
        optEmpty.value = "__EMPTY__";
        optEmpty.textContent = emptyLabel;
        select.appendChild(optEmpty);

        const res = db.exec(`SELECT DISTINCT ${colName} FROM tracks WHERE ${colName} IS NOT NULL AND ${colName} != '' ORDER BY ${colName} ASC`);
        if (res.length && res[0].values) {
            res[0].values.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v[0];
                opt.textContent = v[0];
                select.appendChild(opt);
            });
        }
    };

    populate('albumFilter', 'album', 'Sin Álbum');
    populate('genreFilter', 'genre', 'Sin Género');
    populate('publisherFilter', 'publisher', 'Sin Etiqueta');
    populate('yearFilter', 'year', 'Sin Año');
}

function loadTableData() {
    const searchInput = document.getElementById('searchInput');
    const albumFilter = document.getElementById('albumFilter');
    const genreFilter = document.getElementById('genreFilter');
    const publisherFilter = document.getElementById('publisherFilter');
    const yearFilter = document.getElementById('yearFilter');
    const chkVerDetalle = document.getElementById('chkVerDetalle');

    if (!searchInput || !albumFilter || !genreFilter || !publisherFilter || !yearFilter || !chkVerDetalle) {
        return;
    }

    const search = searchInput.value.replace(/'/g, "''").trim();
    const album = albumFilter.value.replace(/'/g, "''");
    const genre = genreFilter.value.replace(/'/g, "''");
    const publisher = publisherFilter.value.replace(/'/g, "''");
    const year = yearFilter.value.replace(/'/g, "''");
    const verDetalle = chkVerDetalle.checked;
    
    let whereClauses = [];
    if (search) {
        whereClauses.push(`(artist LIKE '%${search}%' OR title LIKE '%${search}%' OR album LIKE '%${search}%' OR filename LIKE '%${search}%' OR remix LIKE '%${search}%')`);
    }
    
    const applyFilter = (col, val) => {
        if (val === "__EMPTY__") {
            whereClauses.push(`(${col} IS NULL OR ${col} = '')`);
        } else if (val) {
            whereClauses.push(`${col} = '${val}'`);
        }
    };

    applyFilter('album', album);
    applyFilter('genre', genre);
    applyFilter('publisher', publisher);
    applyFilter('year', year);
    
    const whereSql = whereClauses.length ? 'WHERE ' + whereClauses.join(' AND ') : '';
    const offset = currentPage * PAGE_SIZE;

    const query = `SELECT cover_blob, filename, artist, title, remix, album, genre, publisher, year FROM tracks ${whereSql} LIMIT ${PAGE_SIZE} OFFSET ${offset}`;
    
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
                <th>NOMBRE DE ARCHIVO</th>
                <th>INTÉRPRETE</th>
                <th>TÍTULO</th>
                <th>REMIX</th>
                <th>ÁLBUM</th>
                <th>GÉNERO</th>
                <th>ETIQUETA</th>
                <th>AÑO</th>
                <th style="text-align: right;">CARÁTULA</th>
            </tr>
        `;
    } else {
        thead.innerHTML = `
            <tr>
                <th>NOMBRE</th>
                <th style="text-align: right;">CARÁTULA</th>
            </tr>
        `;
    }

    if (res && res.length > 0 && res[0].values) {
        res[0].values.forEach(row => {
            const tr = document.createElement('tr');
            
            const coverData = row[0];
            const rawFilename = row[1] || '';
            const artist = row[2] || '';
            const title = row[3] || '';
            const remixVal = row[4] || '';
            const albumVal = row[5] || '';
            const genreVal = row[6] || '';
            const publisherVal = row[7] || '';
            const yearVal = row[8] || '';

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

            if (verDetalle) {
                tr.innerHTML = `
                    <td>${rawFilename}</td>
                    <td>${artist}</td>
                    <td>${title}</td>
                    <td>${remixVal}</td>
                    <td>${albumVal}</td>
                    <td>${genreVal}</td>
                    <td>${publisherVal}</td>
                    <td>${yearVal}</td>
                    <td style="text-align: right;">${imgTag}</td>
                `;
            } else {
                tr.innerHTML = `
                    <td>${cleanFilename}</td>
                    <td style="text-align: right;">${imgTag}</td>
                `;
            }
            tbody.appendChild(tr);
        });
    } else {
        const colSpan = verDetalle ? 9 : 2;
        tbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align: center;">No se encontraron registros.</td></tr>`;
    }

    const pageInfo = document.getElementById('pageInfo');
    if (pageInfo) {
        pageInfo.textContent = `Página ${currentPage + 1}`;
    }
}

function toggleVerDetalle() {
    loadTableData();
}

let searchTimeout;
function debouncedSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(resetAndSearch, 150);
}

function resetAndSearch() {
    currentPage = 0;
    loadTableData();
}

function changePage(delta) {
    if (currentPage + delta >= 0) {
        currentPage += delta;
        loadTableData();
    }
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
    def export_grid_to_html(app):
        """Orquesta la generación de la DB SQLite y el empaquetado final en un archivo .zip listo para Netlify."""
        grid = getattr(app, "grid_panel", None)
        if not grid or not hasattr(grid, "tree"):
            messagebox.showerror("Error", "No se encontró el grid de datos.")
            return

        tree = grid.tree
        visible_cols = [c for c in tree["displaycolumns"] if c != "#0"]
        headers = [tree.heading(c)["text"] for c in visible_cols]

        # Mapeo de índices dinámico
        idx = {"file": 0, "cover": -1, "artist": -1, "title": -1, "remix": -1, "album": -1, "genre": -1, "publisher": -1, "year": -1}
        for i, h in enumerate(headers):
            h_lower = h.lower()
            if any(k in h_lower for k in ["archivo", "filename", "file"]): idx["file"] = i
            elif any(k in h_lower for k in ["carátula", "cover"]): idx["cover"] = i
            elif any(k in h_lower for k in ["intérprete", "artista", "artist"]): idx["artist"] = i
            elif any(k in h_lower for k in ["título", "title"]): idx["title"] = i
            elif any(k in h_lower for k in ["remix"]): idx["remix"] = i
            elif any(k in h_lower for k in ["álbum", "album"]): idx["album"] = i
            elif any(k in h_lower for k in ["género", "genre"]): idx["genre"] = i
            elif any(k in h_lower for k in ["sello", "publisher"]): idx["publisher"] = i
            elif any(k in h_lower for k in ["año", "year"]): idx["year"] = i

        tracks_data = []
        for item_id in tree.get_children():
            values = tree.item(item_id, "values")
            col_indices = [tree["columns"].index(c) for c in visible_cols]
            row_vals = [values[i] if i < len(values) else "" for i in col_indices]

            # Extracción de carátula
            b64_cover = None
            if idx["cover"] != -1:
                audio_path = str(item_id) if os.path.exists(str(item_id)) else row_vals[idx["file"]]
                if os.path.exists(audio_path):
                    b64_cover = HTMLExporter._extract_cover_from_audio(audio_path)

            def get_val(key):
                i = idx[key]
                return row_vals[i].strip() if i != -1 and i < len(row_vals) else ""

            tracks_data.append({
                "filename": get_val("file"),
                "artist": get_val("artist"),
                "title": get_val("title"),
                "remix": get_val("remix"),
                "album": get_val("album"),
                "genre": get_val("genre"),
                "publisher": get_val("publisher"),
                "year": get_val("year"),
                "cover_blob": b64_cover
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

        # Generación en directorio temporal y empaquetado en .ZIP
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                db_file_path = os.path.join(tmp_dir, "data.db")
                SQLiteManager.create_database(db_file_path, tracks_data)

                # Guardar assets estáticos
                with open(os.path.join(tmp_dir, "index.html"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_index_html())
                with open(os.path.join(tmp_dir, "styles.css"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_styles_css())
                with open(os.path.join(tmp_dir, "app.js"), "w", encoding="utf-8") as f:
                    f.write(TemplateProvider.get_app_js())

                # Crear archivo ZIP final
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_out:
                    for filename in ["index.html", "styles.css", "app.js", "data.db"]:
                        file_full_path = os.path.join(tmp_dir, filename)
                        zip_out.write(file_full_path, arcname=filename)

            messagebox.showinfo("Exportación exitosa", f"Paquete ZIP generado en:\n{zip_path}\n\nListo para arrastrar a Netlify Drop.")
        except Exception as e:
            messagebox.showerror("Error al exportar", f"Ocurrió un fallo durante la exportación:\n{str(e)}")