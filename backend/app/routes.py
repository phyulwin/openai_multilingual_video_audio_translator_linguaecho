# routes.py — Validated local REST API and safe media delivery.
import shutil
import uuid
from pathlib import Path
import langcodes
from flask import Blueprint, current_app, jsonify, request, send_file, Response
from werkzeug.utils import secure_filename
from .config import ROOT, SUPPORTED, VOICES
from .schemas import ProcessRequest, ProjectPatch, SegmentPatch
from .services.media import EXTENSIONS, probe
from .services.exports import export
from .services.storage import now

api = Blueprint('api', __name__, url_prefix='/api')


def resources():
    """Resolve application-owned services for request and test isolation."""
    return current_app.extensions['store'], current_app.extensions['jobs']


def public(project):
    """Expose media URLs without disclosing filesystem paths."""
    result = {k: v for k, v in project.items() if k != 'media_file'}
    result['media_url'] = f'/api/projects/{project["id"]}/media'
    return result


@api.get('/health')
def health():
    """Report capabilities without returning secrets."""
    config = current_app.config
    return jsonify(status='ok', ai_configured=bool(config['API_KEY']),
        ffmpeg=bool(shutil.which(config['FFMPEG'])), ffprobe=bool(shutil.which(config['FFPROBE'])),
        max_upload_mb=config['MAX_CONTENT_LENGTH'] // 1024 // 1024,
        languages=[{'code': code, 'name': langcodes.Language.get(code).display_name()} for code in SUPPORTED],
        voices=VOICES, default_voice=config['VOICE'])


@api.route('/projects', methods=['GET', 'POST'])
def projects():
    """List durable projects or validate an uploaded local file."""
    store, _ = resources()
    if request.method == 'GET':
        return jsonify([public(p) for p in store.all()])
    upload = request.files.get('file')
    if not upload or not upload.filename:
        raise ValueError('Choose a media file.')
    extension = Path(upload.filename).suffix.lower()
    if extension not in EXTENSIONS:
        raise ValueError('Unsupported file type. Use MP4, MOV, WEBM, MKV, MP3, WAV, or M4A.')
    pid = uuid.uuid4().hex
    folder = current_app.config['UPLOADS'] / pid
    folder.mkdir()
    filename = 'original' + extension
    try:
        upload.save(folder / filename)
        metadata = probe(folder / filename, current_app.config)
        project = {'id': pid, 'name': upload.filename[:200], 'filename': secure_filename(upload.filename),
            'media_file': filename, **metadata, 'source_language': 'auto', 'segments': [], 'translations': {},
            'favorite': False, 'demo': False, 'status': 'uploaded', 'message': 'Choose languages and start processing',
            'progress': 0, 'created_at': now(), 'updated_at': now()}
        return jsonify(public(store.save(project))), 201
    except Exception:
        shutil.rmtree(folder)
        raise


@api.route('/projects/<pid>', methods=['GET', 'PATCH', 'DELETE'])
def project(pid):
    """Open, rename, favorite, or safely delete a project and its files."""
    store, jobs = resources()
    data = store.get(pid)
    if request.method == 'GET':
        return jsonify(public(data))
    with jobs.lock:
        if pid in jobs.active:
            raise RuntimeError('Cancel processing and wait for the worker before changing this project.')
        if request.method == 'PATCH':
            patch = ProjectPatch.model_validate(request.get_json()).model_dump(exclude_none=True)
            return jsonify(public(store.update(pid, lambda p: p.update(patch))))
        for root in (current_app.config['UPLOADS'], current_app.config['AUDIO']):
            path = (root / pid).resolve()
            if path.parent != root or len(pid) != 32:
                raise ValueError('Invalid project path.')
            if path.exists():
                shutil.rmtree(path)
        store.delete(pid)
    return '', 204


@api.post('/projects/<pid>/process')
@api.post('/projects/<pid>/translations')
@api.post('/projects/<pid>/tts')
def process(pid):
    """Queue AI work without blocking ordinary HTTP requests."""
    store, jobs = resources()
    project = store.get(pid)
    if project['demo']:
        raise ValueError('Demo fixtures cannot be processed by AI; upload your own media.')
    options = ProcessRequest.model_validate(request.get_json() or {})
    if project['segments'] and options.source not in ('auto', project['source_language']):
        raise ValueError('The saved source transcript is immutable. Upload a new project to transcribe a different source language.')
    jobs.start(pid, options, request.path.endswith('/tts'))
    return jsonify(public(store.get(pid))), 202


