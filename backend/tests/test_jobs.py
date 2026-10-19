# test_jobs.py — Full mocked pipeline, cancellation, and resumable failure verification.
import threading
import time
from unittest.mock import MagicMock
from app.schemas import ProcessRequest
from app.services.jobs import failure_message
import httpx
from openai import RateLimitError


def test_quota_error_has_actionable_message():
    """Unavailable API quota is distinguishable from transient throttling."""
    response = httpx.Response(429, request=httpx.Request('POST', 'https://api.openai.com/v1/audio/transcriptions'))
    error = RateLimitError('Quota exceeded', response=response, body={'code': 'insufficient_quota'})
    assert 'quota is unavailable' in failure_message(error)
    assert 'offline demo' in failure_message(error)


def wait_for_job(jobs, pid):
    """Bound background-test waits and fail clearly if the worker hangs."""
    deadline = time.monotonic() + 5
    while pid in jobs.active and time.monotonic() < deadline:
        time.sleep(.01)
    assert pid not in jobs.active


def test_complete_pipeline_and_additional_language(app, project):
    """Background processing persists real mock results without changing original text."""
    jobs, store = app.extensions['jobs'], app.extensions['store']
    jobs.config['API_KEY'] = 'mock-key-never-sent'
    jobs.ai = MagicMock()
    jobs.ai.transcribe.return_value = ('ja', [{'id': 1, 'start': .1, 'end': 1.5, 'original_text': 'こんにちは。', 'favorite': False}])
    jobs.ai.translate.return_value = {'1': 'Hello.'}
    jobs.ai.speech.return_value = 'mocked-reference.mp3'
    pid = project['id']
    jobs.start(pid, ProcessRequest(target='en'))
    wait_for_job(jobs, pid)
    saved = store.get(pid)
    assert saved['status'] == 'ready'
    assert saved['translations']['en']['audio']['coral']['1'] == 'mocked-reference.mp3'
    jobs.ai.translate.return_value = {'1': 'Bonjour.'}
    jobs.start(pid, ProcessRequest(target='fr'))
    wait_for_job(jobs, pid)
    assert set(store.get(pid)['translations']) == {'en', 'fr'}
    assert jobs.ai.transcribe.call_count == 1
    assert store.get(pid)['segments'][0]['original_text'] == 'こんにちは。'


def test_failure_is_reported_without_fabricated_output(app, project):
    """A provider failure leaves an error state and no pretend transcription."""
    jobs = app.extensions['jobs']
    jobs.config['API_KEY'] = 'mock-key-never-sent'
    jobs.ai = MagicMock()
    jobs.ai.transcribe.side_effect = ValueError('No timed speech was detected.')
    jobs.start(project['id'], ProcessRequest())
    wait_for_job(jobs, project['id'])
    saved = app.extensions['store'].get(project['id'])
    assert saved['status'] == 'error'
    assert saved['segments'] == []
    assert saved['message'] == 'No timed speech was detected.'


def test_cancellation_before_processing(app, project):
    """Cancellation checkpoints stop work before any external request."""
    jobs = app.extensions['jobs']
    jobs.ai = MagicMock()
    event = threading.Event()
    event.set()
    jobs.run(project['id'], ProcessRequest(), event, False)
    assert app.extensions['store'].get(project['id'])['status'] == 'cancelled'
    jobs.ai.transcribe.assert_not_called()
