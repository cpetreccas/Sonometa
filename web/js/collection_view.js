/**
 * collection_view.js - Funciones relacionadas con la vista y tabla de tracks
 */

import { context, ALL_COLUMNS, PAGE_SIZE } from './app_context.js';
import { playTrack } from './player.js';

/**
 * Ordena la colección de tracks según el estado de ordenación
 * @param {Array} tracks - Array de tracks a ordenar
 * @returns {Array} Array ordenado
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
 * Ordena por una columna específica, alternando ascendente/descendente
 * @param {String} key - Clave de la columna
 */
export function sortByColumn(key) {
    // Evitar ordenar por carátula
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
 * Carga y renderiza los datos de la tabla con paginación
 */
export function loadTableData() {
    const chkVerDetalle = document.getElementById('chkVerDetalle');
    const verDetalle = chkVerDetalle ? chkVerDetalle.checked : false;

    // Aplicar ordenación seleccionada
    sortCollection(context.filteredTracks);

    const totalRecords = context.filteredTracks.length;
    const totalPages = Math.ceil(totalRecords / PAGE_SIZE);
    if (context.currentPage >= totalPages && totalPages > 0) context.currentPage = totalPages - 1;

    const offset = context.currentPage * PAGE_SIZE;
    const pageTracks = context.filteredTracks.slice(offset, offset + PAGE_SIZE);

    const thead = document.getElementById('tableHeader');
    const tbody = document.getElementById('tableBody');

    if (!tbody || !thead) return;

    // Construir columnas visibles según el modo (Detalle / Normal) y selector
    const activeCols = ALL_COLUMNS.filter(c => {
        if (!context.columnVisibility[c.key]) return false;
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

    // Limpiar el contenido del tbody para evitar residuos de filas de 'sin registros'
    tbody.innerHTML = '';

    if (pageTracks.length > 0) {
        const fragment = document.createDocumentFragment();

        pageTracks.forEach(row => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-track-id', row.id);

            // Seleccionar fila sin disparar la reproducción
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

    // Actualizar y mostrar/ocultar el control de paginación
    updatePaginationUI(totalPages);
}

/**
 * Actualiza la interfaz de paginación
 * @param {Number} totalPages - Total de páginas
 */
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

/**
 * Alterna la visibilidad del selector de columnas
 * @param {Event} e - Evento del click
 */
export function toggleColumnPicker(e) {
    e.stopPropagation();
    const dropdown = document.getElementById('columnPickerDropdown');
    if (dropdown) dropdown.classList.toggle('hidden');
}

/**
 * Renderiza el selector dinámico de visibilidad de columnas
 */
export function renderColumnPicker() {
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

/**
 * Alterna entre vista detalle/normal
 */
export function toggleVerDetalle() {
    renderColumnPicker();
    loadTableData();
}

/**
 * Cambia de página
 * @param {Number} delta - Delta a sumar/restar (1 o -1)
 */
export function changePage(delta) {
    context.currentPage += delta;
    loadTableData();
}

/**
 * Abre el modal de detalle con los datos de la canción elegida
 * @param {String|Number} trackId - ID del track a mostrar
 */
export function openTrackDetailModal(trackId) {
    const track = context.allTracks.find(t => String(t.id) === String(trackId));
    if (!track) return;

    // Actualizar la cabecera con el filename
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

    const remixerEl = document.getElementById('detailRemixer');
    if (remixerEl) {
        if (track.mix_artist) {
            remixerEl.textContent = `Remix: ${track.mix_artist}`;
            remixerEl.style.display = 'block';
        } else {
            remixerEl.style.display = 'none';
        }
    }

    const yearEl = document.getElementById('detailYear');
    if (yearEl) yearEl.textContent = track.year ? `Año: ${track.year}` : '';

    // Asignar evento al botón de Reproducir
    const playBtn = document.getElementById('btnPlayFromModal');
    if (playBtn) {
        playBtn.onclick = () => {
            playTrack(track);
            closeTrackDetailModal();
        };
    }

    // Asignar evento al botón de Compartir Cromo
    const shareBtn = document.getElementById('btnShareFromModal');
    if (shareBtn) {
        shareBtn.onclick = () => {
            if (typeof window.shareTrackCard === 'function') {
                window.shareTrackCard(track);
            }
        };
    }

    document.getElementById('trackDetailOverlay')?.classList.add('active');
    document.getElementById('trackDetailModal')?.classList.add('active');
}

/**
 * Cierra el modal de detalle de canción
 */
export function closeTrackDetailModal() {
    document.getElementById('trackDetailOverlay')?.classList.remove('active');
    document.getElementById('trackDetailModal')?.classList.remove('active');
}

// Exposición global
window.openTrackDetailModal = openTrackDetailModal;
window.closeTrackDetailModal = closeTrackDetailModal;