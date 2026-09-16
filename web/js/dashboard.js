// js/dashboard.js

let chartInstances = {};

// Paleta de colores
const COLORS = [
    '#10B981', '#F59E0B', '#3B82F6', '#EF4444',
    '#9333EA', '#EC4899', '#14B8A6', '#8B5CF6', '#64748B'
];

/**
 * Mapea el porcentaje de salud a un texto descriptivo de estado
 * @param {number} score - Porcentaje global de salud (0 - 100)
 * @returns {string} Texto representativo del estado
 */
function getHealthStatusText(score) {
    if (score >= 95) return 'EXCELENTE';
    if (score >= 80) return 'BUENO';
    if (score >= 60) return 'ACEPTABLE';
    if (score >= 40) return 'MEJORABLE';
    return 'CRÍTICO';
}

/**
 * Rellena los desplegables de filtro con TODOS los valores únicos existentes en el catálogo.
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

        const uniqueValues = new Set();
        allTracks.forEach(t => {
            const val = t[key];
            if (val !== null && val !== undefined && String(val).trim() !== '') {
                uniqueValues.add(String(val));
            }
        });

        const sortedValues = Array.from(uniqueValues).sort((a, b) =>
            a.localeCompare(b, undefined, { numeric: true })
        );

        select.innerHTML = `<option value="">${defaultText}</option>`;
        sortedValues.forEach(val => {
            const opt = document.createElement('option');
            opt.value = val;
            opt.textContent = val;
            select.appendChild(opt);
        });

        if (sortedValues.includes(currentValue)) {
            select.value = currentValue;
        } else {
            select.value = "";
        }
    });
}

/**
 * Renderiza la leyenda personalizada y asigna eventos táctiles
 */
/**
 * Renderiza la leyenda personalizada y asigna eventos táctiles
 */
function renderCustomLegend(legendId, labels, dataVals, keyName, defaultLabel) {
    const legendElem = document.getElementById(legendId);
    if (!legendElem) return;

    const total = dataVals.reduce((a, b) => a + b, 0);

    let html = `
        <div class="legend-header">
            <span>Nombre</span>
            <span class="val-col">Cant.</span>
            <span class="pct-col">%</span>
        </div>
    `;

    labels.forEach((label, i) => {
        const val = dataVals[i];
        const pct = total > 0 ? ((val / total) * 100).toFixed(2) : '0.00';
        const color = COLORS[i % COLORS.length];

        // Formateo dinámico de estrellas para la dimensión de valoración
        let displayLabel = label;
        if (keyName === 'rating') {
            const numStars = parseInt(label, 10);
            displayLabel = numStars > 0 ? '★'.repeat(numStars) : '0 ★';
        }

        html += `
            <div class="legend-item touchable-legend-item"
                 data-key="${keyName}"
                 data-label="${label}"
                 data-default="${defaultLabel}">
                <span class="legend-color" style="background-color: ${color}"></span>
                <span class="legend-name" title="${displayLabel}">${displayLabel}</span>
                <span class="legend-val">${val.toLocaleString('es-ES')}</span>
                <span class="legend-pct">${pct}%</span>
            </div>
        `;
    });

    legendElem.innerHTML = html;

    legendElem.querySelectorAll('.touchable-legend-item').forEach(item => {
        item.addEventListener('click', () => {
            const key = item.getAttribute('data-key');
            const label = item.getAttribute('data-label');
            const def = item.getAttribute('data-default');

            if (typeof window.handleChartClick === 'function') {
                window.handleChartClick(key, label, def);
            }
        });
    });
}

/**
 * Calcula las métricas de completitud de 7 campos y renderiza el score, diagnóstico y Radar Chart
 */
/**
 * Calcula las métricas de completitud de 7 campos y renderiza el score, diagnóstico y Radar Chart
 */
