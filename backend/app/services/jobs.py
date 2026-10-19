# jobs.py — Single-worker local job queue with cooperative cancellation.
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from openai import AuthenticationError, PermissionDeniedError, RateLimitError, APIConnectionError, APITimeoutError, BadRequestError, NotFoundError
from .ai import AI


def failure_message(exc):
    """Translate provider failures into useful messages without exposing secrets."""
    if isinstance(exc, RateLimitError):
        if getattr(exc, 'code', None) == 'insufficient_quota':
            return 'OpenAI API quota is unavailable. Check API billing and project limits, then retry; the offline demo remains available.'
        return 'OpenAI rate limit reached. Wait briefly and retry; completed stages are saved.'
    if isinstance(exc, AuthenticationError):
        return 'OpenAI rejected the server API key. Update OPENAI_API_KEY and restart the backend.'
    if isinstance(exc, PermissionDeniedError):
        return 'The API project lacks permission for the configured model. Check project model access.'
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return 'The OpenAI request could not complete. Check the network connection and retry.'
    if isinstance(exc, (BadRequestError, NotFoundError)):
        return 'The provider rejected this model or media request. Check configured model names and provider support.'
    return str(exc) if isinstance(exc, ValueError) else 'AI service failed; check server logs and API account access, then retry.'


class Jobs:
    """Bound concurrent work and serialize all mutations for a project."""
    def __init__(self, store, config):
        self.store, self.config = store, config
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='linguaecho')
        self.active = {}
        self.lock = threading.RLock()
        self.ai = AI(config)
        # Interrupted jobs cannot remain stuck after a server restart.
        for project in store.all():
            if project['status'] in ('queued', 'processing'):
                store.update(project['id'], lambda p: p.update(status='error', message='Server restarted; retry processing.'))

    def start(self, pid, options, speech_only=False):
        """Reject duplicate jobs and queue at most four outstanding projects."""
        with self.lock:
            if pid in self.active:
                raise RuntimeError('This project already has an active job.')
            if len(self.active) >= 4:
                raise RuntimeError('Processing queue is full; wait for a job to finish.')
            if not self.config['API_KEY']:
                raise ValueError('Set OPENAI_API_KEY in the server .env file, or open the clearly labeled demo.')
            self.store.update(pid, lambda p: p.update(status='queued', progress=0, message='Waiting for worker'))
            event = threading.Event()
            self.active[pid] = event
            self.executor.submit(self.run, pid, options, event, speech_only)

    def cancel(self, pid):
        """Cancel at the next checkpoint; an in-flight API call may finish first."""
        with self.lock:
            if pid in self.active:
                self.active[pid].set()

    def run(self, pid, options, event, speech_only):
        """Persist each completed stage so failures can resume without retranscribing."""
        def checkpoint(message, progress):
            if event.is_set():
                raise InterruptedError('Processing cancelled.')
            self.store.update(pid, lambda p: p.update(status='processing', message=message, progress=progress))
        try:
            checkpoint('Preparing media', 5)
            project = self.store.get(pid)
            if not project['segments']:
                folder = self.config['UPLOADS'] / pid
                source, segments = self.ai.transcribe(folder / project['media_file'], folder,
                    project['duration'], options.source, checkpoint)
                checkpoint('Saving transcript', 42)
                self.store.update(pid, lambda p: p.update(source_language=source, segments=segments))
                project = self.store.get(pid)
            target, voice = options.target, options.voice
            existing = project['translations'].get(target)
            if not existing:
                if speech_only:
                    raise ValueError('Generate a translation first.')
                texts = self.ai.translate(project['source_language'], target, project['segments'], checkpoint)
                checkpoint('Saving translation', 60)
                self.store.update(pid, lambda p: p['translations'].update({target: {'texts': texts, 'audio': {}, 'voice': voice}}))
            project = self.store.get(pid)
            self.store.update(pid, lambda p: p['translations'][target].update(voice=voice))
            for index, segment in enumerate(project['segments']):
                checkpoint(f'Generating speech {index + 1} of {len(project["segments"])}', 60 + int(38 * index / len(project['segments'])))
                sid = str(segment['id'])
                audio = self.ai.speech(pid, target, voice, sid, project['translations'][target]['texts'][sid])
                checkpoint('Saving speech', 60 + int(38 * (index + 1) / len(project['segments'])))
                self.store.update(pid, lambda p: p['translations'][target]['audio'].setdefault(voice, {}).update({sid: audio}))
            checkpoint('Finalizing project', 99)
            self.store.update(pid, lambda p: p.update(status='ready', progress=100, message='Ready to listen'))
        except InterruptedError:
            self.store.update(pid, lambda p: p.update(status='cancelled', message='Cancelled; completed stages were saved.'))
        except Exception as exc:
            logging.error('Project %s failed: %s, HTTP %s, request %s', pid,
                          type(exc).__name__, getattr(exc, 'status_code', None), getattr(exc, 'request_id', None))
            message = failure_message(exc)
            self.store.update(pid, lambda p: p.update(status='error', message=message))
        finally:
            with self.lock:
                self.active.pop(pid, None)
