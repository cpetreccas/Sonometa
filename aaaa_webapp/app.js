
let db = null;
let currentPage = 0;
const PAGE_SIZE = 100;
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

function updateFilterStyles() {
    const filters = ['albumFilter', 'genreFilter', 'publisherFilter', 'yearFilter'];
    let anyActive = false;

    filters.forEach(id => {
        const elem = document.getElementById(id);
        if (elem) {
            if (elem.value !== '') {
                elem.classList.add('active-filter');
                anyActive = true;
            } else {
                elem.classList.remove('active-filter');
            }
        }
    });

    const btnReset = document.getElementById('btnResetFilters');
    if (btnReset) {
        btnReset.style.display = anyActive ? 'inline-block' : 'none';
    }
}

function handleFilterChange() {
    updateFilterStyles();
    resetAndSearch();
}

function resetAllFilters() {
    ['albumFilter', 'genreFilter', 'publisherFilter', 'yearFilter'].forEach(id => {
        const elem = document.getElementById(id);
        if (elem) elem.value = '';
    });
    updateFilterStyles();
    resetAndSearch();
}

function loadTableData() {
    const searchInput = document.getElementById('searchInput');
    const albumFilter = document.getElementById('albumFilter');
    const genreFilter = document.getElementById('genreFilter');
    const publisherFilter = document.getElementById('publisherFilter');
    const yearFilter = document.getElementById('yearFilter');
    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const resultsCountElem = document.getElementById('resultsCount');

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
                <th class="th-cover">CARÁTULA</th>
                <th>INTÉRPRETE</th>
                <th>TÍTULO</th>
                <th>REMIX</th>
                <th>ÁLBUM</th>
                <th>GÉNERO</th>
                <th>ETIQUETA</th>
                <th class="col-center">AÑO</th>
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
            
            // Evento para resaltar fila activa en toque/click móvil
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
            
            let cleanFilename = rawFilename.replace(/\.[^/.]+$/, "");
            
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
        const colSpan = verDetalle ? 8 : 2;
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
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(resetAndSearch, 150);
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
