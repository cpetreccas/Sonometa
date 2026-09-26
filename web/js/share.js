/**
 * share.js - Compartir pistas mediante un enlace público con vista previa
 * (Open Graph) para WhatsApp / Redes
 */

import { supabase } from './supabase.js';
import { showToast } from './filters.js';

/**
 * Crea (o reutiliza) el enlace público /t/<token> de la pista y lo comparte con el
 * menú nativo del móvil; en escritorio lo copia al portapapeles. La página y sus
 * etiquetas Open Graph las sirve netlify/functions/share.mjs.
 * @param {Object} track - Objeto con la información de la canción (necesita track.id)
 */
export async function shareTrackLink(track) {
    if (!track?.id) return;

    const { data: token, error } = await supabase.rpc('create_track_share', { p_track_id: track.id });
    if (error || !token) {
        console.error('Error creando el enlace para compartir:', error);
        showToast('No se pudo crear el enlace');
        return;
    }

    const url = `${window.location.origin}/t/${token}`;
    const title = [track.artist, track.title].filter(Boolean).join(' – ') || 'Sonometa';

    if (navigator.share) {
        try {
            await navigator.share({ title, url });
            return;
        } catch (err) {
            if (err.name === 'AbortError') return;
        }
    }

    try {
        await navigator.clipboard.writeText(url);
        showToast('Enlace copiado');
    } catch {
        window.prompt('Copia el enlace:', url);
    }
}

