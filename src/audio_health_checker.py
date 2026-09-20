import sys
import logging
from dataclasses import dataclass
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

# Por encima de esta duración, el análisis de señal se hace sobre un muestreo
# (inicio/medio/final) en vez de decodificar el archivo completo, para no disparar
# el uso de memoria ni la duración del análisis en mixes/DJ sets largos.
LONG_FILE_THRESHOLD_SEC = 600.0
SAMPLE_SEGMENT_SEC = 60.0

# Tolerancia de integridad: se acepta la mayor de las dos (duraciones cortas con
# padding/VBR necesitan el suelo absoluto de 3s; duraciones largas escalan al 5%).
INTEGRITY_RELATIVE_TOLERANCE = 0.05
INTEGRITY_MIN_TOLERANCE_SEC = 3.0

CLIP_DBFS_THRESHOLD = -0.1          # picos a partir de aquí cuentan como saturación
CLIP_MIN_RUN = 3                    # nº de muestras consecutivas para no ser ruido/inter-sample peak
CLIP_CRITICAL_RATIO = 0.0001        # 0.01% de muestras saturadas -> crítico

LUFS_OK_MIN = -16.0
LUFS_OK_MAX = -8.0
LUFS_WARNING_MIN = -23.0
LUFS_WARNING_MAX = -6.0

CUTOFF_NOISE_FLOOR_DB = -50.0       # relativo al pico del espectro (Welch)

# Corte típico del filtro lowpass de encoders MP3 habituales (aprox., LAME/Xing).
# Se recorre en orden descendente: el primer umbral que cumple `cutoff_khz >= khz` gana.
CUTOFF_BITRATE_TABLE = (
    (19.5, 320),
    (18.5, 256),
    (17.5, 192),
    (16.0, 160),
    (0.0, 128),
)

LOSSLESS_MODULES = ("flac", "wave", "aiff")


@dataclass(frozen=True)
class HealthCheckResult:
    """Resultado de un chequeo individual, listo para pintarse como badge en la UI."""

    status: str   # "ok" | "warning" | "critical"
    label: str    # texto corto para el título de la fila
    detail: str   # explicación larga para el cuerpo de la fila


@dataclass(frozen=True)
class HealthReport:
    """Resultado completo de analizar un archivo. Sin ninguna dependencia de tkinter:
    se construye en un hilo secundario y se entrega a la UI ya terminado."""

    file_path: str
    integrity: HealthCheckResult
    clipping: HealthCheckResult
    loudness: HealthCheckResult
    cutoff: HealthCheckResult
    error: Optional[str] = None

    @staticmethod
    def failed(file_path: str, message: str) -> "HealthReport":
        placeholder = HealthCheckResult("critical", "No disponible", message)
        return HealthReport(file_path, placeholder, placeholder, placeholder, placeholder, error=message)


