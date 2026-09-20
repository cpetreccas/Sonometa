/**
 * collection_view.js - Funciones relacionadas con la vista y tabla de tracks
 */

import { context, ALL_COLUMNS, PAGE_SIZE } from './app_context.js';
import { playTrack } from './player.js';

/**
 * Ordena la colección de tracks según el estado de ordenación
 */
export function sortCollection(tracks) {
    const { key, direction } = context.sortState;
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

/**
 * Ordena por una columna específica
 */
export function sortByColumn(key) {
    if (key === 'cover') return;

    if (context.sortState.key === key) {
        context.sortState.direction = context.sortState.direction === 'asc' ? 'desc' : 'asc';
    } else {
        context.sortState.key = key;
        context.sortState.direction = 'asc';
    }
    loadTableData();
}

/**
 * Carga y renderiza los datos de la tabla y las tarjetas móviles
 */
export function loadTableData() {
    sortCollection(context.filteredTracks);

    const totalRecords = context.filteredTracks.length;
    const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
    if (context.currentPage >= totalPages && totalPages > 0) context.currentPage = totalPages - 1;

    const offset = context.currentPage * PAGE_SIZE;
    const pageTracks = context.filteredTracks.slice(offset, offset + PAGE_SIZE);

    const thead = document.getElementById('tableHeader');
    const tbody = document.getElementById('tableBody');

    if (!tbody || !thead) return;

    const activeCols = ALL_COLUMNS.filter(c => context.columnVisibility[c.key]);

    let headerHtml = '<tr>';
    activeCols.forEach(col => {
        const isCover = col.key === 'cover';
        const isSorted = context.sortState.key === col.key;
        const arrow = isSorted ? (context.sortState.direction === 'asc' ? ' ▲' : ' ▼') : '';
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

    tbody.innerHTML = '';

    if (pageTracks.length > 0) {
        const fragment = document.createDocumentFragment();

        pageTracks.forEach(row => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-track-id', row.id);

            tr.onclick = function() {
                document.querySelectorAll('#tableBody tr').forEach(r => r.classList.remove('selected-row'));
                this.classList.add('selected-row');
            };

            let rowHtml = '';
            activeCols.forEach(col => {
                if (col.key === 'cover') {
                    let imgTag = '<span class="cover-badge">N/A</span>';
                    if (row.cover_url) {
                        imgTag = `<img src="${row.cover_url}" class="cover-thumb clickable-cover" loading="lazy" onclick="event.stopPropagation(); window.openTrackDetailModal('${row.id}')">`;
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

    renderMobileCards(pageTracks);

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

    updatePaginationUI(totalPages);
}

/**
 * Renderiza la vista en modo Card para pantallas móviles
 */
function renderMobileCards(tracks) {
    let cardsContainer = document.getElementById('mobileCardsContainer');
    const tableContainer = document.querySelector('.table-container');

    if (!cardsContainer && tableContainer) {
        cardsContainer = document.createElement('div');
        cardsContainer.id = 'mobileCardsContainer';
        cardsContainer.className = 'mobile-cards-container';
        tableContainer.parentNode.insertBefore(cardsContainer, tableContainer.nextSibling);
    }

    if (!cardsContainer) return;

    cardsContainer.innerHTML = '';

    if (tracks.length === 0) {
        cardsContainer.innerHTML = '<div style="text-align: center; padding: 20px;" class="text-subtle">No se encontraron registros.</div>';
        return;
    }

    const fragment = document.createDocumentFragment();

    tracks.forEach(track => {
        const card = document.createElement('div');
        card.className = 'track-card';
        card.setAttribute('data-track-id', track.id);

        card.onclick = function() {
            document.querySelectorAll('.track-card').forEach(c => c.classList.remove('selected-card'));
            this.classList.add('selected-card');
        };

        const title = track.title || (track.filename ? track.filename.replace(/\.[^/.]+$/, "") : 'Sin título');
        const artist = track.artist || 'Artista Desconocido';
        const remixer = track.mix_artist || track.remixer || '';

        let coverHtml = `<div class="card-cover-wrapper" onclick="event.stopPropagation(); window.openTrackDetailModal('${track.id}')">
            ${track.cover_url ? `<img src="${track.cover_url}" class="card-cover" loading="lazy" alt="Cover">` : '<div class="card-cover-badge">N/A</div>'}
        </div>`;

        const metaItems = [];

        if ((context.columnVisibility['mix_artist'] !== false || context.columnVisibility['remixer'] !== false) && remixer) {
            metaItems.push(`<span>${remixer}</span>`);
        }
        if (context.columnVisibility['genre'] !== false && track.genre) {
            metaItems.push(`<span>${track.genre}</span>`);
        }
        if (context.columnVisibility['year'] !== false && track.year) {
            metaItems.push(`<span>${track.year}</span>`);
        }
        if (context.columnVisibility['album'] !== false && track.album) {
            metaItems.push(`<span>${track.album}</span>`);
        }
        if (context.columnVisibility['publisher'] !== false && track.publisher) {
            metaItems.push(`<span>${track.publisher}</span>`);
        }
        if (context.columnVisibility['cue_count'] !== false && Number(track.cue_count) > 0) {
            metaItems.push(`<span>${track.cue_count} Cues</span>`);
        }
        if (context.columnVisibility['rating'] !== false && track.rating) {
            const ratingStars = `${Math.max(0, Math.min(5, track.rating))}★`;
            metaItems.push(`<span>${ratingStars}</span>`);
        }

        const metaRowHtml = metaItems.length > 0
            ? `<div class="card-meta-row">${metaItems.join(' • ')}</div>`
            : '';

        card.innerHTML = `
            ${coverHtml}
            <div class="card-info" onclick="event.stopPropagation(); window.openTrackDetailModal('${track.id}')">
                <div class="card-title">${title}</div>
                <div class="card-artist">${artist}</div>
                ${metaRowHtml}
            </div>
            <div class="card-actions">
                <button class="btn-card-action" aria-label="Reproducir" onclick="event.stopPropagation(); window.playTrackFromCard('${track.id}')">
                    ▶
                </button>
            </div>
        `;

        fragment.appendChild(card);
    });

    cardsContainer.appendChild(fragment);
}

window.playTrackFromCard = function(trackId) {
    const track = context.allTracks.find(t => String(t.id) === String(trackId));
    if (track) {
        playTrack(track);
    }
};

export function updatePaginationUI(totalPages) {
    const paginationControls = document.getElementById('paginationControls');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const pageInfo = document.getElementById('pageInfo');

    if (!paginationControls) return;

    if (totalPages > 1) {
        paginationControls.style.display = 'flex';
        if (pageInfo) pageInfo.textContent = `Página ${context.currentPage + 1} de ${totalPages}`;
        if (prevBtn) prevBtn.disabled = context.currentPage === 0;
        if (nextBtn) nextBtn.disabled = context.currentPage >= totalPages - 1;
    } else {
        paginationControls.style.display = 'none';
    }
}

export function toggleColumnPicker(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('columnPickerDropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

export function renderColumnPicker() {
    const container = document.getElementById('columnPickerList');
    if (!container) return;

    container.innerHTML = '';
    const excludedKeys = ['cover', 'filename', 'artist', 'title', 'mix_artist'];

    ALL_COLUMNS.forEach(col => {
        if (excludedKeys.includes(col.key)) return;

        const item = document.createElement('label');
        item.className = 'col-picker-item no-select';

        const chk = document.createElement('input');
        chk.type = 'checkbox';
        chk.checked = !!context.columnVisibility[col.key];
        chk.onchange = (e) => {
            context.columnVisibility[col.key] = e.target.checked;
            loadTableData();
        };

        const span = document.createElement('span');
        span.textContent = col.label;

        item.appendChild(chk);
        item.appendChild(span);
        container.appendChild(item);
    });
}

export function changePage(delta) {
    context.currentPage += delta;
    loadTableData();
}

/**
 * Abre el modal de detalle mostrando el Remix debajo del autor y la rejilla de metadatos.
 */
export function openTrackDetailModal(trackId) {
    const track = context.allTracks.find(t => String(t.id) === String(trackId));
    if (!track) return;

    const formatVal = (val, suffix = '') => {
        if (val !== undefined && val !== null && String(val).trim() !== '') {
            return `${val}${suffix}`;
        }
        return '<span style="opacity: 0.4;">Sin especificar</span>';
    };

    const formatRating = (val) => {
        if (val !== undefined && val !== null && Number(val) > 0) {
            return `<span style="color: var(--primary-purple, #8B5CF6); font-weight: 600;">${Math.max(0, Math.min(5, Number(val)))}★</span>`;
        }
        return '<span style="opacity: 0.4;">Sin valoración</span>';
    };

    // 1. Cabecera, carátula, título y artista
    const modalHeaderFilename = document.getElementById('modalHeaderFilename');
    if (modalHeaderFilename) {
        modalHeaderFilename.textContent = track.filename || 'Detalle del Tema';
        modalHeaderFilename.title = track.filename || '';
    }

    const img = document.getElementById('detailCover');
    if (img) img.src = track.cover_url || 'https://via.placeholder.com/300?text=No+Cover';

    const artist = document.getElementById('detailArtist');
    if (artist) artist.textContent = track.artist || 'Artista Desconocido';

    const title = document.getElementById('detailTitle');
    if (title) title.textContent = track.title || track.filename || 'Título Desconocido';

    // 2. Mostrar el Remix justo debajo del autor (Centrado y Morado)
    const remixerEl = document.getElementById('detailRemixer');
    const mixVal = track.mix_artist || track.remixer;
    if (remixerEl) {
        if (mixVal && String(mixVal).trim() !== '') {
            remixerEl.textContent = `Remix: ${mixVal}`;
            remixerEl.style.display = 'block';
            remixerEl.style.color = 'var(--primary-purple, #8B5CF6)';
            remixerEl.style.textAlign = 'center';
            remixerEl.style.fontWeight = '600';
            remixerEl.style.margin = '0 0 8px 0';
        } else {
            remixerEl.style.display = 'none';
        }
    }

    // 3. Grid con el resto de metadatos de la canción
    const yearEl = document.getElementById('detailYear');
    if (yearEl) {
        yearEl.innerHTML = `
            <div id="detailMetadataGrid" style="text-align: left; margin: 15px 0; display: grid; gap: 6px; font-size: 13px; background: rgba(0,0,0,0.25); padding: 12px; border-radius: 8px;">
                <div><strong>Álbum:</strong> ${formatVal(track.album)}</div>
                <div><strong>Género:</strong> ${formatVal(track.genre)}</div>
                <div><strong>Etiqueta:</strong> ${formatVal(track.publisher)}</div>
                <div><strong>Año:</strong> ${formatVal(track.year)}</div>
                <div><strong>Cues:</strong> ${formatVal(track.cue_count)}</div>
                <div><strong>Rating:</strong> ${formatRating(track.rating)}</div>
                <div><strong>Archivo:</strong> ${formatVal(track.filename)}</div>
            </div>
        `;
    }

    // 4. Botones de acción
    const playBtn = document.getElementById('btnPlayFromModal');
    if (playBtn) {
        playBtn.onclick = () => {
            playTrack(track);
            closeTrackDetailModal();
        };
    }

    const shareBtn = document.getElementById('btnShareFromModal');
    if (shareBtn) {
        shareBtn.onclick = () => {
            if (typeof window.shareTrackCard === 'function') {
                window.shareTrackCard(track);
            }
        };
    }

    // 5. Desplegar overlay
    document.getElementById('trackDetailOverlay')?.classList.add('active');
    document.getElementById('trackDetailModal')?.classList.add('active');
}

/**
 * Cierra el modal de detalle
 */
export function closeTrackDetailModal() {
    document.getElementById('trackDetailOverlay')?.classList.remove('active');
    document.getElementById('trackDetailModal')?.classList.remove('active');
}

// Exposición al ámbito global
window.openTrackDetailModal = openTrackDetailModal;
window.closeTrackDetailModal = closeTrackDetailModal;