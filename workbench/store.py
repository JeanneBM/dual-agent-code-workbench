import json
import sqlite3
from pathlib import Path


class Store:
    def __init__(self, path=".local/runs.sqlite"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT, payload TEXT)")

    def connect(self):
        return sqlite3.connect(self.path)

    def save(self, result):
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?, ?, ?)",
                       (result["id"], result["created"], json.dumps(result)))

    def list(self):
        with self.connect() as db:
            return db.execute("SELECT id, created FROM runs ORDER BY created DESC LIMIT 50").fetchall()

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, run_id):
        with self.connect() as db:
            db.execute("DELETE FROM runs WHERE id = ?", (run_id,))