class AudioHealthChecker:
    """Analiza integridad, clipping, volumen LUFS y corte real de frecuencias de un
    archivo de audio. Módulo puramente backend (pensado para ejecutarse en un hilo
    secundario): no importa tkinter/customtkinter ni toca ningún widget."""

    @staticmethod
    def analyze(file_path: str) -> HealthReport:
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

        integrity = AudioHealthChecker._check_integrity(declared_duration, decoded_full_duration, end_decoded_duration)

        samples, sample_rate = AudioHealthChecker._segment_to_float_array(sample_segment)

        clipping = AudioHealthChecker._check_clipping(samples)
        loudness = AudioHealthChecker._check_loudness(samples, sample_rate)
        cutoff = AudioHealthChecker._check_cutoff(samples, sample_rate, declared_bitrate, is_lossless)

        return HealthReport(file_path, integrity, clipping, loudness, cutoff)

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

        module_name = type(info).__module__.split(".")[-1]
        is_lossless = module_name in LOSSLESS_MODULES

        return duration, bitrate, is_lossless

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
        """Convierte un AudioSegment a un array numpy float64 normalizado a [-1, 1].
        Devuelve (muestras, sample_rate); si hay más de un canal, se promedian a mono
        (suficiente para clipping/LUFS/espectro, y evita duplicar el análisis por canal)."""
        raw = np.array(segment.get_array_of_samples())
        channels = segment.channels
        max_value = float(2 ** (8 * segment.sample_width - 1))

        if channels > 1:
            raw = raw.reshape((-1, channels)).mean(axis=1)

        samples = raw.astype(np.float64) / max_value
        return samples, segment.frame_rate

    # ------------------------------------------------------------------
    # Chequeo 1: Integridad
    # ------------------------------------------------------------------
    @staticmethod
    def _check_integrity(
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
    def _check_clipping(samples: np.ndarray) -> HealthCheckResult:
        if len(samples) == 0:
            return HealthCheckResult("warning", "Sin datos", "No hay muestras que analizar.")

        threshold = 10 ** (CLIP_DBFS_THRESHOLD / 20.0)
        is_over = np.abs(samples) >= threshold

        # Longitud de rachas consecutivas, vectorizado (evita un bucle Python sobre
        # millones de muestras).
        padded = np.concatenate(([False], is_over, [False])).astype(np.int8)
        diff = np.diff(padded)
        run_starts = np.where(diff == 1)[0]
        run_ends = np.where(diff == -1)[0]
        run_lengths = run_ends - run_starts
        valid_runs = run_lengths[run_lengths >= CLIP_MIN_RUN]

        run_count = int(len(valid_runs))
        clipped_samples = int(valid_runs.sum())
        ratio = clipped_samples / len(samples)

        if run_count == 0:
            return HealthCheckResult("ok", "Sin clipping detectado", "No se encontraron picos sostenidos a 0 dBFS.")

        if ratio <= CLIP_CRITICAL_RATIO:
            return HealthCheckResult(
                "warning", f"Clipping aislado ({run_count} racha(s))",
                f"{clipped_samples} muestra(s) saturada(s) en {run_count} racha(s) breve(s) "
                f"({ratio * 100:.4f}% del tramo analizado)."
            )

        return HealthCheckResult(
            "critical", f"Clipping significativo ({ratio * 100:.2f}%)",
            f"{clipped_samples} muestras saturadas en {run_count} racha(s) ({ratio * 100:.2f}% del tramo analizado)."
        )

    # ------------------------------------------------------------------
    # Chequeo 3: Volumen integrado (LUFS, ITU-R BS.1770 / EBU R128)
    # ------------------------------------------------------------------
    @staticmethod
    def _check_loudness(samples: np.ndarray, sample_rate: int) -> HealthCheckResult:
        try:
            meter = pyln.Meter(sample_rate)
            loudness = meter.integrated_loudness(samples)
        except Exception as e:
            return HealthCheckResult("warning", "LUFS no disponible", f"No se pudo calcular el volumen integrado: {e}")

        if loudness == float("-inf") or np.isnan(loudness):
            return HealthCheckResult(
                "warning", "Silencio o señal insuficiente",
                "El tramo analizado es demasiado silencioso para medir LUFS de forma fiable."
            )

        label = f"{loudness:.1f} LUFS"

        if LUFS_OK_MIN <= loudness <= LUFS_OK_MAX:
            status = "ok"
            detail = f"Volumen integrado de {loudness:.1f} LUFS, dentro del rango habitual de streaming/club (-16 a -8 LUFS)."
        elif LUFS_WARNING_MIN <= loudness <= LUFS_WARNING_MAX:
            status = "warning"
            if loudness < LUFS_OK_MIN:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: suena bajo respecto al rango habitual (-16 a -8 LUFS)."
            else:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: suena alto/comprimido respecto al rango habitual (-16 a -8 LUFS)."
        else:
            status = "critical"
            if loudness < LUFS_WARNING_MIN:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: extremadamente bajo, revisa si el tema está descompensado."
            else:
                detail = f"Volumen integrado de {loudness:.1f} LUFS: extremadamente alto/hipercomprimido."

        return HealthCheckResult(status, label, detail)

    # ------------------------------------------------------------------
    # Chequeo 4: Corte real de frecuencias (bitrate aparente vs. declarado)
    # ------------------------------------------------------------------
    @staticmethod
    def _check_cutoff(
        samples: np.ndarray, sample_rate: int, declared_bitrate: Optional[int], is_lossless: bool
    ) -> HealthCheckResult:
        if len(samples) < 1024:
            return HealthCheckResult(
                "warning", "Muestra insuficiente",
                "El tramo analizado es demasiado corto para estimar el espectro de frecuencias."
            )

        nperseg = min(8192, len(samples))
        freqs, psd = welch(samples, fs=sample_rate, nperseg=nperseg)
        psd_db = 10 * np.log10(psd + 1e-12)
        noise_floor = np.max(psd_db) + CUTOFF_NOISE_FLOOR_DB

        above_floor = np.where(psd_db > noise_floor)[0]
        cutoff_hz = freqs[above_floor[-1]] if len(above_floor) else 0.0
        cutoff_khz = cutoff_hz / 1000.0

        apparent_kbps = next(kbps for khz, kbps in CUTOFF_BITRATE_TABLE if cutoff_khz >= khz)

        if declared_bitrate:
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

        return HealthCheckResult(status, label, label)
