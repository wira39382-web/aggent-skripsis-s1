"""Additive proposal audit/issue storage. Academic approval is deliberately absent."""
import json
from uuid import uuid4
from datetime import datetime, timezone

from analysis import AnalysisError
from proposal import CRITERIA, manifest, same_snapshot, structure, verify_evidence
from reviews import ReviewConflict

SCHEMA = '''
CREATE TABLE IF NOT EXISTS document_roles (
    document_id TEXT PRIMARY KEY REFERENCES documents(id), kind TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposal_audits (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    created_at TEXT NOT NULL, mode TEXT NOT NULL, status TEXT NOT NULL, result TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposal_issues (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id),
    criterion TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL,
    audit_id TEXT, sources TEXT NOT NULL, details TEXT NOT NULL,
    UNIQUE(document_id, criterion, origin));
CREATE TABLE IF NOT EXISTS proposal_issue_events (
    id TEXT PRIMARY KEY, issue_id TEXT NOT NULL REFERENCES proposal_issues(id),
    created_at TEXT NOT NULL, status TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
    details TEXT NOT NULL);
'''


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def required_text(payload, key, maximum):
    value = payload.get(key)
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= maximum:
        label = {'actor': 'Nama pencatat', 'summary': 'Temuan', 'recommendation': 'Tindak lanjut', 'note': 'Catatan'}[key]
        raise ValueError(f'{label} wajib diisi, maksimal {maximum} karakter.')
    return value.strip()


