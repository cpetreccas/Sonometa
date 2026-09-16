/**
 * share.js - Generación de Cromos visuales (PNG) para compartir por WhatsApp / Redes
 */

/**
 * Genera un cromo visual en memoria a partir de los datos de un track
 * @param {Object} track - Objeto con la información de la canción
 */
export async function shareTrackCard(track) {
    if (!track) return;

    // 1. Crear contenedor temporal para la plantilla del Cromo
    const cardContainer = document.createElement('div');
    cardContainer.id = 'tempTrackCard';
    cardContainer.style.cssText = `
        position: fixed;
        left: -9999px;
        top: -9999px;
        width: 600px;
        padding: 32px;
        background: #18181B;
        color: #FFFFFF;
        font-family: system-ui, -apple-system, sans-serif;
        border-radius: 16px;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
        display: flex;
        flex-direction: column;
        gap: 20px;
        box-sizing: border-box;
    `;

    const coverUrl = track.cover_url || track.cover_blob || 'https://via.placeholder.com/300?text=No+Cover';
    const stars = track.rating ? '★'.repeat(Number(track.rating)) : 'Sin valoración';

    cardContainer.innerHTML = `
        <div style="position: relative; display: flex; gap: 24px; align-items: center; min-height: 180px;">

            <!-- BRANDING DISCRETO EN LA ESQUINA SUPERIOR DERECHA -->
            <div style="position: absolute; top: 0; right: 0; display: flex; align-items: center; gap: 6px; opacity: 0.85;">
                <svg viewBox="0 0 81 78" fill="none" xmlns="http://www.w3.org/2000/svg" style="width: 18px; height: 18px; flex-shrink: 0;">
                    <path d="M27.5926 12.3934C29.8925 9.77124 33.253 8.27092 36.7919 8.27092H56.6772C66.2446 8.27092 74 16.0263 74 25.5937V52.4063C74 61.9737 66.2446 69.7291 56.6772 69.7291H36.7919C33.253 69.7291 29.8925 68.2288 27.5926 65.6066L8.76406 44.1332C6.11281 41.1098 6.11281 36.8902 8.76406 33.8668L27.5926 12.3934Z" stroke="url(#card_grad)" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="22.5" cy="39" r="4.5" fill="url(#card_grad)"/>
                    <defs>
                        <linearGradient id="card_grad" x1="74" y1="8.27092" x2="7" y2="69.7291" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stop-color="#6366F1"/>
                            <stop offset="50%" stop-color="#8B5CF6"/>
                            <stop offset="100%" stop-color="#EC4899"/>
                        </linearGradient>
                    </defs>
                </svg>
                <div style="display: flex; align-items: baseline; gap: 4px;">
                    <span style="font-size: 13px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.2px;">Sonometa</span>
                    <span style="font-size: 10px; font-weight: 600; color: #8B5CF6;">Cloud</span>
                </div>
            </div>

            <img src="${coverUrl}" crossOrigin="anonymous" style="width: 180px; height: 180px; border-radius: 12px; object-fit: cover; flex-shrink: 0; box-shadow: 0 8px 16px rgba(0,0,0,0.4);" />

            <div style="display: flex; flex-direction: column; gap: 6px; overflow: hidden; width: 100%; padding-right: 120px; justify-content: center;">
                <h2 style="margin: 0; font-size: 24px; font-weight: 700; color: #FFFFFF; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${track.title || track.filename || 'Título Desconocido'}</h2>
                <p style="margin: 0; font-size: 17px; color: #A1A1AA; font-weight: 500;">${track.artist || 'Artista Desconocido'}</p>
                ${track.mix_artist ? `<p style="margin: 0; font-size: 13px; color: #6366F1;">Remix: ${track.mix_artist}</p>` : ''}
            </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; background: #24242A; padding: 16px; border-radius: 10px; font-size: 13px;">
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Álbum:</strong> <span style="color: #FFF;">${track.album || '-'}</span></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Género:</strong> <span style="color: #FFF;">${track.genre || '-'}</span></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Etiqueta:</strong> <span style="color: #FFF;">${track.publisher || '-'}</span></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Año:</strong> <span style="color: #FFF;">${track.year || '-'}</span></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Cue Points:</strong> <span style="color: #FFF;">${track.cue_count || 0}</span></div>
            <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap;"><strong style="color: #A1A1AA;">Rating:</strong> <span style="color: #F59E0B;">${stars}</span></div>
        </div>
    `;

    document.body.appendChild(cardContainer);

    try {
        // 2. Renderizar el DOM a Canvas mediante html2canvas
        const canvas = await html2canvas(cardContainer, {
            useCORS: true,
            scale: 2,
            backgroundColor: '#18181B'
        });

        // 3. Convertir el Canvas a Blob (PNG)
        canvas.toBlob(async (blob) => {
            if (!blob) return;

            const file = new File([blob], `cromo-${track.id || 'track'}.png`, { type: 'image/png' });

            // 4. Compartir por Web Share API (Móviles / WhatsApp)
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                try {
                    await navigator.share({
                        files: [file],
                        title: `${track.artist} - ${track.title}`,
                        text: `Mira este tema de mi colección Sonometa: ${track.artist} - ${track.title}`
                    });
                } catch (err) {
                    if (err.name !== 'AbortError') console.error('Error compartiendo:', err);
                }
            } else {
                // Fallback para escritorio: Descargar directamente el archivo PNG
                const link = document.createElement('a');
                link.download = `cromo-${track.title || 'track'}.png`;
                link.href = URL.createObjectURL(blob);
                link.click();
            }
        }, 'image/png');

    } catch (err) {
        console.error('Error generando cromo:', err);
    } finally {
        // Limpiar el DOM eliminando la plantilla ocultada
        document.body.removeChild(cardContainer);
    }
}