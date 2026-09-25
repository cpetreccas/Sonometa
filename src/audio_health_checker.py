import os
import sys
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple

import numpy as np
from scipy.signal import welch

# Efecto lateral: configura AudioSegment.converter/ffprobe apuntando a bin/ffmpeg.exe
# (o al bundle de PyInstaller) tanto en desarrollo como en el .exe empaquetado.
import preview_generator  # noqa: F401

# audioop fue retirado de la stdlib en Python 3.13+; pydub lo usa internamente.
# Mismo parche que ya aplica preview_generator.py para generar previews.
try:
    import audioop  # noqa: F401
except ImportError:
    import audioop_lts as audioop
    sys.modules["audioop"] = audioop

from pydub import AudioSegment
import pyloudnorm as pyln

logger = logging.getLogger("Sonometa")

# ------------------------------------------------------------------
# Umbrales de análisis (ajustables)
# ------------------------------------------------------------------

# Versión de los criterios de análisis. Se guarda en cada informe (health_json) y
# CacheManager trata como pendientes los informes de versiones anteriores, para que
# un cambio de umbrales/lógica obligue a re-analizar en vez de mezclar resultados.
#   1: versión inicial.
#   2: clipping a 0 dBFS por canal con rachas >= 8 muestras; LUFS estéreo real;
#      ALAC/WMA Lossless como sin pérdida; corte de frecuencias exige caída brusca;
#      integridad detecta errores de decodificación; fallos de lectura ya no cuentan
#      como clipping ni bitrate falso.
#   3: tabla corte -> bitrate recalibrada con LAME (antes leía un escalón de más:
#      un 128 real salía como 160); se guarda el bitrate aparente en el informe.
#   4: volumen correcto hasta -6 LUFS (música de club); clipping con rachas >= 12
#      muestras, sin aviso por menos de 3 rachas y crítico a partir del 0.05%.
ANALYSIS_VERSION = 4

# Por encima de esta duración, el análisis de señal se hace sobre un muestreo
# (inicio/medio/final) en vez de decodificar el archivo completo, para no disparar
# el uso de memoria ni la duración del análisis en mixes/DJ sets largos.
LONG_FILE_THRESHOLD_SEC = 600.0
SAMPLE_SEGMENT_SEC = 60.0

# Tolerancia de integridad: se acepta la mayor de las dos (duraciones cortas con
# padding/VBR necesitan el suelo absoluto de 3s; duraciones largas escalan al 5%).
INTEGRITY_RELATIVE_TOLERANCE = 0.05
INTEGRITY_MIN_TOLERANCE_SEC = 3.0

# Saturación = muestras a fondo de escala (0 dBFS). Con -0.1 dBFS se marcaban como
# saturadas las pistas bien masterizadas con el limitador a ese techo.
CLIP_DBFS_THRESHOLD = 0.0
# Margen para que el máximo positivo de un entero (32767/32768 en 16 bits, -0.0003 dBFS)
# cuente como fondo de escala.
CLIP_FULL_SCALE_TOLERANCE = 1e-4
# Rachas cortas a fondo de escala aparecen al decodificar MP3/AAC de masters altos
# (overshoot del decoder recortado a 16 bits); solo cuenta una onda aplanada de verdad.
CLIP_MIN_RUN = 12                   # ~0.27 ms a 44.1 kHz
CLIP_MIN_RUNS_WARNING = 3           # menos rachas que esto = picos aislados, no se avisa
CLIP_CRITICAL_RATIO = 0.0005        # 0.05% de muestras saturadas -> crítico

LUFS_OK_MIN = -16.0
LUFS_OK_MAX = -6.0      # música de club muy masterizada ronda -8 a -6 LUFS
LUFS_WARNING_MIN = -23.0
LUFS_WARNING_MAX = -4.0

CUTOFF_NOISE_FLOOR_DB = -50.0       # relativo al pico del espectro (Welch)
# El lowpass de un encoder es un corte brusco; una caída natural de agudos (grabación
# antigua, producción oscura) es gradual. Se compara el nivel medio 0.5-1.5 kHz por
# debajo y por encima del corte: si baja menos que esto, no es un corte de encoder.
CUTOFF_MIN_CLIFF_DB = 20.0          # medido: material oscuro legítimo ~12 dB, transcodificado ~25 dB

