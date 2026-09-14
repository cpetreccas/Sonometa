
export function shareTrack(track) {
  if (navigator.share) {
    navigator.share({
      title: `${track.title} - ${track.artist}`,
      text: `Escucha esta pista en mi colección Sonometa [${track.bpm} BPM | ${track.key}]`,
      url: `https://tu-dominio.com/track/${track.id}`
    });
  } else {
    navigator.clipboard.writeText(`https://tu-dominio.com/track/${track.id}`);
    alert("Enlace copiado al portapapeles");
  }
}