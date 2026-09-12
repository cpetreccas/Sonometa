import io
import os
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import xml.etree.ElementTree as ET
import threading
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional, Tuple

# Logger unificado de Sonometa
logger = logging.getLogger("Sonometa")

MetadataDict = Dict[str, Any]
MetadataCacheKey = Tuple[str, int, int]
MAX_METADATA_CACHE = 8000


class AudioManager:
    """Responsable exclusivamente de la lectura, modificación y eliminación
    de etiquetas de audio mediante mutagen. No contiene ninguna lógica de UI."""

    def __init__(self, cache_manager=None) -> None:
        self._metadata_cache: "OrderedDict[MetadataCacheKey, MetadataDict]" = OrderedDict()
        self._cache_lock = threading.Lock()
        self.cache_manager = cache_manager  # Caché persistente opcional

    @staticmethod
    def _safe_close_audio(audio_obj) -> None:
        close_fn = getattr(audio_obj, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass

    def _build_file_cache_key(self, file_path: str) -> Optional[MetadataCacheKey]:
        try:
            stat = os.stat(file_path)
            return (os.path.abspath(file_path), stat.st_mtime_ns, stat.st_size)
        except Exception:
            return None

    def _get_cached_metadata(self, file_path: str) -> Optional[MetadataDict]:
        key = self._build_file_cache_key(file_path)
        if not key:
            return None

        with self._cache_lock:
            cached = self._metadata_cache.get(key)
            if cached is None:
                return None
            self._metadata_cache.move_to_end(key)
            return dict(cached)

    def _set_cached_metadata(self, file_path: str, metadata_dict: MetadataDict) -> None:
        key = self._build_file_cache_key(file_path)
        if not key:
            return

        with self._cache_lock:
            if key in self._metadata_cache:
                self._metadata_cache.move_to_end(key)
            self._metadata_cache[key] = dict(metadata_dict)
            while len(self._metadata_cache) > MAX_METADATA_CACHE:
                self._metadata_cache.popitem(last=False)

    def _invalidate_metadata_cache(self, file_path: str) -> None:
        abs_target = os.path.abspath(file_path)
        with self._cache_lock:
            stale_keys = [k for k in self._metadata_cache.keys() if k[0] == abs_target]
            for key in stale_keys:
                self._metadata_cache.pop(key, None)

    def clear_runtime_caches(self) -> None:
        with self._cache_lock:
            self._metadata_cache.clear()

    # ------------------------------------------------------------------
    # Lectura de metadatos
    # ------------------------------------------------------------------

    def extract_metadata(self, file_path: str, filename: str) -> MetadataDict:
        """Lee todas las etiquetas de texto de un archivo de audio incluyendo la duración.

        Returns:
            dict con claves: Filename, Title, Artist, MixArtist, Album,
                             Genre, Publisher, Year, Comment, Duration, Cues, Rating, Cover.
        """
        from mutagen.wave import WAVE
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.id3 import ID3
        from mutagen import File as MutagenFile

        cached = self._get_cached_metadata(file_path)
        if cached is not None:
            return self._normalize_traktor_fields(dict(cached))

        # Intentar caché persistente si está disponible
        if self.cache_manager:
            persistent_cache = self.cache_manager.get_cached_tags(file_path)
            if persistent_cache is not None:
                logger.debug(f"[AUDIO] Metadatos cargados de caché persistente: {filename}")
                normalized = self._normalize_traktor_fields(dict(persistent_cache))
                self._set_cached_metadata(file_path, normalized)
                return normalized

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
            "Duration": "",  # Preservación de la duración calculada del audio
            "Cues": "-",
            "Rating": "0★",
            # Campos crudos para filtros/caché persistente
            "cue_count": 0,
            "rating": 0,
            "Cover": "No",
        }

        open_audio_objects = []
        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".wav":
                audio = WAVE(file_path)
                open_audio_objects.append(audio)
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

            elif ext == ".mp3":
                try:
                    audio_id3 = ID3(file_path)
                    open_audio_objects.append(audio_id3)
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

                except Exception:
                    pass

            elif ext == ".flac":
                audio = FLAC(file_path)
                open_audio_objects.append(audio)
                data["Title"]     = audio.get("title", [""])[0]
                data["Artist"]    = audio.get("artist", [""])[0]
                data["MixArtist"] = (audio.get("REMIXEDBY") or audio.get("MIXARTIST") or audio.get("REMIX") or [""])[0]
                data["Album"]     = audio.get("album", [""])[0]
                data["Genre"]     = audio.get("genre", [""])[0]
                data["Publisher"] = (audio.get("organization") or audio.get("publisher") or [""])[0]
                data["Year"]      = (audio.get("date") or audio.get("year") or [""])[0]
                data["Comment"]   = audio.get("comment", [""])[0]

            elif ext in (".m4a", ".mp4"):
                audio = MP4(file_path)
                open_audio_objects.append(audio)
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

            else:
                audio = MutagenFile(file_path, easy=True)
                if audio is not None:
                    open_audio_objects.append(audio)
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

            # Extracción y formateo seguro de la duración (info.length)
            raw_audio = MutagenFile(file_path)
            if raw_audio is not None:
                open_audio_objects.append(raw_audio)
            if raw_audio and hasattr(raw_audio, "info") and getattr(raw_audio.info, "length", None):
                total_seconds = int(raw_audio.info.length)
                mins, secs = divmod(total_seconds, 60)
                data["Duration"] = f"{mins:02d}:{secs:02d}"

            cue_count = self.count_traktor_cues(file_path)

            # Extracción segura del rating usando el objeto audio mutagen o fallback
            rating_audio_obj = open_audio_objects[0] if open_audio_objects else MutagenFile(file_path)
            if rating_audio_obj is not None:
                rating_value = self.extract_traktor_rating(rating_audio_obj, file_path)
            else:
                rating_value = 0

            data["cue_count"] = cue_count
            data["rating"] = rating_value
            data["Cues"] = str(cue_count) if cue_count > 0 else "-"
            data["Rating"] = f"{rating_value}★"
            # Compatibilidad con versiones previas que consumen la clave histórica
            data["CUEs"] = data["Cues"]

            if self.extract_cover_bytes(file_path):
                data["Cover"] = "Sí"

        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {filename}: {str(e)}")
        finally:
            for audio_obj in open_audio_objects:
                self._safe_close_audio(audio_obj)

        data = self._normalize_traktor_fields(data)
        self._set_cached_metadata(file_path, data)

        # Guardar en caché persistente si está disponible
        if self.cache_manager:
            self.cache_manager.save_tags(file_path, data)

        return data

    @staticmethod
    def _normalize_traktor_fields(metadata: MetadataDict) -> MetadataDict:
        def parse_cues(raw_value) -> int:
            text = str(raw_value or "").strip()
            return int(text) if text.isdigit() else 0

        def parse_rating(raw_value) -> int:
            text = str(raw_value or "").strip().replace("★", "")
            return max(0, min(5, int(text))) if text.isdigit() else 0

        cue_count = metadata.get("cue_count")
        if cue_count is None:
            cue_count = parse_cues(metadata.get("Cues", metadata.get("CUEs", "-")))
        else:
            cue_count = parse_cues(cue_count)

        rating_value = metadata.get("rating")
        if rating_value is None:
            rating_value = parse_rating(metadata.get("Rating", "0★"))
        else:
            rating_value = parse_rating(rating_value)

        metadata["cue_count"] = cue_count
        metadata["rating"] = rating_value
        metadata["Cues"] = str(cue_count) if cue_count > 0 else "-"
        metadata["CUEs"] = metadata["Cues"]
        metadata["Rating"] = f"{rating_value}★"
        return metadata

    def count_traktor_cues(self, file_path):
        """Lee la etiqueta GEOB/PRIV 'TRAKTOR4' o la etiqueta 'TRAKTOR4' y cuenta
        el número de Cue Points configurados dentro del XML subyacente.
        """
        from mutagen import File as MutagenFile

        try:
            audio = MutagenFile(file_path)
            self_audio_ref = audio
            if audio is None:
                return 0

            xml_str = self._extract_traktor_xml_string(audio)
            if not xml_str:
                return 0

            root = self._parse_traktor_root(xml_str)
            if root is None:
                return 0

            cues = root.findall(".//CUE_V2")
            if cues:
                return len(cues)

            # Fallback para estructuras simplificadas sin nodos CUE_V2
            for tag_name in ("CUE", "CUEPOINT"):
                fallback = root.findall(f".//{tag_name}")
                if fallback:
                    return len(fallback)

            # Último fallback textual si el XML es parcial
            return len(re.findall(r"<CUE_V2\b", xml_str, flags=re.IGNORECASE))

        except Exception as e:
            logger.debug(f"Error parseando Traktor CUEs en {os.path.basename(file_path)}: {str(e)}")
        finally:
            self._safe_close_audio(locals().get("self_audio_ref"))

        return 0

    @staticmethod
    def _normalize_rating_value(raw_value) -> Optional[int]:
        if raw_value is None:
            return None

        text = str(raw_value).strip()
        if text == "":
            return None

        try:
            value = float(text)
        except Exception:
            return None

        if value <= 1:
            stars = round(value * 5)
        elif value <= 5:
            stars = round(value)
        elif value <= 100:
            stars = round(value / 20)
        elif value <= 255:
            stars = round(value / 51)
        else:
            stars = round(value)

        return max(0, min(5, int(stars)))

    @staticmethod
    def _extract_traktor_xml_string(audio_obj) -> Optional[str]:
        xml_data_bytes = None

        if hasattr(audio_obj, "tags") and audio_obj.tags:
            for key, tag in audio_obj.tags.items():
                if key.startswith("GEOB") or key.startswith("PRIV"):
                    desc = getattr(tag, "desc", "") or getattr(tag, "owner", "")
                    if "TRAKTOR" in str(desc).upper():
                        xml_data_bytes = getattr(tag, "data", None)
                        break

        if not xml_data_bytes and hasattr(audio_obj, "get"):
            traktor_tag = audio_obj.get("TRAKTOR4") or audio_obj.get("traktor4")
            if traktor_tag:
                val = traktor_tag[0] if isinstance(traktor_tag, list) else traktor_tag
                if isinstance(val, str):
                    xml_data_bytes = val.encode("utf-8", errors="ignore")
                elif isinstance(val, bytes):
                    xml_data_bytes = val

        if not xml_data_bytes:
            return None

        try:
            return xml_data_bytes.decode("utf-8", errors="ignore")
        except Exception:
            try:
                return str(xml_data_bytes)
            except Exception:
                return None

    @staticmethod
    def _parse_traktor_root(xml_str: str):
        if not xml_str:
            return None

        markers = ("<ENTRY", "<NML", "<CUE_V2")
        start_idx = -1
        for marker in markers:
            start_idx = xml_str.find(marker)
            if start_idx != -1:
                break

        if start_idx == -1:
            return None

        end_idx = xml_str.rfind(">")
        if end_idx == -1 or end_idx <= start_idx:
            return None

        clean_xml = xml_str[start_idx : end_idx + 1]
        try:
            return ET.fromstring(clean_xml)
        except Exception:
            return None

    def extract_traktor_rating(self, audio, file_path: str = "") -> int:
        """
        Extrae el rating de Traktor en escala 0-5.
        Soporta MP3 (marcos POPM) y FLAC (Vorbis Comments: rating wmp, rating, traktor_rating, etc.)
        """
        rating_stars = 0

        # Si no se proporciona file_path explícitamente, intentamos inferirlo desde el objeto audio
        if not file_path and hasattr(audio, "filename"):
            file_path = str(audio.filename)

        try:
            # --- CASO 1: ARCHIVOS FLAC (Vorbis Comments) ---
            if file_path.lower().endswith(".flac"):
                # Mapeo de claves habituales en FLAC (se evalúan en minúsculas)
                possible_keys = [
                    "rating wmp",
                    "rating",
                    "rating:traktor",
                    "traktor_rating",
                    "rating_winamp"
                ]

                raw_val = None
                # Convertimos las claves de audio a minúsculas para evitar problemas de mayúsculas
                audio_keys_lower = {str(k).lower(): k for k in audio.keys()}

                for key in possible_keys:
                    if key in audio_keys_lower:
                        original_key = audio_keys_lower[key]
                        val_list = audio[original_key]
                        raw_val = val_list[0] if isinstance(val_list, list) and val_list else val_list
                        break

                if raw_val is not None:
                    try:
                        val_num = float(str(raw_val).strip())
                        # Conversión desde escala 0-255 (estándar POPM / Windows Media Player)
                        if val_num > 5:
                            if val_num >= 224: rating_stars = 5      # 255 es 5 estrellas
                            elif val_num >= 160: rating_stars = 4    # 196 / 160 es 4 estrellas
                            elif val_num >= 96: rating_stars = 3     # 128 / 96 es 3 estrellas
                            elif val_num >= 32: rating_stars = 2     # 64 / 32 es 2 estrellas
                            elif val_num > 0: rating_stars = 1      # 1 / 32 es 1 estrella
                        else:
                            # Si ya viene en escala 1-5
                            rating_stars = int(val_num)
                    except ValueError:
                        rating_stars = 0

            # --- CASO 2: ARCHIVOS MP3 / ID3 (POPM Frame) ---
            else:
                for key in audio.keys():
                    if key.startswith("POPM"):
                        popm_data = audio[key]
                        raw_rating = getattr(popm_data, "rating", 0)
                        if raw_rating >= 224: rating_stars = 5
                        elif raw_rating >= 160: rating_stars = 4
                        elif raw_rating >= 96: rating_stars = 3
                        elif raw_rating >= 32: rating_stars = 2
                        elif raw_rating > 0: rating_stars = 1
                        break

        except Exception as e:
            logger.warning(f"Error extrayendo rating de {file_path}: {e}")

        return rating_stars

    def extract_cover_bytes(self, file_path):
        """Lee y devuelve los bytes de la carátula incrustada, o None si no existe."""
        from mutagen import File as MutagenFile

        try:
            audio = MutagenFile(file_path)
            self_audio_ref = audio
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
        finally:
            self._safe_close_audio(locals().get("self_audio_ref"))

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
            self._invalidate_metadata_cache(file_path)
            # Invalidar caché persistente también
            if self.cache_manager:
                self.cache_manager.invalidate_track_cache(file_path)
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

            self._invalidate_metadata_cache(file_path)
            # Invalidar caché persistente
            if self.cache_manager:
                self.cache_manager.invalidate_track_cache(file_path)
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
            self._invalidate_metadata_cache(file_path)
            # Invalidar caché persistente
            if self.cache_manager:
                self.cache_manager.invalidate_track_cache(file_path)

        except Exception as e:
            logger.error(f"Error al eliminar carátula de {os.path.basename(file_path)}: {str(e)}")

    # ------------------------------------------------------------------
    # Eliminación completa de metadatos
    # ------------------------------------------------------------------

    def _iter_audio_file_paths(self, folder: str, audio_extensions: tuple) -> List[str]:
        file_paths: List[str] = []
        for root, _, files in os.walk(folder):
            for file_name in files:
                if file_name.lower().endswith(audio_extensions):
                    file_paths.append(os.path.join(root, file_name))
        return file_paths

    def scan_audio_files(self, folder: str, progress_callback: Optional[Callable[[int, int, str], None]] = None):
        """Escanea recursivamente una carpeta y devuelve una lista de diccionarios con
        la ruta del archivo y sus metadatos extraídos.

        Args:
            folder: Carpeta raíz a escanear.
            progress_callback: Callback opcional con firma
                               progress_callback(current, total, current_file).
        """
        AUDIO_EXTENSIONS = ('.mp3', '.flac', '.m4a', '.aac', '.wav', '.ogg', '.wma', '.aiff')
        if not os.path.isdir(folder) or not os.access(folder, os.R_OK):
            logger.error(f"Ruta inválida o sin permisos de lectura: {folder}")
            return []

        file_paths = self._iter_audio_file_paths(folder, AUDIO_EXTENSIONS)
        total_files = len(file_paths)
        if total_files == 0:
            return []

        max_workers = min(32, max(4, (os.cpu_count() or 4) * 2))
        ordered_results: List[Optional[dict]] = [None] * total_files
        completed = 0

        def _safe_notify(current: int, total: int, current_file: str) -> None:
            if not callable(progress_callback):
                return
            try:
                progress_callback(current, total, current_file)
            except Exception:
                pass

        def _read_metadata(file_path: str) -> dict:
            file_name = os.path.basename(file_path)
            metadata = self.extract_metadata(file_path, file_name)
            return {
                "file_path": file_path,
                "metadata": metadata,
            }

        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="SonometaScan") as executor:
            future_map = {
                executor.submit(_read_metadata, file_path): (idx, file_path)
                for idx, file_path in enumerate(file_paths)
            }

            for future in as_completed(future_map):
                idx, file_path = future_map[future]
                try:
                    ordered_results[idx] = future.result()
                except Exception as exc:
                    logger.error(f"Error escaneando {os.path.basename(file_path)}: {str(exc)}")
                    ordered_results[idx] = {
                        "file_path": file_path,
                        "metadata": self.extract_metadata(file_path, os.path.basename(file_path)),
                    }

                completed += 1
                _safe_notify(completed, total_files, file_path)

        return [item for item in ordered_results if item is not None]

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
                editable_vorbis = ["title", "artist", "mixartist", "remixedby", "album", "genre", "organization", "publisher", "date", "year", "comment"]
                for key in editable_vorbis:
                    audio.pop(key, None)
                audio.save()

            elif ext in (".m4a", ".aac", ".mp4"):
                audio = MP4(file_path)
                if audio.tags is not None:
                    editable_mp4 = ["\xa9nam", "\xa9ART", "soar", "\xa9alb", "\xa9gen", "covr", "\xa9day", "\xa9cmt", "----:com.apple.iTunes:REMIXEDBY"]
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

            self._invalidate_metadata_cache(file_path)
            # Invalidar caché persistente
            if self.cache_manager:
                self.cache_manager.invalidate_track_cache(file_path)
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

    def get_tag_value(self, file_path, field_name, default=""):
        """Devuelve el valor de una etiqueta específica para un archivo de audio.

        Args:
            file_path (str): Ruta absoluta al archivo en disco.
            field_name (str): Nombre del campo (p. ej. 'Comment', 'Artist', etc.).
            default (str): Valor de retorno si la etiqueta no existe o hay error.

        Returns:
            str: Valor de la etiqueta.
        """
        try:
            filename = os.path.basename(file_path)
            metadata = self.extract_metadata(file_path, filename)
            return metadata.get(field_name, default)
        except Exception as e:
            logger.error(f"Error al obtener el tag '{field_name}' de {file_path}: {str(e)}")
            return default