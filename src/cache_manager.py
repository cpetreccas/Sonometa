import hashlib
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Dict, Optional

logger = logging.getLogger("Sonometa")


class CacheManager:
    """Gestor de caché persistente para Sonometa.

    Proporciona tres capas de caché:
    1. Caché de metadatos locales: almacena tags de archivos con validación mtime/size
    2. Caché de API Discogs: almacena respuestas JSON con expiración temporal
    3. Caché de imágenes: almacena carátulas descargadas en disco con hashing de URL
    """

    # Rutas de almacenamiento
    BASE_CACHE_DIR = os.path.join(
        os.getenv("APPDATA") or os.path.expanduser("~"), "Sonometa"
    )
    CACHE_DB_PATH = os.path.join(BASE_CACHE_DIR, "cache.db")
    COVERS_CACHE_DIR = os.path.join(BASE_CACHE_DIR, "cache", "covers")
    SQLITE_TIMEOUT_SEC = 30.0

    def __init__(self) -> None:
        """Inicializa el gestor de caché y prepara la base de datos SQLite."""
        # RLock evita deadlocks al encadenar helpers internos que también usan lock.
        self._lock = threading.RLock()
        self._ensure_directories()
        self._initialize_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Crea una conexión SQLite segura para acceso concurrente ligero."""
        conn = sqlite3.connect(
            self.CACHE_DB_PATH,
            timeout=self.SQLITE_TIMEOUT_SEC,
            check_same_thread=False,
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn

    @staticmethod
    def _ensure_directories() -> None:
        """Crea los directorios necesarios si no existen."""
        os.makedirs(CacheManager.BASE_CACHE_DIR, exist_ok=True)
        os.makedirs(CacheManager.COVERS_CACHE_DIR, exist_ok=True)

    def _initialize_database(self) -> None:
        """Inicializa la base de datos SQLite con las tablas requeridas."""
        with self._lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()

                # Tabla: track_cache (metadatos locales de archivos)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS track_cache (
                        file_path TEXT PRIMARY KEY,
                        mtime REAL NOT NULL,
                        file_size INTEGER NOT NULL,
                        tags_json TEXT NOT NULL,
                        synced BOOLEAN DEFAULT 0,
                        remote_id TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Migraciones para bases de datos existentes creadas previamente
                try:
                    cursor.execute("ALTER TABLE track_cache ADD COLUMN synced BOOLEAN DEFAULT 0;")
                except sqlite3.OperationalError:
                    pass  # Columna ya existe

                try:
                    cursor.execute("ALTER TABLE track_cache ADD COLUMN remote_id TEXT;")
                except sqlite3.OperationalError:
                    pass  # Columna ya existe

                try:
                    cursor.execute("ALTER TABLE track_cache ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                except sqlite3.OperationalError:
                    pass  # Columna ya existe

                # Tabla: discogs_cache (respuestas de API de Discogs)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS discogs_cache (
                        query_key TEXT PRIMARY KEY,
                        response_json TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    )
                    """
                )

                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"[CACHE] Error inicializando base de datos: {str(e)}")
                raise

    def get_unsynced_tracks(self, limit: int = 50) -> list:
        """Obtiene las canciones marcadas como no sincronizadas (synced = 0) para enviar a la nube."""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT rowid, file_path, tags_json FROM track_cache WHERE COALESCE(synced, 0) = 0 LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                conn.close()

            unsynced = []
            for row_id, file_path, tags_json in rows:
                try:
                    data = json.loads(tags_json)
                    data["local_cache_id"] = row_id
                    data["filepath_local"] = file_path
                    unsynced.append(data)
                except json.JSONDecodeError:
                    continue
            return unsynced
        except Exception as e:
            logger.error(f"[CACHE] Error obteniendo registros no sincronizados: {str(e)}")
            return []

    def mark_tracks_as_synced(self, file_paths: Optional[list] = None, row_ids: Optional[list] = None) -> int:
        """Marca registros como sincronizados usando file_path o rowid de SQLite."""
        file_paths = [p for p in (file_paths or []) if p]
        row_ids = [rid for rid in (row_ids or []) if rid is not None]
        if not file_paths and not row_ids:
            return 0

        affected_rows = 0
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                if file_paths:
                    cursor.executemany(
                        "UPDATE track_cache SET synced = 1, updated_at = CURRENT_TIMESTAMP WHERE file_path = ?",
                        [(path,) for path in file_paths],
                    )
                    affected_rows += cursor.rowcount

                if row_ids:
                    cursor.executemany(
                        "UPDATE track_cache SET synced = 1, updated_at = CURRENT_TIMESTAMP WHERE rowid = ?",
                        [(rid,) for rid in row_ids],
                    )
                    affected_rows += cursor.rowcount

                conn.commit()
                conn.close()

            return affected_rows
        except Exception as e:
            logger.error(f"[CACHE] Error marcando registros como sincronizados: {str(e)}")
            return 0

    # ========================================================================
    # 1. Caché de Metadatos Locales (Tabla: track_cache)
    # ========================================================================

    def get_cached_tags(self, file_path: str) -> Optional[Dict]:
        """
        Retorna los metadatos cacheados si el archivo existe en BBDD y su
        mtime y file_size actuales coinciden con los del disco.

        Args:
            file_path: Ruta absoluta del archivo de audio.

        Returns:
            dict con metadatos si es válido, None si no existe o está desactualizado.
        """
        if not os.path.exists(file_path):
            return None

        try:
            stat = os.stat(file_path)
            current_mtime = stat.st_mtime
            current_size = stat.st_size

            should_invalidate = False
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT mtime, file_size, tags_json FROM track_cache WHERE file_path = ?",
                    (file_path,),
                )
                row = cursor.fetchone()
                conn.close()

                if row is None:
                    return None

                cached_mtime, cached_size, tags_json = row

                # Validar que mtime y size coincidan
                if (
                    abs(cached_mtime - current_mtime) < 0.01
                    and cached_size == current_size
                ):
                    try:
                        return json.loads(tags_json)
                    except json.JSONDecodeError:
                        logger.warning(
                            f"[CACHE] JSON inválido para {os.path.basename(file_path)}"
                        )
                        return None
                else:
                    should_invalidate = True

            # Invalidar fuera de la sección crítica para no encadenar locks.
            if should_invalidate:
                self.invalidate_track_cache(file_path)
            return None

        except Exception as e:
            logger.debug(f"[CACHE] Error leyendo caché de {os.path.basename(file_path)}: {str(e)}")
            return None

    def save_tags(self, file_path: str, tags: Dict, force_unsynced: bool = False) -> bool:
        """
        Inserta o actualiza el registro de metadatos en la caché.

        Args:
            file_path: Ruta absoluta del archivo de audio.
            tags: Diccionario con metadatos (Title, Artist, Album, etc.).

        Returns:
            True si se guardó correctamente, False en caso de error.
        """
        if not os.path.exists(file_path):
            logger.warning(f"[CACHE] Archivo no existe: {file_path}")
            return False

        try:
            stat = os.stat(file_path)
            mtime = stat.st_mtime
            size = stat.st_size

            normalized_tags = dict(tags or {})
            cue_value = normalized_tags.get("cue_count")
            if cue_value is None:
                cue_value = normalized_tags.get("Cues", normalized_tags.get("CUEs", "-"))
            normalized_tags["cue_count"] = self._safe_parse_cues(cue_value)

            rating_value = normalized_tags.get("rating")
            if rating_value is None:
                rating_value = normalized_tags.get("Rating", "0★")
            normalized_tags["rating"] = self._safe_parse_rating(rating_value)

            tags_json = json.dumps(normalized_tags, ensure_ascii=False)

            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT synced, tags_json FROM track_cache WHERE file_path = ?",
                    (file_path,),
                )
                existing_row = cursor.fetchone()

                synced_value = 0
                if existing_row is not None:
                    previous_synced, previous_tags_json = existing_row
                    if force_unsynced:
                        synced_value = 0
                    elif (previous_tags_json or "") == tags_json:
                        synced_value = int(previous_synced or 0)

                cursor.execute(
                    """
                    INSERT INTO track_cache (file_path, mtime, file_size, tags_json, synced, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(file_path) DO UPDATE SET
                        mtime = excluded.mtime,
                        file_size = excluded.file_size,
                        tags_json = excluded.tags_json,
                        synced = excluded.synced,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (file_path, mtime, size, tags_json, synced_value),
                )

                conn.commit()
                conn.close()

            logger.debug(f"[CACHE] Metadatos guardados: {os.path.basename(file_path)}")
            return True

        except Exception as e:
            logger.error(f"[CACHE] Error guardando metadatos de {file_path}: {str(e)}")
            return False

    @staticmethod
    def _safe_parse_cues(raw_value) -> int:
        text = str(raw_value or "").strip()
        return int(text) if text.isdigit() else 0

    @staticmethod
    def _safe_parse_rating(raw_value) -> int:
        text = str(raw_value or "").strip().replace("★", "")
        if not text.isdigit():
            return 0
        return max(0, min(5, int(text)))

    def invalidate_track_cache(self, file_path: str) -> None:
        """Elimina el registro de caché para un archivo específico."""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM track_cache WHERE file_path = ?", (file_path,))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.debug(f"[CACHE] Error invalidando caché de {file_path}: {str(e)}")

    # ========================================================================
    # 2. Caché de API Discogs (Tabla: discogs_cache)
    # ========================================================================

    def get_discogs_response(
        self, query_key: str, max_age_days: int = 30
    ) -> Optional[Dict]:
        """
        Retorna la respuesta JSON guardada de Discogs si no ha expirado.

        Args:
            query_key: Identificador único de la búsqueda (ej: "artist:album" o release_id).
            max_age_days: Edad máxima permitida en días (default: 30).

        Returns:
            dict con la respuesta si es válida y no ha expirado, None en caso contrario.
        """
        try:
            max_age_seconds = max_age_days * 86400  # 24 * 60 * 60
            now = time.time()

            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT response_json, timestamp FROM discogs_cache WHERE query_key = ?",
                    (query_key,),
                )
                row = cursor.fetchone()
                conn.close()

                if row is None:
                    return None

                response_json, timestamp = row
                age = now - timestamp

                if age <= max_age_seconds:
                    try:
                        return json.loads(response_json)
                    except json.JSONDecodeError:
                        logger.warning(f"[CACHE] JSON inválido para query_key: {query_key}")
                        return None
                else:
                    # Expirada, invalidar
                    self.invalidate_discogs_response(query_key)
                    return None

        except Exception as e:
            logger.debug(f"[CACHE] Error leyendo respuesta Discogs ({query_key}): {str(e)}")
            return None

    def save_discogs_response(self, query_key: str, response_data: Dict) -> bool:
        """
        Inserta o actualiza una respuesta de API de Discogs en la caché.

        Args:
            query_key: Identificador único de la búsqueda.
            response_data: Diccionario con la respuesta JSON (artist, title, year, cover_url, etc.).

        Returns:
            True si se guardó correctamente, False en caso de error.
        """
        try:
            timestamp = time.time()
            response_json = json.dumps(response_data, ensure_ascii=False)

            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO discogs_cache (query_key, response_json, timestamp)
                    VALUES (?, ?, ?)
                    """,
                    (query_key, response_json, timestamp),
                )

                conn.commit()
                conn.close()

            logger.debug(f"[CACHE] Respuesta Discogs guardada: {query_key}")
            return True

        except Exception as e:
            logger.error(
                f"[CACHE] Error guardando respuesta Discogs ({query_key}): {str(e)}"
            )
            return False

    def invalidate_discogs_response(self, query_key: str) -> None:
        """Elimina el registro de caché para una búsqueda específica de Discogs."""
        try:
            with self._lock:
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM discogs_cache WHERE query_key = ?", (query_key,))
                conn.commit()
                conn.close()
        except Exception as e:
            logger.debug(f"[CACHE] Error invalidando Discogs cache ({query_key}): {str(e)}")

    # ========================================================================
    # 3. Caché de Imágenes/Carátulas (Almacenamiento en disco)
    # ========================================================================

    @staticmethod
    def _hash_url(image_url: str) -> str:
        """Genera un hash SHA256 de la URL de la imagen."""
        return hashlib.sha256(image_url.encode("utf-8")).hexdigest()

    def get_cached_cover_path(self, image_url: str) -> Optional[str]:
        """
        Retorna la ruta local del archivo de caratula si ya fue descargado previamente.

        Args:
            image_url: URL de la carátula en Discogs.

        Returns:
            Ruta local del archivo si existe, None en caso contrario.
        """
        if not image_url:
            return None

        try:
            file_hash = self._hash_url(image_url)
            # Intentar con múltiples extensiones comunes
            for ext in [".jpg", ".jpeg", ".png", ".gif"]:
                cover_path = os.path.join(self.COVERS_CACHE_DIR, f"{file_hash}{ext}")
                if os.path.exists(cover_path):
                    logger.debug(f"[CACHE] Carátula encontrada en caché: {file_hash}{ext}")
                    return cover_path

            return None

        except Exception as e:
            logger.debug(f"[CACHE] Error buscando carátula en caché: {str(e)}")
            return None

    def save_cached_cover(self, image_url: str, image_bytes: bytes) -> Optional[str]:
        """
        Guarda los bytes de una imagen descargada con un nombre basado en hash de URL.

        Args:
            image_url: URL de la carátula en Discogs.
            image_bytes: Bytes de la imagen descargada.

        Returns:
            Ruta local del archivo guardado, None en caso de error.
        """
        if not image_url or not image_bytes:
            logger.warning("[CACHE] URL o bytes de imagen vacíos")
            return None

        try:
            # Revisar extensión y crear nombre de archivo
            file_hash = self._hash_url(image_url)
            # Detectar tipo de imagen por bytes característicos
            if image_bytes.startswith(b"\xFF\xD8\xFF"):  # JPEG
                ext = ".jpg"
            elif image_bytes.startswith(b"\x89PNG"):  # PNG
                ext = ".png"
            elif image_bytes.startswith(b"GIF8"):  # GIF
                ext = ".gif"
            else:
                # Default a JPEG
                ext = ".jpg"

            cover_path = os.path.join(self.COVERS_CACHE_DIR, f"{file_hash}{ext}")

            # Evitar sobrescrituras innecesarias
            if os.path.exists(cover_path):
                logger.debug(f"[CACHE] Carátula ya existe en caché: {file_hash}{ext}")
                return cover_path

            # Guardar archivo
            with open(cover_path, "wb") as f:
                f.write(image_bytes)

            logger.debug(f"[CACHE] Carátula guardada en caché: {file_hash}{ext}")
            return cover_path

        except Exception as e:
            logger.error(f"[CACHE] Error guardando carátula en caché: {str(e)}")
            return None

