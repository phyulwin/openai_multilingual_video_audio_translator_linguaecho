# conftest.py — Temporary isolated application and real short PCM media fixtures.
import io
import sys
import wave
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


@pytest.fixture
def app(tmp_path):
    """Use real FFmpeg configuration but never send requests to live AI."""
    application = create_app({'TESTING': True, 'API_KEY': '', 'DATABASE': tmp_path / 'test.sqlite3',
                              'UPLOADS': tmp_path / 'uploads', 'AUDIO': tmp_path / 'audio'})
    yield application
    application.extensions['jobs'].executor.shutdown(wait=True)


@pytest.fixture
def client(app):
    """Expose Flask's isolated localhost HTTP client."""
    return app.test_client()


@pytest.fixture
def media_bytes():
    """Create a genuine decodable WAV without an external fixture download."""
    output = io.BytesIO()
    with wave.open(output, 'wb') as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(bytes(64000))
    return output.getvalue()


@pytest.fixture
def project(client, media_bytes):
    """Create a project through the same upload path as the browser."""
    response = client.post('/api/projects', data={'file': (io.BytesIO(media_bytes), 'sample.wav')})
    assert response.status_code == 201, response.json
    return response.json
