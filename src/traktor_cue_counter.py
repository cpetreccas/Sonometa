import base64
import os
import re
import struct
from typing import Dict, Any, List
from mutagen import File as MutagenFile


class TraktorCueCounter:
    """
    Extractor unificado de CUEs de Traktor para FLAC, MP3 y WAV.
    Soporta la lectura del contenedor binario DMRT y la etiqueta traktor4 (basE91).
    Excluye automáticamente los marcadores de tipo 'GRID' (Beatgrid/sistema).
    """

    CUE_TYPES = {
        0: "CUE",
        1: "FADE-IN",
        2: "FADE-OUT",
        3: "LOAD",
        4: "GRID",
        5: "LOOP"
    }

    # Alfabeto estándar basE91
    BASE91_ALPHABET = (
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        '!#$%&()*+,./:;<=>?@[]^_`{|}~"'
    )
    BASE91_DECODE_MAP = {c: i for i, c in enumerate(BASE91_ALPHABET)}

    @classmethod
    def base91_decode(cls, encoded_str: str) -> bytes:
        """Decodifica un string codificado en basE91 (usado en metadatos traktor4 de FLAC)."""
        v = -1
        b = 0
        n = 0
        out = bytearray()

        for ch in encoded_str:
            c = cls.BASE91_DECODE_MAP.get(ch)
            if c is None:
                continue
            if v < 0:
                v = c
            else:
                v += c * 91
                b |= v << n
                n += 13 if (v & 8191) > 88 else 14
                while n >= 8:
                    out.append(b & 255)
                    b >>= 8
                    n -= 8
                v = -1
        if v >= 0:
            out.append((b | (v << n)) & 255)

        return bytes(out)

    @classmethod
    def _decode_traktor_payload(cls, raw_data: bytes) -> bytes:
        """Aplica las estrategias de descompresión o decodificación según la representación del payload."""
        if not raw_data:
            return b""

        clean = raw_data.strip()

        # 1. Intento con Ascii85 (<~ ... ~>)
        if clean.startswith(b"<~") and clean.endswith(b"~>"):
            trimmed = re.sub(rb"\s+", b"", clean[2:-2])
            try:
                decoded = base64.a85decode(trimmed, adobe=True)
                if decoded:
                    return decoded
            except Exception:
                pass

        # 2. Intento con Base64 estándar
        printable_ratio = sum(1 for b in clean[:200] if 32 <= b < 127) / max(len(clean[:200]), 1)
        if printable_ratio > 0.9:
            try:
                b64_clean = re.sub(rb"\s+", b"", clean)
                padding_needed = len(b64_clean) % 4
                if padding_needed:
                    b64_clean += b"=" * (4 - padding_needed)
                decoded = base64.b64decode(b64_clean, validate=False)
                if decoded and len(decoded) > 0:
                    return decoded
            except Exception:
                pass

        return raw_data

    @classmethod
    def _extract_raw_payload(cls, file_path: str) -> bytes:
        """Extrae el payload binario de Traktor según el contenedor del archivo de audio."""
        ext = os.path.splitext(file_path)[1].lower()

        # 1. Lógica para archivos FLAC (Vorbis Comment: traktor4)
        if ext == ".flac":
            try:
                audio = MutagenFile(file_path)
                if not audio or not hasattr(audio, "keys"):
                    return b""

                for pkey in audio.keys():
                    if pkey.lower() == "traktor4" or "traktor" in pkey.lower():
                        val = audio[pkey][0]
                        if isinstance(val, str):
                            # Intentar decodificación basE91 primaria
                            decoded_b91 = cls.base91_decode(val)
                            if len(decoded_b91) > 0 and decoded_b91[:4] == b"DMRT":
                                return decoded_b91
                            # Fallback a decodificación binaria / base64
                            return cls._decode_traktor_payload(val.encode("utf-8", errors="ignore"))
                        return cls._decode_traktor_payload(val)
            except Exception:
                return b""

        # 2. Lógica para MP3 y WAV (Frame ID3 PRIV / chunk ID3)
        elif ext in [".mp3", ".wav"]:
            try:
                if ext == ".mp3":
                    from mutagen.id3 import ID3
                    tags = ID3(file_path)
                    priv_frames = tags.getall("PRIV") if tags else []
                else:
                    from mutagen.wave import WAVE
                    audio = WAVE(file_path)
                    priv_frames = audio.tags.getall("PRIV") if (audio.tags and hasattr(audio.tags, "getall")) else []

                for frame in priv_frames:
                    owner = (frame.owner or "").upper()
                    if "TRAKTOR" in owner:
                        if frame.data and len(frame.data) > 0:
                            return cls._decode_traktor_payload(frame.data)
            except Exception:
                return b""

        return b""

    @classmethod
    def _parse_cues_from_payload(cls, payload: bytes) -> List[Dict[str, Any]]:
        """Procesa el payload binario y extrae las marcas de CUE excluyendo las de tipo GRID."""
        all_cues = []

        # Estrategia 1: Parseo de contenedor CUEP ('PEUC' en Little-Endian)
        cuep_tag = b"PEUC"
        search_start = 0
        while True:
            tag_pos = payload.find(cuep_tag, search_start)
            if tag_pos == -1:
                break

            len_pos = tag_pos + 4
            if len_pos + 4 > len(payload):
                break

            (content_len,) = struct.unpack_from("<I", payload, len_pos)
            content_start = len_pos + 4
            content_end = content_start + content_len

            if content_len <= 0 or content_end > len(payload):
                search_start = tag_pos + 4
                continue

            content = payload[content_start:content_end]
            pos = 0
            n = len(content)

            while pos + 16 <= n:
                try:
                    campo_a, campo_b, const1, name_len = struct.unpack_from("<iiii", content, pos)
                except struct.error:
                    break

                if not (0 <= name_len <= 128):
                    break

                header_end = pos + 16
                name_bytes_len = name_len * 2
                name_end = header_end + name_bytes_len
                tail_end = name_end + 16

                if tail_end > n:
                    break

                try:
                    name = content[header_end:name_end].decode("utf-16-le", errors="replace")
                except Exception:
                    name = ""

                try:
                    unknown, cue_type, position_ms = struct.unpack_from("<iid", content, name_end)
                except struct.error:
                    break

                length_ms = 0.0
                next_pos = name_end + 16
                if next_pos + 8 <= n:
                    try:
                        (length_ms,) = struct.unpack_from("<d", content, next_pos)
                        next_pos += 8
                    except struct.error:
                        pass

                all_cues.append({
                    "type": cls.CUE_TYPES.get(cue_type, f"UNKNOWN({cue_type})"),
                    "raw_type": cue_type,
                    "name": name,
                    "position_ms": round(position_ms, 2),
                    "hotcue": campo_b,
                    "offset": tag_pos
                })
                pos = next_pos

            search_start = content_end

        # Estrategia 2: Escaneo directo DMRT (Fallback para bloques nativos de FLAC)
        if not all_cues and len(payload) >= 16:
            for i in range(0, len(payload) - 24):
                chunk = payload[i:i + 32]
                try:
                    ctype, hotcue_num, pos_ms = struct.unpack("<iid", chunk[:16])
                    if ctype in cls.CUE_TYPES and -1 <= hotcue_num <= 8:
                        if 0.0 <= pos_ms <= 7200000.0:
                            all_cues.append({
                                "type": cls.CUE_TYPES[ctype],
                                "raw_type": ctype,
                                "name": "",
                                "position_ms": round(pos_ms, 2),
                                "hotcue": hotcue_num,
                                "offset": i
                            })
                except Exception:
                    pass

        # Deduplicación por posición dentro del archivo
        unique_cues = []
        seen_ms = []
        all_cues.sort(key=lambda x: x["position_ms"])

        for c in all_cues:
            if not any(abs(c["position_ms"] - prev) < 50.0 for prev in seen_ms):
                seen_ms.append(c["position_ms"])
                unique_cues.append(c)

        # Filtrar exclusivamente los marcadores que NO sean tipo 'GRID'
        user_cues = [
            cue for cue in unique_cues
            if cue["type"] != "GRID" and cue["raw_type"] != 4 and cue["offset"] != 88
        ]

        return user_cues

    @classmethod
    def count_cues(cls, file_path: str) -> int:
        """
        Método principal: devuelve únicamente el total de CUEs de usuario
        (excluyendo marcadores de tipo 'GRID').
        """
        payload = cls._extract_raw_payload(file_path)
        if not payload:
            return 0

        user_cues = cls._parse_cues_from_payload(payload)
        return len(user_cues)

    @classmethod
    def get_cue_info(cls, file_path: str) -> Dict[str, Any]:
        """Devuelve un informe completo con el recuento y la lista de CUEs filtrados."""
        payload = cls._extract_raw_payload(file_path)
        if not payload:
            return {"count": 0, "has_cues": False, "cues": []}

        user_cues = cls._parse_cues_from_payload(payload)
        return {
            "count": len(user_cues),
            "has_cues": len(user_cues) > 0,
            "cues": user_cues
        }


# Example usage:
if __name__ == "__main__":
    test_file = "ruta/a/tu/archivo.flac"  # O .mp3 / .wav

    # 1. Obtención directa de la cantidad
    total_cues = TraktorCueCounter.count_cues(test_file)
    print(f"Número de CUEs reales (sin GRID): {total_cues}")

    # 2. Información detallada
    info = TraktorCueCounter.get_cue_info(test_file)
    print(f"Total CUEs: {info['count']}")
    for c in info["cues"]:
        print(f"  -> Tipo: {c['type']} | Posición: {c['position_ms']} ms | Hotcue Slot: {c['hotcue']}")