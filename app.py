"""Local thesis assistant: projects, PDF reading, and evidence-linked journal analysis."""
import argparse
import json
import logging
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from analysis import AnalysisError, ai_status, analyze
from storage import ProjectStore

MAX_UPLOAD = 15 * 1024 * 1024
WORKERS = threading.BoundedSemaphore(2)
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, format, *args):
            # No headers, keys, PDF text or AI response bodies in access logs.
            logging.info('%s %s', self.command, getattr(self, 'path', '').split('?')[0])

        def send_bytes(self, status, data, content_type, download=False):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
            self.send_header('Connection', 'close')
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="document.pdf"')
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        def reply(self, status, payload):
            self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode(),
                            'application/json; charset=utf-8')

        def check_host(self):
            port = self.server.server_port
            allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if port == 80:
                allowed.update({'127.0.0.1', 'localhost'})
            if self.headers.get('Host', '').lower() not in allowed:
                raise ApiError(403, 'Host tidak diizinkan. Gunakan localhost atau 127.0.0.1.')

        def body(self, limit, media_type):
            if self.headers.get_content_type() != media_type:
                raise ApiError(415, f'Gunakan {media_type}.')
            if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                raise ApiError(400, 'Content-Length tunggal diperlukan.')
            try:
                size = int(self.headers['Content-Length'])
            except ValueError:
                raise ApiError(400, 'Content-Length tidak valid.') from None
            if not 1 <= size <= limit:
                raise ApiError(413, f'Ukuran permintaan harus 1–{limit} byte.')
            try:
                content = self.rfile.read(size)
            except TimeoutError:
                raise ApiError(408, 'Unggahan melewati batas waktu.') from None
            if len(content) != size:
                raise ApiError(400, 'Isi permintaan tidak lengkap.')
            return content

        def json_body(self):
            try:
                payload = json.loads(self.body(4096, 'application/json'))
            except (ValueError, UnicodeDecodeError):
                raise ApiError(400, 'JSON tidak valid.') from None
            if not isinstance(payload, dict):
                raise ApiError(400, 'Permintaan harus berupa objek JSON.')
            return payload

        def dispatch(self, post=False):
            try:
                self.check_host()
                path = urlsplit(self.path).path
                if post:
                    origin = self.headers.get('Origin')
                    if origin and origin != 'http://' + self.headers.get('Host', ''):
                        raise ApiError(403, 'Origin tidak diizinkan.')
                    if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                        raise ApiError(403, 'Permintaan lintas situs tidak diizinkan.')
                    return self.post(path)
                return self.get(path)
            except ApiError as error:
                self.reply(error.status, {'error': error.message})
            except LookupError as error:
                self.reply(404, {'error': str(error)})
            except ValueError as error:
                self.reply(400, {'error': str(error)})
            except AnalysisError as error:
                self.reply(502, {'error': str(error)})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                logging.error('Operasi gagal: %s', self.command)
                self.reply(500, {'error': 'Operasi penyimpanan atau pemrosesan gagal. Periksa layanan lokal.'})

        def do_GET(self):
            self.dispatch()

        def do_POST(self):
            self.dispatch(post=True)

        def get(self, path):
            if path in ASSETS:
                filename, content_type = ASSETS[path]
                return self.send_bytes(200, Path(__file__).with_name(filename).read_bytes(), content_type)
            if path == '/api/health':
                return self.reply(200, {'status': 'ok', 'stage': 'journal_reading',
                                       'ai_status': ai_status()['status'], 'max_upload_bytes': MAX_UPLOAD})
            if path == '/api/ai/status':
                return self.reply(200, ai_status())
            if path == '/api/projects':
                return self.reply(200, {'projects': store.list()})
            match = re.fullmatch(r'/api/projects/([\w-]+)/documents', path)
            if match:
                return self.reply(200, {'documents': store.documents(match[1])})
            match = re.fullmatch(r'/api/documents/([\w-]+)(/pdf)?', path)
            if match:
                if match[2]:
                    return self.send_bytes(200, store.pdf_path(match[1]).read_bytes(), 'application/pdf', True)
                return self.reply(200, store.document(match[1]))
            raise ApiError(404, 'Tidak ditemukan.')

        def post(self, path):
            if path == '/api/projects':
                return self.reply(201, store.create(self.json_body().get('title')))
            match = re.fullmatch(r'/api/projects/([\w-]+)/documents', path)
            if match:
                store.project(match[1])
                filename = unquote(self.headers.get('X-Filename', ''))
                if (not filename.lower().endswith('.pdf') or not 1 <= len(filename) <= 200
                        or any(c in filename for c in '/\\') or any(ord(c) < 32 for c in filename)):
                    raise ApiError(400, 'Nama berkas PDF tidak valid (maksimal 200 karakter, tanpa direktori).')
                if not WORKERS.acquire(blocking=False):
                    raise ApiError(503, 'Dua dokumen sedang diproses. Coba lagi setelah selesai.')
                try:
                    content = self.body(MAX_UPLOAD, 'application/pdf')
                    if not content.startswith(b'%PDF-'):
                        raise ApiError(400, 'Isi berkas bukan PDF yang valid.')
                    document = store.add_document(match[1], filename, content)
                finally:
                    WORKERS.release()
                return self.reply(201, document)
            match = re.fullmatch(r'/api/documents/([\w-]+)/analyze', path)
            if match:
                payload = self.json_body()
                if payload.get('consent') is not True:
                    raise ApiError(400, 'Persetujuan mengirim teks jurnal ke OpenAI diperlukan.')
                document = store.document(match[1])
                if not WORKERS.acquire(blocking=False):
                    raise ApiError(503, 'Pemrosesan sedang penuh. Coba lagi setelah selesai.')
                try:
                    try:
                        status, result = analyze(document)
                    except AnalysisError as error:
                        store.save_analysis(document['id'], 'failed', {'message': str(error)})
                        raise
                    if status == 'not_configured':
                        return self.reply(503, {'status': status, 'error': result['message']})
                    record = store.save_analysis(document['id'], status, result)
                finally:
                    WORKERS.release()
                return self.reply(201, record)
            raise ApiError(404, 'Tidak ditemukan.')

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--data-dir', type=Path, default=Path('data'))
    args = parser.parse_args()
    store = ProjectStore(args.data_dir / 'projects.sqlite3')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(store))
    print(f'Asisten Skripsi berjalan pada port {args.port}; hanya akses lokal.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
