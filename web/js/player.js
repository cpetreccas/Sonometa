/**
 * player.js - Lógica del reproductor flotante y control de audio
 */

import { context } from './app_context.js';

/**
 * Inicia la reproducción de una canción
 * @param {Object} track - Objeto track con todos los metadatos
 */
export function playTrack(track) {
    if (!track.preview_audio_url) {
        alert("Esta canción no dispone de preescucha subida en la nube.");
        return;
    }

    context.currentTrackIndex = context.filteredTracks.findIndex(t => t.id === track.id);

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

/**
 * Reproduce la siguiente canción en la lista filtrada
 */
export function playNextTrack() {
    if (context.filteredTracks.length === 0) return;

    let nextIndex;
    if (context.isShuffle) {
        if (context.filteredTracks.length === 1) {
            nextIndex = 0;
        } else {
            do {
                nextIndex = Math.floor(Math.random() * context.filteredTracks.length);
            } while (nextIndex === context.currentTrackIndex);
        }
    } else {
        nextIndex = (context.currentTrackIndex + 1) % context.filteredTracks.length;
    }

    const nextTrack = context.filteredTracks[nextIndex];
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

/**
 * Alterna entre play/pausa
 */
export function togglePlayPause() {
    const mainAudio = document.getElementById('mainAudio');
    if (!mainAudio || !mainAudio.src) return;

    if (mainAudio.paused) {
        mainAudio.play();
        updatePlayIcon(true);
    } else {
        mainAudio.pause();
        updatePlayIcon(false);
    }
}

/**
 * Actualiza el icono de play/pausa según el estado de reproducción
 * @param {Boolean} isPlaying - True si está reproduciendo
 */
export function updatePlayIcon(isPlaying) {
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

/**
 * Alterna el modo shuffle
 */
export function toggleShuffle() {
    context.isShuffle = !context.isShuffle;
    const btn = document.getElementById('btnShuffle');
    if (btn) {
        if (context.isShuffle) {
            btn.classList.add('active-shuffle');
        } else {
            btn.classList.remove('active-shuffle');
        }
    }
}

/**
 * Busca la posición en el audio basada en click del usuario
 * @param {Event} e - Evento de click en la barra de progreso
 */
export function seekAudio(e) {
    const mainAudio = document.getElementById('mainAudio');
    if (!mainAudio || !mainAudio.src) return;

    const wrapper = e.currentTarget;
    const rect = wrapper.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const width = rect.width;

    const targetPct = clickX / width;
    mainAudio.currentTime = targetPct * 20;
}

/**
 * Cambia el volumen del audio
 * @param {String|Number} val - Valor de volumen (0-1)
 */
export function changeVolume(val) {
    const mainAudio = document.getElementById('mainAudio');
    if (mainAudio) mainAudio.volume = parseFloat(val);
}

