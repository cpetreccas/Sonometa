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

    def __init__(self) -> None:
        """Inicializa el gestor de caché y prepara la base de datos SQLite."""
        self._lock = threading.Lock()
        self._ensure_directories()
        self._initialize_database()

    @staticmethod
    def _ensure_directories() -> None:
        """Crea los directorios necesarios si no existen."""
        os.makedirs(CacheManager.BASE_CACHE_DIR, exist_ok=True)
        os.makedirs(CacheManager.COVERS_CACHE_DIR, exist_ok=True)

    def _initialize_database(self) -> None:
        """Inicializa la base de datos SQLite con las tablas requeridas."""
        with self._lock:
            try:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                cursor = conn.cursor()

                # Tabla: track_cache (metadatos locales de archivos)
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS track_cache (
                        file_path TEXT PRIMARY KEY,
                        mtime REAL NOT NULL,
                        file_size INTEGER NOT NULL,
                        tags_json TEXT NOT NULL
                    )
                    """
                )

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

            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
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
                    # Archivo modificado, invalidar caché
                    self.invalidate_track_cache(file_path)
                    return None

        except Exception as e:
            logger.debug(f"[CACHE] Error leyendo caché de {os.path.basename(file_path)}: {str(e)}")
            return None

    def save_tags(self, file_path: str, tags: Dict) -> bool:
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
            tags_json = json.dumps(tags, ensure_ascii=False)

            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT OR REPLACE INTO track_cache (file_path, mtime, file_size, tags_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (file_path, mtime, size, tags_json),
                )

                conn.commit()
                conn.close()

            logger.debug(f"[CACHE] Metadatos guardados: {os.path.basename(file_path)}")
            return True

        except Exception as e:
            logger.error(f"[CACHE] Error guardando metadatos de {file_path}: {str(e)}")
            return False

    def invalidate_track_cache(self, file_path: str) -> None:
        """Elimina el registro de caché para un archivo específico."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
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
                conn = sqlite3.connect(self.CACHE_DB_PATH)
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
                conn = sqlite3.connect(self.CACHE_DB_PATH)
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
                conn = sqlite3.connect(self.CACHE_DB_PATH)
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

    # ========================================================================
    # Utilidades de limpieza y mantenimiento
    # ========================================================================

    def cleanup_expired_discogs_cache(self, max_age_days: int = 30) -> int:
        """
        Elimina entradas de caché de Discogs que han expirado.

        Args:
            max_age_days: Edad máxima permitida en días.

        Returns:
            Número de registros eliminados.
        """
        try:
            max_age_seconds = max_age_days * 86400
            now = time.time()

            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM discogs_cache WHERE ? - timestamp > ?",
                    (now, max_age_seconds),
                )

                affected = cursor.rowcount
                conn.commit()
                conn.close()

            if affected > 0:
                logger.info(f"[CACHE] {affected} registros de Discogs expirados eliminados")
            return affected

        except Exception as e:
            logger.error(f"[CACHE] Error limpiando caché expirada: {str(e)}")
            return 0

    def clear_all_caches(self) -> None:
        """Limpia todas las cachés (SQLite y archivos de carátulas)."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM track_cache")
                cursor.execute("DELETE FROM discogs_cache")
                conn.commit()
                conn.close()

            logger.info("[CACHE] Base de datos de caché vaciada")

            # Limpiar carátulas en disco (opcional: comentar si quieres conservar imágenes)
            # try:
            #     for file in os.listdir(self.COVERS_CACHE_DIR):
            #         file_path = os.path.join(self.COVERS_CACHE_DIR, file)
            #         if os.path.isfile(file_path):
            #             os.remove(file_path)
            #     logger.info("[CACHE] Carátulas en caché eliminadas")
            # except Exception as e:
            #     logger.warning(f"[CACHE] Error limpiando carátulas: {str(e)}")

        except Exception as e:
            logger.error(f"[CACHE] Error limpiando cachés: {str(e)}")

    def get_cache_stats(self) -> Dict:
        """Retorna estadísticas sobre el tamaño y contenido de las cachés."""
        try:
            with self._lock:
                conn = sqlite3.connect(self.CACHE_DB_PATH)
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM track_cache")
                track_count = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM discogs_cache")
                discogs_count = cursor.fetchone()[0]

                conn.close()

            # Tamaño de archivos de carátulas
            covers_size = 0
            covers_count = 0
            if os.path.exists(self.COVERS_CACHE_DIR):
                for file in os.listdir(self.COVERS_CACHE_DIR):
                    file_path = os.path.join(self.COVERS_CACHE_DIR, file)
                    if os.path.isfile(file_path):
                        covers_count += 1
                        covers_size += os.path.getsize(file_path)

            db_size = os.path.getsize(self.CACHE_DB_PATH) if os.path.exists(
                self.CACHE_DB_PATH
            ) else 0

            return {
                "track_cache_entries": track_count,
                "discogs_cache_entries": discogs_count,
                "covers_cached": covers_count,
                "covers_size_mb": round(covers_size / (1024 * 1024), 2),
                "db_size_mb": round(db_size / (1024 * 1024), 2),
            }

        except Exception as e:
            logger.error(f"[CACHE] Error obteniendo estadísticas: {str(e)}")
            return {}

