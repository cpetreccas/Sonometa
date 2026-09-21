import threading
import logging
import os
import time
import hashlib
from typing import Any
from src.supabase_client import SupabaseClientManager

logger = logging.getLogger("Sonometa")

class CloudSyncWorker(threading.Thread):
    """Hilo en segundo plano para sincronizar cambios locales con Supabase Cloud."""

    def __init__(
        self,
        cache_manager,
        supabase_manager: SupabaseClientManager,
        interval_sec: int = 10,
        batch_size: int = 20,
        diagnostic_mode: bool = False,
    ):
        super().__init__()
        self.cache_manager = cache_manager
        self.supabase = supabase_manager
        self.interval_sec = interval_sec
        self.batch_size = max(1, int(batch_size or 20))
        env_diag = os.getenv("SONOMETA_SYNC_DIAGNOSTIC", "0").strip().lower() in ("1", "true", "yes", "on")
        self.diagnostic_mode = bool(diagnostic_mode or env_diag)
        self.daemon = True  # Permite cerrar la app sin esperar al hilo
        self._running = True
        self._stop_event = threading.Event()

    def _diag_log(self, message: str) -> None:
        if self.diagnostic_mode:
            logger.info(f"[SYNC_DIAG] {message}")

    def stop(self):
        self._running = False
        self._stop_event.set()

    def run(self):
        if threading.current_thread() is threading.main_thread():
            logger.error("[SYNC] run() fue invocado en el hilo principal. Usa start() para evitar congelar la UI.")
            return

        logger.info("Iniciando motor de sincronización Cloud en segundo plano...")
        self._diag_log(f"worker_started interval_sec={self.interval_sec} batch_size={self.batch_size}")

        # Nunca tocar widgets Tk desde este hilo; solo trabajo de I/O + logging.
        # Pausa breve para permitir transferencia de foco/UI tras cerrar login modal.
        time.sleep(1.0)

        while self._running:
            loop_t0 = time.perf_counter()
            try:
                if self.supabase.is_authenticated():
                    self._process_pending_syncs_until_idle()
                    self._process_pending_health_until_idle()
                else:
                    self._diag_log("loop_skip_not_authenticated")
            except Exception as e:
                logger.error(f"Error en bucle de sincronización: {e}")
            finally:
                self._diag_log(f"loop_elapsed_ms={((time.perf_counter() - loop_t0) * 1000):.2f}")

            # Esperar antes de la siguiente verificación sin bloquear el cierre.
            self._stop_event.wait(self.interval_sec)

    def _process_pending_syncs_until_idle(self):
        while self._running and self.supabase.is_authenticated():
            success, had_pending = self._process_pending_syncs()
            # Si no hay más registros pendientes o la sincronización falló, salir del bucle
            if not had_pending or not success:
                return
            # Breve pausa entre lotes para no saturar SQLite ni el hilo de interfaz
            self._stop_event.wait(0.2)

    def _process_pending_syncs(self):
        total_t0 = time.perf_counter()
        user_id = self.supabase.get_user_id()
        if not user_id:
            return False, False

        # 1. Obtener registros no sincronizados de SQLite cache
        fetch_t0 = time.perf_counter()
        pending_tracks = self.cache_manager.get_unsynced_tracks(limit=self.batch_size)
        fetch_ms = (time.perf_counter() - fetch_t0) * 1000
        self._diag_log(f"fetch_unsynced_ms={fetch_ms:.2f} rows={len(pending_tracks)}")
        if not pending_tracks:
            return True, False

        logger.info(f"Sincronizando {len(pending_tracks)} canciones con la nube...")
        payload_batch = []
        synced_filepaths = []
        synced_row_ids = []
        cover_extract_ms_total = 0.0
        cover_upload_ms_total = 0.0
        cover_upload_count = 0

        for track in pending_tracks:
            if self._stop_event.is_set() or not self._running:
                return False, True

            filepath = track.get("filepath_local")
            local_row_id = track.get("local_cache_id")
            if not filepath:
                continue

            # Asegurar que filename no sea nulo (fallback extraído del path local)
            filename = track.get("filename") or track.get("Filename")
            if not filename:
                filename = os.path.basename(filepath)

            filename_hash = hashlib.sha256(filepath.encode("utf-8")).hexdigest()

            # Extraer y subir portada si aplica
            cover_url = None
            cover_extract_t0 = time.perf_counter()
            cover_bytes = self._extract_cover_bytes(filepath)
            cover_extract_ms = (time.perf_counter() - cover_extract_t0) * 1000
            cover_extract_ms_total += cover_extract_ms
            if cover_extract_ms > 250:
                self._diag_log(f"slow_cover_extract_ms={cover_extract_ms:.2f} file={os.path.basename(filepath)}")
            if cover_bytes:
                cover_path = f"{user_id}/{filename_hash}.jpg"
                upload_t0 = time.perf_counter()
                cover_url = self.supabase.upload_storage_file("covers", cover_path, cover_bytes, "image/jpeg")
                upload_ms = (time.perf_counter() - upload_t0) * 1000
                cover_upload_ms_total += upload_ms
                cover_upload_count += 1
                if upload_ms > 1200:
                    self._diag_log(f"slow_cover_upload_ms={upload_ms:.2f} file={os.path.basename(filepath)}")

            # Extraer y subir fragmento de preescucha de audio (20s MP3 @ 32k Mono)
            preview_url = None
            preview_bytes = self._extract_preview_bytes(filepath)
            if preview_bytes:
                preview_path = f"{user_id}/{filename_hash}.mp3"
                preview_url = self.supabase.upload_storage_file("previews", preview_path, preview_bytes, "audio/mpeg")

            # Parsear entero para rating limpiando posibles símbolos de estrellas (★)
            raw_rating = track.get("rating") if track.get("rating") is not None else track.get("Rating")
            try:
                parsed_rating = int(str(raw_rating).replace("★", "").strip()) if raw_rating is not None else 0
            except (ValueError, TypeError):
                parsed_rating = 0

            # Parsear entero para número de cues
            raw_cues = (
                track.get("cue_count")
                if track.get("cue_count") is not None
                else (track.get("Cues") or track.get("CUEs"))
            )
            try:
                parsed_cues = int(raw_cues) if raw_cues is not None else 0
            except (ValueError, TypeError):
                parsed_cues = 0

            # Estructurar dict para PostgreSQL con schema unificado
            track_payload = {
                "user_id": user_id,
                "filepath_local": filepath,
                "filename": filename,
                "title": track.get("title") or track.get("Title") or track.get("título"),
                "artist": track.get("artist") or track.get("Artist") or track.get("intérprete"),
                "mix_artist": track.get("mix_artist") or track.get("MixArtist") or track.get("remixer") or track.get("remix"),
                "album": track.get("album") or track.get("Album") or track.get("álbum") or track.get("TALB"),
                "genre": track.get("genre") or track.get("Genre") or track.get("género") or track.get("style") or track.get("Style"),
                "publisher": track.get("publisher") or track.get("Publisher") or track.get("label") or track.get("Label") or track.get("record_label"),
                "year": track.get("year") or track.get("Year") or track.get("año"),
                "duration": track.get("duration") or track.get("Duration"),
                "comment": track.get("comment") or track.get("Comment") or track.get("comentario"),
                "cue_count": parsed_cues,
                "rating": parsed_rating,
                "cover_url": cover_url,
                "preview_audio_url": preview_url
            }
            payload_batch.append(track_payload)
            synced_filepaths.append(filepath)
            if local_row_id is not None:
                synced_row_ids.append(local_row_id)

        # 2. Enviar lote masivo a PostgreSQL
        if payload_batch:
            upsert_t0 = time.perf_counter()
            upsert_result = self.supabase.upsert_tracks_batch(payload_batch)
            upsert_ms = (time.perf_counter() - upsert_t0) * 1000
            if self._is_upsert_ok(upsert_result):
                # 3. Marcar como sincronizados en SQLite local
                mark_t0 = time.perf_counter()
                self.cache_manager.mark_tracks_as_synced(
                    file_paths=synced_filepaths,
                    row_ids=synced_row_ids,
                )
                mark_ms = (time.perf_counter() - mark_t0) * 1000
                logger.info(f"¡Éxito! {len(synced_filepaths)} canciones sincronizadas.")
                self._diag_log(
                    "batch_ok "
                    f"rows={len(payload_batch)} "
                    f"cover_extract_total_ms={cover_extract_ms_total:.2f} "
                    f"cover_upload_total_ms={cover_upload_ms_total:.2f} "
                    f"cover_upload_count={cover_upload_count} "
                    f"upsert_ms={upsert_ms:.2f} "
                    f"mark_synced_ms={mark_ms:.2f} "
                    f"total_ms={((time.perf_counter() - total_t0) * 1000):.2f}"
                )
                return True, True
            else:
                logger.error("[SYNC] Supabase no confirmó estado OK para upsert masivo.")
                self._diag_log(
                    "batch_fail "
                    f"rows={len(payload_batch)} "
                    f"cover_extract_total_ms={cover_extract_ms_total:.2f} "
                    f"cover_upload_total_ms={cover_upload_ms_total:.2f} "
                    f"cover_upload_count={cover_upload_count} "
                    f"upsert_ms={upsert_ms:.2f} "
                    f"total_ms={((time.perf_counter() - total_t0) * 1000):.2f}"
                )
                return False, True

        return True, False

    def _process_pending_health_until_idle(self):
        """Drena audio_health_cache igual que _process_pending_syncs_until_idle drena
        track_cache, en lotes, hasta que no queden pendientes o falle un lote."""
        while self._running and self.supabase.is_authenticated():
            success, had_pending = self._process_pending_health()
            if not had_pending or not success:
                return
            self._stop_event.wait(0.2)

    def _process_pending_health(self):
        """Sube a la tabla `audio_health` de Postgres los resultados de 'Evaluar salud'
        pendientes (audio_health_cache.synced = 0). Payload ya plano: no requiere
        extraer portadas/previews como sí hace _process_pending_syncs."""
        user_id = self.supabase.get_user_id()
        if not user_id:
            return False, False

        pending_health = self.cache_manager.get_unsynced_health(limit=self.batch_size)
        if not pending_health:
            return True, False

        logger.info(f"Sincronizando salud de audio de {len(pending_health)} pista(s) con la nube...")

        payload_batch = []
        synced_filepaths = []
        for health in pending_health:
            filepath = health.get("filepath_local")
            if not filepath:
                continue
            payload_batch.append({
                "user_id": user_id,
                "filepath_local": filepath,
                "health_score": health.get("health_score"),
                "integrity_status": health.get("integrity_status"),
                "has_clipping": health.get("has_clipping"),
                "lufs_integrated": health.get("lufs_integrated"),
                "cutoff_khz": health.get("cutoff_khz"),
                "bitrate_fake": health.get("bitrate_fake"),
                "analyzed_at": health.get("analyzed_at"),
            })
            synced_filepaths.append(filepath)

        if not payload_batch:
            return True, False

        upsert_result = self.supabase.upsert_health_batch(payload_batch)
        if self._is_upsert_ok(upsert_result):
            self.cache_manager.mark_health_synced(file_paths=synced_filepaths)
            logger.info(f"¡Éxito! Salud de {len(synced_filepaths)} pista(s) sincronizada.")
            return True, True
        else:
            logger.error("[SYNC] Supabase no confirmó estado OK para upsert masivo de audio_health.")
            return False, True

    @staticmethod
    def _extract_preview_bytes(filepath: str):
        """Genera el snippet de audio en MP3 ultra-ligero para la preescucha web."""
        try:
            from src.preview_generator import MediaProcessor
            return MediaProcessor.generate_audio_snippet(filepath, duration_sec=20)
        except Exception as exc:
            logger.warning(f"[SYNC] No se pudo generar preview de audio para sincronización: {exc}")
            return None

    @staticmethod
    def _extract_cover_bytes(filepath: str):
        """Import lazy para evitar coste de inicialización en hilo UI al cargar módulos."""
        try:
            from src.preview_generator import MediaProcessor
            return MediaProcessor.extract_cover_bytes(filepath)
        except Exception as exc:
            logger.warning(f"[SYNC] No se pudo extraer portada para sincronización: {exc}")
            return None

    @staticmethod
    def _extract_status_code(result: Any) -> int:
        if isinstance(result, dict):
            code = result.get("status_code")
            return int(code) if isinstance(code, int) else -1
        code = getattr(result, "status_code", None)
        return int(code) if isinstance(code, int) else -1

    def _is_upsert_ok(self, upsert_result: Any) -> bool:
        if isinstance(upsert_result, bool):
            status_code = getattr(self.supabase, "last_upsert_status_code", None)
            if status_code is None:
                return upsert_result
            return upsert_result and status_code in (200, 201)

        status_code = self._extract_status_code(upsert_result)
        if status_code in (200, 201):
            return True
        return bool(upsert_result) and status_code == -1