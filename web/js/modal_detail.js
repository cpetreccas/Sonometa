/**
 * Abre el modal de detalle con los datos de la canción elegida
 */
export function openTrackDetailModal(trackId) {
    const track = context.allTracks.find(t => String(t.id) === String(trackId));
    if (!track) return;

    document.getElementById('detailCover').src = track.cover_url || 'https://via.placeholder.com/300?text=No+Cover';
    document.getElementById('detailArtist').textContent = track.artist || 'Artista Desconocido';
    document.getElementById('detailTitle').textContent = track.title || track.filename || 'Título Desconocido';

    const remixerEl = document.getElementById('detailRemixer');
    if (track.mix_artist) {
        remixerEl.textContent = `Remix: ${track.mix_artist}`;
        remixerEl.style.display = 'block';
    } else {
        remixerEl.style.display = 'none';
    }

    document.getElementById('detailYear').textContent = track.year ? `Año: ${track.year}` : '';

    // Asignar evento al botón de compartir cromo
    const shareBtn = document.getElementById('btnShareFromModal');
    shareBtn.onclick = () => window.shareTrackCard(track);

    document.getElementById('trackDetailOverlay')?.classList.remove('hidden');
}

export function closeTrackDetailModal() {
    document.getElementById('trackDetailOverlay')?.classList.add('hidden');
}

window.openTrackDetailModal = openTrackDetailModal;
window.closeTrackDetailModal = closeTrackDetailModal;