# test_api.py — Real media, persistence, validation, export, and cache-invalidation checks.
import io
from pathlib import Path
import pytest
from app.schemas import ProcessRequest
from app.services.media import chunks


def seed(app, pid):
    """Install deterministic output in an isolated project for non-AI API tests."""
    app.extensions['store'].update(pid, lambda p: p.update(source_language='ja', status='ready',
        segments=[{'id': 1, 'start': .2, 'end': 1.5, 'original_text': 'こんにちは。', 'favorite': False}],
        translations={'en': {'texts': {'1': 'Hello.'}, 'voice': 'coral', 'audio': {'coral': {'1': 'cached.mp3'}, 'alloy': {'1': 'old.mp3'}}}}))


def test_health_and_credentials(client):
    """Health advertises capabilities without leaking keys."""
    response = client.get('/api/health')
    assert response.status_code == 200
    assert len(response.json['languages']) > 50
    assert response.json['ai_configured'] is False
    assert 'API_KEY' not in response.json


def test_upload_persistence_and_range(client, project):
    """Uploaded data remains available and supports HTML5 byte-range requests."""
    assert project['kind'] == 'audio'
    assert project['duration'] == pytest.approx(2)
    assert client.get('/api/projects').json[0]['id'] == project['id']
    response = client.get(project['media_url'], headers={'Range': 'bytes=0-15'})
    assert response.status_code == 206
    assert response.data[:4] == b'RIFF'
    assert 'media_file' not in project


@pytest.mark.parametrize('filename', ['malware.exe', 'fake.mp4'])
def test_invalid_uploads(client, filename):
    """Extensions and real file content are both validated."""
    response = client.post('/api/projects', data={'file': (io.BytesIO(b'not media'), filename)})
    assert response.status_code == 400
    assert client.get('/api/projects').json == []


def test_size_limit(client, app):
    """Oversize requests return a JSON 413 before being stored."""
    app.config['MAX_CONTENT_LENGTH'] = 100
    response = client.post('/api/projects', data={'file': (io.BytesIO(bytes(200)), 'large.wav')})
    assert response.status_code == 413
    assert 'error' in response.json


def test_source_and_target_validation():
    """Provider-supported BCP-47 codes are accepted, unknown codes rejected."""
    assert ProcessRequest(source='auto', target='ar').target == 'ar'
    assert ProcessRequest(source='ja', target='uk').source == 'ja'
    with pytest.raises(ValueError):
        ProcessRequest(target='not-a-language')
    with pytest.raises(ValueError):
        ProcessRequest(target='auto')


def test_metadata_edit_and_safe_delete(client, app, project):
    """Delete removes project-owned files and preserves unrelated directories."""
    pid = project['id']
    sentinel = app.config['UPLOADS'] / 'keep.txt'
    sentinel.write_text('keep')
    result = client.patch(f'/api/projects/{pid}', json={'name': 'New name', 'favorite': True})
    assert result.json['favorite'] is True
    assert client.patch(f'/api/projects/{pid}', json={'media_file': '../keep.txt'}).status_code == 422
    assert client.delete(f'/api/projects/{pid}').status_code == 204
    assert sentinel.read_text() == 'keep'
    assert not (app.config['UPLOADS'] / pid).exists()
    assert client.get(f'/api/projects/{pid}').status_code == 404


def test_edit_keeps_original_and_invalidates_all_voices(client, app, project):
    """Saving a correction invalidates speech before any later playback."""
    pid = project['id']
    seed(app, pid)
    response = client.patch(f'/api/projects/{pid}/segments/1', json={'target': 'en', 'translated_text': 'Hi there.'})
    assert response.json['segments'][0]['original_text'] == 'こんにちは。'
    assert response.json['translations']['en']['texts']['1'] == 'Hi there.'
    assert all(not refs for refs in response.json['translations']['en']['audio'].values())
    assert client.get(f'/api/projects/{pid}/audio/1').status_code == 404


@pytest.mark.parametrize('kind,language', [('txt','original'),('txt','translated'),('txt','bilingual'),('srt','original'),('srt','translated'),('json','bilingual')])
def test_downloads(client, app, project, kind, language):
    """Every advertised download returns UTF-8 content and real attachments."""
    seed(app, project['id'])
    response = client.get(f'/api/projects/{project["id"]}/export?format={kind}&language={language}')
    assert response.status_code == 200
    assert 'attachment' in response.headers['Content-Disposition']
    text = response.data.decode('utf-8')
    if kind == 'srt':
        assert '00:00:00,200 --> 00:00:01,500' in text
    if language == 'original' or language == 'bilingual':
        assert 'こんにちは。' in text


def test_missing_key_is_honest(client, project):
    """Normal mode never substitutes fixtures for unconfigured API processing."""
    response = client.post(f'/api/projects/{project["id"]}/process', json={'target': 'en'})
    assert response.status_code == 400
    assert 'OPENAI_API_KEY' in response.json['error']['message']


def test_origin_protection(client):
    """A foreign web page cannot mutate the unauthenticated local service."""
    assert client.post('/api/demo', headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.get('/api/health', headers={'Host': 'evil.example'}).status_code == 403


def test_ffmpeg_extraction(app, project):
    """Exercise real FFmpeg encoding and chunk-size limits."""
    folder = app.config['UPLOADS'] / project['id']
    output = list(chunks(folder / 'original.wav', folder, project['duration'], app.config))
    assert output[0][0] == 0
    assert 0 < output[0][1].stat().st_size < 24 * 1024 * 1024


def test_demo_is_labelled_and_has_playable_assets(client):
    """Offline fixtures travel through the same media and speech endpoints."""
    response = client.post('/api/demo')
    assert response.status_code == 201
    project = response.json
    assert project['demo'] is True and len(project['segments']) == 6
    assert client.get(project['media_url']).status_code == 200
    assert client.get(f'/api/projects/{project["id"]}/audio/1?target=en&voice=coral').status_code == 200
    assert client.post(f'/api/projects/{project["id"]}/process', json={}).status_code == 400
