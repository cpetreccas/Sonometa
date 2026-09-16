import { checkSession, login, logout } from './auth.js';
import { updateDashboard, populateFilterDropdowns } from './dashboard.js';
import { context } from './app_context.js';
import { fetchAllTracks } from './data_loader.js';
import { shareTrackCard } from './share.js';
import {
    sortByColumn,
    loadTableData,
    toggleColumnPicker,
    renderColumnPicker,
    toggleVerDetalle,
    changePage
} from './collection_view.js';
import {
    populateSelectFilters,
    handleFilterChange,
    updateFilterSummaryBar,
    toggleFilterFlag,
    applyFilters,
    applyFiltersAndClose,
    resetAllFilters,
    openFilterModal,
    closeFilterModal,
    handleChartClick
} from './filters.js';
import {
    playTrack,
    togglePlayPause,
    toggleShuffle,
    seekAudio,
    changeVolume,
    changePlaybackSpeed
} from './player.js';

// ============================================================================
// 1. Inicialización PWA & Auth
// ============================================================================
window.addEventListener('DOMContentLoaded', async () => {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('./sw.js').catch(console.error);
    }

    // Cerrar dropdown de columnas al hacer clic fuera
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('columnPickerDropdown');
        if (dropdown && !dropdown.classList.contains('hidden')) {
            dropdown.classList.add('hidden');
        }
    });

    try {
        const session = await checkSession();
        if (session) {
            showApp();
        } else {
            showLogin();
        }
    } catch (err) {
        showGlobalError('Error al iniciar la aplicación');
    }
});

// Eventos Auth
document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('loginEmail').value;
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('authError');
    errorEl.textContent = '';

    try {
        await login(email, password);
        showApp();
    } catch (err) {
        errorEl.textContent = err.message || 'Error de autenticación';
    }
});

document.getElementById('btnLogout')?.addEventListener('click', () => logout());

function showLogin() {
    document.getElementById('authContainer')?.classList.remove('hidden');
    document.getElementById('appContainer')?.classList.add('hidden');
}

async function showApp() {
    document.getElementById('authContainer')?.classList.add('hidden');
    document.getElementById('appContainer')?.classList.remove('hidden');
    await loadInitialCollection();
}

/**
 * Carga exhaustiva de metadatos desde Supabase usando el módulo data_loader
 */
async function loadInitialCollection() {
    try {
        context.allTracks = await fetchAllTracks();
        populateFilterDropdowns(context.allTracks);
        renderColumnPicker();
        applyFilters();
    } catch (err) {
        console.error('Error al cargar colección:', err);
        showGlobalError('No se pudo cargar la biblioteca de canciones.');
    }
}

function showGlobalError(msg) {
    const summaryText = document.getElementById('filterSummaryText');
    if (summaryText) {
        summaryText.textContent = `⚠️ ${msg}`;
        summaryText.style.color = 'var(--color-error, #ff4d4d)';
    }
}

// ============================================================================
// 2. Controlador Orquestador Principal - Exposición de Funciones Globales
// ============================================================================
// Exponer funciones del Menú Móvil y Espaciado del Reproductor
export function toggleMobileMenu() {
    const actions = document.getElementById('headerActions');
    if (actions) {
        actions.classList.toggle('show');
    }
}
window.toggleMobileMenu = toggleMobileMenu;

export function updatePlayerSpacing(isPlayerVisible) {
    if (isPlayerVisible) {
        document.body.classList.add('has-player');
    } else {
        document.body.classList.remove('has-player');
    }
}
window.updatePlayerSpacing = updatePlayerSpacing;

// Exponer funciones de filtrado
window.populateSelectFilters = populateSelectFilters;
window.handleFilterChange = handleFilterChange;
window.updateFilterSummaryBar = updateFilterSummaryBar;
window.toggleFilterFlag = toggleFilterFlag;
window.applyFilters = applyFilters;
window.applyFiltersAndClose = applyFiltersAndClose;
window.resetAllFilters = resetAllFilters;
window.openFilterModal = openFilterModal;
window.closeFilterModal = closeFilterModal;
window.handleChartClick = handleChartClick;

// Exponer funciones de colección/tabla
window.sortByColumn = sortByColumn;
window.loadTableData = loadTableData;
window.toggleColumnPicker = toggleColumnPicker;
window.renderColumnPicker = renderColumnPicker;
window.toggleVerDetalle = toggleVerDetalle;
window.changePage = changePage;

// Exponer funciones del reproductor
window.playTrack = playTrack;
window.togglePlayPause = togglePlayPause;
window.toggleShuffle = toggleShuffle;
window.seekAudio = seekAudio;
window.changeVolume = changeVolume;
window.changePlaybackSpeed = changePlaybackSpeed;

// ============================================================================
// 3. Funciones Auxiliares
// ============================================================================
let searchTimeout;
export function debouncedSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        context.currentFilters.search = searchInput.value.trim();
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => applyFilters(), 150);
    }
}

window.debouncedSearch = debouncedSearch;

export function syncMobileSearch(val) {
    context.currentFilters.search = val.trim();
    const sInput = document.getElementById('searchInput');
    if (sInput) sInput.value = val;
}

window.syncMobileSearch = syncMobileSearch;

export function switchView(view) {
    const isDashboard = view === 'dashboard';
    const dashView = document.getElementById('dashboardView');
    const tblView = document.getElementById('tableView');
    const btnDash = document.getElementById('btnDashboard');
    const btnTbl = document.getElementById('btnTable');

    if (dashView) dashView.style.display = isDashboard ? 'block' : 'none';
    if (tblView) tblView.style.display = isDashboard ? 'none' : 'block';
    if (btnDash) btnDash.style.display = isDashboard ? 'none' : 'inline-block';
    if (btnTbl) btnTbl.style.display = isDashboard ? 'inline-block' : 'none';

    // Cerrar menú hamburguesa al cambiar de vista en móvil
    const actions = document.getElementById('headerActions');
    if (actions && actions.classList.contains('show')) {
        actions.classList.remove('show');
    }
}

window.switchView = switchView;

window.shareTrackCard = shareTrackCard;