function renderCollectionHealth(tracks = []) {
    const total = tracks.length;
    if (total === 0) return;

    // Conteo de tracks que tienen datos en cada uno de los 7 campos
    const hasAlbum = tracks.filter(t => t.album && String(t.album).trim() !== '' && t.album !== 'Sin Álbum').length;
    const hasGenre = tracks.filter(t => t.genre && String(t.genre).trim() !== '' && t.genre !== 'Sin Género').length;
    const hasPublisher = tracks.filter(t => t.publisher && String(t.publisher).trim() !== '' && t.publisher !== 'Sin Etiqueta').length;
    const hasCues = tracks.filter(t => t.cue_count && Number(t.cue_count) > 0).length;
    const hasRating = tracks.filter(t => t.rating && Number(t.rating) > 0).length;
    const hasCover = tracks.filter(t => t.cover_url || t.cover_blob).length;
    const hasYear = tracks.filter(t => t.year && String(t.year).trim() !== '' && t.year !== 'Sin Año').length;

    // Cálculo de porcentaje por dimensión
    const metrics = {
        album: Math.round((hasAlbum / total) * 100),
        genre: Math.round((hasGenre / total) * 100),
        publisher: Math.round((hasPublisher / total) * 100),
        cues: Math.round((hasCues / total) * 100),
        rating: Math.round((hasRating / total) * 100),
        cover: Math.round((hasCover / total) * 100),
        year: Math.round((hasYear / total) * 100)
    };

    // Score Global (Promedio de los 7 campos)
    const overallScore = Math.round(
        (metrics.album + metrics.genre + metrics.publisher + metrics.cues + metrics.rating + metrics.cover + metrics.year) / 7
    );

    // 1. Actualizar Círculo SVG y Texto de Estado
    const scoreValElem = document.getElementById('healthScoreValue');
    const scoreCircle = document.getElementById('healthScoreCircle');
    const scoreLabelElem = document.getElementById('healthScoreLabel');

    if (scoreValElem) scoreValElem.textContent = `${overallScore}%`;
    if (scoreLabelElem) scoreLabelElem.textContent = getHealthStatusText(overallScore);
    if (scoreCircle) {
        const circumference = 251.3;
        const offset = circumference - (overallScore / 100) * circumference;
        scoreCircle.style.strokeDashoffset = offset;
    }

    // 2. Diagnóstico: Formato limpio y espaciado con badges
    const diagElem = document.getElementById('healthDiagnosis');
    if (diagElem) {
        let diagHtml = '';

        const createBadge = (icon, count, label) => `
            <div class="diag-item" style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; color: #A1A1AA;">
                <span class="diag-icon" style="font-size: 0.95rem;">${icon}</span>
                <strong class="diag-num" style="color: #F4F4F5; font-weight: 600;">${count.toLocaleString('es-ES')}</strong>
                <span>${label}</span>
            </div>
        `;

        if (hasCover < total) diagHtml += createBadge('🖼️', total - hasCover, 'sin carátula');
        if (hasRating < total) diagHtml += createBadge('⭐', total - hasRating, 'sin valoración');
        if (hasCues < total) diagHtml += createBadge('🎧', total - hasCues, 'sin Cue points');
        if (hasGenre < total) diagHtml += createBadge('🎵', total - hasGenre, 'sin género');
        if (hasPublisher < total) diagHtml += createBadge('🏷️', total - hasPublisher, 'sin etiqueta');
        if (hasAlbum < total) diagHtml += createBadge('💿', total - hasAlbum, 'sin álbum');
        if (hasYear < total) diagHtml += createBadge('📅', total - hasYear, 'sin año');

        if (diagHtml === '') diagHtml = '<div style="color:#10B981; grid-column: span 2;">✨ Colección 100% completada</div>';
        diagElem.innerHTML = diagHtml;
    }

    // 3. Renderizar Radar Chart con los 7 ejes
    const canvas = document.getElementById('healthRadarChart');
    if (!canvas || typeof Chart === 'undefined') return;

    if (chartInstances['healthRadarChart']) {
        chartInstances['healthRadarChart'].destroy();
    }

    chartInstances['healthRadarChart'] = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: ['Álbum', 'Género', 'Etiqueta', 'Cue Points', 'Rating', 'Carátula', 'Año'],
            datasets: [{
                label: 'Completitud (%)',
                data: [
                    metrics.album,
                    metrics.genre,
                    metrics.publisher,
                    metrics.cues,
                    metrics.rating,
                    metrics.cover,
                    metrics.year
                ],
                backgroundColor: 'rgba(139, 92, 246, 0.25)',
                borderColor: '#8B5CF6',
                borderWidth: 2,
                pointBackgroundColor: '#EC4899',
                pointBorderColor: '#FFF',
                pointHoverBackgroundColor: '#FFF',
                pointHoverBorderColor: '#EC4899',
                pointRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                r: {
                    angleLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    grid: { color: 'rgba(255, 255, 255, 0.1)' },
                    pointLabels: {
                        color: '#A1A1AA',
                        font: { size: 10, weight: '600' }
                    },
                    ticks: {
                        color: '#71717A',
                        backdropColor: 'transparent',
                        stepSize: 20
                    },
                    suggestedMin: 0,
                    suggestedMax: 100
                }
            }
        }
    });
}

/**
 * Actualiza los KPIs y renderiza los dashboards
 * @param {Array} tracksList - Array de canciones a mostrar
 */
