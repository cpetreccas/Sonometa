import io
import os
import sys
import logging
from typing import Optional, Tuple
from PIL import Image

logger = logging.getLogger("Sonometa")

def setup_ffmpeg_path():
    """Detecta la carpeta bin/ ubicada en la raíz del proyecto y la añade al PATH."""
    if getattr(sys, 'frozen', False):
        # Si se ejecuta empaquetado como executable (.exe)
        base_dir = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        # En desarrollo: estamos en src/preview_generator.py, subimos un nivel a la raíz (..)
        src_dir = os.path.dirname(os.path.abspath(__file__))
        base_dir = os.path.abspath(os.path.join(src_dir, '..'))

    ffmpeg_dir = os.path.join(base_dir, 'bin')

    if os.path.exists(ffmpeg_dir):
        # Añadir al PATH del proceso actual
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

        # Configurar pydub si está instalado
        try:
            from pydub import AudioSegment
            AudioSegment.converter = os.path.join(ffmpeg_dir, "ffmpeg.exe")
            AudioSegment.ffprobe = os.path.join(ffmpeg_dir, "ffprobe.exe")
        except ImportError:
            pass

# Ejecutar automáticamente al importar el módulo
setup_ffmpeg_path()


class MediaProcessor:
    """Extrae portadas e imágenes y genera previews cortas de audio para la nube."""

    # Tipo de imagen "portada frontal" (ID3 APIC / FLAC METADATA_BLOCK_PICTURE).
    FRONT_COVER_TYPE = 3

    @staticmethod
    def _find_embedded_cover(audio) -> Optional[bytes]:
        """Bytes de la carátula incrustada según el formato, o None. Si hay varias
        imágenes, prefiere la portada frontal.

        Cada formato la guarda en un sitio distinto:
          - FLAC: bloque de imágenes propio (audio.pictures), NO en las etiquetas.
          - OGG Vorbis/Opus: etiqueta METADATA_BLOCK_PICTURE (base64 de un bloque FLAC).
          - MP3/WAV/AIFF: frames ID3 APIC.
          - M4A/AAC: átomo covr.
          - WMA: atributo WM/Picture.
        """
        from mutagen.flac import Picture

        def _pick(pictures):
            pictures = [p for p in pictures if getattr(p, "data", None)]
            if not pictures:
                return None
            front = [p for p in pictures if getattr(p, "type", None) == MediaProcessor.FRONT_COVER_TYPE]
            return (front or pictures)[0].data

        # FLAC
        data = _pick(getattr(audio, "pictures", None) or [])
        if data:
            return data

        tags = getattr(audio, "tags", None)
        if not tags:
            return None

        # OGG Vorbis / Opus
        if hasattr(tags, "get") and not hasattr(tags, "getall"):
            import base64
            blocks = []
            for raw in tags.get("metadata_block_picture", []) or []:
                try:
                    blocks.append(Picture(base64.b64decode(raw)))
                except Exception:
                    continue
            data = _pick(blocks)
            if data:
                return data

        # MP3 / WAV / AIFF (ID3)
        if hasattr(tags, "getall"):
            data = _pick(tags.getall("APIC"))
            if data:
                return data

        # M4A / AAC
        try:
            covers = tags.get("covr") if hasattr(tags, "get") else None
        except Exception:
            covers = None
        if covers:
            return bytes(covers[0])

        # WMA
        try:
            wm_pictures = tags.get("WM/Picture") if hasattr(tags, "get") else None
        except Exception:
            wm_pictures = None
        if wm_pictures:
            raw = wm_pictures[0].value
            # ASF WM/Picture: tipo (1 byte) + tamaño (4) + mime y descripción en
            # UTF-16 terminados en \0\0; después, los bytes de la imagen.
            try:
                pos = 5
                for _ in range(2):
                    end = raw.index(b"\x00\x00", pos)
                    while (end - pos) % 2:
                        end = raw.index(b"\x00\x00", end + 1)
                    pos = end + 2
                return raw[pos:]
            except ValueError:
                return None

        return None

    @staticmethod
    def extract_cover_bytes(audio_path: str) -> Optional[bytes]:
        """Extrae la portada incrustada del audio usando mutagen y devuelve bytes JPEG."""
        try:
            from mutagen import File
            audio = File(audio_path)
            if not audio:
                return None

            image_data = MediaProcessor._find_embedded_cover(audio)

            if image_data:
                # Normalizar imagen a JPEG comprimido (máx 600x600 para web)
                img = Image.open(io.BytesIO(image_data))
                img.thumbnail((600, 600))
                output = io.BytesIO()
                img.convert("RGB").save(output, format="JPEG", quality=80)
                return output.getvalue()
        except Exception as e:
            logger.warning(f"No se pudo extraer portada de {audio_path}: {e}")
        return None

    @staticmethod
    def generate_audio_snippet(audio_path: str, duration_sec: int = 20) -> Optional[bytes]:
        """Genera un fragmento de audio en MP3 ultra-ligero para preescucha en la WebApp.
        Usa pydub. Exporta a 32kbps Mono para minimizar almacenamiento y ancho de banda.
        """
        # Patch para Python 3.13 (reemplazo de audioop eliminado)
        try:
            import audioop
        except ImportError:
            import audioop_lts as audioop
            import sys
            sys.modules["audioop"] = audioop

        try:
            from pydub import AudioSegment
            # Cargar archivo original
            sound = AudioSegment.from_file(audio_path)
            total_ms = len(sound)
            snippet_ms = duration_sec * 1000

            # Extraer fragmento central
            start_ms = max(0, (total_ms // 2) - (snippet_ms // 2))
            end_ms = min(total_ms, start_ms + snippet_ms)

            snippet = sound[start_ms:end_ms].fade_in(1000).fade_out(1000)

            out_buffer = io.BytesIO()
            # Compresión máxima: 32k bitrate y 1 solo canal (-ac 1 = Mono)
            snippet.export(out_buffer, format="mp3", bitrate="32k", parameters=["-ac", "1"])
            return out_buffer.getvalue()
        except Exception as e:
            logger.warning(f"No se pudo generar preview de audio para {audio_path}: {e}")
            return None