// js/dashboard.js

let chartInstances = {};

// Paleta de colores idéntica al código original
const COLORS = [
    '#10B981', '#F59E0B', '#3B82F6', '#EF4444',
    '#9333EA', '#EC4899', '#14B8A6', '#8B5CF6', '#64748B'
];

/**
 * Rellena los desplegables de filtro con TODOS los valores únicos existentes en el catálogo.
 * Llama a esta función al cargar los datos (o pásale `allTracks`).
 * @param {Array} allTracks - Array completo de canciones sin filtrar
 */
export function populateFilterDropdowns(allTracks = []) {
    const fields = [
        { id: 'filterGenre', key: 'genre', defaultText: 'Todos los Géneros' },
        { id: 'filterAlbum', key: 'album', defaultText: 'Todos los Álbumes' },
        { id: 'filterPublisher', key: 'publisher', defaultText: 'Todas las Etiquetas' },
        { id: 'filterYear', key: 'year', defaultText: 'Todos los Años' }
    ];

    fields.forEach(({ id, key, defaultText }) => {
        const select = document.getElementById(id);
        if (!select) return;

        const currentValue = select.value;

        // Extraer valores únicos no vacíos
        const uniqueValues = new Set();
        allTracks.forEach(t => {
            const val = t[key];
            if (val !== null && val !== undefined && String(val).trim() !== '') {
                uniqueValues.add(String(val));
            }
        });

        // Ordenar los valores
        const sortedValues = Array.from(uniqueValues).sort((a, b) =>
            a.localeCompare(b, undefined, { numeric: true })
        );

        // Limpiar y poblar opciones
        select.innerHTML = `<option value="">${defaultText}</option>`;
        sortedValues.forEach(val => {
            const opt = document.createElement('option');
            opt.value = val;
            opt.textContent = val;
            select.appendChild(opt);
        });

        // Mantener la selección actual si sigue disponible
        if (sortedValues.includes(currentValue)) {
            select.value = currentValue;
        } else {
            select.value = "";
        }
    });
}

/**
 * Genera la leyenda HTML lateral idéntica a la interfaz original
 */
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

/**
 * Actualiza los KPIs y renderiza los dashboards usando el estado en memoria
 * @param {Array} tracksList - Array de canciones a mostrar (allTracks o filteredTracks)
 */
export function updateDashboard(tracksList = []) {
    try {
        const totalTracks = tracksList.length;

        // Actualizar KPI de total de canciones
        const totalElem = document.getElementById('kpiTotalTracks');
        if (totalElem) {
            totalElem.textContent = totalTracks.toLocaleString('es-ES');
        }

        const buildChart = (canvasId, legendId, keyName, defaultLabel, chartType, sortAsc = false) => {
            const counts = {};

            // Agrupar datos directamente en memoria
            tracksList.forEach(t => {
                let val = t[keyName];
                if (val === null || val === undefined || String(val).trim() === '') {
                    val = defaultLabel;
                } else {
                    val = String(val);
                }
                counts[val] = (counts[val] || 0) + 1;
            });

            // Ordenar claves
            let sortedKeys = Object.keys(counts);
            if (sortAsc) {
                sortedKeys.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
            } else {
                sortedKeys.sort((a, b) => counts[b] - counts[a]);
            }

            const labels = sortedKeys;
            const dataVals = labels.map(k => counts[k]);
            const sliceColors = labels.map((_, i) => COLORS[i % COLORS.length]);

            const chartCanvas = document.getElementById(canvasId);
            if (!chartCanvas) return;

            // Destruir instancia previa para redibujar
            if (chartInstances[canvasId]) {
                chartInstances[canvasId].destroy();
            }

            if (typeof Chart === 'undefined') return;

            // Eliminar borde interno si solo hay un valor en las tartas
            const isSingleSlice = labels.length <= 1;
            const computedBorderWidth = (chartType === 'pie') ? (isSingleSlice ? 0 : 1) : 0;

            const chartConfig = {
                type: chartType,
                data: {
                    labels: labels,
                    datasets: [{
                        data: dataVals,
                        backgroundColor: sliceColors,
                        borderWidth: computedBorderWidth,
                        borderColor: '#24242A',
                        borderRadius: chartType === 'bar' ? 4 : 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    }
                }
            };

            if (chartType === 'bar') {
                chartConfig.options.scales = {
                    x: { display: false },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#363640' },
                        ticks: { color: '#A1A1AA' }
                    }
                };
            }

            chartInstances[canvasId] = new Chart(chartCanvas, chartConfig);
            renderCustomLegend(legendId, labels, dataVals);
        };

        // Renderizado de las 4 gráficas
        buildChart('albumChart', 'albumLegend', 'album', 'Sin Álbum', 'pie');
        buildChart('genreChart', 'genreLegend', 'genre', 'Sin Género', 'pie');
        buildChart('publisherChart', 'publisherLegend', 'publisher', 'Sin Etiqueta', 'bar', true);
        buildChart('yearChart', 'yearLegend', 'year', 'Sin Año', 'bar', true);

    } catch (err) {
        console.error('Error al actualizar Dashboard:', err);
    }
}