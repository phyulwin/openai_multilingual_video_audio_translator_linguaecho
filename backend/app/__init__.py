# __init__.py — Flask application factory with local-origin protection.
import logging
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, jsonify, request, send_from_directory
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException
from .config import configuration, ROOT
from .services.storage import Store
from .services.jobs import Jobs
from .routes import api


def create_app(overrides=None):
    """Compose isolated services, error handling, and a production frontend."""
    app = Flask(__name__, static_folder=None)
    app.config.update(configuration(overrides))
    store = Store(app.config['DATABASE'])
    app.extensions['store'] = store
    app.extensions['jobs'] = Jobs(store, app.config)
    app.register_blueprint(api)

    @app.before_request
    def local_only():
        """Block DNS rebinding and cross-origin writes to the unauthenticated MVP."""
        if request.host.split(':')[0] not in ('localhost', '127.0.0.1', '[::1]'):
            return jsonify(error={'message': 'This MVP accepts localhost requests only.'}), 403
        origin = request.headers.get('Origin')
        if origin and origin not in ('http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:5000', 'http://127.0.0.1:5000'):
            return jsonify(error={'message': 'Cross-origin request rejected.'}), 403

    @app.errorhandler(Exception)
    def errors(exc):
        """Return predictable JSON errors without exposing credentials or paths."""
        if isinstance(exc, ValidationError):
            return jsonify(error={'message': '; '.join(e['msg'] for e in exc.errors())}), 422
        if isinstance(exc, LookupError):
            return jsonify(error={'message': str(exc)}), 404
        if isinstance(exc, ValueError):
            return jsonify(error={'message': str(exc)}), 400
        if isinstance(exc, RuntimeError):
            return jsonify(error={'message': str(exc)}), 409
        if isinstance(exc, HTTPException):
            return jsonify(error={'message': exc.description}), exc.code
        logging.exception('Unexpected request failure')
        return jsonify(error={'message': 'Unexpected server error. Check the server log.'}), 500

    @app.get('/')
    @app.get('/<path:path>')
    def frontend(path='index.html'):
        """Serve Vite output through Waitress after a production build."""
        if path.startswith('api/'):
            return jsonify(error={'message': 'API endpoint not found'}), 404
        folder = ROOT / 'frontend/dist'
        if not (folder / 'index.html').exists():
            return jsonify(message='Run npm run build in frontend, or use the Vite development server.'), 503
        return send_from_directory(folder, path if (folder / path).is_file() else 'index.html')

    return app
