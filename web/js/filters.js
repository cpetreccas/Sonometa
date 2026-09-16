/**
 * filters.js - Funciones de filtrado y gestión de filtros
 * ✅ Corregido: Cross-filtering de gráficas (handleChartClick)
 * ✅ Corregido: Manejo completo de filtro por Rating (1-5 estrellas)
 * ✅ Corregido: Persistencia de rating en resetAllFilters()
 * ✅ Corregido: Búsqueda insensible a acentos/diacríticos
 * ✅ Añadido: Memoización para rendimiento y Toast de feedback visual
 */

import { context } from './app_context.js';
import { updateDashboard } from './dashboard.js';
import { loadTableData } from './collection_view.js';

let lastFiltersCache = null;
let lastResultsCache = null;

// Función para normalizar texto (convierte a minúsculas y quita acentos)
function normalizeText(text) {
    if (!text) return '';
    return text.toString().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
}

/**
 * Popula los selectores de filtros dinámicamente según los tracks actuales
 */
export function populateSelectFilters() {
    const filterDefs = [
        { id: 'albumFilter', key: 'album', defaultLabel: 'Álbum: Todos', emptyLabel: 'Sin Álbum' },
        { id: 'genreFilter', key: 'genre', defaultLabel: 'Género: Todos', emptyLabel: 'Sin Género' },
        { id: 'publisherFilter', key: 'publisher', defaultLabel: 'Etiqueta: Todas', emptyLabel: 'Sin Etiqueta' },
        { id: 'yearFilter', key: 'year', defaultLabel: 'Año: Todos', emptyLabel: 'Sin Año' }
    ];

    const desktopContainer = document.getElementById('desktopFilterContainer');
    const mobileContainer = document.getElementById('mobileFilterContainer');

    if (desktopContainer) desktopContainer.innerHTML = '';
    if (mobileContainer) mobileContainer.innerHTML = '';

    for (const f of filterDefs) {
        const uniqueVals = new Set();
        let hasEmpty = false;

        context.allTracks.forEach(track => {
            let match = true;

            // Validar búsqueda (normalizada con acentos)
            if (context.currentFilters.search) {
                const q = normalizeText(context.currentFilters.search);
                const fn = normalizeText(track.filename);
                const title = normalizeText(track.title);
                const artist = normalizeText(track.artist);
                if (!fn.includes(q) && !title.includes(q) && !artist.includes(q)) match = false;
            }

            // Validar filtros de campos
            for (const key of ['album', 'genre', 'publisher', 'year']) {
                if (key === f.key) continue;
                const val = context.currentFilters[key];
                if (!val) continue;

                const trackVal = track[key];
                if (val === '__EMPTY__') {
                    if (trackVal !== null && trackVal !== undefined && String(trackVal).trim() !== '') match = false;
                } else if (String(trackVal) !== String(val)) {
                    match = false;
                }
            }

            // Validar flags especiales
            if (context.currentFilters.noCues && track.cue_count > 0) match = false;
            if (context.currentFilters.noCover && track.cover_url) match = false;

            if (context.currentFilters.noRating && Number(track.rating || 0) > 0) {
                match = false;
            }
            if (context.currentFilters.rating && String(track.rating) !== String(context.currentFilters.rating)) {
                match = false;
            }

            if (match) {
                const val = track[f.key];
                if (val === null || val === undefined || String(val).trim() === '') {
                    hasEmpty = true;
                } else {
                    uniqueVals.add(String(val));
                }
            }
        });

        const sortedVals = Array.from(uniqueVals).sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));

        const createSelect = (selectId) => {
            const select = document.createElement('select');
            select.id = selectId;
            select.className = 'filter-select';
            select.onchange = (e) => handleFilterChange(f.key, e.target.value);

            const optAll = document.createElement('option');
            optAll.value = "";
            optAll.textContent = f.defaultLabel;
            select.appendChild(optAll);

            if (hasEmpty) {
                const optEmpty = document.createElement('option');
                optEmpty.value = "__EMPTY__";
                optEmpty.textContent = f.emptyLabel;
                select.appendChild(optEmpty);
            }

            sortedVals.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v;
                opt.textContent = v;
                select.appendChild(opt);
            });

            select.value = context.currentFilters[f.key] || "";
            if (context.currentFilters[f.key]) select.classList.add('active-filter');

            return select;
        };

        if (desktopContainer) desktopContainer.appendChild(createSelect(f.id));
        if (mobileContainer) mobileContainer.appendChild(createSelect(f.id + '_mobile'));
    }

    updateFilterSummaryBar();
}

/**
 * Maneja cambios en los filtros select
 */
export function handleFilterChange(key, value) {
    context.currentFilters[key] = value;
    applyFilters();
}

/**
 * Actualiza la barra visual de resumen de filtros activos
 */
