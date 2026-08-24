import io
import os
import logging
import xml.etree.ElementTree as ET

# Logger unificado de Sonometa
logger = logging.getLogger("Sonometa")


class AudioManager:
    """Responsable exclusivamente de la lectura, modificación y eliminación
    de etiquetas de audio mediante mutagen. No contiene ninguna lógica de UI."""

    # ------------------------------------------------------------------
    # Lectura de metadatos
    # ------------------------------------------------------------------

    def extract_metadata(self, file_path, filename):
        """Lee todas las etiquetas de texto de un archivo de audio.

        Returns:
            dict con claves: Filename, Title, Artist, MixArtist, Album,
                             Genre, Publisher, Year, CUEs, Cover.
        """
        from mutagen.wave import WAVE
        from mutagen import File as MutagenFile

        data = {
            "Filename": filename,
            "Title": "",
            "Artist": "",
            "MixArtist": "",
            "Album": "",
            "Genre": "",
            "Publisher": "",
            "Year": "",
            "CUEs": 0,
            "Cover": "No",
        }

        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".wav":
                audio = WAVE(file_path)
                if audio.tags:
                    data["Title"]     = str(audio.tags.get("TIT2", ""))
                    data["Artist"]    = str(audio.tags.get("TPE1", ""))
                    data["MixArtist"] = str(audio.tags.get("TPE4", ""))
                    data["Album"]     = str(audio.tags.get("TALB", ""))
                    data["Genre"]     = str(audio.tags.get("TCON", ""))
                    data["Publisher"] = str(audio.tags.get("TPUB", ""))
                    data["Year"]      = str(audio.tags.get("TDRC", ""))
            else:
                audio = MutagenFile(file_path, easy=True)
                if audio is not None:
                    def get_tag(tag_name):
                        val = audio.get(tag_name, [""])
                        return val[0] if val else ""

                    data["Title"]     = get_tag("title")
                    data["Artist"]    = get_tag("artist")
                    data["MixArtist"] = get_tag("mixartist")
                    data["Album"]     = get_tag("album")
                    data["Genre"] = get_tag("genre")
                    data["Publisher"] = get_tag("organization") or get_tag("publisher")
                    data["Year"]      = get_tag("date") or get_tag("year")

            if self.extract_cover_bytes(file_path):
                data["Cover"] = "Sí"

        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {filename}: {str(e)}")

        return data

    def extract_cover_bytes(self, file_path):
        """Lee y devuelve los bytes de la carátula incrustada, o None si no existe."""
        from mutagen import File as MutagenFile

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return None

            if hasattr(audio, "tags") and audio.tags:
                for tag_key in audio.tags.keys():
                    if tag_key.startswith("APIC") or tag_key.startswith("PIC"):
                        return audio.tags[tag_key].data

            if hasattr(audio, "pictures") and audio.pictures:
                return audio.pictures[0].data

            if "covr" in audio:
                covers = audio["covr"]
                if covers:
                    return bytes(covers[0])

        except Exception as e:
            logger.debug(f"Error al leer bytes de portada en {os.path.basename(file_path)}: {str(e)}")

        return None

    # ------------------------------------------------------------------
    # Escritura de etiquetas de texto
    # ------------------------------------------------------------------

    def save_single_tag(self, file_path, field_name, new_value, app=None):
        """Guarda (o elimina) una única etiqueta de texto en el archivo de audio."""
        from mutagen.id3 import (
            ID3, TIT2, TPE1, TPE4, TALB, TCON, TPUB, TDRC, ID3NoHeaderError,
        )
        from mutagen.wave import WAVE
        from mutagen import File as MutagenFile

        was_playing, saved_pos = False, 0.0
        if app and hasattr(app, "detail_panel") and app.detail_panel.audio_player:
            was_playing, saved_pos = app.detail_panel.audio_player.prepare_for_file_write()

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext in (".mp3", ".wav"):
                audio_wav = None
                is_new_id3 = False
                if ext == ".wav":
                    audio_wav = WAVE(file_path)
                    if audio_wav.tags is None:
                        audio_wav.add_tags()
                    audio_tags = audio_wav.tags
                else:
                    try:
                        audio_tags = ID3(file_path)
                    except ID3NoHeaderError:
                        audio_tags = ID3()
                        is_new_id3 = True

                frame_map = {
                    "Title":     TIT2,
                    "Artist":    TPE1,
                    "MixArtist": TPE4,
                    "Album":     TALB,
                    "Genre":     TCON,
                    "Publisher": TPUB,
                    "Year":      TDRC,
                }

                frame_cls = frame_map.get(field_name)
                if not frame_cls:
                    logger.warning(f"Campo no soportado para guardar: {field_name}")
                    return

                if new_value:
                    audio_tags.add(frame_cls(encoding=3, text=str(new_value)))
                else:
                    audio_tags.delall(frame_cls.__name__)

                if ext == ".wav" and audio_wav is not None:
                    audio_wav.save()
                else:
                    if is_new_id3:
                        audio_tags.save(file_path, v2_version=4)
                    else:
                        audio_tags.save(file_path)

            else:
                tag_map = {
                    "Title":     "title",
                    "Artist":    "artist",
                    "MixArtist": "mixartist",
                    "Album":     "album",
                    "Genre":     "genre",
                    "Publisher": "organization",
                    "Year":      "date",
                }

                mutagen_key = tag_map.get(field_name)
                if not mutagen_key:
                    logger.warning(f"Campo no soportado para guardar: {field_name}")
                    return

                audio = MutagenFile(file_path, easy=True)
                if audio is None:
                    logger.error(f"No se pudo cargar el archivo para modificar tags: {file_path}")
                    return

                if audio.tags is None:
                    audio.add_tags()

                if new_value:
                    audio[mutagen_key] = [str(new_value)]
                else:
                    audio.pop(mutagen_key, None)

                audio.save()

        except Exception as e:
            logger.error(f"Error al guardar etiqueta '{field_name}' en {os.path.basename(file_path)}: {str(e)}")

        finally:
            if app and hasattr(app, "detail_panel") and app.detail_panel.audio_player:
                app.detail_panel.audio_player.resume_after_file_write(file_path, was_playing, saved_pos)

    # ------------------------------------------------------------------
    # Carátulas (escritura / eliminación)
    # ------------------------------------------------------------------

    def embed_cover_art(self, file_path, image_bytes):
        """Incrusta la carátula en el archivo de audio. Devuelve True si tiene éxito."""
        from mutagen.id3 import ID3, APIC, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC, Picture
        from mutagen.mp4 import MP4, MP4Cover

        ext = os.path.splitext(file_path)[1].lower()
        try:
            if ext in (".mp3", ".wav"):
                audio_wav = None
                is_new_id3 = False
                if ext == ".wav":
                    audio_wav = WAVE(file_path)
                    if audio_wav.tags is None:
                        audio_wav.add_tags()
                    audio_tags = audio_wav.tags
                else:
                    try:
                        audio_tags = ID3(file_path)
                    except ID3NoHeaderError:
                        audio_tags = ID3()
                        is_new_id3 = True

                audio_tags.delall("APIC")
                audio_tags.add(APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover",
                    data=image_bytes,
                ))

                if ext == ".wav" and audio_wav is not None:
                    audio_wav.save()
                else:
                    if is_new_id3:
                        audio_tags.save(file_path, v2_version=4)
                    else:
                        audio_tags.save(file_path)

            elif ext == ".flac":
                audio = FLAC(file_path)
                image = Picture()
                image.type = 3
                image.mime = "image/jpeg"
                image.desc = "Cover"
                image.data = image_bytes
                audio.clear_pictures()
                audio.add_picture(image)
                audio.save()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                audio["covr"] = [MP4Cover(image_bytes, imageformat=MP4Cover.FORMAT_JPEG)]
                audio.save()

            else:
                logger.warning(
                    f"Formato no soportado para incrustar carátula de forma fiable: "
                    f"{os.path.basename(file_path)}"
                )
                return False

            return True

        except Exception as e:
            logger.error(
                f"Error incrustando la carátula en {os.path.basename(file_path)}: {str(e)}"
            )
            return False

    def embed_cover_art_verified(self, file_path, image_bytes):
        """Incrusta la carátula y verifica que quedó escrita en disco."""
        if not self.embed_cover_art(file_path, image_bytes):
            logger.error(
                f"Falló la incrustación de la carátula en: {os.path.basename(file_path)}"
            )
            return False

        try:
            persisted = self.extract_cover_bytes(file_path)
            if persisted:
                return True

            logger.error(
                f"Verificación post-guardado FALLIDA: no se detectó carátula en "
                f"{os.path.basename(file_path)}"
            )
        except Exception as e:
            logger.error(
                f"Error verificando la carátula guardada en "
                f"{os.path.basename(file_path)}: {str(e)}"
            )

        return False

    def strip_cover_tags(self, file_path):
        """Elimina todos los tags de portada del archivo de audio."""
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen import File as MutagenFile

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".mp3":
                try:
                    tags = ID3(file_path)
                except ID3NoHeaderError:
                    return
                tags.delall("APIC")
                tags.save(file_path)

            elif ext == ".wav":
                audio = WAVE(file_path)
                if audio.tags:
                    audio.tags.delall("APIC")
                    audio.save()

            elif ext == ".flac":
                audio = FLAC(file_path)
                audio.clear_pictures()
                audio.save()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                audio.pop("covr", None)
                audio.save()

            else:
                audio = MutagenFile(file_path)
                if audio and hasattr(audio, "tags") and audio.tags is not None:
                    for key in list(audio.tags.keys()):
                        if "APIC" in key or "covr" in key or "PIC" in key:
                            del audio.tags[key]
                    audio.save()

            logger.info(f"Carátula eliminada con éxito de: {os.path.basename(file_path)}")

        except Exception as e:
            logger.error(f"Error al eliminar carátula de {os.path.basename(file_path)}: {str(e)}")

    # ------------------------------------------------------------------
    # Eliminación completa de metadatos
    # ------------------------------------------------------------------

    def scan_audio_files(self, folder):
        """Escanea recursivamente una carpeta y devuelve una lista de diccionarios con
        la ruta del archivo y sus metadatos extraídos.
        """
        AUDIO_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.aac', '.wav', '.ogg', '.wma', '.aiff')
        if not os.path.isdir(folder) or not os.access(folder, os.R_OK):
            logger.error(f"Ruta inválida o sin permisos de lectura: {folder}")
            return []

        results = []
        for root, _, files in os.walk(folder):
            for file in files:
                if file.lower().endswith(AUDIO_EXTENSIONS):
                    file_path = os.path.join(root, file)
                    metadata = self.extract_metadata(file_path, file)
                    results.append({
                        "file_path": file_path,
                        "metadata": metadata
                    })
        return results

    def clear_audio_file_metadata(self, file_path):
        """Elimina todos los metadatos del archivo de audio, conservando solo el nombre."""
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.aiff import AIFF
        from mutagen import File as MutagenFile

        ext = os.path.splitext(file_path)[1].lower()

        try:
            if ext == ".mp3":
                try:
                    ID3(file_path).delete(file_path)
                except ID3NoHeaderError:
                    pass

            elif ext == ".wav":
                audio = WAVE(file_path)
                if audio.tags is not None:
                    audio.delete()

            elif ext == ".flac":
                audio = FLAC(file_path)
                if getattr(audio, "pictures", None):
                    audio.clear_pictures()
                    audio.save()
                if audio.tags is not None:
                    audio.delete()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                if audio.tags is not None:
                    audio.delete()

            elif ext == ".aiff":
                audio = AIFF(file_path)
                if audio.tags is not None:
                    audio.delete()

            else:
                audio = MutagenFile(file_path)
                if audio is None:
                    logger.warning(
                        f"No se pudieron identificar los metadatos para limpiar: "
                        f"{os.path.basename(file_path)}"
                    )
                    return False

                if hasattr(audio, "delete"):
                    audio.delete()
                elif hasattr(audio, "tags") and audio.tags is not None:
                    audio.tags.clear()
                    audio.save()

            return True

        except Exception as e:
            logger.error(
                f"Error al limpiar metadatos de {os.path.basename(file_path)}: {str(e)}"
            )
            return False

    # ------------------------------------------------------------------
    # Utilidades de imagen (sin UI)
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_cover_image_bytes(image_bytes):
        """Normaliza los bytes de imagen a JPEG RGB con calidad 95."""
        from PIL import Image

        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode not in ("RGB",):
                image = image.convert("RGB")

            output = io.BytesIO()
            image.save(output, format="JPEG", quality=95, optimize=True)
            return output.getvalue()
        except Exception as e:
            logger.debug(f"Error normalizando imagen (se devuelven bytes originales): {str(e)}")
            return image_bytes