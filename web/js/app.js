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

let currentFilters = {
    search: '',
    album: '',
    genre: '',
    publisher: '',
    year: ''
};

// 1. Inicialización PWA & Auth
window.addEventListener('DOMContentLoaded', async () => {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('./sw.js').catch(console.error);
    }

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

        // Poblar desplegables de filtro inicialmente con los datos del catálogo
        populateFilterDropdowns(allTracks);

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
}

function handleFilterChange(key, value) {
    currentFilters[key] = value;
    populateSelectFilters();
    if (window.innerWidth >= 768) {
        window.applyFilters();
    }
}

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
        return true;
    });

    populateSelectFilters();
    updateDashboard(filteredTracks); // Recálculo local instantáneo
    currentPage = 0;
    loadTableData();
};

window.applyFiltersAndClose = function() {
    window.applyFilters();
    closeFilterModal();
};

window.resetAllFilters = function() {
    currentFilters = { search: '', album: '', genre: '', publisher: '', year: '' };
    const sInput = document.getElementById('searchInput');
    const sMobile = document.getElementById('searchInputMobile');
    if (sInput) sInput.value = '';
    if (sMobile) sMobile.value = '';
    window.applyFilters();
};

function loadTableData() {
    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const verDetalle = chkVerDetalle ? chkVerDetalle.checked : false;

    if (verDetalle) {
        filteredTracks.sort((a, b) => {
            const artistA = a.artist || '';
            const artistB = b.artist || '';
            const cmp = artistA.localeCompare(artistB);
            if (cmp !== 0) return cmp;
            return (a.title || '').localeCompare(b.title || '');
        });
    } else {
        filteredTracks.sort((a, b) => (a.filename || '').localeCompare(b.filename || ''));
    }

    const totalRecords = filteredTracks.length;
    const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
    if (currentPage >= totalPages && totalPages > 0) currentPage = totalPages - 1;

    const offset = currentPage * PAGE_SIZE;
    const pageTracks = filteredTracks.slice(offset, offset + PAGE_SIZE);

    const thead = document.getElementById('tableHeader');
    const tbody = document.getElementById('tableBody');

    if (!tbody) return;

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

    const existingRows = new Map();
    Array.from(tbody.children).forEach(row => {
        const id = row.getAttribute('data-track-id');
        if (id) existingRows.set(id, row);
    });

    if (pageTracks.length > 0) {
        const fragment = document.createDocumentFragment();

        pageTracks.forEach(row => {
            let tr = existingRows.get(String(row.id));

            if (tr) {
                existingRows.delete(String(row.id));
            } else {
                tr = document.createElement('tr');
                tr.setAttribute('data-track-id', row.id);
            }

            tr.onclick = function() {
                document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected-row'));
                this.classList.add('selected-row');
                playTrack(row);
            };

            let imgTag = '<span class="cover-badge">N/A</span>';
            if (row.cover_url) {
                imgTag = `<img src="${row.cover_url}" class="cover-thumb" loading="lazy">`;
            }

            const cleanFilename = (row.filename || '').replace(/\.[^/.]+$/, "");
            const ratingVal = `${Math.max(0, Math.min(5, row.rating || 0))}★`;
            const cuesVal = (row.cue_count !== undefined && row.cue_count !== null && Number(row.cue_count) > 0)
                ? String(row.cue_count)
                : '-';

            const renderCell = (val, isCenter = false) => {
                const hasValue = val && String(val).trim() !== '';
                const displayValue = hasValue ? val : '—';
                return `<td class="${!hasValue ? 'text-subtle' : ''} ${isCenter ? 'col-center' : ''}" title="${displayValue}">${displayValue}</td>`;
            };

            if (verDetalle) {
                tr.innerHTML = `
                    <td class="td-cover">${imgTag}</td>
                    ${renderCell(row.artist)}
                    ${renderCell(row.title)}
                    ${renderCell(row.mix_artist)}
                    ${renderCell(row.album)}
                    ${renderCell(row.genre)}
                    ${renderCell(row.publisher)}
                    ${renderCell(row.year, true)}
                    ${renderCell(cuesVal, true)}
                    ${renderCell(ratingVal, true)}
                `;
            } else {
                tr.innerHTML = `
                    <td class="td-cover">${imgTag}</td>
                    <td title="${cleanFilename}">${cleanFilename}</td>
                `;
            }

            fragment.appendChild(tr);
        });

        existingRows.forEach(row => row.remove());
        tbody.appendChild(fragment);

    } else {
        tbody.innerHTML = `<tr><td colspan="${verDetalle ? 10 : 2}" style="text-align: center;" class="text-subtle">No se encontraron registros.</td></tr>`;
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
            const maxDuration = 20; // Límite de preescucha

            if (current >= maxDuration) {
                playNextTrack();
            }

            // Actualizar barra y tiempo
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
        // Resaltar en la tabla si la fila existe visible
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

// Helpers globales para interacción
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
    mainAudio.currentTime = targetPct * 20; // Escala sobre el máximo de 20s
};

window.changeVolume = function(val) {
    const mainAudio = document.getElementById('mainAudio');
    if (mainAudio) mainAudio.volume = parseFloat(val);
};

// 4. Modales y Helpers expuestos
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

window.toggleVerDetalle = function() { loadTableData(); };
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