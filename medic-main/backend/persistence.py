"""One local SQLite file. JSON snapshots retain facts, sources and controller state."""
import json
import sqlite3
import threading
from contextlib import contextmanager, closing
from pathlib import Path


class EncounterRepository:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connection() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS encounters (
                    id TEXT PRIMARY KEY, call_id TEXT UNIQUE, started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL, ended_at TEXT, status TEXT NOT NULL,
                    call_active INTEGER NOT NULL, payload TEXT NOT NULL, controller TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        with self.lock, closing(sqlite3.connect(self.path, timeout=10)) as db:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db

    @staticmethod
    def _save(db, snapshot, state):
        db.execute('''INSERT INTO encounters
            (id, call_id, started_at, updated_at, ended_at, status, call_active, payload, controller)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                call_id=excluded.call_id, updated_at=excluded.updated_at, ended_at=excluded.ended_at,
                status=excluded.status, call_active=excluded.call_active,
                payload=excluded.payload, controller=excluded.controller''',
            (snapshot['encounter']['id'], snapshot['call_id'], snapshot['encounter']['started_at'],
             snapshot['updated_at'], snapshot['ended_at'], snapshot['encounter']['encounter_status'],
             int(snapshot['call_active']), json.dumps(snapshot), json.dumps(state)))

    def save(self, snapshot, state, activate=False):
        with self.connection() as db:
            self._save(db, snapshot, state)
            if activate:
                db.execute("INSERT INTO metadata(key,value) VALUES ('current_encounter_id',?) "
                           "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (snapshot['encounter']['id'],))

    def current_id(self):
        with self.connection() as db:
            row = db.execute("SELECT value FROM metadata WHERE key='current_encounter_id'").fetchone()
            return row['value'] if row else None

    def get(self, encounter_id):
        with self.connection() as db:
            row = db.execute('SELECT payload,controller FROM encounters WHERE id=?', (encounter_id,)).fetchone()
            return (json.loads(row['payload']), json.loads(row['controller'])) if row else None

    def recent(self, limit=50):
        with self.connection() as db:
            return [dict(r) for r in db.execute('''SELECT id, call_id, started_at, updated_at,
                ended_at, status, call_active FROM encounters ORDER BY started_at DESC, id DESC LIMIT ?''', (limit,))]

    def has_call(self, call_id):
        with self.connection() as db:
            return db.execute('SELECT 1 FROM encounters WHERE call_id=?', (call_id,)).fetchone() is not None
