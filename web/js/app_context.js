/**
 * app_context.js - Contexto global y estado de la aplicación
 * Define constantes y propiedades mutables del estado global
 */

export const PAGE_SIZE = 100;

export const ALL_COLUMNS = [
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

/**
 * Objeto de contexto mutable que contiene el estado global de la aplicación
 */
export const context = {
    // Paginación
    currentPage: 0,

    // Tracks
    allTracks: [],
    filteredTracks: [],
    currentTrackIndex: -1,
    isShuffle: false,

    // Estado de ordenación
    sortState: {
        key: 'filename',
        direction: 'asc'
    },

    // Visibilidad de columnas
    columnVisibility: {
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
    },

    // Filtros activos
    currentFilters: {
        search: '',
        album: '',
        genre: '',
        publisher: '',
        year: '',
        noCues: false,
        noCover: false,
        noRating: false
    }
};

