// js/app.js
import { supabase } from './supabase.js';
import { checkSession, login, logout } from './auth.js';
import { updateDashboard, populateFilterDropdowns } from './dashboard.js';

let currentPage = 0;
const PAGE_SIZE = 100;

let allTracks = [];
let filteredTracks = [];
let currentTrackIndex = -1;
let isShuffle = false;

// Estado de ordenación global
let sortState = {
    key: 'filename',
    direction: 'asc' // 'asc' | 'desc'
};

// Configuración de visibilidad de columnas
let columnVisibility = {
    cover: true,
    artist: true,
    title: true,
    mix_artist: true,
    album: true,
    genre: true,
    publisher: true,
    year: true,
    cue_count: true,
    rating: true,
    filename: true
};

const ALL_COLUMNS = [
    { key: 'cover', label: 'Carátula', detailOnly: false },
    { key: 'filename', label: 'Nombre de Archivo', detailOnly: false, normalOnly: true },
    { key: 'artist', label: 'Intérprete', detailOnly: true },
    { key: 'title', label: 'Título', detailOnly: true },
    { key: 'mix_artist', label: 'Remix', detailOnly: true },
    { key: 'album', label: 'Álbum', detailOnly: true },
    { key: 'genre', label: 'Género', detailOnly: true },
    { key: 'publisher', label: 'Etiqueta', detailOnly: true },
    { key: 'year', label: 'Año', detailOnly: true },
    { key: 'cue_count', label: 'Cues', detailOnly: true },
    { key: 'rating', label: 'Rating', detailOnly: true }
];

let currentFilters = {
    search: '',
    album: '',
    genre: '',
    publisher: '',
    year: '',
    noCues: false,
    noCover: false,
    noRating: false
};

// 1. Inicialización PWA & Auth
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
 * Carga única de metadatos desde Supabase al iniciar la sesión.
 */
async function loadInitialCollection() {
    try {
        const { data, error } = await supabase
            .from('tracks')
            .select('id, filename, artist, title, mix_artist, album, genre, publisher, year, duration, cue_count, rating, cover_url, preview_audio_url');

        if (error) throw error;

        allTracks = data || [];
        populateFilterDropdowns(allTracks);
        renderColumnPicker();
        window.applyFilters();
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

// 2. Filtros Dinámicos en Memoria
function populateSelectFilters() {
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

        allTracks.forEach(track => {
            let match = true;
            if (currentFilters.search) {
                const q = currentFilters.search.toLowerCase();
                const fn = (track.filename || '').toLowerCase();
                const title = (track.title || '').toLowerCase();
                const artist = (track.artist || '').toLowerCase();
                if (!fn.includes(q) && !title.includes(q) && !artist.includes(q)) match = false;
            }

            for (const key of ['album', 'genre', 'publisher', 'year']) {
                if (key === f.key) continue;
                const val = currentFilters[key];
                if (!val) continue;

                const trackVal = track[key];
                if (val === '__EMPTY__') {
                    if (trackVal !== null && trackVal !== undefined && String(trackVal).trim() !== '') match = false;
                } else if (String(trackVal) !== String(val)) {
                    match = false;
                }
            }

            // Validar flags especiales en el cómputo de opciones
            if (currentFilters.noCues && track.cue_count > 0) match = false;
            if (currentFilters.noCover && track.cover_url) match = false;
            if (currentFilters.noRating && track.rating > 0) match = false;

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

            select.value = currentFilters[f.key] || "";
            if (currentFilters[f.key]) select.classList.add('active-filter');

            return select;
        };

        if (desktopContainer) desktopContainer.appendChild(createSelect(f.id));
        if (mobileContainer) mobileContainer.appendChild(createSelect(f.id + '_mobile'));
    }

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
        if (currentFilters[k] && currentFilters[k] !== "") {
            activeCount++;
            const valLabel = currentFilters[k] === '__EMPTY__' ? 'Sin valor' : currentFilters[k];
            activeNames.push(`${mapping[k]}: ${valLabel}`);
        }
    });

    if (currentFilters.noCues) { activeCount++; activeNames.push('Sin Cues'); }
    if (currentFilters.noCover) { activeCount++; activeNames.push('Sin Carátula'); }
    if (currentFilters.noRating) { activeCount++; activeNames.push('Sin Rating'); }

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

    // Actualizar estilos visuales de botones tipo Chip Toggle
    ['noCues', 'noCover', 'noRating'].forEach(key => {
        const capitalized = key.charAt(0).toUpperCase() + key.slice(1);
        const btnDesktop = document.getElementById(`btnToggle${capitalized}`);
        const btnMobile = document.getElementById(`btnToggle${capitalized}Mobile`);

        if (currentFilters[key]) {
            btnDesktop?.classList.add('active');
            btnMobile?.classList.add('active');
        } else {
            btnDesktop?.classList.remove('active');
            btnMobile?.classList.remove('active');
        }
    });
}