# Frecuencia de corte -> bitrate aparente. Calibrado midiendo el lowpass de LAME
# (el encoder de MP3 más habitual) con este mismo análisis:
#   96/112 kbps ~15.4 kHz · 128 ~16.9 · 160 ~17.6 · 192 ~18.9 · 224/256 ~19.6 · 320 ~20.3
# (224 y 256 no se distinguen: ambos se leen como 256). Cada umbral queda algo por
# debajo del punto medio entre dos escalones: ante la duda se estima el bitrate más
# alto, para no marcar como falso un archivo legítimo. Encoders antiguos (FhG/Xing)
# cortan más bajo y pueden leerse un escalón por debajo.
# Se recorre en orden descendente: el primer umbral que cumple `cutoff_khz >= khz` gana.
CUTOFF_BITRATE_TABLE = (
    (19.75, 320),   # 256 ~19.6 | 320 ~20.3
    (19.2, 256),    # 192 ~18.9 | 256 ~19.6
    (18.0, 192),    # 160 ~17.6 | 192 ~18.9
    (17.1, 160),    # 128 ~16.9 | 160 ~17.6
    (16.0, 128),    # 112 ~15.5 | 128 ~16.9
    (0.0, 96),
)

LOSSLESS_MODULES = ("flac", "wave", "aiff")

# Integridad: errores que reporta ffmpeg al decodificar el archivo completo
# (tramas dañadas que se saltan sin alterar la duración).
DECODE_ERROR_CRITICAL = 10          # nº de errores a partir del cual es crítico
DECODE_TIMEOUT_SEC = 180

# Penalización sobre 100 según el status de cada chequeo, para el "health_score" resumen
# que se persiste en caché/exportación. Ajustable sin tocar la lógica de cada chequeo.
SCORE_PENALTIES = {
    "integrity": {"warning": 15, "critical": 40},
    "clipping": {"warning": 10, "critical": 30},
    "loudness": {"warning": 8, "critical": 20},
    "cutoff": {"warning": 10, "critical": 25},
}


@dataclass(frozen=True)
class HealthCheckResult:
    """Resultado de un chequeo individual, listo para pintarse como badge en la UI."""

    status: str   # "ok" | "warning" | "critical"
    label: str    # texto corto para el título de la fila
    detail: str   # explicación larga para el cuerpo de la fila

    def to_dict(self) -> dict:
        return {"status": self.status, "label": self.label, "detail": self.detail}

    @staticmethod
    def from_dict(data: dict) -> "HealthCheckResult":
        return HealthCheckResult(
            status=data.get("status", "warning"),
            label=data.get("label", ""),
            detail=data.get("detail", ""),
        )


