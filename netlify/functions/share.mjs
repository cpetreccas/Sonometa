/**
 * share.mjs - Página pública de una pista compartida: /t/<token>
 *
 * WhatsApp, Instagram, Telegram, etc. no ejecutan JavaScript al generar la
 * vista previa de un enlace: las etiquetas Open Graph tienen que venir ya en el
 * HTML. Esta función consulta la pista con get_shared_track() (supabase/shared_tracks.sql)
 * y devuelve una tarjeta ligera con esas etiquetas.
 *
 * La clave anon es pública (es la misma que usa la PWA en web/js/supabase.js);
 * se puede sobrescribir con las variables de entorno SUPABASE_URL / SUPABASE_ANON_KEY.
 */

const SUPABASE_URL = process.env.SUPABASE_URL || 'https://iwgpfqnyhjewuufrqali.supabase.co';
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml3Z3BmcW55aGpld3V1ZnJxYWxpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODkzMjcxNzAsImV4cCI6MjEwNDkwMzE3MH0.3cHCKKVaqrU2-NhKHFzNU7-SuFRIjWhv3h0by8hQOdE';

const TOKEN_PATTERN = /^[0-9a-f]{18}$/;

export const config = { path: '/t/:token' };

export default async (req, context) => {
    const origin = new URL(req.url).origin;
    const token = String(context.params?.token || '').toLowerCase();

    if (!TOKEN_PATTERN.test(token)) {
        return htmlResponse(renderNotFound(origin), 404);
    }

    let track = null;
    try {
        const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/get_shared_track`, {
            method: 'POST',
            headers: {
                apikey: SUPABASE_ANON_KEY,
                Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ p_token: token }),
        });
        if (!res.ok) throw new Error(`Supabase ${res.status}`);
        const rows = await res.json();
        track = Array.isArray(rows) ? rows[0] : null;
    } catch (err) {
        console.error('share: error consultando la pista', err);
        return htmlResponse(renderNotFound(origin), 502, 'no-store');
    }

    if (!track) {
        return htmlResponse(renderNotFound(origin), 404);
    }
    return htmlResponse(renderTrack(track, `${origin}/t/${token}`, origin));
};

function htmlResponse(html, status = 200, cacheControl = 'public, max-age=300') {
    return new Response(html, {
        status,
        headers: {
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': cacheControl,
            'X-Robots-Tag': 'noindex',
        },
    });
}

function esc(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function clean(value) {
    const text = String(value ?? '').trim();
    return text && text !== '0' ? text : '';
}

/** "3:45", "225" (segundos) o "00:03:45" -> "3:45". */
function formatDuration(value) {
    const raw = clean(value);
    if (!raw) return '';
    if (/^\d+(\.\d+)?$/.test(raw)) {
        const total = Math.round(Number(raw));
        return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
    }
    return raw.replace(/^00:/, '').replace(/^0(\d:)/, '$1');
}

const ISOTYPE_SVG = `
<svg class="brand-icon" viewBox="0 0 81 78" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M27.5926 12.3934C29.8925 9.77124 33.253 8.27092 36.7919 8.27092H56.6772C66.2446 8.27092 74 16.0263 74 25.5937V52.4063C74 61.9737 66.2446 69.7291 56.6772 69.7291H36.7919C33.253 69.7291 29.8925 68.2288 27.5926 65.6066L8.76406 44.1332C6.11281 41.1098 6.11281 36.8902 8.76406 33.8668L27.5926 12.3934Z" stroke="url(#sg)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="22.5" cy="39" r="4.5" fill="url(#sg)"/>
  <defs>
    <linearGradient id="sg" x1="74" y1="8.27" x2="7" y2="69.73" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#6366F1"/><stop offset="50%" stop-color="#8B5CF6"/><stop offset="100%" stop-color="#EC4899"/>
    </linearGradient>
  </defs>
</svg>`;

const STYLES = `
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center;
  padding: 24px 16px; background: #1A1A1E; color: #F4F4F5;
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
}
.card {
  width: 100%; max-width: 420px; background: #24242A; border: 1px solid #363640;
  border-radius: 16px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.35);
}
.cover {
  display: block; width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 12px;
  background: #2D2D35;
}
.cover-empty { display: flex; align-items: center; justify-content: center; }
.cover-empty .brand-icon { width: 30%; height: auto; opacity: 0.5; }
h1 { margin: 18px 0 4px; font-size: 22px; line-height: 1.25; font-weight: 700; overflow-wrap: anywhere; }
.artist { margin: 0; font-size: 16px; color: #B3B3AD; font-weight: 500; overflow-wrap: anywhere; }
.remix { margin: 6px 0 0; font-size: 13px; color: #A78BFA; }
dl {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px;
  margin: 18px 0 0; padding: 14px 16px; background: #1F1F24; border-radius: 10px;
}
dt { font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #8E8E96; }
dd { margin: 2px 0 0; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brand {
  display: flex; align-items: center; justify-content: center; gap: 8px;
  margin-top: 18px; font-size: 12px; color: #8E8E96;
}
.brand .brand-icon { width: 16px; height: 16px; }
.brand strong { color: #F4F4F5; font-weight: 700; }
.brand span { color: #8B5CF6; font-weight: 600; }
.empty { text-align: center; }
.empty .brand-icon { width: 56px; height: 56px; }
.empty p { color: #B3B3AD; margin: 8px 0 0; }
`;

function page({ title, head, body }) {
    return `<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#1A1A1E">
<title>${esc(title)}</title>
${head}
<style>${STYLES}</style>
</head>
<body>
${body}
</body>
</html>`;
}

function renderTrack(track, pageUrl, origin) {
    const title = clean(track.title) || 'Tema sin título';
    const artist = clean(track.artist) || 'Artista desconocido';
    const remix = clean(track.mix_artist);
    const details = [
        ['Álbum', clean(track.album)],
        ['Sello', clean(track.publisher)],
        ['Género', clean(track.genre)],
        ['Año', clean(track.year)],
        ['Duración', formatDuration(track.duration)],
    ].filter(([, value]) => value);

    const coverUrl = clean(track.cover_url);
    const imageUrl = coverUrl || `${origin}/assets/icono_iphone_512.png`;
    const ogTitle = `${artist} – ${title}`;
    const ogDescription = [remix && `Remix: ${remix}`, clean(track.publisher), clean(track.year), clean(track.genre)]
        .filter(Boolean).join(' · ') || 'Compartido desde Sonometa';

    const head = `
<meta name="description" content="${esc(ogDescription)}">
<meta property="og:type" content="music.song">
<meta property="og:site_name" content="Sonometa">
<meta property="og:locale" content="es_ES">
<meta property="og:url" content="${esc(pageUrl)}">
<meta property="og:title" content="${esc(ogTitle)}">
<meta property="og:description" content="${esc(ogDescription)}">
<meta property="og:image" content="${esc(imageUrl)}">
<meta property="og:image:alt" content="${esc(coverUrl ? `Portada de ${ogTitle}` : 'Sonometa')}">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="${esc(ogTitle)}">
<meta name="twitter:description" content="${esc(ogDescription)}">
<meta name="twitter:image" content="${esc(imageUrl)}">
<link rel="icon" href="/assets/logo.webp">`;

    const cover = coverUrl
        ? `<img class="cover" src="${esc(coverUrl)}" alt="Portada de ${esc(ogTitle)}" width="600" height="600">`
        : `<div class="cover cover-empty" role="img" aria-label="Sin portada">${ISOTYPE_SVG}</div>`;

    const grid = details.length
        ? `<dl>${details.map(([label, value]) => `<div><dt>${label}</dt><dd title="${esc(value)}">${esc(value)}</dd></div>`).join('')}</dl>`
        : '';

    const body = `
<main class="card">
  ${cover}
  <h1>${esc(title)}</h1>
  <p class="artist">${esc(artist)}</p>
  ${remix ? `<p class="remix">Remix: ${esc(remix)}</p>` : ''}
  ${grid}
  <div class="brand">${ISOTYPE_SVG}<strong>Sonometa</strong><span>Cloud</span></div>
</main>`;

    return page({ title: `${ogTitle} · Sonometa`, head, body });
}

function renderNotFound(origin) {
    const head = `
<meta property="og:site_name" content="Sonometa">
<meta property="og:title" content="Enlace no disponible">
<meta property="og:image" content="${esc(`${origin}/assets/icono_iphone_512.png`)}">
<link rel="icon" href="/assets/logo.webp">`;
    const body = `
<main class="card empty">
  ${ISOTYPE_SVG}
  <h1>Enlace no disponible</h1>
  <p>Este tema ya no se comparte o el enlace es incorrecto.</p>
</main>`;
    return page({ title: 'Enlace no disponible · Sonometa', head, body });
}
