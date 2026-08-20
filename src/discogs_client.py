import json
import logging
import urllib.parse
import urllib.request
from http import HTTPStatus

logger = logging.getLogger("Sonometa")


class DiscogsClient:

    def __init__(self, token_getter):
        self._get_token = token_getter

    def _get_headers(self):
        headers = {
            "User-Agent": "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"
        }
        token = self._get_token()
        if token and not token.startswith("NO_TOKEN"):
            headers["Authorization"] = f"Discogs token={token}"
        return headers

    def search_release(self, query):
        """Busca un lanzamiento en Discogs y devuelve (artist, title, year, cover_url)."""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.discogs.com/database/search?q={encoded_query}&format=Vinyl&type=release"
            req = urllib.request.Request(url, headers=self._get_headers())

            with urllib.request.urlopen(req, timeout=5) as response:
                status_code = response.status
                status_phrase = HTTPStatus(status_code).phrase

                data = json.loads(response.read().decode("utf-8"))
                results = data.get("results", [])

                if results:
                    first_result = results[0]
                    title_full = first_result.get("title", "")
                    cover_url = first_result.get("cover_image") or first_result.get("thumb") or ""
                    year = first_result.get("year", "N/A")

                    artist, title = "", title_full
                    if " - " in title_full:
                        parts = title_full.split(" - ", 1)
                        artist, title = parts[0].strip(), parts[1].strip()

                    # Contamos cuántos resultados válidos traen imagen
                    covers_count = sum(1 for r in results if r.get("cover_image") or r.get("thumb"))

                    logger.info(
                        f"[DISCOGS] [{status_code} {status_phrase}] '{query}' | "
                        f"Año: {year} | Covers: {covers_count}"
                    )
                    return artist, title, str(year), cover_url

                logger.warning(
                    f"[DISCOGS] [{status_code} {status_phrase}] '{query}' | "
                    f"Año: N/A | Covers: 0"
                )

        except urllib.error.HTTPError as e:
            try:
                phrase = HTTPStatus(e.code).phrase
            except ValueError:
                phrase = e.reason
            logger.error(
                f"[DISCOGS] [{e.code} {phrase}] '{query}' | "
                f"Año: N/A | Covers: 0"
            )
        except Exception as e:
            logger.error(
                f"[DISCOGS] [ERR {e.__class__.__name__}] '{query}' | "
                f"Año: N/A | Covers: 0"
            )

        return "", "", "", ""

    def download_image_bytes(self, image_url):
        """Descarga los bytes de una imagen utilizando las cabeceras autenticadas."""
        try:
            req = urllib.request.Request(image_url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    return response.read()
        except Exception as e:
            logger.error(f"[DISCOGS] Error descargando imagen ({image_url}): {str(e)}")
        return None

    def get_release_images(self, query, max_images=8):
        """Devuelve una lista con las URLs de las carátulas disponibles."""
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.discogs.com/database/search?q={encoded_query}&format=Vinyl&type=release&per_page={max_images}"
            req = urllib.request.Request(url, headers=self._get_headers())

            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    results = data.get("results", [])
                    images = []
                    for res in results:
                        img = res.get("cover_image") or res.get("thumb")
                        if img and img not in images:
                            images.append(img)
                        if len(images) >= max_images:
                            break
                    return images
        except Exception as e:
            logger.error(f"[DISCOGS] Error obteniendo lista de imágenes: {str(e)}")

        return []