function handleFilterChange(key, value) {
    currentFilters[key] = value;
    populateSelectFilters();
    if (window.innerWidth >= 768) {
        window.applyFilters();
    }
}

window.toggleFilterFlag = function(key) {
    currentFilters[key] = !currentFilters[key];
    populateSelectFilters();
    window.applyFilters();
};

// 3. Objeto controlador principal expuesto
window.applyFilters = function() {
    const q = (currentFilters.search || '').toLowerCase();

    filteredTracks = allTracks.filter(t => {
        if (q) {
            const fn = (t.filename || '').toLowerCase();
            const title = (t.title || '').toLowerCase();
            const artist = (t.artist || '').toLowerCase();
            if (!fn.includes(q) && !title.includes(q) && !artist.includes(q)) return false;
        }

        for (const key of ['album', 'genre', 'publisher', 'year']) {
            const filterVal = currentFilters[key];
            if (!filterVal) continue;

            const trackVal = t[key];
            if (filterVal === '__EMPTY__') {
                if (trackVal !== null && trackVal !== undefined && String(trackVal).trim() !== '') return false;
            } else if (String(trackVal) !== String(filterVal)) {
                return false;
            }
        }

        if (currentFilters.noCues && Number(t.cue_count || 0) > 0) return false;
        if (currentFilters.noCover && t.cover_url && String(t.cover_url).trim() !== '') return false;
        if (currentFilters.noRating && Number(t.rating || 0) > 0) return false;

        return true;
    });

    populateSelectFilters();
    updateDashboard(filteredTracks);
    currentPage = 0;
    loadTableData();
};

window.applyFiltersAndClose = function() {
    window.applyFilters();
    closeFilterModal();
};

window.resetAllFilters = function() {
    currentFilters = {
        search: '', album: '', genre: '', publisher: '', year: '',
        noCues: false, noCover: false, noRating: false
    };
    const sInput = document.getElementById('searchInput');
    const sMobile = document.getElementById('searchInputMobile');
    if (sInput) sInput.value = '';
    if (sMobile) sMobile.value = '';
    window.applyFilters();
};

// 4. Lógica de Ordenación por Cabeceras y Renderizado de Tabla
window.sortByColumn = function(key) {
    // Evitar ordenar por carátula
    if (key === 'cover') return;

    if (sortState.key === key) {
        sortState.direction = sortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        sortState.key = key;
        sortState.direction = 'asc';
    }
    loadTableData();
};

function sortCollection(tracks) {
    const { key, direction } = sortState;
    const modifier = direction === 'asc' ? 1 : -1;

    return tracks.sort((a, b) => {
        let valA = a[key];
        let valB = b[key];

        if (key === 'cover') {
            valA = a.cover_url ? 1 : 0;
            valB = b.cover_url ? 1 : 0;
        }

        if (valA === null || valA === undefined || valA === '') return 1;
        if (valB === null || valB === undefined || valB === '') return -1;

        if (typeof valA === 'number' && typeof valB === 'number') {
            return (valA - valB) * modifier;
        }

        return String(valA).localeCompare(String(valB), undefined, { numeric: true, sensitivity: 'base' }) * modifier;
    });
}