export function updateFilterSummaryBar() {
    let activeCount = 0;
    let activeNames = [];

    if (context.currentFilters.search) {
        activeCount++;
        activeNames.push(`"${context.currentFilters.search}"`);
    }

    const mapping = { album: 'Álbum', genre: 'Género', publisher: 'Etiqueta', year: 'Año' };
    Object.keys(mapping).forEach(k => {
        if (context.currentFilters[k] && context.currentFilters[k] !== "") {
            activeCount++;
            const valLabel = context.currentFilters[k] === '__EMPTY__' ? 'Sin valor' : context.currentFilters[k];
            activeNames.push(`${mapping[k]}: ${valLabel}`);
        }
    });

    if (context.currentFilters.noCues) { activeCount++; activeNames.push('Sin Cues'); }
    if (context.currentFilters.noCover) { activeCount++; activeNames.push('Sin Carátula'); }

    if (context.currentFilters.noRating) {
        activeCount++;
        activeNames.push('Sin Rating');
    }
    if (context.currentFilters.rating && context.currentFilters.rating !== "") {
        activeCount++;
        activeNames.push(`Rating: ${context.currentFilters.rating}★`);
    }

    const badge = document.getElementById('activeFilterBadge');
    const summaryText = document.getElementById('filterSummaryText');
    const resetBtn = document.getElementById('btnGlobalResetFilters');

    if (badge) {
        badge.style.display = activeCount > 0 ? 'inline-block' : 'none';
        badge.textContent = activeCount;
    }
    if (summaryText) {
        summaryText.style.color = '';
        summaryText.textContent = activeCount > 0 ? activeNames.join(' | ') : 'Sin filtros aplicados';
    }
    if (resetBtn) {
        resetBtn.style.display = activeCount > 0 ? 'inline-block' : 'none';
    }

    ['noCues', 'noCover', 'noRating'].forEach(key => {
        const capitalized = key.charAt(0).toUpperCase() + key.slice(1);
        const btnDesktop = document.getElementById(`btnToggle${capitalized}`);
        const btnMobile = document.getElementById(`btnToggle${capitalized}Mobile`);

        if (context.currentFilters[key]) {
            btnDesktop?.classList.add('active');
            btnMobile?.classList.add('active');
        } else {
            btnDesktop?.classList.remove('active');
            btnMobile?.classList.remove('active');
        }
    });
}

export function toggleFilterFlag(key) {
    context.currentFilters[key] = !context.currentFilters[key];
    applyFilters();
}

/**
 * Aplica los filtros actuales a la colección de tracks con memoización y búsqueda insensible a acentos
 */
export function applyFilters() {
    const currentFiltersStr = JSON.stringify(context.currentFilters);

    // Memoización: evitar filtrado en memoria si los criterios no cambiaron
    if (currentFiltersStr === lastFiltersCache && lastResultsCache) {
        context.filteredTracks = lastResultsCache;
        return;
    }

    const q = normalizeText(context.currentFilters.search);

    context.filteredTracks = context.allTracks.filter(t => {
        // Búsqueda insensible a acentos
        if (q) {
            const fn = normalizeText(t.filename);
            const title = normalizeText(t.title);
            const artist = normalizeText(t.artist);
            if (!fn.includes(q) && !title.includes(q) && !artist.includes(q)) return false;
        }

        // Filtros por campos
        for (const key of ['album', 'genre', 'publisher', 'year']) {
            const filterVal = context.currentFilters[key];
            if (!filterVal) continue;

            const trackVal = t[key];
            if (filterVal === '__EMPTY__') {
                if (trackVal !== null && trackVal !== undefined && String(trackVal).trim() !== '') return false;
            } else if (String(trackVal) !== String(filterVal)) {
                return false;
            }
        }

        // Flags especiales
        if (context.currentFilters.noCues && Number(t.cue_count || 0) > 0) return false;
        if (context.currentFilters.noCover && t.cover_url && String(t.cover_url).trim() !== '') return false;

        // Rating
        if (context.currentFilters.noRating && Number(t.rating || 0) > 0) return false;
        if (context.currentFilters.rating && String(t.rating) !== String(context.currentFilters.rating)) return false;

        return true;
    });

    lastFiltersCache = currentFiltersStr;
    lastResultsCache = context.filteredTracks;

    populateSelectFilters();
    updateDashboard(context.filteredTracks);
    context.currentPage = 0;
    loadTableData();
}

export function applyFiltersAndClose() {
    applyFilters();
    closeFilterModal();
}

/**
 * Resetea todos los filtros a su estado inicial
 */
export function resetAllFilters() {
    context.currentFilters = {
        search: '',
        album: '',
        genre: '',
        publisher: '',
        year: '',
        rating: '',
        noCues: false,
        noCover: false,
        noRating: false
    };
    const sInput = document.getElementById('searchInput');
    const sMobile = document.getElementById('searchInputMobile');
    if (sInput) sInput.value = '';
    if (sMobile) sMobile.value = '';
    applyFilters();
}

export function openFilterModal() {
    const sMobile = document.getElementById('searchInputMobile');
    if (sMobile) sMobile.value = context.currentFilters.search;
    document.getElementById('filterOverlay')?.classList.add('active');
    document.getElementById('filterModal')?.classList.add('active');
}

export function closeFilterModal() {
    document.getElementById('filterOverlay')?.classList.remove('active');
    document.getElementById('filterModal')?.classList.remove('active');
}

/**
 * Maneja el clic sobre elementos de las gráficas del Dashboard (Cross-Filtering)
 */
export function handleChartClick(key, label, defaultLabel) {
    const filterValue = (label === defaultLabel) ? '__EMPTY__' : label;

    if (key === 'rating') {
        if (filterValue === '__EMPTY__') {
            context.currentFilters.noRating = true;
            context.currentFilters.rating = '';
        } else {
            context.currentFilters.noRating = false;
            context.currentFilters.rating = filterValue;
        }
    } else if (['album', 'genre', 'publisher', 'year'].includes(key)) {
        context.currentFilters[key] = filterValue;
    }

    applyFilters();
    showFilterToast(`Filtro aplicado: ${key} = ${label}`);
}

function showFilterToast(message) {
    let toast = document.getElementById('filterToast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'filterToast';
        toast.style.cssText = `
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #8B5CF6;
            color: #FFF;
            padding: 10px 18px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 10000;
            transition: opacity 0.3s ease;
        `;
        document.body.appendChild(toast);
    }
    toast.textContent = message;
    toast.style.opacity = '1';
    setTimeout(() => { toast.style.opacity = '0'; }, 2000);
}