@api.post('/projects/<pid>/cancel')
def cancel(pid):
    """Signal cooperative cancellation and retain completed output."""
    store, jobs = resources()
    store.get(pid)
    jobs.cancel(pid)
    return jsonify(message='Cancellation requested; the current provider request may finish first.'), 202


@api.get('/projects/<pid>/status')
@api.get('/projects/<pid>/transcript')
def status(pid):
    """Return consistent snapshots for polling and transcript rendering."""
    return jsonify(public(resources()[0].get(pid)))


@api.patch('/projects/<pid>/segments/<int:sid>')
def segment(pid, sid):
    """Save bookmarks or invalidate every voice cache after a translation edit."""
    store, jobs = resources()
    patch = SegmentPatch.model_validate(request.get_json())
    with jobs.lock:
        if pid in jobs.active:
            raise RuntimeError('Wait for processing to finish before editing.')
        def update(project):
            row = next((s for s in project['segments'] if s['id'] == sid), None)
            if row is None:
                raise LookupError('Sentence not found')
            if patch.favorite is not None:
                row['favorite'] = patch.favorite
            if patch.translated_text is not None:
                if project['demo']:
                    raise ValueError('Demo audio is fixed; upload media to save and regenerate translations.')
                translation = project['translations'].get(patch.target)
                if not translation:
                    raise ValueError('Translation not found')
                translation['texts'][str(sid)] = patch.translated_text
                for references in translation['audio'].values():
                    references.pop(str(sid), None)
                project['message'] = 'Correction saved; regenerate speech before bilingual playback.'
        return jsonify(public(store.update(pid, update)))


@api.get('/projects/<pid>/media')
def media(pid):
    """Serve range-capable original media through a checked project record."""
    project = resources()[0].get(pid)
    return send_file(current_app.config['UPLOADS'] / pid / project['media_file'], conditional=True)


@api.get('/projects/<pid>/audio/<int:sid>')
def audio(pid, sid):
    """Resolve speech only through persisted cache references."""
    project = resources()[0].get(pid)
    translation = project['translations'].get(request.args.get('target', 'en'), {})
    reference = translation.get('audio', {}).get(request.args.get('voice', 'coral'), {}).get(str(sid))
    if not reference:
        raise LookupError('Speech is unavailable; generate it for the selected voice.')
    root = current_app.config['AUDIO']
    path = (root / reference).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Invalid speech path')
    return send_file(path, conditional=True)


@api.get('/projects/<pid>/export')
def download(pid):
    """Deliver actual UTF-8 downloads with safe generated names."""
    project = resources()[0].get(pid)
    kind = request.args.get('format', 'txt')
    content = export(project, request.args.get('target', 'en'), kind, request.args.get('language', 'bilingual'))
    return Response(content.encode('utf-8'), content_type={'json': 'application/json', 'srt': 'application/x-subrip', 'txt': 'text/plain'}[kind] + '; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename="linguaecho-{pid[:8]}.{kind}"'})


@api.post('/demo')
def demo():
    """Copy explicitly labeled offline fixtures into a normal persistent project."""
    import json
    store, _ = resources()
    source = ROOT / 'fixtures'
    if not (source / 'demo.json').exists():
        raise ValueError('Demo assets are missing; run scripts/create_demo.py first.')
    pid = uuid.uuid4().hex
    project = json.loads((source / 'demo.json').read_text(encoding='utf-8'))
    folder = current_app.config['UPLOADS'] / pid
    folder.mkdir()
    shutil.copy2(source / 'demo.mp4', folder / 'original.mp4')
    for target, translation in project['translations'].items():
        references = {}
        for segment in project['segments']:
            sid = str(segment['id'])
            relative = Path(pid) / target / 'coral' / f'{sid}.wav'
            destination = current_app.config['AUDIO'] / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / f'{target}-{sid}.wav', destination)
            references[sid] = relative.as_posix()
        translation['audio'] = {'coral': references}
    project.update(id=pid, media_file='original.mp4', created_at=now(), updated_at=now())
    return jsonify(public(store.save(project))), 201
