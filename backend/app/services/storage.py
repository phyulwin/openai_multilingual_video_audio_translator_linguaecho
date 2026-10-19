# storage.py — SQLite JSON documents with serialized local mutations.
import json
import sqlite3
import threading
from datetime import datetime, timezone


def now():
    """Use UTC timestamps for stable ordering across clients."""
    return datetime.now(timezone.utc).isoformat()


class Store:
    """Keep project documents durable with transactional read-modify-write."""
    def __init__(self, path):
        self.path = path
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, document TEXT NOT NULL)')

    def connect(self):
        """Open a connection per operation for background-thread safety."""
        return sqlite3.connect(self.path, timeout=30)

    def all(self):
        """Return newest projects first without reading media files."""
        with self.connect() as db:
            docs = [json.loads(row[0]) for row in db.execute('SELECT document FROM projects')]
        return sorted(docs, key=lambda p: p['updated_at'], reverse=True)

    def get(self, pid):
        """Raise a lookup error for missing or unknown identifiers."""
        with self.connect() as db:
            row = db.execute('SELECT document FROM projects WHERE id=?', (pid,)).fetchone()
        if not row:
            raise LookupError('Project not found')
        return json.loads(row[0])

    def save(self, project):
        """Atomically replace a complete project document."""
        with self.lock, self.connect() as db:
            project['updated_at'] = now()
            db.execute('INSERT OR REPLACE INTO projects VALUES (?, ?)',
                       (project['id'], json.dumps(project, ensure_ascii=False)))
        return project

    def update(self, pid, function):
        """Serialize concurrent metadata and worker updates."""
        with self.lock:
            project = self.get(pid)
            function(project)
            return self.save(project)

    def delete(self, pid):
        """Remove only the requested persistent record."""
        with self.lock, self.connect() as db:
            db.execute('DELETE FROM projects WHERE id=?', (pid,))
