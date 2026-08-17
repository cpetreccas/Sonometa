import json
import logging
import urllib.parse
import urllib.request

logger = logging.getLogger("Sonometa")


class DiscogsClient:

    def __init__(self, token_getter):
        """
        :param token_getter: Función/callback que devuelve el token de Discogs actual.
        """
        self._get_token = token_getter

    def _get_headers(self):
        headers = {
            "User-Agent":
                "SonometaTagApp/1.0 (Mozilla/5.0 Windows NT 10.0; Win64; x64)"
        }
        token = self._get_token()
        if token:
            headers["Authorization"] = f"Discogs token={token}"
        else:
            logger.warning(
                "No hay token de Discogs configurado. Las carátulas pueden no estar disponibles."
            )
        return headers

    def search_release(self, query):
        """Busca un lanzamiento de tipo 'Vinyl' en la API de Discogs por término de búsqueda.

        Devuelve una tupla (artist, title, year, cover_url).
        """
        try:
            encoded_query = urllib.parse.quote(query)
            url = f"https://api.discogs.com/database/search?q={encoded_query}&format=Vinyl&type=release"
            req = urllib.request.Request(url, headers=self._get_headers())

            logger.info("--- [DISCOGS REQUEST (VINYL FILTER)] ---")
            logger.info(f"URL: {url}")

            with urllib.request.urlopen(req, timeout=5) as response:
                status_code = response.status
                raw_response = response.read().decode("utf-8")
                data = json.loads(raw_response)

                logger.info(
                    f"--- [DISCOGS RESPONSE] (Status Code: {status_code}) ---")

                results = data.get("results", [])
                if results:
                    first_result = results[0]
                    title_full = first_result.get("title", "")
                    cover_url = (first_result.get("cover_image")
                                 or first_result.get("thumb") or "")
                    year = first_result.get("year", "")

                    logger.info(
                        f"Discogs encontró {len(results)} resultado(s). "
                        f"Primero: '{title_full}' ({year}) | cover_url: '{cover_url}'"
                    )

                    artist = ""
                    title = title_full
                    if " - " in title_full:
                        parts = title_full.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()

                    return artist, title, year, cover_url
                else:
                    logger.warning(
                        "Discogs no devolvió resultados para la búsqueda.")

        except urllib.error.HTTPError as e:
            logger.error(f"HTTPError Discogs API [{e.code}]: {e.reason}")
        except urllib.error.URLError as e:
            logger.error(f"URLError Discogs API: {e.reason}")
        except Exception as e:
            logger.error(f"Error consultando la API de Discogs: {str(e)}")

        return "", "", "", ""

    def download_image_bytes(self, image_url):
        """Descarga una imagen de la URL especificada usando las cabeceras autenticadas."""
        try:
            req = urllib.request.Request(
                image_url, headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    payload = response.read()
                    logger.info(
                        f"Bytes descargados de carátula: {len(payload)}")
                    return payload
        except Exception as e:
            logger.error(
                f"Error descargando imagen de carátula ({image_url}): {str(e)}"
            )
        return None