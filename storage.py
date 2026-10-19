"""SQLite metadata and immutable document/analysis history; file names are server-generated."""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pdf_reader import extract_pdf
from proposal_store import ProposalStoreMixin, SCHEMA as PROPOSAL_SCHEMA
from reviews import ReviewConflict, assess_review, review_state


def now():
    return datetime.now(timezone.utc).isoformat()


class ProjectStore(ProposalStoreMixin):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.files = self.path.parent / 'documents'
        self.files.mkdir(exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    filename TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL,
                    created_at TEXT NOT NULL, status TEXT NOT NULL, extraction TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analyses (
                    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
                    created_at TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analysis_reviews (
                    id TEXT PRIMARY KEY, analysis_id TEXT NOT NULL REFERENCES analyses(id),
                    created_at TEXT NOT NULL, status TEXT NOT NULL, details TEXT NOT NULL);
            ''')
            db.executescript(PROPOSAL_SCHEMA)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA foreign_keys=ON')
            # SQLite's own context manager commits/rolls back, but does not close.
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM projects ORDER BY created_at DESC')]

    def project(self, project_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
        if row is None:
            raise LookupError('Proyek tidak ditemukan.')
        return dict(row)

    def create(self, title):
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError('Judul harus berisi 1–200 karakter.')
        project = {'id': str(uuid4()), 'title': title.strip(), 'created_at': now()}
        with self.connect() as db:
            db.execute('INSERT INTO projects VALUES (:id, :title, :created_at)', project)
        return project

    def documents(self, project_id):
        self.project(project_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT d.id, d.project_id, d.filename, d.sha256, d.size, d.created_at, d.status, COALESCE(r.kind,'journal') AS kind "
                'FROM documents d LEFT JOIN document_roles r ON r.document_id=d.id '
                'WHERE d.project_id=? ORDER BY d.rowid DESC', (project_id,))]

    def add_document(self, project_id, filename, content, kind='journal'):
        self.project(project_id)
        if kind not in ('journal', 'proposal', 'guideline'):
            raise ValueError('Jenis dokumen harus journal, proposal, atau guideline.')
        document_id = str(uuid4())
        path = self.files / (document_id + '.pdf')
        # No original filename is ever used as a filesystem path.
        with path.open('xb') as stream:
            stream.write(content)
        try:
            extraction = extract_pdf(path)
            document = {'id': document_id, 'project_id': project_id, 'filename': filename,
                        'sha256': hashlib.sha256(content).hexdigest(), 'size': len(content),
                        'created_at': now(), 'status': extraction['status'],
                        'extraction': json.dumps(extraction, ensure_ascii=False)}
            with self.connect() as db:
                db.execute('INSERT INTO documents VALUES '
                           '(:id,:project_id,:filename,:sha256,:size,:created_at,:status,:extraction)', document)
                db.execute('INSERT INTO document_roles VALUES (?,?)', (document_id, kind))
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return self.document(document_id)

    def document(self, document_id):
        with self.connect() as db:
            db.execute('BEGIN')  # One consistent snapshot for source, analyses and reviews.
            row = db.execute("SELECT d.*, COALESCE(r.kind,'journal') AS kind FROM documents d "
                             'LEFT JOIN document_roles r ON r.document_id=d.id WHERE d.id=?', (document_id,)).fetchone()
            history = db.execute('SELECT * FROM analyses WHERE document_id=? ORDER BY rowid DESC',
                                 (document_id,)).fetchall()
            reviews = db.execute(
                'SELECT r.* FROM analysis_reviews r JOIN analyses a ON a.id=r.analysis_id '
                'WHERE a.document_id=? ORDER BY r.rowid DESC', (document_id,)).fetchall()
        if row is None:
            raise LookupError('Dokumen tidak ditemukan.')
        doc = dict(row)
        doc['source_integrity'] = self.source_integrity(doc)
        doc['extraction'] = json.loads(doc['extraction'])
        doc['analyses'] = [dict(r, result=json.loads(r['result'])) for r in history]
        current_id = next((r['id'] for r in history if r['status'] == 'needs_review'), None)
        for record in doc['analyses']:
            record['reviews'] = [dict(r, details=json.loads(r['details']))
                                 for r in reviews if r['analysis_id'] == record['id']]
            record['review_state'] = review_state(record, doc, current_id)
        return doc

    def pdf_path(self, document_id):
        # Resolve by stored ID, never by an untrusted path component.
        document = self.document(document_id)
        if document['source_integrity'] != 'matched':
            raise ValueError('PDF sumber hilang atau berubah. Jangan gunakan berkas ini sebagai sumber asli.')
        return self.files / (document['id'] + '.pdf')

    def source_integrity(self, document):
        path = self.files / (document['id'] + '.pdf')
        try:
            if path.stat().st_size != document['size']:
                return 'changed'
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            return 'matched' if digest == document['sha256'] else 'changed'
        except OSError:
            return 'unavailable'

    def save_analysis(self, document_id, status, result):
        record = {'id': str(uuid4()), 'document_id': document_id, 'created_at': now(),
                  'status': status, 'result': json.dumps(result, ensure_ascii=False)}
        with self.connect() as db:
            db.execute('INSERT INTO analyses VALUES (:id,:document_id,:created_at,:status,:result)', record)
        return dict(record, result=result)

    def save_review(self, document_id, payload):
        with self.connect() as db:
            # Serialize latest-version checks and append, including concurrent re-analysis.
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM documents WHERE id=?', (document_id,)).fetchone()
            if row is None:
                raise LookupError('Dokumen tidak ditemukan.')
            row_analysis = db.execute(
                "SELECT * FROM analyses WHERE document_id=? AND status='needs_review' "
                'ORDER BY rowid DESC LIMIT 1', (document_id,)).fetchone()
            if row_analysis is None or row_analysis['id'] != payload.get('analysis_id'):
                raise ReviewConflict('Analisis terbaru berbeda atau belum tersedia. Muat ulang dokumen.')
            document = dict(row, extraction=json.loads(row['extraction']))
            document['source_integrity'] = self.source_integrity(document)
            analysis = dict(row_analysis, result=json.loads(row_analysis['result']))
            status, details = assess_review(document, analysis, payload)
            record = {'id': str(uuid4()), 'analysis_id': analysis['id'], 'created_at': now(),
                      'status': status, 'details': json.dumps(details, ensure_ascii=False)}
            db.execute('INSERT INTO analysis_reviews VALUES '
                       '(:id,:analysis_id,:created_at,:status,:details)', record)
        return dict(record, details=details)
