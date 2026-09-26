// js/dashboard.js

let chartInstances = {};

// Paleta de colores ajustada a la Guía de Estilos de Sonometa (Dark UI / Purple Accent)
const COLORS = [
    '#8B5CF6', // Purple Primary
    '#6366F1', // Indigo Accent
    '#A855F7', // Purple Light
    '#EC4899', // Pink Accent
    '#3B82F6', // Blue Secondary
    '#7C3AED', // Purple Dark Hover
    '#C084FC', // Violet Soft
    '#38BDF8', // Sky Blue
    '#64748B'  // Neutral Muted
];

// Escala monocromática de la Guía de Estilos para la distribución por valoración
// (--chart-5-star ... --chart-1-star). Sin valorar (0) usa el morado corporativo al
// 35% en vez del gris --chart-0-star, para que todas las barras sean moradas.
// Mismos valores que RATING_COLORS en src/stats_dashboard_view.py (escritorio).
const RATING_COLORS = {
    '5': '#8B5CF6',
    '4': '#7C3AED',
    '3': '#6D28D9',
    '2': '#4C1D95',
    '1': '#2E1065',
    '0': '#483871'
};

// Rango de volumen correcto de la auditoría técnica (LUFS_OK_MIN / LUFS_OK_MAX en
// src/audio_health_checker.py): por debajo "volumen bajo", por encima "volumen excesivo".
const LUFS_OK_MIN = -16;
const LUFS_OK_MAX = -6;