function loadTableData() {
    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const verDetalle = chkVerDetalle ? chkVerDetalle.checked : false;

    // Aplicar ordenación seleccionada
    sortCollection(filteredTracks);

    const totalRecords = filteredTracks.length;
    const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
    if (currentPage >= totalPages && totalPages > 0) currentPage = totalPages - 1;

    const offset = currentPage * PAGE_SIZE;
    const pageTracks = filteredTracks.slice(offset, offset + PAGE_SIZE);

    const thead = document.getElementById('tableHeader');
    const tbody = document.getElementById('tableBody');

    if (!tbody || !thead) return;

    // Construir columnas visibles según el modo (Detalle / Normal) y selector
    const activeCols = ALL_COLUMNS.filter(c => {
        if (!columnVisibility[c.key]) return false;
        if (verDetalle) {
            return !c.normalOnly;
        } else {
            return !c.detailOnly;
        }
    });

    // Renderizar cabecera (excluyendo interacción de orden en 'cover')
    let headerHtml = '<tr>';
    activeCols.forEach(col => {
        const isCover = col.key === 'cover';
        const isSorted = sortState.key === col.key;
        const arrow = isSorted ? (sortState.direction === 'asc' ? ' ▲' : ' ▼') : '';
        const alignClass = (col.key === 'year' || col.key === 'cue_count' || col.key === 'rating') ? 'col-center' : '';
        const coverClass = isCover ? 'th-cover' : '';

        const sortableAttrs = isCover ? '' : `class="sortable-th ${alignClass} ${coverClass} ${isSorted ? 'sorted-col' : ''}" onclick="sortByColumn('${col.key}')"`;
        const defaultAttrs = isCover ? `class="${alignClass} ${coverClass}"` : '';

        headerHtml += `<th ${isCover ? defaultAttrs : sortableAttrs}>
            ${col.label}${arrow}
        </th>`;
    });
    headerHtml += '</tr>';
    thead.innerHTML = headerHtml;

    // Limpiar el contenido del tbody para evitar residuos de filas de 'sin registros'
    tbody.innerHTML = '';

    if (pageTracks.length > 0) {
        const fragment = document.createDocumentFragment();

        pageTracks.forEach(row => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-track-id', row.id);

            tr.onclick = function() {
                document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected-row'));
                this.classList.add('selected-row');
                playTrack(row);
            };

            let rowHtml = '';
            activeCols.forEach(col => {
                if (col.key === 'cover') {
                    let imgTag = '<span class="cover-badge">N/A</span>';
                    if (row.cover_url) {
                        imgTag = `<img src="${row.cover_url}" class="cover-thumb" loading="lazy">`;
                    }
                    rowHtml += `<td class="td-cover">${imgTag}</td>`;
                } else if (col.key === 'filename') {
                    const cleanFilename = (row.filename || '').replace(/\.[^/.]+$/, "");
                    rowHtml += `<td title="${cleanFilename}">${cleanFilename}</td>`;
                } else {
                    let val = row[col.key];
                    if (col.key === 'rating') val = val ? `${Math.max(0, Math.min(5, val))}★` : null;
                    if (col.key === 'cue_count') val = (val !== undefined && val !== null && Number(val) > 0) ? String(val) : null;

                    const isCenter = (col.key === 'year' || col.key === 'cue_count' || col.key === 'rating');
                    const hasValue = val && String(val).trim() !== '';
                    const displayValue = hasValue ? val : '—';

                    rowHtml += `<td class="${!hasValue ? 'text-subtle' : ''} ${isCenter ? 'col-center' : ''}" title="${displayValue}">${displayValue}</td>`;
                }
            });

            tr.innerHTML = rowHtml;
            fragment.appendChild(tr);
        });

        tbody.appendChild(fragment);

    } else {
        tbody.innerHTML = `<tr><td colspan="${activeCols.length || 1}" style="text-align: center;" class="text-subtle">No se encontraron registros.</td></tr>`;
    }

    const resultsCountElem = document.getElementById('resultsCount');
    if (resultsCountElem) {
        if (totalRecords === 0) {
            resultsCountElem.textContent = '0 resultados';
        } else {
            const start = offset + 1;
            const end = offset + pageTracks.length;
            resultsCountElem.textContent = `${start} - ${end} de ${totalRecords}`;
        }
    }
}

