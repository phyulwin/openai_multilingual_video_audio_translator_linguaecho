# test_production.py — Isolation, CORS, resource admission, and request-owned work.
import io
import hashlib
import threading
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest
from app.schemas import ProcessRequest
from app.security import cleanup
from app.config import configuration


@pytest.fixture
def production(app):
    """Enable production policy on isolated fixture paths without creating real secrets."""
    app.config.update(PRODUCTION=True, REQUEST_JOBS=True,
                      ALLOWED_ORIGINS=['https://example.github.io'],
                      ACCESS_USERS={hashlib.sha256(token.encode()).hexdigest(): owner
                                    for token, owner in [('alice-token', 'alice'), ('bob-token', 'bob')]})
    return app


def headers(token='alice-token', **extra):
    """Model the TLS ingress and an individually provisioned caller."""
    return {'Authorization': f'Bearer {token}', 'X-Forwarded-Proto': 'https',
            'Origin': 'https://example.github.io', **extra}


def upload(client, media_bytes, token='alice-token'):
    """Upload a real decodable file as one owner."""
    response = client.post('/api/projects', headers=headers(token),
                           data={'file': (io.BytesIO(media_bytes), 'sample.wav')})
    assert response.status_code == 201, response.json
    return response.json


def test_every_project_endpoint_is_owner_scoped(production, client, media_bytes):
    """A known project ID grants no access to another user's media or mutations."""
    project = upload(client, media_bytes)
    prefix = f'/api/projects/{project["id"]}'
    assert client.get('/api/projects', headers=headers('bob-token')).json == []
    assert 'owner' not in project
    for method, suffix in [('GET', ''), ('PATCH', ''), ('DELETE', ''), ('GET', '/media'),
                           ('GET', '/audio/1'), ('GET', '/export'), ('GET', '/transcript'),
                           ('GET', '/status'), ('POST', '/process'), ('POST', '/tts'),
                           ('POST', '/translations'), ('POST', '/cancel'), ('PATCH', '/segments/1')]:
        response = client.open(prefix + suffix, method=method, headers=headers('bob-token'), json={})
        assert response.status_code == 404, (method, suffix)
    assert client.get(prefix, headers={'X-Forwarded-Proto': 'https'}).status_code == 401


def test_media_ticket_scope_range_and_revocation(production, client, media_bytes):
    """Native media can seek; tickets cannot read transcripts, cross projects, or write."""
    first, second = upload(client, media_bytes), upload(client, media_bytes)
    ticket = first['media_ticket']
    media = f'/api/projects/{first["id"]}/media?ticket={ticket}'
    tls = {'X-Forwarded-Proto': 'https'}
    assert client.get(media, headers={**tls, 'Range': 'bytes=0-10'}).status_code == 206
    assert client.get(media + 'tampered', headers=tls).status_code == 401
    assert client.get(f'/api/projects/{second["id"]}/media?ticket={ticket}', headers=tls).status_code == 401
    assert client.get(f'/api/projects/{first["id"]}/transcript?ticket={ticket}', headers=tls).status_code == 401
    assert client.delete(f'/api/projects/{first["id"]}?ticket={ticket}', headers=tls).status_code == 401
    production.config['ACCESS_USERS'] = {}
    assert client.get(media, headers=tls).status_code == 401


def test_cors_https_and_private_cache(production, client):
    """Preflight succeeds only for the approved origin, without requiring a bearer token."""
    response = client.options('/api/projects', headers=headers())
    assert response.status_code == 204
    assert response.headers['Access-Control-Allow-Origin'] == 'https://example.github.io'
    assert 'Authorization' in response.headers['Access-Control-Allow-Headers']
    assert client.get('/api/projects', headers=headers(Origin='https://evil.test')).status_code == 403
    assert client.get('/api/projects', headers=headers(**{'X-Forwarded-Proto': 'http'})).status_code == 400
    response = client.get('/api/projects', headers=headers())
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'


def test_expiry_skips_active_work_and_deletes_files(production, client, media_bytes):
    """Expired metadata and files are removed together once active processing ends."""
    project = upload(client, media_bytes)
    pid = project['id']
    store, jobs = production.extensions['store'], production.extensions['jobs']
    store.update(pid, lambda p: p.update(created_at=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()))
    jobs.active[pid] = threading.Event()
    cleanup(production)
    assert store.get(pid)
    jobs.active.clear()
    cleanup(production)
    assert not (production.config['UPLOADS'] / pid).exists()
    with pytest.raises(LookupError):
        store.get(pid)


def test_admission_is_released_after_validation_failure(production, client, media_bytes):
    """Malformed uploads cannot lock out subsequent users or exceed project quotas."""
    assert client.post('/api/projects', headers=headers()).status_code == 400
    upload(client, media_bytes)
    production.config['MAX_PROJECTS'] = 1
    assert client.post('/api/demo', headers=headers()).status_code == 429


def test_processing_stays_in_request_and_resumes(production, client, media_bytes):
    """Production jobs complete on the HTTP caller thread, preserving cached stages."""
    project = upload(client, media_bytes)
    jobs = production.extensions['jobs']
    jobs.config['API_KEY'] = 'never-sent'
    jobs.ai = MagicMock()
    caller = threading.get_ident()
    def transcribe(*args):
        """Assert no idle-background executor owns production work."""
        assert threading.get_ident() == caller
        return 'en', [{'id': 1, 'start': 0, 'end': 1, 'original_text': 'Hello.', 'favorite': False}]
    jobs.ai.transcribe.side_effect = transcribe
    jobs.ai.translate.return_value = {'1': 'Bonjour.'}
    jobs.ai.speech.return_value = 'unused.mp3'
    path = f'/api/projects/{project["id"]}/process'
    response = client.post(path, headers=headers(), json={'target': 'fr'})
    assert response.json['status'] == 'ready'
    assert not jobs.active
    client.post(path, headers=headers(), json={'target': 'fr'})
    assert jobs.ai.transcribe.call_count == 1


def test_deadline_and_ai_allowance(production, client, media_bytes):
    """Expired attempts do not call AI and per-user processing allowances reject excess."""
    project = upload(client, media_bytes)
    jobs = production.extensions['jobs']
    jobs.config.update(API_KEY='never-sent', JOB_SECONDS=-1)
    jobs.ai = MagicMock()
    path = f'/api/projects/{project["id"]}/process'
    response = client.post(path, headers=headers(), json={})
    assert response.json['status'] == 'error'
    jobs.ai.transcribe.assert_not_called()
    for _ in range(7):
        client.post(path, headers=headers(), json={})
    assert client.post(path, headers=headers(), json={}).status_code == 429


@pytest.mark.parametrize('users,origins', [({}, ['https://example.github.io']),
    ({'z' * 64: 'alice'}, ['https://example.github.io']),
    ({'a' * 64: 'alice'}, ['*']),
    ({'a' * 64: 'alice'}, ['https://example.github.io/repository/'])])
def test_production_factory_rejects_unsafe_configuration(users, origins):
    """Deployment must fail before serving requests if credentials or origins are invalid."""
    with pytest.raises(ValueError):
        configuration({'PRODUCTION': True, 'ACCESS_USERS': users, 'ALLOWED_ORIGINS': origins})
