/**
 * data_loader.js - Carga exhaustiva de metadatos desde Supabase
 */

import { supabase } from './supabase.js';

/**
 * Realiza peticiones paginadas a Supabase en bloques de 1,000
 * para superar el límite por defecto de PostgREST/Supabase.
 * Retorna el array completo de todas las canciones de la tabla 'tracks'.
 *
 * @returns {Promise<Array>} Array de todos los tracks
 */
export async function fetchAllTracks() {
    let fetchedTracks = [];
    let from = 0;
    const step = 1000;
    let hasMore = true;

    while (hasMore) {
        const { data, error } = await supabase
            .from('tracks')
            .select('id, filename, artist, title, mix_artist, album, genre, publisher, year, duration, cue_count, rating, cover_url, preview_audio_url')

            .range(from, from + step - 1);

        if (error) {
            console.error('Error fetching tracks:', error);
            break;
        }

        if (data && data.length > 0) {
            fetchedTracks = fetchedTracks.concat(data);
            from += step;
            if (data.length < step) {
                hasMore = false;
            }
        } else {
            hasMore = false;
        }
    }

    return fetchedTracks;
}