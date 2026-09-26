/**
 * data_loader.js - Carga exhaustiva de metadatos desde Supabase
 */

import { supabase } from './supabase.js';

const PAGE_STEP = 1000;

/**
 * Lee todas las filas de una tabla en bloques de 1,000 para superar el límite
 * por defecto de PostgREST/Supabase. Si un bloque falla, devuelve lo leído hasta ahí.
 *
 * @param {string} table - Tabla de Supabase
 * @param {string} columns - Columnas del select
 * @returns {Promise<Array>} Filas de la tabla
 */
async function fetchAllRows(table, columns) {
    let rows = [];
    let from = 0;

    while (true) {
        const { data, error } = await supabase
            .from(table)
            .select(columns)
            .range(from, from + PAGE_STEP - 1);

        if (error) {
            console.error(`Error fetching ${table}:`, error);
            break;
        }
        if (!data || data.length === 0) break;

        rows = rows.concat(data);
        if (data.length < PAGE_STEP) break;
        from += PAGE_STEP;
    }

    return rows;
}

/**
 * Retorna el array completo de todas las canciones de la tabla 'tracks'.
 * @returns {Promise<Array>} Array de todos los tracks
 */
export function fetchAllTracks() {
    return fetchAllRows(
        'tracks',
        'id, filepath_local, filename, artist, title, mix_artist, album, genre, publisher, year, duration, cue_count, rating, cover_url, preview_audio_url'
    );
}

/**
 * Resultados de la auditoría técnica ('Evaluar calidad' en escritorio), tabla 'audio_health'.
 * Se enlazan con 'tracks' por filepath_local.
 * @returns {Promise<Array>} Filas de audio_health
 */
export function fetchAllHealth() {
    return fetchAllRows(
        'audio_health',
        'filepath_local, integrity_status, has_clipping, lufs_integrated, bitrate_fake'
    );
}
