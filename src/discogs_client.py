import json
import logging
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("Sonometa")


class DiscogsAPIClient:
    """Responsable exclusivamente de la búsqueda y consumo del API de Discogs
    mediante urllib. No contiene ninguna lógica de UI ni de audio."""

    USER_AGENT = "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"
    SEARCH_URL = "https://api.discogs.com/database/search"

    def __init__(self, token: str = ""):
        self.token = token.strip()

    # ------------------------------------------------------------------
    # Cabeceras HTTP
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        """Construye las cabeceras HTTP para cada petición a la API."""
        headers = {"User-Agent": self.USER_AGENT}
        token = self.token or ""
        if token:
            headers["Authorization"] = f"Discogs token={token}"
        else:
            logger.warning(
                "No hay token de Discogs configurado. "
                "Las carátulas pueden no estar disponibles."
            )
        return headers

    # ------------------------------------------------------------------
    # Búsqueda en la API
    # ------------------------------------------------------------------

    def search(self, query: str):
        """Busca un release en Discogs filtrando por formato Vinyl.

        Returns:
            tuple (artist, title, year, cover_url).
            Todas las cadenas son vacías si no hay resultado o se produce un error.
        """
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"{self.SEARCH_URL}?q={encoded_query}&format=Vinyl&type=release"
            req = urllib.request.Request(url, headers=self._headers())

            logger.info("--- [DISCOGS REQUEST (VINYL FILTER)] ---")
            logger.info(f"URL: {url}")

            with urllib.request.urlopen(req, timeout=5) as response:
                status_code = response.status
                data = json.loads(response.read().decode("utf-8"))

                logger.info(f"--- [DISCOGS RESPONSE] (Status Code: {status_code}) ---")

                results = data.get("results", [])
                if results:
                    first = results[0]
                    title_full = first.get("title", "")
                    cover_url = first.get("cover_image") or first.get("thumb") or ""
                    year = first.get("year", "")

                    logger.info(
                        f"Discogs encontró {len(results)} resultado(s). "
                        f"Primero: '{title_full}' ({year}) | cover_url: '{cover_url}'"
                    )

                    artist, title = "", title_full
                    if " - " in title_full:
                        parts = title_full.split(" - ", 1)
                        artist, title = parts[0].strip(), parts[1].strip()

                    return artist, title, year, cover_url
                else:
                    logger.warning("Discogs no devolvió resultados para la búsqueda.")

        except urllib.error.HTTPError as e:
            logger.error(f"HTTPError Discogs API [{e.code}]: {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"URLError Discogs API: {e.reason}")
        except Exception as e:
            logger.error(f"Error consultando la API de Discogs: {str(e)}")

        return "", "", "", ""

    # ------------------------------------------------------------------
    # Descarga de imágenes
    # ------------------------------------------------------------------

    def download_image_bytes(self, image_url: str):
        """Descarga y devuelve los bytes de la imagen ubicada en *image_url*.

        Returns:
            bytes con el contenido de la imagen, o None si falla.
        """
        try:
            req = urllib.request.Request(image_url, headers=self._headers())
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    payload = response.read()
                    logger.info(f"Bytes descargados de carátula: {len(payload)}")
                    return payload
        except Exception as e:
            logger.error(f"Error descargando imagen de carátula ({image_url}): {str(e)}")
        return None