export function updateDashboard(tracksList = []) {
    try {
        const totalTracks = tracksList.length;

        const totalElem = document.getElementById('kpiTotalTracks');
        if (totalElem) {
            totalElem.textContent = totalTracks.toLocaleString('es-ES');
        }

        // Renderizar Salud de la Colección (Score Global + Radar Chart)
        renderCollectionHealth(tracksList);

        const buildChart = (canvasId, legendId, keyName, defaultLabel, chartType, sortAsc = false, customLabels = null, overrideDataMap = null) => {
            let labels = [];
            let dataVals = [];

            if (overrideDataMap) {
                labels = Object.keys(overrideDataMap);
                dataVals = labels.map(k => overrideDataMap[k]);
            } else {
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

                let sortedKeys = Object.keys(counts);
                if (customLabels) {
                    sortedKeys = customLabels.filter(k => counts[k] !== undefined || k === defaultLabel);
                } else if (sortAsc) {
                    sortedKeys.sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
                } else {
                    sortedKeys.sort((a, b) => counts[b] - counts[a]);
                }

                labels = sortedKeys;
                dataVals = labels.map(k => counts[k] || 0);
            }

            const sliceColors = labels.map((_, i) => COLORS[i % COLORS.length]);

            const chartCanvas = document.getElementById(canvasId);
            if (!chartCanvas) return;

            if (chartInstances[canvasId]) {
                chartInstances[canvasId].destroy();
            }

            if (typeof Chart === 'undefined') return;

            const isSingleSlice = labels.length <= 1;
            const computedBorderWidth = (chartType === 'pie') ? (isSingleSlice ? 0 : 1) : 0;

            const datasetConfig = {
                data: dataVals,
                backgroundColor: chartType === 'line' ? 'rgba(99, 102, 241, 0.2)' : sliceColors,
                borderColor: chartType === 'line' ? '#6366F1' : '#24242A',
                borderWidth: chartType === 'line' ? 2 : computedBorderWidth,
                borderRadius: chartType === 'bar' ? 4 : 0,
                fill: chartType === 'line',
                tension: 0.3,
                pointRadius: 0,
                pointHitRadius: 10
            };

            const isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);

            const chartConfig = {
                type: chartType,
                data: {
                    labels: labels,
                    datasets: [datasetConfig]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { display: false }
                    },
                    onClick: isTouchDevice ? null : (event, activeElements) => {
                        if (activeElements && activeElements.length > 0) {
                            const index = activeElements[0].index;
                            const selectedLabel = labels[index];
                            if (typeof window.handleChartClick === 'function') {
                                window.handleChartClick(keyName, selectedLabel, defaultLabel);
                            }
                        }
                    }
                }
            };

            if (chartType === 'bar' || chartType === 'line') {
                chartConfig.options.scales = {
                    x: {
                        display: chartType === 'line',
                        grid: { color: '#363640' },
                        ticks: {
                            color: '#A1A1AA',
                            maxRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: '#363640' },
                        ticks: { color: '#A1A1AA' }
                    }
                };
            }

            chartInstances[canvasId] = new Chart(chartCanvas, chartConfig);
            if (legendId) {
                renderCustomLegend(legendId, labels, dataVals, keyName, defaultLabel);
            }
        };

        // 1. Álbum y Género
        buildChart('albumChart', 'albumLegend', 'album', 'Sin Álbum', 'pie');
        buildChart('genreChart', 'genreLegend', 'genre', 'Sin Género', 'pie');

        // 2. Pistas por Etiqueta
        buildChart('publisherChart', 'publisherLegend', 'publisher', 'Sin Etiqueta', 'bar', false);

        // 3. Agrupación dinámica SOLO de los años existentes
        const yearCounts = {};
        tracksList.forEach(t => {
            const yr = parseInt(t.year, 10);
            if (t.year && !isNaN(yr)) {
                yearCounts[yr] = (yearCounts[yr] || 0) + 1;
            }
        });

        const sortedYears = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);

        const yearBuckets = {};
        sortedYears.forEach(yr => {
            yearBuckets[String(yr)] = yearCounts[yr];
        });

        buildChart('yearChart', 'yearLegend', 'year', 'Sin Año', 'line', false, null, yearBuckets);

        // 4. Distribución por Rating (0 a 5 Estrellas)
        const ratingLabels = ['0', '1', '2', '3', '4', '5'];
        buildChart('ratingChart', 'ratingLegend', 'rating', '0', 'bar', false, ratingLabels);

    } catch (err) {
        console.error('Error al actualizar Dashboard:', err);
    }
}