/**
 * Mapea el porcentaje de calidad a un texto descriptivo de estado
 * @param {number} score - Porcentaje global de calidad (0 - 100)
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
function renderCustomLegend(legendId, labels, dataVals, keyName, defaultLabel, colors) {
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
        // Categorías sin pistas (p. ej. años intermedios rellenados a 0 para que el
        // eje del gráfico sea continuo) no aportan nada en la leyenda.
        if (!val) return;
        const pct = total > 0 ? ((val / total) * 100).toFixed(2) : '0.00';
        const color = colors[i];

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
 * Calidad de la colección: completitud de 7 campos + auditoría técnica de audio
 * (integridad, saturación, volumen, bitrate real). En el score global la parte
 * técnica pesa la mitad multiplicada por la cobertura del análisis (50/50 con todo
 * analizado) y el radar lleva un eje por indicador. Mismo cálculo que
 * _compute_quality() en src/health_dashboard_view.py (escritorio).
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

    // Parte de datos: promedio de los 7 campos
    const dataScore = Math.round(
        (metrics.album + metrics.genre + metrics.publisher + metrics.cues + metrics.rating + metrics.cover + metrics.year) / 7
    );

    // Parte técnica: solo sobre las pistas ya analizadas
    const analyzed = tracks.filter(t => t.health);
    const nAnalyzed = analyzed.length;
    const hasLufs = h => h.lufs_integrated !== null && h.lufs_integrated !== undefined;
    const audit = {
        clipping: analyzed.filter(t => t.health.has_clipping).length,
        loudLow: analyzed.filter(t => hasLufs(t.health) && t.health.lufs_integrated < LUFS_OK_MIN).length,
        loudHigh: analyzed.filter(t => hasLufs(t.health) && t.health.lufs_integrated > LUFS_OK_MAX).length,
        bitrateFake: analyzed.filter(t => t.health.bitrate_fake).length,
        integrity: analyzed.filter(t => ['warning', 'critical'].includes(t.health.integrity_status)).length
    };
    const passPct = count => Math.round(((nAnalyzed - count) / nAnalyzed) * 100);
    const techAxes = nAnalyzed ? [
        ['Integridad', passPct(audit.integrity)],
        ['Sin saturación', passPct(audit.clipping)],
        ['Volumen', passPct(audit.loudLow + audit.loudHigh)],
        ['Bitrate real', passPct(audit.bitrateFake)]
    ] : [];
    const techScore = nAnalyzed ? techAxes.reduce((sum, [, v]) => sum + v, 0) / techAxes.length : null;

    // Score Global: la técnica pesa 50% × cobertura (solo datos si no hay nada analizado)
    const techWeight = 0.5 * (nAnalyzed / total);
    const overallScore = techScore === null
        ? dataScore
        : Math.round(dataScore * (1 - techWeight) + techScore * techWeight);

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

    // 2. Diagnóstico: iconos SVG de línea coloreados por gravedad (Guía de Estilos):
    //    ámbar = aviso (campo que falta, volumen, bitrate), rojo = crítico (saturación, corruptos)
    const diagElem = document.getElementById('healthDiagnosis');
    if (diagElem) {
        let diagHtml = '';

        const DIAG_ICONS = {
            cover: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>`,
            rating: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
            cues: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/></svg>`,
            genre: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
            publisher: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>`,
            album: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/></svg>`,
            year: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>`,
            clipping: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
            loudLow: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
            loudHigh: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>`,
            bitrateFake: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#F59E0B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 14l4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>`,
            integrity: `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`
        };

        const createBadge = (iconSvg, count, label) => `
            <div class="diag-item" style="display: flex; align-items: center; gap: 8px; font-size: 0.85rem; color: #A1A1AA;">
                <span class="diag-icon" style="display: flex; align-items: center; justify-content: center;">${iconSvg}</span>
                <strong class="diag-num" style="color: #F4F4F5; font-weight: 600;">${count.toLocaleString('es-ES')}</strong>
                <span>${label}</span>
            </div>
        `;

        if (hasCover < total) diagHtml += createBadge(DIAG_ICONS.cover, total - hasCover, 'sin carátula');
        if (hasRating < total) diagHtml += createBadge(DIAG_ICONS.rating, total - hasRating, 'sin valoración');
        if (hasCues < total) diagHtml += createBadge(DIAG_ICONS.cues, total - hasCues, 'sin Cue points');
        if (hasGenre < total) diagHtml += createBadge(DIAG_ICONS.genre, total - hasGenre, 'sin género');
        if (hasPublisher < total) diagHtml += createBadge(DIAG_ICONS.publisher, total - hasPublisher, 'sin etiqueta');
        if (hasAlbum < total) diagHtml += createBadge(DIAG_ICONS.album, total - hasAlbum, 'sin álbum');
        if (hasYear < total) diagHtml += createBadge(DIAG_ICONS.year, total - hasYear, 'sin año');

        // Avisos de la auditoría técnica
        if (audit.clipping) diagHtml += createBadge(DIAG_ICONS.clipping, audit.clipping, 'con saturación');
        if (audit.loudLow) diagHtml += createBadge(DIAG_ICONS.loudLow, audit.loudLow, 'con volumen bajo');
        if (audit.loudHigh) diagHtml += createBadge(DIAG_ICONS.loudHigh, audit.loudHigh, 'con volumen excesivo');
        if (audit.bitrateFake) diagHtml += createBadge(DIAG_ICONS.bitrateFake, audit.bitrateFake, 'con bitrate falso');
        if (audit.integrity) diagHtml += createBadge(DIAG_ICONS.integrity, audit.integrity, 'corruptos o truncados');

        if (diagHtml === '') diagHtml = '<div style="color:#10B981; grid-column: span 2;">✨ Colección 100% completada</div>';
        diagElem.innerHTML = diagHtml;
    }

    // Cobertura del análisis técnico (se analiza desde la app de escritorio)
    const coveragePct = Math.round((nAnalyzed / total) * 100);
    const coverageText = document.getElementById('healthCoverageText');
    const coverageFill = document.getElementById('healthCoverageFill');
    if (coverageText) coverageText.textContent = `${nAnalyzed.toLocaleString('es-ES')} de ${total.toLocaleString('es-ES')} analizadas (${coveragePct}%)`;
    if (coverageFill) coverageFill.style.width = `${coveragePct}%`;

    // 3. Renderizar Radar Chart
    const canvas = document.getElementById('healthRadarChart');
    if (!canvas || typeof Chart === 'undefined') return;

    if (chartInstances['healthRadarChart']) {
        chartInstances['healthRadarChart'].destroy();
    }

    chartInstances['healthRadarChart'] = new Chart(canvas, {
        type: 'radar',
        data: {
            labels: ['Álbum', 'Género', 'Etiqueta', 'Cue Points', 'Rating', 'Carátula', 'Año', ...techAxes.map(([label]) => label)],
            datasets: [{
                label: 'Calidad (%)',
                data: [
                    metrics.album,
                    metrics.genre,
                    metrics.publisher,
                    metrics.cues,
                    metrics.rating,
                    metrics.cover,
                    metrics.year,
                    ...techAxes.map(([, value]) => value)
                ],
                backgroundColor: 'rgba(139, 92, 246, 0.3)',
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
                    angleLines: { color: 'rgba(255, 255, 255, 0.22)' },
                    grid: { color: 'rgba(255, 255, 255, 0.18)' },
                    pointLabels: {
                        color: '#F4F4F5',
                        font: { size: 11, weight: '600' }
                    },
                    ticks: {
                        color: '#B3B3AD',
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

        // Renderizar Calidad de la Colección (Score Global + Radar Chart)
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

            // Aplicar la paleta de colores corporativa (escala de morados para la valoración)
            const sliceColors = keyName === 'rating'
                ? labels.map(l => RATING_COLORS[l] || COLORS[0])
                : labels.map((_, i) => COLORS[i % COLORS.length]);

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
                backgroundColor: chartType === 'line' ? 'rgba(139, 92, 246, 0.25)' : sliceColors,
                borderColor: chartType === 'line' ? '#8B5CF6' : '#24242A',
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
                        grid: { color: 'rgba(255, 255, 255, 0.08)' },
                        ticks: {
                            color: '#B3B3AD',
                            maxRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 15
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.08)' },
                        ticks: { color: '#B3B3AD' }
                    }
                };
            }

            chartInstances[canvasId] = new Chart(chartCanvas, chartConfig);
            if (legendId) {
                renderCustomLegend(legendId, labels, dataVals, keyName, defaultLabel, sliceColors);
            }
        };

        // 1. Álbum y Género (Gráficos de tarta)
        buildChart('albumChart', 'albumLegend', 'album', 'Sin Álbum', 'pie');
        buildChart('genreChart', 'genreLegend', 'genre', 'Sin Género', 'pie');

        // 2. Pistas por Etiqueta (Gráfico de barras)
        buildChart('publisherChart', 'publisherLegend', 'publisher', 'Sin Etiqueta', 'bar', false);

        // 3. Distribución por año (Gráfico de líneas). El eje X cubre TODO el rango de
        // años, con 0 en los que no tienen pistas, para que la distancia entre años sea
        // proporcional al tiempo; la leyenda solo lista los años con pistas.
        const yearCounts = {};
        tracksList.forEach(t => {
            const yr = parseInt(t.year, 10);
            if (t.year && !isNaN(yr)) {
                yearCounts[yr] = (yearCounts[yr] || 0) + 1;
            }
        });

        const sortedYears = Object.keys(yearCounts).map(Number).sort((a, b) => a - b);

        const yearBuckets = {};
        if (sortedYears.length > 0) {
            for (let yr = sortedYears[0]; yr <= sortedYears[sortedYears.length - 1]; yr++) {
                yearBuckets[String(yr)] = yearCounts[yr] || 0;
            }
        }

        buildChart('yearChart', 'yearLegend', 'year', 'Sin Año', 'line', false, null, yearBuckets);

        // 4. Distribución por Rating (0 a 5 Estrellas)
        const ratingLabels = ['0', '1', '2', '3', '4', '5'];
        buildChart('ratingChart', 'ratingLegend', 'rating', '0', 'bar', false, ratingLabels);

    } catch (err) {
        console.error('Error al actualizar Dashboard:', err);
    }
}