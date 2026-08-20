import os
import re

class FilenameFormatter:
    def __init__(self):
        # Palabras reservadas en minúscula para Publisher (MixArtist)
        self.lower_words_par = {'remix', 'mix', 'rework', 'edit', 'side', 'dub', 'instrumental', 'club', 'version', 'acoustic'}
        # Palabras reservadas en minúscula para Intérprete (Artist)
        self.lower_words_prefix = {'feat.', 'vs', 'meets', 'pres.'}

        # Diccionario de nombres propios para proteger en el Título (Sentence Case)
        self.proper_nouns = {'sun', 'moon', 'earth', 'god', 'london', 'paris', 'new york'}

        self.dotted_initials_pattern = re.compile(r"^([A-Za-z](?:\.[A-Za-z])+\.?)([.,;:!?])?$")

    def _clean_garbage_and_symbols(self, text):
        """Limpia símbolos tipográficos inválidos, basura digital y versiones/coletillas eliminables."""
        # 1. Tipografía y guiones
        text = text.replace("`", "'").replace("´", "'").replace("’", "'")
        text = text.replace("—", "-").replace("–", "-").replace("~", "-")
        text = text.replace("_", " ")

        # 2. Basura digital y calidades
        text = re.sub(r'(?i)\[\s*(?:320\s*kbps|1080p|exclusive)\s*\]', '', text)
        text = re.sub(r'(?i)\(\s*(?:flac|hd|free download)\s*\)', '', text)
        text = re.sub(r'(?i)\[?\s*www\.[^\s\]\)]+\s*\]?', '', text)

        # 3. Eliminar coletillas de "Original Mix/Version", "Extended Mix/Remix/Edit", etc.
        text = re.sub(r'(?i)\(\s*original\s+(?:mix|version)\s*\)', '', text)
        text = re.sub(r'(?i)\[\s*original\s+(?:mix|version)\s*\]', '', text)
        text = re.sub(r'(?i)\(\s*extended\s+(?:mix|remix|edit)\s*\)', '', text)
        text = re.sub(r'(?i)\[\s*extended\s+(?:mix|remix|edit)\s*\]', '', text)

        # 4. Normalizar corchetes restantes a paréntesis
        text = re.sub(r'\[(.*?)\]', r'(\1)', text)

        return text

    def _normalize_connectors(self, text):
        """Unifica variantes de conectores como vs, pres/presents, feat y &."""
        if not text: return ""

        # Unificar "vs." o "vs" a "vs"
        text = re.sub(r'(?i)\bvs\.?\b', 'vs', text)

        # Unificar "presents", "present", "pres", "pres.", "pres.." a "pres."
        text = re.sub(r'(?i)\b(?:presents?|pres)\b\.?', 'pres.', text)
        # Limpiar cualquier exceso de puntos consecutivos que hayan quedado (ej. pres..)
        text = re.sub(r'(?i)\bpres\.+\b', 'pres.', text)

        # Unificar "feat"
        text = re.sub(r'(?i)\b(?:ft\.?|feat\.?|featuring)\b', 'feat.', text)
        # Unificar "&" (and, with, +, x aislada)
        text = re.sub(r'(?i)\b(?:and|with)\b|\+|(?<=\s)[xX](?=\s)', '&', text)

        return text

    def _format_artist(self, artist):
        """Formatea el Intérprete: Title Case + unificación de conectores."""
        if not artist: return ""

        artist = self._normalize_connectors(artist)

        words = artist.split()
        formatted = []
        for w in words:
            clean = w.lower()
            if clean in self.lower_words_prefix or clean == '&':
                formatted.append(clean)
            else:
                dotted_match = self.dotted_initials_pattern.match(w)
                if dotted_match:
                    suffix = dotted_match.group(2) or ""
                    formatted.append(f"{dotted_match.group(1).upper()}{suffix}")
                else:
                    formatted.append(w.capitalize())
        return " ".join(formatted)

    def _format_title(self, title):
        """Formatea el Título: Sentence Case + protección de nombres propios."""
        if not title: return ""

        words = title.split()
        formatted = []
        for i, w in enumerate(words):
            clean = w.lower()
            dotted_match = self.dotted_initials_pattern.match(w)
            if dotted_match:
                suffix = dotted_match.group(2) or ""
                formatted.append(f"{dotted_match.group(1).upper()}{suffix}")
                continue

            # Primera palabra o nombre propio va en mayúscula, el resto minúscula
            if i == 0 or clean in self.proper_nouns:
                formatted.append(w.capitalize())
            else:
                formatted.append(clean)
        return " ".join(formatted)

    def _format_publisher(self, publisher):
        """Formatea el Publisher (Paréntesis): Title Case + palabras reservadas en minúscula."""
        if not publisher: return ""

        publisher = self._normalize_connectors(publisher)

        # Unificar alias comunes
        publisher = re.sub(r'(?i)\b(?:rmx|rem)\b', 'remix', publisher)
        publisher = re.sub(r'(?i)\b(?:instr)\b', 'instrumental', publisher)

        words = publisher.split()
        formatted = []
        for w in words:
            clean = w.lower()
            if clean in self.lower_words_par or clean in self.lower_words_prefix:
                formatted.append(clean)
            else:
                dotted_match = self.dotted_initials_pattern.match(w)
                if dotted_match:
                    suffix = dotted_match.group(2) or ""
                    formatted.append(f"{dotted_match.group(1).upper()}{suffix}")
                else:
                    formatted.append(w.capitalize())
        return " ".join(formatted)

    def parse_and_format(self, filename):
        """Extrae, limpia, normaliza y devuelve diccionario con las partes."""
        clean_name, ext = os.path.splitext(filename)

        # 1. Limpiar número de pista / prefijo numérico
        clean_name = re.sub(r'^(?:\d{1,3}|[A-Za-d]\d{1,2})[\s._-]+', '', clean_name)

        # 2. Limpieza de basura, tipografía y coletillas prohibidas
        clean_name = self._clean_garbage_and_symbols(clean_name)

        # 3. Extraer contenido de paréntesis (Publisher / MixArtist)
        matches_paren = re.findall(r'\((.*?)\)', clean_name)
        mixartist = " ".join(matches_paren).strip()

        # Limpiar los paréntesis del string principal
        clean_name = re.sub(r'\s*\([^)]*\)', '', clean_name).strip()

        # 4. Separar Artista y Título por guion
        artist, title = "", ""
        if "-" in clean_name:
            parts = clean_name.split("-", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            title = clean_name.strip()

        if not artist and not title:
            return None

        # 5. Formatear cada bloque con su regla específica
        artist_formatted = self._format_artist(artist)
        title_formatted = self._format_title(title)
        mixartist_formatted = self._format_publisher(mixartist)

        # 6. Eliminar posibles dobles espacios resultantes
        artist_formatted = re.sub(r'\s+', ' ', artist_formatted).strip()
        title_formatted = re.sub(r'\s+', ' ', title_formatted).strip()
        mixartist_formatted = re.sub(r'\s+', ' ', mixartist_formatted).strip()

        return {
            "artist": artist_formatted,
            "title": title_formatted,
            "mixartist": mixartist_formatted,
            "ext": ext
        }

    def format_filename_pattern(self, filename):
        """Devuelve el nombre de archivo completo formateado."""
        parsed = self.parse_and_format(filename)
        if not parsed:
            return filename

        artist = parsed.get("artist", "")
        title = parsed.get("title", "")
        mixartist = parsed.get("mixartist", "")
        ext = parsed.get("ext", "")

        if artist:
            base = f"{artist} - {title}"
        else:
            base = title

        if mixartist:
            base += f" ({mixartist})"

        return f"{base}{ext}"