// 5. Gestión del Selector de Columnas Visibles
window.toggleColumnPicker = function(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('columnPickerDropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
};

function renderColumnPicker() {
    const container = document.getElementById('columnPickerList');
    if (!container) return;

    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const verDetalle = chkVerDetalle ? chkVerDetalle.checked : false;

    container.innerHTML = '';
    ALL_COLUMNS.forEach(col => {
        if (verDetalle && col.normalOnly) return;
        if (!verDetalle && col.detailOnly) return;

        const item = document.createElement('label');
        item.className = 'col-picker-item no-select';

        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = !!columnVisibility[col.key];
        chk.onchange = (e) => {
            columnVisibility[col.key] = e.target.checked;
            loadTableData();
        };

        const span = document.createElement('span');
        span.textContent = col.label;

        item.appendChild(chk);
        item.appendChild(span);
        container.appendChild(item);
    });
}

// 6. Reproducción de Audio
export function playTrack(track) {
    if (!track.preview_audio_url) {
        alert("Esta canción no dispone de preescucha subida en la nube.");
        return;
    }

    currentTrackIndex = filteredTracks.findIndex(t => t.id === track.id);

    const playerBar = document.getElementById('playerBar');
    const playerCoverContainer = document.getElementById('playerCoverContainer');
    const playerTitle = document.getElementById('playerTitle');
    const playerArtist = document.getElementById('playerArtist');
    const mainAudio = document.getElementById('mainAudio');

    if (playerBar) playerBar.classList.remove('hidden');
    if (playerTitle) playerTitle.textContent = track.title || track.filename;
    if (playerArtist) playerArtist.textContent = track.artist || 'Artista Desconocido';

    if (playerCoverContainer) {
        if (track.cover_url && track.cover_url.trim() !== '') {
            playerCoverContainer.innerHTML = `<img src="${track.cover_url}" class="cover-thumb">`;
        } else {
            playerCoverContainer.innerHTML = `<span class="cover-badge">N/A</span>`;
        }
    }

    if (mainAudio) {
        mainAudio.src = track.preview_audio_url;
        mainAudio.play().then(() => updatePlayIcon(true)).catch(console.error);

        mainAudio.ontimeupdate = function() {
            const current = mainAudio.currentTime;
            const maxDuration = 20;

            if (current >= maxDuration) {
                playNextTrack();
            }

            const pct = Math.min((current / maxDuration) * 100, 100);
            const progressBar = document.getElementById('playerProgressBar');
            const timeElem = document.getElementById('playerTimeCurrent');

            if (progressBar) progressBar.style.width = `${pct}%`;
            if (timeElem) {
                const mins = Math.floor(current / 60);
                const secs = Math.floor(current % 60).toString().padStart(2, '0');
                timeElem.textContent = `${mins}:${secs}`;
            }
        };

        mainAudio.onended = function() {
            playNextTrack();
        };
    }
}

function playNextTrack() {
    if (filteredTracks.length === 0) return;

    let nextIndex;
    if (isShuffle) {
        if (filteredTracks.length === 1) {
            nextIndex = 0;
        } else {
            do {
                nextIndex = Math.floor(Math.random() * filteredTracks.length);
            } while (nextIndex === currentTrackIndex);
        }
    } else {
        nextIndex = (currentTrackIndex + 1) % filteredTracks.length;
    }

    const nextTrack = filteredTracks[nextIndex];
    if (nextTrack) {
        document.querySelectorAll('#tableBody tr').forEach(r => {
            if (r.getAttribute('data-track-id') === String(nextTrack.id)) {
                r.classList.add('selected-row');
            } else {
                r.classList.remove('selected-row');
            }
        });
        playTrack(nextTrack);
    }
}

window.toggleShuffle = function() {
    isShuffle = !isShuffle;
    const btn = document.getElementById('btnShuffle');
    if (btn) {
        if (isShuffle) {
            btn.classList.add('active-shuffle');
        } else {
            btn.classList.remove('active-shuffle');
        }
    }
};

function updatePlayIcon(isPlaying) {
    const iconPlay = document.getElementById('iconPlay');
    const iconPause = document.getElementById('iconPause');
    if (iconPlay && iconPause) {
        if (isPlaying) {
            iconPlay.classList.add('hidden');
            iconPause.classList.remove('hidden');
        } else {
            iconPlay.classList.remove('hidden');
            iconPause.classList.add('hidden');
        }
    }
}

window.togglePlayPause = function() {
    const mainAudio = document.getElementById('mainAudio');
    if (!mainAudio || !mainAudio.src) return;

    if (mainAudio.paused) {
        mainAudio.play();
        updatePlayIcon(true);
    } else {
        mainAudio.pause();
        updatePlayIcon(false);
    }
};

window.seekAudio = function(e) {
    const mainAudio = document.getElementById('mainAudio');
    if (!mainAudio || !mainAudio.src) return;

    const wrapper = e.currentTarget;
    const rect = wrapper.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;

    const targetPct = clickX / width;
    mainAudio.currentTime = targetPct * 20;
};

window.changeVolume = function(val) {
    const mainAudio = document.getElementById('mainAudio');
    if (mainAudio) mainAudio.volume = parseFloat(val);
};

let searchTimeout;
window.debouncedSearch = function() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        currentFilters.search = searchInput.value.trim();
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => window.applyFilters(), 150);
    }
};

window.syncMobileSearch = function(val) {
    currentFilters.search = val.trim();
    const sInput = document.getElementById('searchInput');
    if (sInput) sInput.value = val;
};

window.toggleVerDetalle = function() {
    renderColumnPicker();
    loadTableData();
};
window.changePage = function(delta) { currentPage += delta; loadTableData(); };

window.switchView = function(view) {
    const isDashboard = view === 'dashboard';
    const dashView = document.getElementById('dashboardView');
    const tblView = document.getElementById('tableView');
    const btnDash = document.getElementById('btnDashboard');
    const btnTbl = document.getElementById('btnTable');

    if (dashView) dashView.style.display = isDashboard ? 'block' : 'none';
    if (tblView) tblView.style.display = isDashboard ? 'none' : 'block';
    if (btnDash) btnDash.style.display = isDashboard ? 'none' : 'inline-block';
    if (btnTbl) btnTbl.style.display = isDashboard ? 'inline-block' : 'none';
};

window.openFilterModal = function() {
    const sMobile = document.getElementById('searchInputMobile');
    if (sMobile) sMobile.value = currentFilters.search;
    document.getElementById('filterOverlay')?.classList.add('active');
    document.getElementById('filterModal')?.classList.add('active');
};

window.closeFilterModal = function() {
    document.getElementById('filterOverlay')?.classList.remove('active');
    document.getElementById('filterModal')?.classList.remove('active');
};