@dataclass(frozen=True)
class HealthReport:
    """Resultado completo de analizar un archivo. Sin ninguna dependencia de tkinter:
    se construye en un hilo secundario y se entrega a la UI ya terminado. Serializable
    (to_dict/from_dict) para persistirse en CacheManager y, desde ahí, exportarse."""

    file_path: str
    integrity: HealthCheckResult
    clipping: HealthCheckResult
    loudness: HealthCheckResult
    cutoff: HealthCheckResult
    lufs_integrated: Optional[float] = None    # valor crudo (None si no se pudo medir)
    cutoff_khz: Optional[float] = None         # valor crudo (None si no se pudo medir)
    analyzed_at: Optional[str] = None          # ISO 8601 UTC
    error: Optional[str] = None
    # Bitrate real estimado por el corte de frecuencias (tramos de CUTOFF_BITRATE_TABLE).
    # None si no hay corte de encoder (sin pérdida íntegro o caída natural de agudos).
    apparent_kbps: Optional[int] = None
    declared_kbps: Optional[int] = None
    lossless: Optional[bool] = None
    analysis_version: int = ANALYSIS_VERSION

    @property
    def health_score(self) -> int:
        """Puntuación 0-100 derivada del status de los 4 chequeos (ver SCORE_PENALTIES).
        Un archivo que no se pudo analizar puntúa 0."""
        if self.error:
            return 0
        score = 100
        for check_name, penalties in SCORE_PENALTIES.items():
            status = getattr(self, check_name).status
            score -= penalties.get(status, 0)
        return max(0, min(100, score))

    @property
    def has_clipping(self) -> bool:
        return self.clipping.status in ("warning", "critical")

    @property
    def bitrate_fake(self) -> bool:
        """True si el corte real de frecuencias sugiere una fuente transcodificada
        desde un bitrate menor al declarado (o, en lossless, indicios de pérdida previa)."""
        return self.cutoff.status in ("warning", "critical")

    @property
    def overall_status(self) -> str:
        """Peor status entre los 4 chequeos: resume la pista en un único badge."""
        statuses = {self.integrity.status, self.clipping.status, self.loudness.status, self.cutoff.status}
        if "critical" in statuses:
            return "critical"
        if "warning" in statuses:
            return "warning"
        return "ok"

    @staticmethod
    def failed(file_path: str, message: str) -> "HealthReport":
        """Informe de un archivo que no se pudo leer/decodificar: es un problema de
        integridad (crítico); el resto de chequeos quedan "unknown" (no ejecutados)
        para que no cuenten también como clipping o bitrate falso."""
        integrity = HealthCheckResult("critical", "No se pudo analizar", message)
        not_run = HealthCheckResult("unknown", "No analizado", "El archivo no se pudo leer o decodificar.")
        return HealthReport(
            file_path, integrity, not_run, not_run, not_run,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            error=message,
        )

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "integrity": self.integrity.to_dict(),
            "clipping": self.clipping.to_dict(),
            "loudness": self.loudness.to_dict(),
            "cutoff": self.cutoff.to_dict(),
            "lufs_integrated": self.lufs_integrated,
            "cutoff_khz": self.cutoff_khz,
            "analyzed_at": self.analyzed_at,
            "error": self.error,
            "apparent_kbps": self.apparent_kbps,
            "declared_kbps": self.declared_kbps,
            "lossless": self.lossless,
            "analysis_version": self.analysis_version,
        }

    @staticmethod
    def from_dict(data: dict) -> "HealthReport":
        return HealthReport(
            file_path=data["file_path"],
            integrity=HealthCheckResult.from_dict(data["integrity"]),
            clipping=HealthCheckResult.from_dict(data["clipping"]),
            loudness=HealthCheckResult.from_dict(data["loudness"]),
            cutoff=HealthCheckResult.from_dict(data["cutoff"]),
            lufs_integrated=data.get("lufs_integrated"),
            cutoff_khz=data.get("cutoff_khz"),
            analyzed_at=data.get("analyzed_at"),
            error=data.get("error"),
            apparent_kbps=data.get("apparent_kbps"),
            declared_kbps=data.get("declared_kbps"),
            lossless=data.get("lossless"),
            analysis_version=data.get("analysis_version", 1),
        )


