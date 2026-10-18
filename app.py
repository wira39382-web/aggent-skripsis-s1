"""Local-only thesis project starter. Python 3.11+, standard library only."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4


class ProjectStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL)')

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY created_at DESC')]

    def create(self, title):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('Judul harus berisi 1–200 karakter.')
        project = {'id': str(uuid4()), 'title': title.strip(), 'created_at': datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute('INSERT INTO projects VALUES (:id, :title, :created_at)', project)
        return project


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, payload):
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == '/api/health':
                return self.reply(200, {'status': 'ok', 'stage': 'foundation', 'ai_status': 'not_configured'})
            if self.path == '/api/projects':
                return self.reply(200, {'projects': store.list()})
            if self.path == '/':
                data = Path(__file__).with_name('index.html').read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(data)
                return
            self.reply(404, {'error': 'Tidak ditemukan.'})

        def do_POST(self):
            if self.path != '/api/projects':
                return self.reply(404, {'error': 'Tidak ditemukan.'})
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.reply(415, {'error': 'Gunakan application/json.'})
            # Local prototype: disallow cross-origin browser writes.
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.reply(403, {'error': 'Origin tidak diizinkan.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 1 <= size <= 4096:
                    return self.reply(413, {'error': 'Ukuran permintaan tidak sesuai.'})
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('Permintaan harus berupa objek JSON.')
                project = store.create(payload.get('title'))
            except (ValueError, UnicodeDecodeError) as error:
                return self.reply(400, {'error': str(error)})
            self.reply(201, project)

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    store = ProjectStore(args.data_dir / 'projects.sqlite3')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(store))
    print(f'Asisten Skripsi: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
