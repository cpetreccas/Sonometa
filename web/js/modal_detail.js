/**
 * Abre el modal de detalle mostrando todos los campos de la canción.
 * Reemplaza dinámicamente el contenido sin importar qué estructura tenga el HTML.
 */
export function openTrackDetailModal(trackId) {
    const track = context.allTracks.find(t => String(t.id) === String(trackId));
    if (!track) return;

    // Helper para formatear valores no informados
    const formatVal = (val, suffix = '') => {
        if (val !== undefined && val !== null && String(val).trim() !== '') {
            return `${val}${suffix}`;
        }
        return '<span style="opacity: 0.4;">Sin especificar</span>';
    };

    // Formateo para Rating en morado corporativo
    const formatRating = (val) => {
        if (val !== undefined && val !== null && Number(val) > 0) {
            const stars = `${Math.max(0, Math.min(5, Number(val)))}★`;
            return `<span style="color: var(--primary-purple, #8B5CF6); font-weight: 600;">${stars}</span>`;
        }
        return '<span style="opacity: 0.4;">Sin valoración</span>';
    };

    // 1. Asignación de datos básicos
    const headerEl = document.getElementById('modalHeaderFilename');
    if (headerEl) headerEl.textContent = track.filename || 'Detalle del Tema';

    const imgEl = document.getElementById('detailCover');
    if (imgEl) imgEl.src = track.cover_url || 'https://via.placeholder.com/300?text=No+Cover';

    const artistEl = document.getElementById('detailArtist');
    if (artistEl) artistEl.textContent = track.artist || 'Artista Desconocido';

    const titleEl = document.getElementById('detailTitle');
    if (titleEl) titleEl.textContent = track.title || track.filename || 'Título Desconocido';

    // Ocultar remixer viejo si existe
    const remixerEl = document.getElementById('detailRemixer');
    if (remixerEl) remixerEl.style.display = 'none';

    // 2. Construcción de la rejilla de metadatos completa
    const metadataHtml = `
        <div id="detailMetadataGrid" style="text-align: left; margin: 15px 0; display: grid; gap: 6px; font-size: 13px; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">
            <div><strong>Remix:</strong> ${formatVal(track.mix_artist || track.remixer)}</div>
            <div><strong>Álbum:</strong> ${formatVal(track.album)}</div>
            <div><strong>Género:</strong> ${formatVal(track.genre)}</div>
            <div><strong>Etiqueta:</strong> ${formatVal(track.publisher)}</div>
            <div><strong>Año:</strong> ${formatVal(track.year)}</div>
            <div><strong>Cues:</strong> ${formatVal(track.cue_count)}</div>
            <div><strong>Rating:</strong> ${formatRating(track.rating)}</div>
            <div><strong>Archivo:</strong> ${formatVal(track.filename)}</div>
        </div>
    `;

    // 3. Inyección en el elemento de año o directamente tras el artista
    const yearEl = document.getElementById('detailYear');
    if (yearEl) {
        yearEl.innerHTML = metadataHtml;
    } else if (artistEl && artistEl.parentNode) {
        let grid = document.getElementById('detailMetadataGrid');
        if (grid) grid.remove();
        artistEl.insertAdjacentHTML('afterend', metadataHtml);
    }

    // 4. Asignación de eventos de botones
    const playBtn = document.getElementById('btnPlayFromModal');
    if (playBtn) {
        playBtn.onclick = () => {
            if (typeof window.playTrack === 'function') window.playTrack(track);
            closeTrackDetailModal();
        };
    }

    const shareBtn = document.getElementById('btnShareFromModal');
    if (shareBtn) {
        shareBtn.onclick = () => {
            if (typeof window.shareTrackCard === 'function') window.shareTrackCard(track);
        };
    }

    // 5. Control de apertura para cualquier variante de CSS/clases
    const overlay = document.getElementById('trackDetailOverlay');
    const modal = document.getElementById('trackDetailModal');

    if (overlay) {
        overlay.classList.remove('hidden');
        overlay.classList.add('active');
        overlay.style.display = 'flex';
    }
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('active');
        modal.style.display = 'block';
    }
}

export function closeTrackDetailModal() {
    const overlay = document.getElementById('trackDetailOverlay');
    const modal = document.getElementById('trackDetailModal');

    if (overlay) {
        overlay.classList.add('hidden');
        overlay.classList.remove('active');
        overlay.style.display = 'none';
    }
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

// Vincular obligatoriamente al objeto global window
window.openTrackDetailModal = openTrackDetailModal;
window.closeTrackDetailModal = closeTrackDetailModal;