class AudioHealthChecker:
    """Analiza integridad, clipping, volumen LUFS y corte real de frecuencias de un
    archivo de audio. Módulo puramente backend (pensado para ejecutarse en un hilo
    secundario): no importa tkinter/customtkinter ni toca ningún widget."""

    @staticmethod
    def analyze(file_path: str, cache_manager=None) -> HealthReport:
        """Analiza el archivo y devuelve un HealthReport.

        Si se pasa `cache_manager` (inyección de dependencia opcional, igual que
        AudioManager(cache_manager=...)), el resultado se persiste automáticamente
        en caché al terminar (CacheManager.save_health_report). Sin él, el módulo
        sigue siendo puro/testeable de forma aislada.
        """
        report = AudioHealthChecker._run_analysis(file_path)

        if cache_manager is not None:
            try:
                cache_manager.save_health_report(file_path, report)
            except Exception as e:
                logger.warning(f"HealthCheck: no se pudo guardar en caché '{file_path}': {e}")

        return report

    @staticmethod
    def _run_analysis(file_path: str) -> HealthReport:
        try:
            declared_duration, declared_bitrate, is_lossless = AudioHealthChecker._read_mutagen_info(file_path)
        except Exception as e:
            logger.warning(f"HealthCheck: no se pudo leer la cabecera de '{file_path}': {e}")
            return HealthReport.failed(file_path, f"No se pudo leer la cabecera del archivo: {e}")

        try:
            sample_segment, decoded_full_duration, end_decoded_duration = AudioHealthChecker._load_signal_sample(
                file_path, declared_duration
            )
        except Exception as e:
            logger.warning(f"HealthCheck: no se pudo decodificar '{file_path}': {e}")
            return HealthReport.failed(file_path, f"No se pudo decodificar el audio: {e}")

        decode_errors = AudioHealthChecker._count_decode_errors(file_path)
        integrity = AudioHealthChecker._check_integrity(
            declared_duration, decoded_full_duration, end_decoded_duration, decode_errors
        )

        frames, sample_rate = AudioHealthChecker._segment_to_float_array(sample_segment)

        clipping = AudioHealthChecker._check_clipping(frames)
        loudness, lufs_value = AudioHealthChecker._check_loudness(frames, sample_rate)
        cutoff, cutoff_khz_value, apparent_kbps = AudioHealthChecker._check_cutoff(
            frames.mean(axis=1), sample_rate, declared_bitrate, is_lossless
        )

        return HealthReport(
            file_path, integrity, clipping, loudness, cutoff,
            lufs_integrated=lufs_value,
            cutoff_khz=cutoff_khz_value,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            apparent_kbps=apparent_kbps,
            declared_kbps=declared_bitrate // 1000 if declared_bitrate else None,
            lossless=is_lossless,
        )

    # ------------------------------------------------------------------
    # Metadatos (mutagen) - solo cabecera, sin decodificar audio
    # ------------------------------------------------------------------
    @staticmethod
    def _read_mutagen_info(file_path: str) -> Tuple[Optional[float], Optional[int], bool]:
        from mutagen import File as MutagenFile

        audio = MutagenFile(file_path)
        if audio is None or audio.info is None:
            raise ValueError("Formato no reconocido o cabecera corrupta")

        info = audio.info
        duration = float(getattr(info, "length", 0.0)) or None
        bitrate = getattr(info, "bitrate", None)
        bitrate = int(bitrate) if bitrate else None

        return duration, bitrate, AudioHealthChecker._is_lossless(info)

    @staticmethod
    def _is_lossless(info) -> bool:
        """FLAC/WAV/AIFF por contenedor; en contenedores que admiten ambos tipos se
        mira el códec: ALAC dentro de .m4a (MP4Info.codec == "alac") y WMA Lossless
        (ASFInfo.codec_name). Sin esto, un ALAC (~900 kbps declarados) salía siempre
        como bitrate falso al compararse con la tabla de MP3."""
        module_name = type(info).__module__.split(".")[-1]
        if module_name in LOSSLESS_MODULES:
            return True
        codec = str(getattr(info, "codec", "") or "").lower()
        codec_name = str(getattr(info, "codec_name", "") or "").lower()
        return codec.startswith("alac") or "lossless" in codec_name

    # ------------------------------------------------------------------
    # Decodificación (pydub/ffmpeg), con muestreo para archivos largos
    # ------------------------------------------------------------------
    @staticmethod
    def _load_signal_sample(file_path: str, declared_duration: Optional[float]):
        """Devuelve (segmento_para_analisis, duracion_decodificada_total_o_None,
        duracion_decodificada_del_tramo_final).

        Archivos <= LONG_FILE_THRESHOLD_SEC: se decodifican por completo (permite
        comparar duración total para el chequeo de integridad).
        Archivos más largos (mixes/DJ sets): se decodifican solo 3 tramos de
        SAMPLE_SEGMENT_SEC (inicio, medio, final) vía ffmpeg -ss/-t, para no cargar
        el archivo entero en memoria ni demorar el análisis.
        """
        if not declared_duration or declared_duration <= LONG_FILE_THRESHOLD_SEC:
            full = AudioSegment.from_file(file_path)
            decoded_full = len(full) / 1000.0
            end_start = max(0.0, decoded_full - SAMPLE_SEGMENT_SEC)
            end_decoded = decoded_full - end_start
            return full, decoded_full, end_decoded

        starts = (
            0.0,
            max(0.0, declared_duration / 2.0 - SAMPLE_SEGMENT_SEC / 2.0),
            max(0.0, declared_duration - SAMPLE_SEGMENT_SEC),
        )

        segments = [
            AudioSegment.from_file(file_path, start_second=start, duration=SAMPLE_SEGMENT_SEC)
            for start in starts
        ]
        end_decoded = len(segments[-1]) / 1000.0

        combined = segments[0]
        for extra in segments[1:]:
            combined += extra

        return combined, None, end_decoded

    @staticmethod
    def _segment_to_float_array(segment: AudioSegment) -> Tuple[np.ndarray, int]:
        """Convierte un AudioSegment a un array numpy float64 normalizado a [-1, 1]
        con forma (frames, canales). Devuelve (frames, sample_rate). Los canales se
        conservan por separado: promediarlos a mono ocultaba la saturación de un solo
        canal (el pico quedaba a la mitad) y falseaba la medida LUFS estéreo."""
        raw = np.array(segment.get_array_of_samples())
        channels = max(1, segment.channels)
        max_value = float(2 ** (8 * segment.sample_width - 1))

        frames = raw.reshape((-1, channels)).astype(np.float64) / max_value
        return frames, segment.frame_rate

    @staticmethod
    def _count_decode_errors(file_path: str) -> Optional[Tuple[int, str]]:
        """Decodifica el archivo completo con ffmpeg sin guardar nada (-f null) y
        cuenta los errores que reporta (tramas dañadas que se saltan sin que cambie la
        duración). Solo la pista de audio (-map 0:a:0): la carátula embebida no
        cuenta. Devuelve (nº de errores, primer mensaje) o None si ffmpeg no está
        disponible o no terminó a tiempo (el chequeo se omite, no se penaliza)."""
        converter = getattr(AudioSegment, "converter", None) or "ffmpeg"
        cmd = [converter, "-nostdin", "-v", "error", "-i", file_path, "-map", "0:a:0", "-f", "null", "-"]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=DECODE_TIMEOUT_SEC, creationflags=creationflags
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            logger.debug(f"HealthCheck: chequeo de decodificación omitido para '{file_path}': {e}")
            return None

        lines = [line.strip() for line in proc.stderr.decode("utf-8", "replace").splitlines() if line.strip()]
        return len(lines), (lines[0] if lines else "")

    # ------------------------------------------------------------------
    # Chequeo 1: Integridad
    # ------------------------------------------------------------------
    @staticmethod
    def _check_integrity(
        declared_duration: Optional[float],
        decoded_full_duration: Optional[float],
        end_decoded_duration: float,
        decode_errors: Optional[Tuple[int, str]] = None,
    ) -> HealthCheckResult:
        """Combina dos señales: duración (¿está truncado?) y errores de decodificación
        (¿tiene tramas dañadas a mitad?). El resultado es el peor de los dos."""
        problems = []  # (status, label, detail)

        duration = AudioHealthChecker._check_duration(declared_duration, decoded_full_duration, end_decoded_duration)
        if duration.status != "ok":
            problems.append((duration.status, duration.label, duration.detail))

        if decode_errors is not None and decode_errors[0] > 0:
            count, first_message = decode_errors
            status = "critical" if count >= DECODE_ERROR_CRITICAL else "warning"
            detail = f"ffmpeg reportó {count} error(es) al decodificar el archivo completo"
            if first_message:
                detail += f' (p. ej. "{first_message[:120]}")'
            problems.append((status, f"Errores de decodificación ({count})", detail + "."))

        if not problems:
            return duration

        worst = "critical" if any(p[0] == "critical" for p in problems) else "warning"
        return HealthCheckResult(
            worst, " · ".join(p[1] for p in problems), " ".join(p[2] for p in problems)
        )

    @staticmethod
    def _check_duration(
        declared_duration: Optional[float],
        decoded_full_duration: Optional[float],
        end_decoded_duration: float,
    ) -> HealthCheckResult:
        if declared_duration is None:
            return HealthCheckResult(
                "warning", "Duración desconocida",
                "La cabecera no declara una duración; no se puede verificar si el archivo está truncado."
            )

        if decoded_full_duration is not None:
            # Archivo corto: comparación directa contra la duración total decodificada.
            tolerance = max(declared_duration * INTEGRITY_RELATIVE_TOLERANCE, INTEGRITY_MIN_TOLERANCE_SEC)
            diff = declared_duration - decoded_full_duration
            if diff > tolerance:
                return HealthCheckResult(
                    "warning", "Posible archivo truncado",
                    f"La cabecera declara {declared_duration:.1f}s pero solo se pudieron decodificar "
                    f"{decoded_full_duration:.1f}s (diferencia de {diff:.1f}s)."
                )
            return HealthCheckResult("ok", "Archivo íntegro", "La duración decodificada coincide con la declarada.")

        # Archivo largo (muestreado): solo se decodificó el tramo final, se usa como
        # comprobación de truncamiento (si el final no decodifica, el resto tampoco importa).
        requested_end = min(SAMPLE_SEGMENT_SEC, declared_duration)
        tolerance = max(requested_end * INTEGRITY_RELATIVE_TOLERANCE, INTEGRITY_MIN_TOLERANCE_SEC)
        diff = requested_end - end_decoded_duration
        if diff > tolerance:
            return HealthCheckResult(
                "warning", "Posible archivo truncado",
                f"El tramo final decodificó {end_decoded_duration:.1f}s de los {requested_end:.1f}s "
                f"esperados; el archivo podría estar cortado."
            )
        return HealthCheckResult(
            "ok", "Archivo íntegro",
            "Cabecera legible y tramo final decodificado correctamente (análisis muestreado por duración larga)."
        )

    # ------------------------------------------------------------------
    # Chequeo 2: Clipping
    # ------------------------------------------------------------------
    @staticmethod
    def _check_clipping(frames: np.ndarray) -> HealthCheckResult:
        """Rachas de CLIP_MIN_RUN+ muestras a fondo de escala, canal por canal."""
        if frames.size == 0:
            return HealthCheckResult("warning", "Sin datos", "No hay muestras que analizar.")

        threshold = 10 ** (CLIP_DBFS_THRESHOLD / 20.0) - CLIP_FULL_SCALE_TOLERANCE
        run_count = 0
        clipped_samples = 0
        clipped_channels = 0
        for channel in frames.T:
            is_over = np.abs(channel) >= threshold
            # Longitud de rachas consecutivas, vectorizado (evita un bucle Python sobre
            # millones de muestras).
            padded = np.concatenate(([False], is_over, [False])).astype(np.int8)
            diff = np.diff(padded)
            run_lengths = np.where(diff == -1)[0] - np.where(diff == 1)[0]
            valid_runs = run_lengths[run_lengths >= CLIP_MIN_RUN]
            if len(valid_runs):
                clipped_channels += 1
                run_count += int(len(valid_runs))
                clipped_samples += int(valid_runs.sum())

        ratio = clipped_samples / frames.size

        if run_count == 0:
            return HealthCheckResult("ok", "Sin clipping detectado", "No se encontraron picos sostenidos a 0 dBFS.")
        if run_count < CLIP_MIN_RUNS_WARNING:
            return HealthCheckResult(
                "ok", "Sin clipping relevante",
                f"{run_count} racha(s) aislada(s) a 0 dBFS ({clipped_samples} muestras): inaudible en la práctica."
            )

        channels_note = "" if frames.shape[1] == 1 else f" en {clipped_channels} de {frames.shape[1]} canal(es)"

        if ratio <= CLIP_CRITICAL_RATIO:
            return HealthCheckResult(
                "warning", f"Clipping aislado ({run_count} racha(s))",
                f"{clipped_samples} muestra(s) saturada(s) en {run_count} racha(s) breve(s){channels_note} "
                f"({ratio * 100:.4f}% del tramo analizado)."
            )

        return HealthCheckResult(
            "critical", f"Clipping significativo ({ratio * 100:.2f}%)",
            f"{clipped_samples} muestras saturadas en {run_count} racha(s){channels_note} "
            f"({ratio * 100:.2f}% del tramo analizado)."
        )

    # ------------------------------------------------------------------
    # Chequeo 3: Volumen integrado (LUFS, ITU-R BS.1770 / EBU R128)
    # ------------------------------------------------------------------
    @staticmethod
    def _check_loudness(frames: np.ndarray, sample_rate: int) -> Tuple[HealthCheckResult, Optional[float]]:
        """LUFS según BS.1770 con los canales por separado (el medidor suma su
        energía). Antes se medía la mezcla a mono, que en estéreo da ~3 LU menos."""
        try:
            meter = pyln.Meter(sample_rate)
            loudness = meter.integrated_loudness(frames if frames.shape[1] > 1 else frames[:, 0])
        except Exception as e:
            return HealthCheckResult("warning", "LUFS no disponible", f"No se pudo calcular el volumen integrado: {e}"), None

        if loudness == float("-inf") or np.isnan(loudness):
            return HealthCheckResult(
                "warning", "Silencio o señal insuficiente",
                "El tramo analizado es demasiado silencioso para medir LUFS de forma fiable."
            ), None

        label = f"{loudness:.1f} LUFS"

        if LUFS_OK_MIN <= loudness <= LUFS_OK_MAX:
            status = "ok"
            detail = f"Volumen integrado de {loudness:.1f} LUFS, dentro del rango habitual ({LUFS_OK_MIN:.0f} a {LUFS_OK_MAX:.0f} LUFS)."
        elif LUFS_WARNING_MIN <= loudness <= LUFS_WARNING_MAX:
            status = "warning"
            if loudness < LUFS_OK_MIN:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: suena bajo respecto al rango habitual ({LUFS_OK_MIN:.0f} a {LUFS_OK_MAX:.0f} LUFS)."
            else:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: suena alto/comprimido respecto al rango habitual ({LUFS_OK_MIN:.0f} a {LUFS_OK_MAX:.0f} LUFS)."
        else:
            status = "critical"
            if loudness < LUFS_WARNING_MIN:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: extremadamente bajo, revisa si el tema está descompensado."
            else:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: extremadamente alto/hipercomprimido."

        return HealthCheckResult(status, label, detail), float(loudness)

    # ------------------------------------------------------------------
    # Chequeo 4: Corte real de frecuencias (bitrate aparente vs. declarado)
    # ------------------------------------------------------------------
    @staticmethod
    def _check_cutoff(
        samples: np.ndarray, sample_rate: int, declared_bitrate: Optional[int], is_lossless: bool
    ) -> Tuple[HealthCheckResult, Optional[float], Optional[int]]:
        """Devuelve (resultado, corte en kHz, bitrate real estimado en kbps o None si
        no hay corte de encoder)."""
        if len(samples) < 1024:
            return HealthCheckResult(
                "warning", "Muestra insuficiente",
                "El tramo analizado es demasiado corto para estimar el espectro de frecuencias."
            ), None, None

        nperseg = min(8192, len(samples))
        freqs, psd = welch(samples, fs=sample_rate, nperseg=nperseg)
        psd_db = 10 * np.log10(psd + 1e-12)
        noise_floor = np.max(psd_db) + CUTOFF_NOISE_FLOOR_DB

        above_floor = np.where(psd_db > noise_floor)[0]
        cutoff_hz = freqs[above_floor[-1]] if len(above_floor) else 0.0
        cutoff_khz = cutoff_hz / 1000.0

        apparent_kbps = next(kbps for khz, kbps in CUTOFF_BITRATE_TABLE if cutoff_khz >= khz)

        # ¿Corte brusco de encoder o caída natural de agudos? Nivel medio justo por
        # debajo vs. justo por encima del corte. Sin banda por encima (corte en
        # Nyquist) no hay ningún corte artificial.
        below = (freqs >= cutoff_hz - 1500) & (freqs < cutoff_hz - 500)
        above = (freqs > cutoff_hz + 500) & (freqs <= cutoff_hz + 1500)
        cliff_db = (
            float(np.mean(psd_db[below]) - np.mean(psd_db[above]))
            if below.any() and above.any() else None
        )
        natural_rolloff = cliff_db is not None and cliff_db < CUTOFF_MIN_CLIFF_DB

        if is_lossless:
            label = f"Corte a {cutoff_khz:.1f} kHz (formato sin pérdida)"
        elif declared_bitrate:
            label = f"Corte a {cutoff_khz:.1f} kHz (Parece ~{apparent_kbps} kbps vs {declared_bitrate // 1000} kbps declarados)"
        else:
            label = f"Corte a {cutoff_khz:.1f} kHz (Parece ~{apparent_kbps} kbps; bitrate declarado desconocido)"

        if is_lossless:
            # Un formato sin pérdida no debería tener un corte artificial: si lo tiene,
            # es indicio de que la fuente original ya venía comprimida con pérdida.
            if cutoff_khz >= 19.5:
                status = "ok"
            elif cutoff_khz >= 17.5:
                status = "warning"
            else:
                status = "critical"
        elif declared_bitrate:
            declared_kbps = declared_bitrate // 1000
            if declared_kbps >= 256 and apparent_kbps <= 160:
                status = "critical"
            elif apparent_kbps < declared_kbps - 32:
                status = "warning"
            else:
                status = "ok"
        else:
            status = "ok" if apparent_kbps >= 256 else "warning"

        if status != "ok" and natural_rolloff:
            status = "ok"
            label = (
                f"Caída natural de agudos desde {cutoff_khz:.1f} kHz "
                f"(sin corte brusco de encoder: {cliff_db:.0f} dB en 2 kHz)"
            )

        # Sin corte de encoder no hay bitrate "real" que estimar: caída natural de
        # agudos, o formato sin pérdida con el espectro completo.
        has_encoder_cut = not natural_rolloff and not (is_lossless and cutoff_khz >= 19.5)
        return HealthCheckResult(status, label, label), float(cutoff_khz), (apparent_kbps if has_encoder_cut else None)


