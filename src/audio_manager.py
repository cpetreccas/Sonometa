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
        """Lee todas las etiquetas de texto de un archivo de audio incluyendo la duración.

        Returns:
            dict con claves: Filename, Title, Artist, MixArtist, Album,
                             Genre, Publisher, Year, Comment, Comment2, Duration, CUEs, Cover.
        """
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.id3 import ID3
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
            "Comment": "",
            "Comment2": "",
            "Duration": "",  # Preservación de la duración calculada del audio
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

                    # Lectura de comentarios en ID3 (WAV)
                    comm_frames = [v for k, v in audio.tags.items() if k.startswith("COMM")]
                    if comm_frames and comm_frames[0].text:
                        data["Comment"] = str(comm_frames[0].text[0])
                    if "TXXX:COMMENT2" in audio.tags and audio.tags["TXXX:COMMENT2"].text:
                        data["Comment2"] = str(audio.tags["TXXX:COMMENT2"].text[0])

            elif ext == ".mp3":
                try:
                    audio_id3 = ID3(file_path)
                    data["Title"]     = str(audio_id3.get("TIT2", ""))
                    data["Artist"]    = str(audio_id3.get("TPE1", ""))
                    data["Album"]     = str(audio_id3.get("TALB", ""))
                    data["Genre"]     = str(audio_id3.get("TCON", ""))
                    data["Publisher"] = str(audio_id3.get("TPUB", ""))
                    data["Year"]      = str(audio_id3.get("TDRC", ""))

                    # MixArtist
                    if "TPE4" in audio_id3 and audio_id3["TPE4"].text:
                        data["MixArtist"] = str(audio_id3["TPE4"].text[0])
                    elif "TXXX:REMIXEDBY" in audio_id3 and audio_id3["TXXX:REMIXEDBY"].text:
                        data["MixArtist"] = str(audio_id3["TXXX:REMIXEDBY"].text[0])

                    # Comment (Buscar frame COMM)
                    comm_frames = [v for k, v in audio_id3.items() if k.startswith("COMM")]
                    if comm_frames and comm_frames[0].text:
                        data["Comment"] = str(comm_frames[0].text[0])

                    # Comment2 (TXXX:COMMENT2)
                    if "TXXX:COMMENT2" in audio_id3 and audio_id3["TXXX:COMMENT2"].text:
                        data["Comment2"] = str(audio_id3["TXXX:COMMENT2"].text[0])

                except Exception:
                    pass

            elif ext == ".flac":
                audio = FLAC(file_path)
                data["Title"]     = audio.get("title", [""])[0]
                data["Artist"]    = audio.get("artist", [""])[0]
                data["MixArtist"] = (audio.get("REMIXEDBY") or audio.get("MIXARTIST") or audio.get("REMIX") or [""])[0]
                data["Album"]     = audio.get("album", [""])[0]
                data["Genre"]     = audio.get("genre", [""])[0]
                data["Publisher"] = (audio.get("organization") or audio.get("publisher") or [""])[0]
                data["Year"]      = (audio.get("date") or audio.get("year") or [""])[0]
                data["Comment"]   = audio.get("comment", [""])[0]
                data["Comment2"]  = audio.get("comment2", [""])[0]

            elif ext in (".m4a", ".mp4"):
                audio = MP4(file_path)
                data["Title"]     = audio.get("\xa9nam", [""])[0]
                data["Artist"]    = audio.get("\xa9ART", [""])[0]
                data["Album"]     = audio.get("\xa9alb", [""])[0]
                data["Genre"]     = audio.get("\xa9gen", [""])[0]
                data["Publisher"] = audio.get("\xa9dir", [""])[0]
                data["Year"]      = audio.get("\xa9day", [""])[0]
                data["Comment"]   = audio.get("\xa9cmt", [""])[0]

                atom_remix = audio.get("----:com.apple.iTunes:REMIXEDBY")
                if atom_remix:
                    val = atom_remix[0]
                    data["MixArtist"] = val.decode("utf-8") if isinstance(val, bytes) else str(val)

                atom_cmt2 = audio.get("----:com.apple.iTunes:COMMENT2")
                if atom_cmt2:
                    val = atom_cmt2[0]
                    data["Comment2"] = val.decode("utf-8") if isinstance(val, bytes) else str(val)

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
                    data["Genre"]     = get_tag("genre")
                    data["Publisher"] = get_tag("organization") or get_tag("publisher")
                    data["Year"]      = get_tag("date") or get_tag("year")
                    data["Comment"]   = get_tag("comment")
                    data["Comment2"]  = get_tag("comment2")

            # Extracción y formateo seguro de la duración (info.length)
            raw_audio = MutagenFile(file_path)
            if raw_audio and hasattr(raw_audio, "info") and getattr(raw_audio.info, "length", None):
                total_seconds = int(raw_audio.info.length)
                mins, secs = divmod(total_seconds, 60)
                data["Duration"] = f"{mins:02d}:{secs:02d}"

            data["CUEs"] = self.count_traktor_cues(file_path)

            if self.extract_cover_bytes(file_path):
                data["Cover"] = "Sí"

        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {filename}: {str(e)}")

        return data

    def count_traktor_cues(self, file_path):
        """Lee la etiqueta GEOB/PRIV 'TRAKTOR4' o la etiqueta 'TRAKTOR4' y cuenta
        el número de Cue Points configurados dentro del XML subyacente.
        """
        from mutagen import File as MutagenFile

        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return 0

            xml_data_bytes = None

            # 1. Búsqueda en tags ID3 (MP3, WAV, AIFF)
            if hasattr(audio, "tags") and audio.tags:
                for key, tag in audio.tags.items():
                    if key.startswith("GEOB") or key.startswith("PRIV"):
                        desc = getattr(tag, "desc", "") or getattr(tag, "owner", "")
                        if "TRAKTOR" in desc.upper():
                            xml_data_bytes = getattr(tag, "data", None)
                            break

            # 2. Búsqueda en tags de otros formatos (FLAC, OGG, etc.) o respaldo genérico
            if not xml_data_bytes and hasattr(audio, "get"):
                traktor_tag = audio.get("TRAKTOR4") or audio.get("traktor4")
                if traktor_tag:
                    val = traktor_tag[0] if isinstance(traktor_tag, list) else traktor_tag
                    if isinstance(val, str):
                        xml_data_bytes = val.encode("utf-8", errors="ignore")
                    elif isinstance(val, bytes):
                        xml_data_bytes = val

            if not xml_data_bytes:
                return 0

            # 3. Decodificación y parsing XML
            try:
                xml_str = xml_data_bytes.decode("utf-8", errors="ignore")
            except Exception:
                xml_str = str(xml_data_bytes)

            start_idx = xml_str.find("<CUE_V2")
            if start_idx == -1:
                start_idx = xml_str.find("<ENTRY")
                if start_idx == -1:
                    return 0

            end_idx = xml_str.rfind(">")
            if end_idx == -1 or end_idx <= start_idx:
                return 0

            clean_xml = xml_str[start_idx : end_idx + 1]
            root = ET.fromstring(clean_xml)

            cues = root.findall(".//CUE_V2")
            return len(cues)

        except Exception as e:
            logger.debug(f"Error parseando Traktor CUEs en {os.path.basename(file_path)}: {str(e)}")

        return 0

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
            ID3, TIT2, TPE1, TPE4, TALB, TCON, TPUB, TDRC, COMM, TXXX, ID3NoHeaderError,
        )
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
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

                if field_name == "Comment":
                    if new_value:
                        audio_tags.add(COMM(encoding=3, lang="eng", desc="", text=str(new_value)))
                    else:
                        audio_tags.delall("COMM")

                elif field_name == "Comment2":
                    if new_value:
                        audio_tags.add(TXXX(encoding=3, desc="COMMENT2", text=str(new_value)))
                    else:
                        audio_tags.delall("TXXX:COMMENT2")

                else:
                    frame_cls = frame_map.get(field_name)
                    if not frame_cls:
                        logger.warning(f"Campo no soportado para guardar: {field_name}")
                        return

                    if new_value:
                        audio_tags.add(frame_cls(encoding=3, text=str(new_value)))
                        if field_name == "MixArtist":
                            audio_tags.add(TXXX(encoding=3, desc="REMIXEDBY", text=str(new_value)))
                    else:
                        audio_tags.delall(frame_cls.__name__)
                        if field_name == "MixArtist":
                            audio_tags.delall("TXXX:REMIXEDBY")

                if ext == ".wav" and audio_wav is not None:
                    audio_wav.save()
                else:
                    if is_new_id3:
                        audio_tags.save(file_path, v2_version=4)
                    else:
                        audio_tags.save(file_path)

            elif ext == ".flac":
                audio = FLAC(file_path)
                tag_map = {
                    "Title":     "TITLE",
                    "Artist":    "ARTIST",
                    "MixArtist": "REMIXEDBY",
                    "Album":     "ALBUM",
                    "Genre":     "GENRE",
                    "Publisher": "ORGANIZATION",
                    "Year":      "DATE",
                    "Comment":   "COMMENT",
                    "Comment2":  "COMMENT2",
                }
                flac_key = tag_map.get(field_name)
                if not flac_key:
                    logger.warning(f"Campo no soportado para guardar en FLAC: {field_name}")
                    return

                if new_value:
                    audio[flac_key] = str(new_value)
                else:
                    audio.pop(flac_key, None)
                audio.save()

            elif ext in (".m4a", ".mp4"):
                audio = MP4(file_path)
                tag_map = {
                    "Title":     "\xa9nam",
                    "Artist":    "\xa9ART",
                    "Album":     "\xa9alb",
                    "Genre":     "\xa9gen",
                    "Publisher": "\xa9dir",
                    "Year":      "\xa9day",
                    "Comment":   "\xa9cmt",
                }
                if field_name == "MixArtist":
                    atom_key = "----:com.apple.iTunes:REMIXEDBY"
                    if new_value:
                        audio[atom_key] = str(new_value).encode("utf-8")
                    else:
                        audio.pop(atom_key, None)

                elif field_name == "Comment2":
                    atom_key = "----:com.apple.iTunes:COMMENT2"
                    if new_value:
                        audio[atom_key] = str(new_value).encode("utf-8")
                    else:
                        audio.pop(atom_key, None)

                else:
                    m4a_key = tag_map.get(field_name)
                    if not m4a_key:
                        logger.warning(f"Campo no soportado para guardar en M4A: {field_name}")
                        return
                    if new_value:
                        audio[m4a_key] = [str(new_value)]
                    else:
                        audio.pop(m4a_key, None)
                audio.save()

            else:
                tag_map = {
                    "Title":     "title",
                    "Artist":    "artist",
                    "MixArtist": "mixartist",
                    "Album":     "album",
                    "Genre":     "genre",
                    "Publisher": "organization",
                    "Year":      "date",
                    "Comment":   "comment",
                    "Comment2":  "comment2",
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
        """Elimina únicamente las etiquetas de texto editables y la carátula,
        preservando intactas la estructura del archivo, cabeceras y duración.
        """
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.aiff import AIFF
        from mutagen import File as MutagenFile

        ext = os.path.splitext(file_path)[1].lower()

        try:
            # Lista de tags ID3 a remover explícitamente (sin eliminar el header o TLEN/info)
            id3_tags_to_delete = ["TIT2", "TPE1", "TPE4", "TALB", "TCON", "TPUB", "TDRC", "APIC", "COMM", "TXXX"]

            if ext == ".mp3":
                try:
                    tags = ID3(file_path)
                    for t in id3_tags_to_delete:
                        tags.delall(t)
                    tags.save(file_path)
                except ID3NoHeaderError:
                    pass

            elif ext == ".wav":
                audio = WAVE(file_path)
                if audio.tags is not None:
                    for t in id3_tags_to_delete:
                        audio.tags.delall(t)
                    audio.save()

            elif ext == ".flac":
                audio = FLAC(file_path)
                if getattr(audio, "pictures", None):
                    audio.clear_pictures()
                # Limpiar solo tags editables de Vorbis
                editable_vorbis = ["title", "artist", "mixartist", "remixedby", "album", "genre", "organization", "publisher", "date", "year", "comment", "comment2"]
                for key in editable_vorbis:
                    audio.pop(key, None)
                audio.save()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                if audio.tags is not None:
                    editable_mp4 = ["\xa9nam", "\xa9ART", "soar", "\xa9alb", "\xa9gen", "covr", "\xa9day", "\xa9cmt", "----:com.apple.iTunes:REMIXEDBY", "----:com.apple.iTunes:COMMENT2"]
                    for key in editable_mp4:
                        audio.tags.pop(key, None)
                    audio.save()

            elif ext == ".aiff":
                audio = AIFF(file_path)
                if audio.tags is not None:
                    for t in id3_tags_to_delete:
                        audio.tags.delall(t)
                    audio.save()

            else:
                audio = MutagenFile(file_path)
                if audio is not None and hasattr(audio, "tags") and audio.tags is not None:
                    # Se borran las etiquetas comunes sin hacer audio.delete() directo
                    keys_to_remove = [k for k in audio.tags.keys() if not k.startswith("TLEN")]
                    for k in keys_to_remove:
                        del audio.tags[k]
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