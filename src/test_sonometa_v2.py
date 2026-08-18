import pytest
from unittest.mock import patch, MagicMock
from src.format_filename import FilenameFormatter
from src.discogs_client import DiscogsClient

class TestFilenameFormatter:
    @pytest.fixture
    def formatter(self):
        return FilenameFormatter()

    @pytest.mark.parametrize("input_name, expected", [
        ("artist - title (REMIX).mp3", "Artist - Title (remix).mp3"),
        ("FEAT. artist - song.wav", "feat. Artist - Song.wav"),
        ("t.n.t. - dynamite.flac", "T.N.T. - Dynamite.flac"),
        ("solo_titulo_sin_guion.mp3", "Solo_titulo_sin_guion.mp3")
    ])
    def test_format_filename_pattern(self, formatter, input_name, expected):
        """Verifica la correcta capitalización y el manejo de sufijos/prefijos especiales."""
        result = formatter.format_filename_pattern(input_name)
        assert result == expected, f"El formateo falló para {input_name}"

class TestDiscogsClient:
    @pytest.fixture
    def client(self):
        # Mock de la función token_getter
        return DiscogsClient(token_getter=lambda: "test_fake_token")

    @patch('src.discogs_client.urllib.request.urlopen')
    def test_search_release_success(self, mock_urlopen, client):
        """Valida la correcta extracción de metadatos desde una respuesta JSON simulada de Discogs."""
        # Arrange: Configurar el mock de la respuesta HTTP
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"results": [{"title": "Daft Punk - Homework", "year": "1997", "cover_image": "http://img.url"}]}'
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        # Act
        artist, title, year, cover_url = client.search_release("Homework")

        # Assert
        assert artist == "Daft Punk"
        assert title == "Homework"
        assert year == "1997"
        assert cover_url == "http://img.url"
        mock_urlopen.assert_called_once()