import os
import re

class FilenameFormatter:
    def __init__(self):
        # Palabras reservadas que deben permanecer en minúsculas en Remix / Mixes
        self.lower_words_par = {'remix', 'mix', 'rework', 'edit', 'side', 'dub', 'instrumental', 'club', 'extended', 'original'}
        self.lower_words_prefix = {'feat.', 'feat', 'ft.', 'ft', 'pres.', 'pres', 'presents'}
        self.dotted_initials_pattern = re.compile(r"^([A-Za-z](?:\.[A-Za-z])+\.?)([.,;:!?])?$")

    def _format_word(self, word, lower_words=None, force_lower=False):
        # Mantener siglas con iniciales separadas por puntos (T.N.T., A.B.C)
        dotted_match = self.dotted_initials_pattern.match(word)
        if dotted_match:
            suffix = dotted_match.group(2) or ""
            return f"{dotted_match.group(1).upper()}{suffix}"

        if lower_words and word.lower() in lower_words:
            return word.lower()
        if force_lower:
            return word.lower()
        return word.capitalize()

    def _format_parentheses(self, match):
        content = match.group(1).strip()
        words = content.split()
        formatted_words = [
            self._format_word(w, lower_words=self.lower_words_par)
            for w in words
        ]
        return f"({' '.join(formatted_words)})"

    def format_filename_pattern(self, filename):
        name, ext = os.path.splitext(filename)

        # 1. Limpieza de prefijos de pista numéricos (ej: "01. ", "01 - ", "A1 - ")
        name = re.sub(r'^(?:\d{1,3}|[A-Za-d]\d{1,2})[\s._-]+', '', name)

        # 2. Normalizar guiones bajos a espacios
        name = name.replace('_', ' ')

        # 3. Normalizar corchetes a paréntesis [Mix] -> (Mix)
        name = re.sub(r'\[(.*?)\]', r'(\1)', name)

        # 4. Formatear el contenido de los paréntesis
        name = re.sub(r'\((.*?)\)', self._format_parentheses, name)

        # Buscar separador Artista - Título
        if " - " in name:
            prefix, suffix = name.split(" - ", 1)
        elif " _ " in name:
            prefix, suffix = name.split(" _ ", 1)
        elif "-" in name:
            prefix, suffix = name.split("-", 1)
        else:
            words = name.strip().split()
            if not words:
                return filename
            formatted = self._format_word(words[0]) + (" " + " ".join(self._format_word(w, force_lower=True) for w in words[1:]) if len(words) > 1 else "")
            return f"{formatted}{ext}"

        # Formatear el Prefijo (Intérprete)
        prefix_words = prefix.strip().split()
        formatted_prefix_words = [
            self._format_word(w, lower_words=self.lower_words_prefix)
            for w in prefix_words
        ]
        formatted_prefix = " ".join(formatted_prefix_words)

        # Formatear el Sufijo (Título)
        suffix_words = suffix.strip().split()
        if suffix_words:
            first_word = self._format_word(suffix_words[0])
            rest_words = [
                w if w.startswith("(") or w.endswith(")") else self._format_word(w, force_lower=True)
                for w in suffix_words[1:]
            ]
            formatted_suffix = " ".join([first_word] + rest_words)
        else:
            formatted_suffix = ""

        return f"{formatted_prefix} - {formatted_suffix}{ext}"

    def parse_and_format(self, filename):
        """Aplica las reglas de formato local y devuelve una estructura parseada."""
        clean_name, ext = os.path.splitext(filename)

        # 1. Limpiar número de pista / prefijo de DJ
        clean_name = re.sub(r'^(?:\d{1,3}|[A-Za-d]\d{1,2})[\s._-]+', '', clean_name)
        clean_name = clean_name.replace('_', ' ').strip()
        clean_name = re.sub(r'\[(.*?)\]', r'(\1)', clean_name)

        mixartist = ""
        # 2. Extraer versión/remix dentro de paréntesis
        matches_paren = re.findall(r'\((.*?)\)', clean_name)
        if matches_paren:
            mixartist = " ".join(matches_paren).strip()
            # Formatear la versión (p. ej. "original mix")
            words_mix = mixartist.split()
            mixartist = " ".join([self._format_word(w, lower_words=self.lower_words_par) for w in words_mix])
            clean_name = re.sub(r'\s*\([^)]*\)', '', clean_name).strip()

        # 3. Intentar separar Artista y Título por los patrones más habituales
        artist, title = "", ""
        for sep in [" - ", " _ ", " ~ ", "-"]:
            if sep in clean_name:
                parts = clean_name.split(sep, 1)
                artist = parts[0].strip()
                title = parts[1].strip()
                break

        if not artist and not title:
            # Si no hay separador explícito, no asumimos y devolvemos None para fallback
            return None

        # 4. Capitalizar Artista y Título de forma limpia
        artist_words = [self._format_word(w, lower_words=self.lower_words_prefix) for w in artist.split()]
        title_words = [self._format_word(w) for w in title.split()]

        artist_formatted = " ".join(artist_words)
        title_formatted = " ".join(title_words)

        if artist_formatted and title_formatted:
            return {
                "artist": artist_formatted,
                "title": title_formatted,
                "mixartist": mixartist
            }

        return None