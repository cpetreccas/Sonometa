import pytest
from unittest.mock import MagicMock, patch
from audio_manager import AudioManager
from discogs_client import DiscogsClient

@pytest.fixture
def audio_mgr():
    return AudioManager()

@patch("audio_manager.MutagenFile")
def test_extract_metadata_flac(mock_mutagen_file, audio_mgr):
    # Simular lectura de etiquetas de texto genéricas[cite: 5]
    mock_audio = MagicMock()
    mock_audio.get.side_effect = lambda tag, default: ["Daft Punk"] if tag == "artist" else default
    mock_mutagen_file.return_value = mock_audio

    result = audio_mgr.extract_metadata("track.flac", "track.flac")

    assert result["Artist"] == "Daft Punk"
    assert result["Filename"] == "track.flac"

@patch("discogs_client.urllib.request.urlopen")
def test_discogs_search_release(mock_urlopen):
    # Simular búsqueda de lanzamientos Vinyl[cite: 5]
    client = DiscogsClient(lambda: "token_seguro")

    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = b'{"results": [{"title": "Artist - Album", "year": "2021", "cover_image": "url"}]}'
    mock_urlopen.return_value.__enter__.return_value = mock_response

    artist, title, year, cover = client.search_release("Artist Album")

    assert artist == "Artist"
    assert year == "2021"