def estimate_kbps_from_cutoff(cutoff_khz: float) -> int:
    """Bitrate aparente a partir de la frecuencia de corte (tabla LAME aproximada)."""
    return next(kbps for khz, kbps in CUTOFF_BITRATE_TABLE if cutoff_khz >= khz)


LOSSLESS_EXTENSIONS = (".flac", ".wav", ".aiff", ".aif")


def format_real_bitrate(
    cutoff_khz: Optional[float],
    apparent_kbps: Optional[int],
    declared_kbps: Optional[int],
    lossless: Optional[bool],
    bitrate_fake: bool,
    file_path: str = "",
) -> str:
    """Texto de la columna "Bitrate real" de la grilla:
    "~320 kbps", "~128 kbps (declara 320)", "Sin pérdida", "~192 kbps (en FLAC)",
    "Sin corte" (caída natural de agudos) o "—" (sin análisis).

    Informes sin los campos apparent_kbps/lossless (hechos antes de añadirlos) se
    aproximan a partir de cutoff_khz y de la extensión del archivo."""
    if cutoff_khz is None:
        return "—"

    ext = os.path.splitext(file_path)[1].lower()
    if lossless is None:
        lossless = ext in LOSSLESS_EXTENSIONS
        apparent_kbps = None if (lossless and cutoff_khz >= 19.5) else estimate_kbps_from_cutoff(cutoff_khz)

    if lossless:
        if apparent_kbps is None:
            return "Sin pérdida"
        container = ext.lstrip(".").upper() or "sin pérdida"
        return f"~{apparent_kbps} kbps (en {container})"

    if apparent_kbps is None:
        return "Sin corte"
    if bitrate_fake and declared_kbps:
        return f"~{apparent_kbps} kbps (declara {declared_kbps})"
    return f"~{apparent_kbps} kbps"
