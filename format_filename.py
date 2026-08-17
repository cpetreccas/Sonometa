import os
import re


class FilenameFormatter:
    def __init__(self):
        # Palabras reservadas que deben permanecer en minúsculas
        self.lower_words_par = {'remix', 'mix', 'rework', 'edit', 'side'}
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

        # 1. Formatear los paréntesis
        name = re.sub(r'\((.*?)\)', self._format_parentheses, name)

        if " - " in name:
            prefix, suffix = name.split(" - ", 1)
        elif "-" in name:
            prefix, suffix = name.split("-", 1)
        else:
            words = name.strip().split()
            if not words:
                return filename
            formatted = self._format_word(words[0]) + (" " + " ".join(self._format_word(w, force_lower=True) for w in words[1:]) if len(words) > 1 else "")
            return f"{formatted}{ext}"

        # 2. Formatear el Prefijo (Intérprete): ignorar mayúsculas en 'feat.', 'pres.', etc.
        prefix_words = prefix.strip().split()
        formatted_prefix_words = [
            self._format_word(w, lower_words=self.lower_words_prefix)
            for w in prefix_words
        ]
        formatted_prefix = " ".join(formatted_prefix_words)

        # 3. Formatear el Sufijo (Título)
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