class ProposalStoreMixin:
    def active_proposal_id(self, project_id, db=None):
        sql = ("SELECT d.id FROM documents d JOIN document_roles r ON r.document_id=d.id "
               "WHERE d.project_id=? AND r.kind='proposal' ORDER BY d.rowid DESC LIMIT 1")
        if db is not None:
            row = db.execute(sql, (project_id,)).fetchone()
        else:
            with self.connect() as connection:
                row = connection.execute(sql, (project_id,)).fetchone()
        return row['id'] if row else None

    def proposal_inputs(self, document_id, guideline_ids):
        document = self.document(document_id)
        if document['kind'] != 'proposal':
            raise ValueError('Audit proposal hanya untuk dokumen berjenis proposal.')
        if self.active_proposal_id(document['project_id']) != document_id:
            raise ReviewConflict('Proposal ini versi sebelumnya. Gunakan proposal aktif terbaru.')
        if (not isinstance(guideline_ids, list) or len(guideline_ids) > 5
                or any(not isinstance(i, str) for i in guideline_ids)
                or len(set(guideline_ids)) != len(guideline_ids)):
            raise ValueError('Pilih paling banyak 5 pedoman unik.')
        guidelines = [self.document(i) for i in guideline_ids]
        if any(d['project_id'] != document['project_id'] or d['kind'] != 'guideline' for d in guidelines):
            raise ValueError('Pedoman harus berasal dari proyek yang sama dan berjenis pedoman.')
        return document, guidelines

    def sources_current(self, sources, cache=None):
        cache = cache if cache is not None else {}
        try:
            for source in sources:
                key = source['document_id']
                if key not in cache:
                    cache[key] = self.document(key)
                if not same_snapshot(cache[key], source):
                    return False
            return bool(sources)
        except (LookupError, KeyError):
            return False

    def _require_current(self, document_id, sources, db):
        document = self.document(document_id)
        if (document['kind'] != 'proposal'
                or self.active_proposal_id(document['project_id'], db) != document_id
                or not self.sources_current(sources, {document_id: document})):
            raise ReviewConflict('Proposal/pedoman berubah saat diproses. Hasil lama tidak diterapkan ke versi baru.')
        return document

    def _issue(self, db, document_id, criterion, origin, details, sources, audit_id, actor):
        row = db.execute('SELECT id FROM proposal_issues WHERE document_id=? AND criterion=? AND origin=?',
                         (document_id, criterion, origin)).fetchone()
        issue_id = row['id'] if row else str(uuid4())
        if row:
            db.execute('UPDATE proposal_issues SET audit_id=?, sources=?, details=? WHERE id=?',
                       (audit_id, json.dumps(sources), json.dumps(details, ensure_ascii=False), issue_id))
        else:
            db.execute('INSERT INTO proposal_issues VALUES (?,?,?,?,?,?,?,?)',
                       (issue_id, document_id, criterion, origin, timestamp(), audit_id,
                        json.dumps(sources), json.dumps(details, ensure_ascii=False)))
        # Findings recurring in a new audit reopen the same stable issue, preserving previous events.
        db.execute('INSERT INTO proposal_issue_events VALUES (?,?,?,?,?,?,?)',
                   (str(uuid4()), issue_id, timestamp(), 'open', actor,
                    'Temuan dicatat; perlu tindak lanjut dan penilaian ulang.',
                    json.dumps({'audit_id': audit_id, 'finding': details, 'sources': sources}, ensure_ascii=False)))
        return issue_id

    def save_proposal_audit(self, document_id, mode, status, result):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._require_current(document_id, result['sources'], db)
            record = {'id': str(uuid4()), 'document_id': document_id, 'created_at': timestamp(),
                      'mode': mode, 'status': status, 'result': json.dumps(result, ensure_ascii=False)}
            db.execute('INSERT INTO proposal_audits VALUES (:id,:document_id,:created_at,:mode,:status,:result)', record)
            for criterion, check in result.get('checks', {}).items():
                if check['status'] == 'needs_revision':
                    self._issue(db, document_id, criterion, 'ai', check, result['sources'], record['id'], 'AI (draf)')
        return dict(record, result=result)

    def add_proposal_issue(self, document_id, payload):
        document, guidelines = self.proposal_inputs(document_id, payload.get('guideline_ids', []))
        criterion = payload.get('criterion')
        if not isinstance(criterion, str) or criterion not in CRITERIA:
            raise ValueError('Kriteria temuan tidak valid.')
        severity = payload.get('severity')
        if severity not in ('minor', 'major', 'critical'):
            raise ValueError('Tingkat masalah harus minor, major, atau critical.')
        actor = required_text(payload, 'actor', 100)
        summary = required_text(payload, 'summary', 2500)
        recommendation = required_text(payload, 'recommendation', 2500)
        documents = [document, *guidelines]
        try:
            evidence = verify_evidence(payload.get('evidence'), documents)
        except AnalysisError as error:
            raise ValueError(str(error)) from None
        if not any(e['document_id'] == document_id for e in evidence):
            raise ValueError('Temuan wajib menunjuk kutipan pada proposal yang diaudit.')
        if criterion == 'pedoman' and not any(e['document_id'] != document_id for e in evidence):
            raise ValueError('Temuan kepatuhan wajib menunjuk bukti aturan pada pedoman yang dilampirkan.')
        details = {'status': 'needs_revision', 'summary': summary,
                   'recommendation': recommendation, 'severity': severity, 'evidence': evidence}
        sources = manifest(documents)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self._require_current(document_id, sources, db)
            issue_id = self._issue(db, document_id, criterion, 'manual', details, sources, None, actor)
        return {'id': issue_id}

    def proposal_issues(self, project_id):
        self.project(project_id)
        active_id = self.active_proposal_id(project_id)
        with self.connect() as db:
            db.execute('BEGIN')
            rows = db.execute('SELECT i.* FROM proposal_issues i JOIN documents d ON d.id=i.document_id '
                              'WHERE d.project_id=? ORDER BY i.rowid DESC', (project_id,)).fetchall()
            events = db.execute('SELECT e.* FROM proposal_issue_events e JOIN proposal_issues i ON i.id=e.issue_id '
                                'JOIN documents d ON d.id=i.document_id WHERE d.project_id=? ORDER BY e.rowid DESC',
                                (project_id,)).fetchall()
        cache, output = {}, []
        for row in rows:
            issue = dict(row, details=json.loads(row['details']), sources=json.loads(row['sources']))
            issue['events'] = [dict(e, details=json.loads(e['details'])) for e in events if e['issue_id'] == issue['id']]
            issue['status'] = issue['events'][0]['status'] if issue['events'] else 'open'
            issue['fresh'] = issue['document_id'] == active_id and self.sources_current(issue['sources'], cache)
            issue['criterion_label'] = CRITERIA[issue['criterion']][0]
            output.append(issue)
        return output

    def update_proposal_issue(self, issue_id, payload):
        status = payload.get('status')
        if status not in ('open', 'in_progress', 'addressed'):
            raise ValueError('Status hanya open, in_progress, atau addressed; tidak ada persetujuan akademik otomatis.')
        actor = required_text(payload, 'actor', 100)
        note = required_text(payload, 'note', 2500)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            issue = db.execute('SELECT * FROM proposal_issues WHERE id=?', (issue_id,)).fetchone()
            if issue is None:
                raise LookupError('Temuan tidak ditemukan.')
            if payload.get('expected_event_id') != (db.execute(
                'SELECT id FROM proposal_issue_events WHERE issue_id=? ORDER BY rowid DESC LIMIT 1',
                (issue_id,)).fetchone() or {'id': None})['id']:
                raise ReviewConflict('Status temuan berubah sejak formulir dibuka. Muat ulang daftar revisi.')
            self._require_current(issue['document_id'], json.loads(issue['sources']), db)
            event = {'id': str(uuid4()), 'issue_id': issue_id, 'created_at': timestamp(),
                     'status': status, 'actor': actor, 'note': note,
                     'details': json.dumps({'audit_id': issue['audit_id'], 'sources': json.loads(issue['sources'])})}
            db.execute('INSERT INTO proposal_issue_events VALUES (:id,:issue_id,:created_at,:status,:actor,:note,:details)', event)
        return event

    def proposal_view(self, document_id):
        document = self.document(document_id)
        if document['kind'] != 'proposal':
            raise ValueError('Dokumen bukan proposal.')
        active_id = self.active_proposal_id(document['project_id'])
        with self.connect() as db:
            rows = db.execute('SELECT * FROM proposal_audits WHERE document_id=? ORDER BY rowid DESC LIMIT 20',
                              (document_id,)).fetchall()
            latest_ai = db.execute("SELECT * FROM proposal_audits WHERE document_id=? AND status='draft_audit' "
                                   'ORDER BY rowid DESC LIMIT 1', (document_id,)).fetchone()
            if latest_ai and all(row['id'] != latest_ai['id'] for row in rows):
                rows.append(latest_ai)
        audits, cache = [], {document_id: document}
        for row in rows:
            audit = dict(row, result=json.loads(row['result']))
            audit['fresh'] = document_id == active_id and self.sources_current(audit['result']['sources'], cache)
            audits.append(audit)
        return {'document_id': document_id, 'is_active': document_id == active_id,
                'structure': structure(document), 'audits': audits,
                'issues': [i for i in self.proposal_issues(document['project_id']) if i['document_id'] == document_id],
                'criteria': {key: label for key, (label, _) in CRITERIA.items()}}

    def dashboard(self, project_id):
        project = self.project(project_id)
        documents = self.documents(project_id)
        proposal_id = self.active_proposal_id(project_id)
        issues = self.proposal_issues(project_id)
        active_issues = [i for i in issues if i['fresh']]
        pending = [i for i in active_issues if i['status'] != 'addressed']
        proposal_status, next_action = 'not_uploaded', 'Unggah proposal untuk memulai pemeriksaan struktur.'
        if proposal_id:
            document = self.document(proposal_id)
            view = self.proposal_view(proposal_id)
            audit = next((a for a in view['audits'] if a['status'] == 'draft_audit'), None)
            if audit and not audit['fresh']:
                audit = None
            if document['source_integrity'] != 'matched':
                proposal_status, next_action = 'stale', 'PDF proposal berubah/tidak tersedia. Pulihkan sumber atau unggah proposal baru.'
            elif pending:
                proposal_status, next_action = 'revisions_pending', 'Tindak lanjuti temuan terbuka pada daftar revisi; periksa isu paling berat dahulu.'
            elif not any(a['fresh'] and a['status'] != 'failed' for a in view['audits']):
                proposal_status, next_action = 'not_audited', 'Jalankan pemeriksaan struktur proposal; audit isi memerlukan AI atau catatan manual.'
            elif not audit:
                proposal_status, next_action = 'structure_only', 'Struktur sudah diperiksa. Tambahkan pedoman dan lanjutkan audit isi/tinjauan manual.'
            elif any(c['status'] == 'unknown' for c in audit['result']['checks'].values()):
                proposal_status, next_action = 'unknown', 'Lengkapi bukti pada kriteria yang belum dapat dinilai.'
            elif audit['result']['structure']['unread_pages']:
                proposal_status, next_action = 'partial', 'Ada halaman proposal belum terbaca; OCR belum tersedia.'
            elif any(i['status'] == 'addressed' for i in active_issues):
                proposal_status, next_action = 'needs_reaudit', 'Temuan ditandai ditangani; unggah proposal revisi dan audit ulang. Ini belum verifikasi penyelesaian.'
            else:
                proposal_status, next_action = 'needs_human_review', 'Draf audit tersedia; tinjau bukti dan temuan. Belum berarti proposal disetujui.'
        return {'project': project, 'documents': documents, 'active_proposal_id': proposal_id,
                'proposal_status': proposal_status, 'next_action': next_action,
                'counts': {'proposal': sum(d['kind'] == 'proposal' for d in documents),
                           'journal': sum(d['kind'] == 'journal' for d in documents),
                           'guideline': sum(d['kind'] == 'guideline' for d in documents),
                           'open_issues': len(pending), 'addressed': sum(i['status'] == 'addressed' for i in active_issues)},
                'issues': issues}
