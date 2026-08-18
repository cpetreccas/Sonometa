import os
import unittest
from unittest.mock import MagicMock, patch

# Importaciones de los módulos de tu proyecto
from audio_manager import AudioManager
from catalog_manager import CatalogManager
from format_filename import FilenameFormatter


class TestSonometa(unittest.TestCase):
    """Conjunto de pruebas unitarias para los componentes core de Sonometa."""

    def setUp(self):
        """Configuración inicial antes de cada test."""
        self.audio_manager = AudioManager()
        self.formatter = FilenameFormatter()

        # Mock de la app principal para CatalogManager
        self.mock_app = MagicMock()
        self.mock_app.CLEAR_OPTION = "<Limpiar>"
        self.catalog_manager = CatalogManager(self.mock_app)

    # ------------------------------------------------------------------
    # Pruebas para FilenameFormatter
    # ------------------------------------------------------------------
    def test_format_filename_standard(self):
        """Verifica que el nombre de archivo con formato 'Artista - Título' se capitalice correctamente."""
        raw_name = "artist name - song title (feat. guest) (remix).mp3"
        expected = "Artist Name - Song title (feat. guest) (remix).mp3"
        result = self.formatter.format_filename_pattern(raw_name)
        self.assertEqual(result, expected)

    def test_format_filename_dotted_initials(self):
        """Verifica que las siglas separadas por puntos (ej. T.N.T.) se mantengan en mayúsculas."""
        raw_name = "t.n.t. - heavy metal.wav"
        formatted = self.formatter.format_filename_pattern(raw_name)
        self.assertTrue(formatted.startswith("T.N.T."))

    # ------------------------------------------------------------------
    # Pruebas para CatalogManager
    # ------------------------------------------------------------------
    def test_normalize_catalog_text(self):
        """Comprueba la normalización de texto (primera letra mayúscula, resto minúsculas)."""
        input_text = "tEcHnO"
        expected = "Techno"
        result = self.catalog_manager.normalize_catalog_text(input_text)
        self.assertEqual(result, expected)

    def test_add_catalog_value_success(self):
        """Verifica la adición exitosa de un nuevo elemento al catálogo."""
        field = "Genre"
        value = "Deep House"

        # Asegurar estado inicial limpio
        self.catalog_manager.catalog_values[field] = []

        added = self.catalog_manager.add_catalog_value(
            field, value, persist=False
        )
        self.assertTrue(added)
        self.assertIn("Deep house", self.catalog_manager.catalog_values[field])

    def test_add_catalog_value_duplicate(self):
        """Verifica que no se agreguen elementos duplicados al catálogo."""
        field = "Genre"
        value = "Techno"
        self.catalog_manager.catalog_values[field] = ["Techno"]

        added = self.catalog_manager.add_catalog_value(
            field, "techno", persist=False
        )
        self.assertFalse(added)

    # ------------------------------------------------------------------
    # Pruebas para AudioManager (utilizando Mocks)
    # ------------------------------------------------------------------
    @patch("os.path.splitext")
    @patch("mutagen.wave.WAVE")
    def test_extract_metadata_wav(self, mock_wave, mock_splitext):
        """Prueba la extracción de metadatos de un archivo .wav simulado."""
        mock_splitext.return_value = ("song", ".wav")

        # Configurar las etiquetas simuladas retornadas por mutagen
        mock_audio_instance = MagicMock()
        mock_audio_instance.tags = {
            "TIT2": "Test Title",
            "TPE1": "Test Artist",
            "TALB": "Test Album",
            "TCON": "Techno",
        }
        mock_wave.return_value = mock_audio_instance

        # Mock de la lectura de carátulas para evitar accesos al disco
        self.audio_manager.extract_cover_bytes = MagicMock(return_value=None)

        metadata = self.audio_manager.extract_metadata(
            "dummy_path/song.wav", "song.wav"
        )

        self.assertEqual(metadata["Filename"], "song.wav")
        self.assertEqual(metadata["Title"], "Test Title")
        self.assertEqual(metadata["Artist"], "Test Artist")
        self.assertEqual(metadata["Album"], "Test Album")
        self.assertEqual(metadata["Cover"], "No")

    # ------------------------------------------------------------------
    # Pruebas para DiscogsClient
    # ------------------------------------------------------------------
    @patch("urllib.request.urlopen")
    def test_discogs_search_release(self, mock_urlopen):
        """Prueba la respuesta y parseo exitoso de la API de Discogs (Mocked)."""
        from discogs_client import DiscogsClient

        # Respuesta JSON simulada de la API de Discogs
        mock_json_response = b"""
        {
            "results": [
                {
                    "title": "Daft Punk - Around The World",
                    "cover_image": "https://example.com/cover.jpg",
                    "year": "1997"
                }
            ]
        }
        """

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = mock_json_response
        mock_response.__enter__.return_value = mock_response

        mock_urlopen.return_value = mock_response

        client = DiscogsClient(token_getter=lambda: "fake_token")
        artist, title, year, cover_url = client.search_release(
            "Daft Punk Around The World"
        )

        self.assertEqual(artist, "Daft Punk")
        self.assertEqual(title, "Around The World")
        self.assertEqual(year, "1997")
        self.assertEqual(cover_url, "https://example.com/cover.jpg")


if __name__ == "__main__":
    unittest.main()