import base64
import io
import json
import os
from tkinter import filedialog, messagebox

from mutagen import File
from mutagen.flac import FLAC
from mutagen.id3 import APIC
from PIL import Image


class HTMLExporter:

    @staticmethod
    def _compress_and_encode_image(
            image_bytes, max_size=(100, 100), quality=70
    ):
        """Redimensiona y comprime la imagen para mantener el HTML extremadamente liviano."""
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
    def _get_logo_base64(relative_path="assets/logo_completo.png"):
        """Convierte el logo de la aplicación a Base64 para incrustarlo en el HTML."""
        if not relative_path or not os.path.exists(relative_path):
            return None
        try:
            with open(relative_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded}"
        except Exception:
            return None

    @staticmethod
    def _get_chartjs_code(relative_path="scripts/chart.min.js"):
        """Lee el código fuente de Chart.js local para inyectarlo directamente en el HTML."""
        if not relative_path or not os.path.exists(relative_path):
            return None
        try:
            with open(relative_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return None

    @staticmethod
    def _extract_cover_from_audio(audio_path):
        """Extrae la carátula y la comprime a miniatura de baja resolución."""
        if not audio_path or not os.path.exists(audio_path):
            return None
        try:
            if audio_path.lower().endswith(".flac"):
                try:
                    flac = FLAC(audio_path)
                    if flac.pictures:
                        return HTMLExporter._compress_and_encode_image(
                            flac.pictures[0].data
                        )
                except Exception:
                    pass

            audio = File(audio_path)
            if audio is not None:
                if hasattr(audio, "tags") and audio.tags:
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            return HTMLExporter._compress_and_encode_image(
                                tag.data
                            )

                if hasattr(audio, "pictures") and audio.pictures:
                    return HTMLExporter._compress_and_encode_image(
                        audio.pictures[0].data
                    )
        except Exception:
            pass
        return None

    @staticmethod
    def _image_to_base64(img_path):
        if not img_path or not os.path.exists(img_path):
            return None
        try:
            with open(img_path, "rb") as f:
                return HTMLExporter._compress_and_encode_image(f.read())
        except Exception:
            return None

    @staticmethod
    def export_grid_to_html(app):
        grid = getattr(app, "grid_panel", None)
        if not grid or not hasattr(grid, "tree"):
            messagebox.showerror("Error", "No se encontró el grid de datos.")
            return

        tree = grid.tree
        visible_cols = [c for c in tree["displaycolumns"] if c != "#0"]
        headers = [tree.heading(c)["text"] for c in visible_cols]

        indices = {
            "file": -1,
            "cover": -1,
            "artist": -1,
            "title": -1,
            "remix": -1,
            "album": -1,
            "genre": -1,
            "publisher": -1,
            "year": -1,
        }

        for i, h in enumerate(headers):
            h_lower = h.lower()
            if any(
                    k in h_lower for k in ["archivo", "filename", "file", "nombre"]
            ):
                indices["file"] = i
            elif any(
                    k in h_lower
                    for k in ["carátula", "caratula", "cover", "imagen", "portada"]
            ):
                indices["cover"] = i
            elif any(
                    k in h_lower
                    for k in ["intérprete", "interprete", "artista", "artist"]
            ):
                indices["artist"] = i
            elif any(k in h_lower for k in ["título", "titulo", "title", "track"]):
                indices["title"] = i
            elif any(k in h_lower for k in ["remix", "mezcla"]):
                indices["remix"] = i
            elif any(k in h_lower for k in ["álbum", "album"]):
                indices["album"] = i
            elif any(k in h_lower for k in ["género", "genero", "genre"]):
                indices["genre"] = i
            elif any(
                    k in h_lower
                    for k in ["etiqueta", "sello", "label", "publisher"]
            ):
                indices["publisher"] = i
            elif any(k in h_lower for k in ["año", "year", "fecha"]):
                indices["year"] = i

        if indices["file"] == -1:
            indices["file"] = 0

        rows_data = []
        chart_data = []

        for item_id in tree.get_children():
            values = tree.item(item_id, "values")
            col_indices = [tree["columns"].index(c) for c in visible_cols]
            row_vals = [
                values[idx] if idx < len(values) else "" for idx in col_indices
            ]

            if indices["cover"] != -1:
                audio_path = None
                if os.path.exists(str(item_id)):
                    audio_path = str(item_id)

                if (
                        not audio_path
                        and hasattr(app, "tracks")
                        and item_id in app.tracks
                ):
                    track_obj = app.tracks[item_id]
                    for attr in ["file_path", "path", "filepath", "filename"]:
                        p = getattr(track_obj, attr, None)
                        if p and os.path.exists(p):
                            audio_path = p
                            break

                if not audio_path:
                    raw_file = row_vals[indices["file"]]
                    if os.path.exists(raw_file):
                        audio_path = raw_file
                    else:
                        for folder_attr in [
                            "current_folder",
                            "working_dir",
                            "music_dir",
                            "folder_path",
                        ]:
                            folder = getattr(app, folder_attr, None)
                            if folder:
                                candidate = os.path.join(folder, raw_file)
                                if os.path.exists(candidate):
                                    audio_path = candidate
                                    break

                b64_img = None
                if audio_path:
                    b64_img = HTMLExporter._extract_cover_from_audio(audio_path)

                val_cover = row_vals[indices["cover"]]
                if not b64_img and val_cover and os.path.exists(val_cover):
                    b64_img = HTMLExporter._image_to_base64(val_cover)

                row_vals[indices["cover"]] = b64_img if b64_img else ""

            def get_val(idx, default):
                val = (
                    row_vals[idx].strip()
                    if idx != -1 and row_vals[idx]
                    else ""
                )
                return val if val else default

            chart_data.append(
                {
                    "album": get_val(indices["album"], "Sin Álbum"),
                    "genre": get_val(indices["genre"], "Sin Género"),
                    "publisher": get_val(indices["publisher"], "Sin Etiqueta"),
                    "year": get_val(indices["year"], "Sin Año"),
                }
            )

            rows_data.append(row_vals)

        if not rows_data:
            messagebox.showwarning(
                "Exportar HTML",
                "No hay datos visibles en la tabla para exportar.",
            )
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[
                ("Página HTML", "*.html"),
                ("Todos los archivos", "*.*"),
            ],
            title="Guardar informe HTML",
        )
        if not file_path:
            return

        html_content = HTMLExporter._build_html_template(
            headers, rows_data, indices, chart_data
        )

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            messagebox.showinfo(
                "Exportación completada",
                f"Informe generado exitosamente:\n{file_path}",
            )
        except Exception as e:
            messagebox.showerror(
                "Error de guardado",
                f"No se pudo guardar el archivo HTML:\n{str(e)}",
            )

    @staticmethod
    def _build_html_template(
            headers, rows, idx_map, chart_data, logo_path="assets/logo_completo.png"
    ):
        th_html = "".join(
            [
                f'<th data-col="{i}" data-original="{h}">{h}</th>'
                for i, h in enumerate(headers)
            ]
        )

        tr_html = ""
        for row in rows:
            tds = ""
            for i, cell in enumerate(row):
                if i == idx_map["cover"]:
                    if cell and cell.startswith("data:image"):
                        tds += f'<td data-col="{i}" class="cover-cell"><img src="{cell}" class="cover-thumb" loading="lazy" alt="Cover"/></td>'
                    else:
                        tds += f'<td data-col="{i}" class="cover-cell"><div class="no-cover">N/A</div></td>'
                elif i == idx_map["file"]:
                    raw_val = cell
                    clean_val = os.path.splitext(cell)[0] if cell else ""
                    tds += f'<td data-col="{i}" data-full="{raw_val}" data-clean="{clean_val}">{raw_val}</td>'
                else:
                    tds += f'<td data-col="{i}">{cell}</td>'
            tr_html += f"<tr>{tds}</tr>\n"

        chart_data_json = json.dumps(chart_data)

        # Cargar Chart.js local o fallback al CDN en caso de ausencia
        chart_js_code = HTMLExporter._get_chartjs_code("scripts/chart.min.js")
        if chart_js_code:
            chart_script_tag = f"<script>{chart_js_code}</script>"
        else:
            chart_script_tag = '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>'

        logo_b64 = HTMLExporter._get_logo_base64(logo_path)
        if logo_b64:
            logo_brand_html = f'<img src="{logo_b64}" class="brand-logo-full" alt="Sonometa Audio Tag Suite"/>'
        else:
            logo_brand_html = """
                <div class="brand-container">
                    <div class="brand-logo"></div>
                    <div class="brand-text">
                        <span class="brand-title">Sonometa</span>
                        <span class="brand-subtitle">AUDIO TAG SUITE</span>
                    </div>
                </div>
            """

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <!-- Habilita el modo App nativa en iOS (Pantalla Completa) -->
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Sonometa">
    <title>Sonometa - Mi Colección</title>
    {chart_script_tag}
    <style>
        :root {{
            /* Tonos ajustados estilo CustomTkinter/App Escritorio */
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
        }}

        * {{ box-sizing: border-box; }}

        body {{
            background-color: var(--bg-color);
            color: var(--text-main);
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 16px;
            -webkit-font-smoothing: antialiased;
        }}

        @media (min-width: 768px) {{
            body {{ padding: 28px; }}
        }}

        .header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        .brand-logo-full {{
            max-height: 42px;
            width: auto;
            object-fit: contain;
            filter: drop-shadow(0 2px 8px rgba(139, 92, 246, 0.3));
        }}

        .brand-container {{ display: flex; align-items: center; gap: 12px; }}
        .brand-logo {{
            width: 32px; height: 32px;
            background: linear-gradient(135deg, #A855F7 0%, #6366F1 100%);
            clip-path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%);
        }}
        .brand-text {{ display: flex; flex-direction: column; }}
        .brand-title {{ font-size: 20px; font-weight: 700; color: #FFFFFF; line-height: 1; }}
        .brand-subtitle {{ font-size: 9px; font-weight: 600; letter-spacing: 1.5px; color: var(--text-muted); margin-top: 3px; }}

        .btn-primary {{
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
        }}

        .btn-primary:hover {{
            background-color: var(--primary-hover);
            box-shadow: 0 4px 14px rgba(139, 92, 246, 0.5);
        }}

        #dashboardView {{ display: block; }}

        .kpi-card {{
            background: linear-gradient(180deg, #2D243A 0%, var(--surface-color) 100%);
            border: 1px solid var(--border-highlight);
            border-radius: 12px;
            padding: 28px 20px;
            text-align: center;
            margin-bottom: 24px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
            position: relative;
            overflow: hidden;
        }}

        .kpi-card::before {{
            content: "";
            position: absolute;
            top: 0; left: 0; right: 0; height: 2px;
            background: linear-gradient(90deg, transparent, var(--primary-purple), transparent);
        }}

        .kpi-value {{
            font-size: 60px;
            font-weight: 800;
            color: #FFFFFF;
            line-height: 1;
            letter-spacing: -1.5px;
            margin-bottom: 8px;
            text-shadow: 0 0 20px rgba(168, 85, 247, 0.3);
        }}

        .kpi-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--text-muted);
            font-weight: 600;
        }}

        @media (min-width: 768px) {{
            .kpi-value {{ font-size: 72px; }}
            .kpi-label {{ font-size: 13px; }}
        }}

        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }}

        @media (min-width: 1024px) {{
            .charts-grid {{ grid-template-columns: repeat(2, 1fr); }}
        }}

        .chart-card {{
            background-color: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
            transition: border-color 0.2s;
        }}

        .chart-card:hover {{ border-color: var(--border-highlight); }}

        .chart-card h3 {{
            margin-top: 0;
            margin-bottom: 16px;
            font-size: 13px;
            font-weight: 600;
            letter-spacing: 0.5px;
            color: var(--text-main);
            text-transform: uppercase;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 10px;
        }}

        .chart-flex-wrapper {{
            display: flex;
            flex-direction: column;
            gap: 16px;
            align-items: center;
        }}

        @media (min-width: 600px) {{
            .chart-flex-wrapper {{
                flex-direction: row;
                justify-content: space-between;
                align-items: center;
            }}
        }}

        .canvas-pie-container {{
            position: relative;
            height: 210px;
            width: 100%;
            max-width: 210px;
            flex-shrink: 0;
        }}

        .canvas-bar-container {{
            position: relative;
            height: 210px;
            width: 100%;
            max-width: 240px;
            flex-shrink: 0;
        }}

        .custom-legend {{
            width: 100%;
            font-size: 12px;
            max-height: 210px;
            overflow-y: auto;
            padding-right: 4px;
        }}

        .custom-legend::-webkit-scrollbar {{ width: 4px; }}
        .custom-legend::-webkit-scrollbar-track {{ background: rgba(0, 0, 0, 0.1); }}
        .custom-legend::-webkit-scrollbar-thumb {{ background: var(--border-highlight); border-radius: 2px; }}

        .legend-header {{
            display: flex;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 11px;
            font-weight: 700;
            text-transform: lowercase;
            padding-bottom: 8px;
            margin-bottom: 6px;
            border-bottom: 1px solid var(--border-color);
        }}

        .legend-header span:first-child {{ flex: 1; }}
        .legend-header span.val-col {{ width: 55px; text-align: right; }}
        .legend-header span.pct-col {{ width: 65px; text-align: right; }}

        .legend-item {{
            display: flex;
            align-items: center;
            padding: 4px 0;
            color: #E4E4E7;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
        }}

        .legend-color {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
            margin-right: 10px;
            display: inline-block;
            flex-shrink: 0;
        }}

        .legend-name {{
            flex: 1;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 12px;
        }}

        .legend-val {{ width: 55px; text-align: right; font-weight: 600; color: #FFFFFF; }}
        .legend-pct {{ width: 65px; text-align: right; color: var(--text-muted); font-size: 11px; }}

        #tableView {{ display: none; }}

        .controls-panel {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            background-color: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }}

        .controls-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
            justify-content: space-between;
        }}

        .search-box {{ flex: 1; min-width: 100%; }}

        @media (min-width: 600px) {{ .search-box {{ min-width: 240px; }} }}
        
        .filter-select, .search-input {{
            background-color: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 10px 12px;
            color: var(--text-main);
            font-size: 13px;
            outline: none;
            flex: 1;
            transition: border-color 0.2s;
        }}

        .filter-select:focus, .search-input:focus {{ border-color: var(--primary-purple); }}
        .search-input {{ width: 100%; }}

        .checkbox-container {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
            cursor: pointer;
            background-color: var(--input-bg);
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            transition: border-color 0.2s;
        }}

        .checkbox-container:hover {{ border-color: var(--border-highlight); }}
        .checkbox-container input {{ accent-color: var(--primary-purple); width: 16px; height: 16px; }}

        .table-container {{
            background-color: var(--surface-color);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow-x: auto;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
            -webkit-overflow-scrolling: touch;
        }}

        table {{ width: 100%; border-collapse: collapse; font-size: 13px; text-align: left; }}
        th {{ 
            background-color: #1B1B20; 
            color: var(--text-muted); 
            font-weight: 600; 
            padding: 12px 16px; 
            border-bottom: 1px solid var(--border-color); 
            font-size: 11px; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
        }}
        td {{ 
            padding: 10px 16px; 
            border-bottom: 1px solid var(--border-color); 
            color: var(--text-main); 
            white-space: nowrap; 
            overflow: hidden; 
            text-overflow: ellipsis; 
            max-width: 260px; 
            vertical-align: middle; 
        }}
        tr:nth-child(even) {{ background-color: var(--row-even); }}
        tr:hover {{ background-color: var(--surface-hover); }}

        .cover-cell {{ width: 52px; text-align: center; padding: 6px; }}
        .cover-thumb {{ width: 42px; height: 42px; object-fit: cover; border-radius: 6px; border: 1px solid var(--border-color); }}
        .no-cover {{ width: 42px; height: 42px; line-height: 42px; background-color: var(--input-bg); color: var(--text-subtle); font-size: 10px; border-radius: 6px; margin: 0 auto; border: 1px dashed var(--border-color); }}
        
        .hidden-col {{ display: none !important; }}
        .footer {{ margin-top: 16px; font-size: 12px; color: var(--text-subtle); display: flex; justify-content: space-between; padding: 0 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            {logo_brand_html}
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
            <div class="kpi-label">Canciones en tu colección</div>
        </div>

        <div class="charts-grid">
            <div class="chart-card">
                <h3>Distribución por Álbum</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-pie-container"><canvas id="albumChart"></canvas></div>
                    <div id="albumLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>Distribución por Género</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-pie-container"><canvas id="genreChart"></canvas></div>
                    <div id="genreLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>Pistas por Etiqueta</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-bar-container"><canvas id="publisherChart"></canvas></div>
                    <div id="publisherLegend" class="custom-legend"></div>
                </div>
            </div>
            <div class="chart-card">
                <h3>Lanzamientos por Año</h3>
                <div class="chart-flex-wrapper">
                    <div class="canvas-bar-container"><canvas id="yearChart"></canvas></div>
                    <div id="yearLegend" class="custom-legend"></div>
                </div>
            </div>
        </div>
    </div>

    <!-- TABLE VIEW -->
    <div id="tableView">
        <div class="controls-panel">
            <div class="controls-row">
                <div class="search-box">
                    <input type="text" id="searchInput" class="search-input" placeholder="Buscar canción..." onkeyup="filterTable()">
                </div>
            </div>
            <div class="controls-row">
                <select id="albumFilter" class="filter-select" onchange="filterTable()"><option value="">Álbum: Todos</option></select>
                <select id="genreFilter" class="filter-select" onchange="filterTable()"><option value="">Género: Todos</option></select>
                <select id="publisherFilter" class="filter-select" onchange="filterTable()"><option value="">Etiqueta: Todas</option></select>
            </div>
            <div class="controls-row" style="justify-content: flex-end;">
                <label class="checkbox-container">
                    <input type="checkbox" id="toggleViewBtn" onchange="toggleDetailedView()">
                    <span>Ver detalles</span>
                </label>
            </div>
        </div>

        <div class="table-container">
            <table id="dataTable">
                <thead><tr>{th_html}</tr></thead>
                <tbody>{tr_html}</tbody>
            </table>
        </div>

        <div class="footer">
            <span id="recordCount">Mostrando {len(rows)} registros</span>
            <span>Sonometa Mobile Suite</span>
        </div>
    </div>

    <script>
        const idxMap = {idx_map};
        const rawChartData = {chart_data_json};

        Chart.defaults.color = '#A1A1AA';
        Chart.defaults.borderColor = '#363640';

        function switchView(view) {{
            if (view === 'dashboard') {{
                document.getElementById('dashboardView').style.display = 'block';
                document.getElementById('tableView').style.display = 'none';
                document.getElementById('btnDashboard').style.display = 'none';
                document.getElementById('btnTable').style.display = 'inline-block';
            }} else {{
                document.getElementById('dashboardView').style.display = 'none';
                document.getElementById('tableView').style.display = 'block';
                document.getElementById('btnDashboard').style.display = 'inline-block';
                document.getElementById('btnTable').style.display = 'none';
                
                if(document.getElementById('albumFilter').options.length <= 1) populateFilters();
            }}
        }}

        function aggregateData(key) {{
            const counts = {{}};
            rawChartData.forEach(item => {{
                let val = item[key] || "Desconocido";
                counts[val] = (counts[val] || 0) + 1;
            }});
            const sortedKeys = Object.keys(counts).sort((a,b) => counts[b] - counts[a]);
            return {{ labels: sortedKeys, data: sortedKeys.map(k => counts[k]) }};
        }}

        function renderCustomLegend(containerId, dataObj, colors) {{
            const container = document.getElementById(containerId);
            const total = dataObj.data.reduce((a, b) => a + b, 0);

            let html = `
                <div class="legend-header">
                    <span></span>
                    <span class="val-col">valores</span>
                    <span class="pct-col">porcentaje</span>
                </div>
            `;

            dataObj.labels.forEach((label, i) => {{
                const val = dataObj.data[i];
                const pct = total > 0 ? ((val / total) * 100).toFixed(2) + '%' : '0%';
                const color = colors[i % colors.length];

                html += `
                    <div class="legend-item">
                        <span class="legend-color" style="background-color: ${{color}};"></span>
                        <span class="legend-name" title="${{label}}">${{label}}</span>
                        <span class="legend-val">${{val}}</span>
                        <span class="legend-pct">${{pct}}</span>
                    </div>
                `;
            }});

            container.innerHTML = html;
        }}

        function initCharts() {{
            document.getElementById('kpiTotalTracks').textContent = rawChartData.length.toLocaleString('es-ES');

            const colors = ['#10B981', '#F59E0B', '#3B82F6', '#EF4444', '#9333EA', '#EC4899', '#14B8A6', '#8B5CF6', '#64748B'];
            
            // 1. ÁLBUM (Tarta)
            const albumData = aggregateData('album');
            new Chart(document.getElementById('albumChart'), {{
                type: 'pie',
                data: {{ labels: albumData.labels, datasets: [{{ data: albumData.data, backgroundColor: colors, borderWidth: 1, borderColor: '#24242A' }}] }},
                options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
            }});
            renderCustomLegend('albumLegend', albumData, colors);

            // 2. GÉNERO (Tarta)
            const genreData = aggregateData('genre');
            new Chart(document.getElementById('genreChart'), {{
                type: 'pie',
                data: {{ labels: genreData.labels, datasets: [{{ data: genreData.data, backgroundColor: colors, borderWidth: 1, borderColor: '#24242A' }}] }},
                options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ display: false }} }} }}
            }});
            renderCustomLegend('genreLegend', genreData, colors);

            // 3. ETIQUETA (Barra)
            const pubData = aggregateData('publisher');
            const pubColors = pubData.labels.map((_, i) => colors[i % colors.length]);
            new Chart(document.getElementById('publisherChart'), {{
                type: 'bar',
                data: {{ labels: pubData.labels, datasets: [{{ label: 'Canciones', data: pubData.data, backgroundColor: pubColors, borderRadius: 4 }}] }},
                options: {{ 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: {{ legend: {{ display: false }} }}, 
                    scales: {{ 
                        x: {{ display: false }},
                        y: {{ beginAtZero: true, grid: {{ color: '#363640' }} }} 
                    }} 
                }}
            }});
            renderCustomLegend('publisherLegend', pubData, pubColors);

            // 4. AÑO (Barra)
            const yearData = aggregateData('year');
            const sortedYears = Object.keys(yearData.labels).map(k => yearData.labels[k]).sort();
            const sortedYearVals = sortedYears.map(y => {{
                const idx = yearData.labels.indexOf(y);
                return yearData.data[idx];
            }});
            const sortedYearObj = {{ labels: sortedYears, data: sortedYearVals }};
            const yearColors = sortedYears.map((_, i) => colors[i % colors.length]);

            new Chart(document.getElementById('yearChart'), {{
                type: 'bar',
                data: {{ labels: sortedYears, datasets: [{{ label: 'Lanzamientos', data: sortedYearVals, backgroundColor: yearColors, borderRadius: 4 }}] }},
                options: {{ 
                    responsive: true, 
                    maintainAspectRatio: false, 
                    plugins: {{ legend: {{ display: false }} }}, 
                    scales: {{ 
                        x: {{ display: false }},
                        y: {{ beginAtZero: true, grid: {{ color: '#363640' }} }} 
                    }} 
                }}
            }});
            renderCustomLegend('yearLegend', sortedYearObj, yearColors);
        }}

        function populateFilters() {{
            const table = document.getElementById('dataTable');
            const tr = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

            const populateSelect = (selectId, colIdx) => {{
                if (colIdx === -1) {{ document.getElementById(selectId).style.display = 'none'; return; }}
                const values = new Set();
                for (let i = 0; i < tr.length; i++) {{
                    const tds = tr[i].getElementsByTagName('td');
                    if (tds[colIdx]) {{
                        const val = tds[colIdx].textContent.trim();
                        if (val && val !== 'N/A') values.add(val);
                    }}
                }}
                const select = document.getElementById(selectId);
                Array.from(values).sort().forEach(val => {{
                    const opt = document.createElement('option');
                    opt.value = val.toLowerCase(); opt.textContent = val;
                    select.appendChild(opt);
                }});
            }};

            populateSelect('albumFilter', idxMap.album);
            populateSelect('genreFilter', idxMap.genre);
            populateSelect('publisherFilter', idxMap.publisher);
        }}

        function filterTable() {{
            const textFilter = document.getElementById('searchInput').value.toLowerCase();
            const albumVal = document.getElementById('albumFilter').value;
            const genreVal = document.getElementById('genreFilter').value;
            const pubVal = document.getElementById('publisherFilter').value;

            const tr = document.getElementById('dataTable').getElementsByTagName('tbody')[0].getElementsByTagName('tr');
            let visibleCount = 0;

            for (let i = 0; i < tr.length; i++) {{
                const tds = tr[i].getElementsByTagName('td');
                let matchText = !textFilter;
                if (textFilter) {{
                    for (let j = 0; j < tds.length; j++) {{
                        if (tds[j].offsetWidth > 0 || tds[j].classList.contains('simplified-target')) {{
                            if (tds[j].textContent.toLowerCase().includes(textFilter)) {{ matchText = true; break; }}
                        }}
                    }}
                }}

                const matchCombo = (colIdx, targetVal) => {{
                    if (!targetVal || colIdx === -1) return true;
                    return tds[colIdx] && tds[colIdx].textContent.trim().toLowerCase() === targetVal;
                }};

                if (matchText && matchCombo(idxMap.album, albumVal) && matchCombo(idxMap.genre, genreVal) && matchCombo(idxMap.publisher, pubVal)) {{
                    tr[i].style.display = ""; visibleCount++;
                }} else {{
                    tr[i].style.display = "none";
                }}
            }}
            document.getElementById('recordCount').textContent = `Mostrando ${{visibleCount}} registros`;
        }}

        function toggleDetailedView() {{
            const showDetails = document.getElementById('toggleViewBtn').checked;
            const allTh = document.querySelectorAll('th');
            const allTd = document.querySelectorAll('td');

            const isEssentialCol = (colIdx) => colIdx == idxMap.file || colIdx == idxMap.cover;

            allTh.forEach(th => {{
                const col = th.getAttribute('data-col');
                if (!showDetails) {{
                    if (!isEssentialCol(col)) {{
                        th.classList.add('hidden-col');
                    }} else {{
                        th.classList.remove('hidden-col');
                        if (col == idxMap.file) th.textContent = 'Nombre';
                        if (col == idxMap.cover) th.textContent = 'Carátula';
                    }}
                }} else {{
                    th.classList.remove('hidden-col');
                    th.textContent = th.getAttribute('data-original');
                }}
            }});

            allTd.forEach(td => {{
                const col = td.getAttribute('data-col');
                if (!showDetails) {{
                    if (!isEssentialCol(col)) {{
                        td.classList.add('hidden-col');
                    }} else {{
                        td.classList.remove('hidden-col');
                        td.classList.add('simplified-target');
                        if (col == idxMap.file && td.hasAttribute('data-clean')) {{
                            td.textContent = td.getAttribute('data-clean');
                        }}
                    }}
                }} else {{
                    td.classList.remove('hidden-col');
                    td.classList.remove('simplified-target');
                    if (col == idxMap.file && td.hasAttribute('data-full')) {{
                        td.textContent = td.getAttribute('data-full');
                    }}
                }}
            }});

            filterTable();
        }}

        window.onload = () => {{
            initCharts();
            toggleDetailedView();
        }};
    </script>
</body>
</html>
"""