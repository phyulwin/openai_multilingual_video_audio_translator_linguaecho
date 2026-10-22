# security.py — Individual access, scoped media tickets, and temporary resource limits.
import hashlib
import secrets
import shutil
import threading
import time
from datetime import datetime
from flask import current_app, g, jsonify, request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired


def check_capacity(config):
    """Stop admission and AI stages before exhausting the bounded temporary volume."""
    total = 0
    for root in (config['UPLOADS'], config['AUDIO']):
        for path in root.rglob('*'):
            try:
                if path.is_file():
                    total += path.stat().st_size
            except FileNotFoundError:
                # A different HTTP thread may have finished deleting this file.
                continue
    if total >= config['MAX_TEMP_BYTES']:
        raise ValueError('Temporary storage is full; delete projects and retry.')


def media_ticket(project):
    """Issue read-only project capabilities without exposing an account credential."""
    return current_app.extensions['tickets'].dumps([project['id'], project.get('owner')])


def cleanup(app):
    """Expire inactive projects on requests; active work is never deleted underneath a worker."""
    jobs, store = app.extensions['jobs'], app.extensions['store']
    with jobs.lock:
        for project in store.all():
            age = time.time() - datetime.fromisoformat(project['created_at']).timestamp()
            if age < app.config['TEMP_TTL_SECONDS'] or project['id'] in jobs.active:
                continue
            for root in (app.config['UPLOADS'], app.config['AUDIO']):
                path = (root / project['id']).resolve()
                if path.parent == root:
                    shutil.rmtree(path, ignore_errors=True)
            store.delete(project['id'])


def install_security(app):
    """Install default-deny production protection while retaining localhost development."""
    app.extensions['tickets'] = URLSafeTimedSerializer(secrets.token_hex(32), salt='media')
    counters, counter_lock = {}, threading.Lock()
    admission = threading.Lock()

    def limited(owner, category, maximum, window):
        """Use bounded fixed-window counters keyed only by provisioned identities."""
        key = (owner, category)
        bucket = int(time.time() // window)
        with counter_lock:
            previous, count = counters.get(key, (bucket, 0))
            count = count + 1 if previous == bucket else 1
            counters[key] = (bucket, count)
            return count > maximum

    @app.before_request
    def authorize():
        """Authorize every project route, including range requests and exports."""
        g.owner = None
        if not app.config['PRODUCTION']:
            return None
        if request.headers.get('X-Forwarded-Proto', request.scheme) != 'https':
            return jsonify(error={'message': 'HTTPS is required.'}), 400
        origin = request.headers.get('Origin')
        if origin and origin not in app.config['ALLOWED_ORIGINS']:
            return jsonify(error={'message': 'Origin rejected.'}), 403
        if request.method == 'OPTIONS':
            return '', 204
        if request.path == '/api/health':
            return None
        if not request.path.startswith('/api/'):
            return jsonify(error={'message': 'Not found.'}), 404
        credential = request.headers.get('Authorization', '').removeprefix('Bearer ')
        digest = hashlib.sha256(credential.encode()).hexdigest()
        g.owner = app.config['ACCESS_USERS'].get(digest)
        pid = (request.view_args or {}).get('pid')
        ticket = request.args.get('ticket')
        # Tickets are accepted only for media/export GET/HEAD, never transcript APIs or writes.
        if not g.owner and ticket and pid and request.method in ('GET', 'HEAD') and request.endpoint in ('api.media', 'api.audio', 'api.download'):
            try:
                ticket_pid, owner = app.extensions['tickets'].loads(ticket, max_age=3600)
                if ticket_pid == pid and owner in app.config['ACCESS_USERS'].values():
                    g.owner = owner
            except (BadSignature, SignatureExpired, ValueError, TypeError):
                pass
        if not g.owner:
            return jsonify(error={'message': 'Enter your individual access token; reload to try again.'}), 401
        if limited(g.owner, 'requests', 600, 60):
            return jsonify(error={'message': 'Request limit reached; wait one minute.'}), 429
        if pid and app.extensions['store'].get(pid).get('owner') != g.owner:
            return jsonify(error={'message': 'Project not found.'}), 404
        if request.method not in ('GET', 'HEAD'):
            if limited(g.owner, 'writes', 120, 3600):
                return jsonify(error={'message': 'Hourly change limit reached.'}), 429
            if request.endpoint == 'api.process' and (limited(g.owner, 'ai', 8, 3600) or limited('global', 'ai', 100, 86400)):
                return jsonify(error={'message': 'Processing allowance reached; retry later.'}), 429
        if request.method == 'POST' and request.endpoint in ('api.projects', 'api.demo'):
            if not admission.acquire(blocking=False):
                return jsonify(error={'message': 'Another upload is in progress; retry shortly.'}), 429
            g.admission = True
            cleanup(app)
            if len(app.extensions['store'].all()) >= app.config['MAX_PROJECTS']:
                return jsonify(error={'message': 'Temporary workspace is full; delete projects or wait for expiry.'}), 429
            check_capacity(app.config)
        else:
            cleanup(app)

    @app.after_request
    def headers(response):
        """Expose only exact allowed origins and prevent shared caching of private output."""
        if app.config['PRODUCTION']:
            origin = request.headers.get('Origin')
            if origin in app.config['ALLOWED_ORIGINS']:
                response.headers['Access-Control-Allow-Origin'] = origin
                response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, Range'
                response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, POST, PATCH, DELETE, OPTIONS'
                response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition, Content-Range, Accept-Ranges'
                response.vary.add('Origin')
            response.headers['Cache-Control'] = 'private, no-store'
            response.headers['Referrer-Policy'] = 'no-referrer'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
            if response.status_code == 429:
                response.headers['Retry-After'] = '60'
        return response

    @app.teardown_request
    def release_admission(error):
        """Release upload admission after success, validation errors, or disconnected clients."""
        if getattr(g, 'admission', False):
            admission.release()
            g.admission = False
