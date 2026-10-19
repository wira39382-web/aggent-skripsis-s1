"""Human reviews must not approve incomplete evidence or silently move between versions."""
import copy
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from analysis import FIELDS, analyze
from app import ProjectStore, make_handler
from scripts.make_test_pdf import TEST_PAGES, make_pdf
from test_documents import valid_result


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ProjectStore(Path(self.tmp.name) / 'projects.sqlite3')
        self.project = self.store.create('Pengujian tinjauan')
        self.doc = self.store.add_document(self.project['id'], 'synthetic.pdf', make_pdf(TEST_PAGES))
        self.record = self.add_analysis(self.doc)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store))
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=.01), daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}/api/documents/{self.doc["id"]}/reviews'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.tmp.cleanup()

    def add_analysis(self, document, raw=None):
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'mock-test-only'}), patch(
            'analysis.request_model', return_value=(raw or valid_result(), 'MOCK-NOT-REAL-AI', {})
        ):
            status, result = analyze(document)
        return self.store.save_analysis(document['id'], status, result)

    def payload(self):
        return {'analysis_id': self.record['id'], 'source_sha256': self.doc['sha256'],
                'extraction_sha256': self.record['result']['extraction_sha256'],
                'reviewer': 'Peninjau uji', 'note': 'Catatan uji sintetis; bukan persetujuan akademik.',
                'decisions': {name: ('supported' if field['status'] == 'found' else 'not_found_in_readable_text')
                              for name, field in self.record['result']['fields'].items()}}

    def send(self, payload, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        request = Request(self.url, data=json.dumps(payload).encode(), headers=headers)
        try:
            response = urlopen(request, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def current(self):
        return self.store.document(self.doc['id'])['analyses'][0]

    def test_valid_review_is_append_only_and_survives_reopen(self):
        payload = self.payload()
        status, first = self.send(payload)
        self.assertEqual(status, 201, first)
        self.assertEqual(first['status'], 'reviewed')
        payload['note'] = 'Penjelasan tinjauan kedua.'
        status, second = self.send(payload)
        self.assertEqual(status, 201)
        record = ProjectStore(self.store.path).document(self.doc['id'])['analyses'][0]
        self.assertEqual(record['review_state'], 'reviewed')
        self.assertEqual(record['result'], self.record['result'])
        self.assertEqual(record['status'], 'needs_review')  # Original AI output remains immutable.
        self.assertEqual([r['id'] for r in record['reviews']], [second['id'], first['id']])
        self.assertNotIn('academic_approval', second['details'])

    def test_unknown_or_revision_is_never_marked_reviewed(self):
        for decision, state in [('unknown', 'unknown'), ('needs_revision', 'needs_revision')]:
            payload = self.payload()
            payload['decisions']['temuan'] = decision
            self.assertEqual(self.send(payload)[0], 201)
            self.assertEqual(self.current()['review_state'], state)

    def test_invalid_or_missing_decisions_reviewer_and_reason_rejected(self):
        candidates = []
        for key in ['reviewer', 'note', 'decisions']:
            payload = self.payload()
            payload.pop(key)
            candidates.append(payload)
        payload = self.payload()
        payload['decisions'].pop('tujuan')
        candidates.append(payload)
        payload = self.payload()
        payload['decisions']['keterbatasan'] = 'supported'
        candidates.append(payload)
        for payload in candidates:
            with self.subTest(payload=payload):
                self.assertEqual(self.send(payload)[0], 400)
        self.assertEqual(self.current()['reviews'], [])

    def test_snapshot_mismatch_rejected(self):
        for key in ['source_sha256', 'extraction_sha256']:
            payload = self.payload()
            payload[key] = 'outdated'
            self.assertEqual(self.send(payload)[0], 409)
        self.assertEqual(self.current()['reviews'], [])

    def test_reanalysis_does_not_inherit_old_review_and_rejects_old_form(self):
        self.assertEqual(self.send(self.payload())[0], 201)
        newer = self.add_analysis(self.doc)
        self.assertEqual(self.send(self.payload())[0], 409)
        history = self.store.document(self.doc['id'])['analyses']
        self.assertEqual(history[0]['id'], newer['id'])
        self.assertEqual(history[0]['review_state'], 'needs_review')
        self.assertEqual(history[0]['reviews'], [])
        self.assertEqual(history[1]['review_state'], 'superseded')
        self.assertEqual(len(history[1]['reviews']), 1)

    def test_extraction_change_invalidates_review_without_erasing_history(self):
        self.assertEqual(self.send(self.payload())[0], 201)
        changed = copy.deepcopy(self.doc['extraction'])
        changed['pages'][0]['text'] += '\nExtraction revision.'
        with self.store.connect() as db:
            db.execute('UPDATE documents SET extraction=? WHERE id=?', (json.dumps(changed), self.doc['id']))
        self.assertEqual(self.current()['review_state'], 'stale')
        self.assertEqual(len(self.current()['reviews']), 1)
        self.assertEqual(self.send(self.payload())[0], 409)

    def test_partial_reading_cannot_be_marked_as_full_review(self):
        self.doc = self.store.add_document(self.project['id'], 'partial.pdf', make_pdf([TEST_PAGES[0], []]))
        raw = {name: {'status': 'not_found', 'claims': []} for name in FIELDS}
        self.record = self.add_analysis(self.doc, raw)
        self.url = self.url.replace(self.url.split('/')[-2], self.doc['id'])
        status, body = self.send(self.payload())
        self.assertEqual(status, 201, body)
        self.assertEqual(body['status'], 'reviewed_partial')
        self.assertEqual(self.current()['review_state'], 'reviewed_partial')

    def test_legacy_analysis_without_extraction_snapshot_requires_reanalysis(self):
        result = copy.deepcopy(self.record['result'])
        result.pop('extraction_sha256')
        self.store.save_analysis(self.doc['id'], 'needs_review', result)
        self.assertEqual(self.current()['review_state'], 'stale')

    def test_database_migration_preserves_existing_documents_and_results(self):
        legacy = copy.deepcopy(self.record['result'])
        legacy.pop('extraction_sha256')
        original_pdf = self.store.pdf_path(self.doc['id']).read_bytes()
        with self.store.connect() as db:
            db.execute('DROP TABLE analysis_reviews')
            db.execute('UPDATE analyses SET result=? WHERE id=?', (json.dumps(legacy), self.record['id']))
        reopened = ProjectStore(self.store.path)
        document = reopened.document(self.doc['id'])
        self.assertEqual(reopened.project(self.project['id']), self.project)
        self.assertEqual(reopened.pdf_path(self.doc['id']).read_bytes(), original_pdf)
        self.assertEqual(document['analyses'][0]['result'], legacy)
        self.assertEqual(document['analyses'][0]['reviews'], [])
        self.assertEqual(document['analyses'][0]['review_state'], 'stale')

    def test_failed_provider_attempt_does_not_discard_valid_human_review(self):
        self.assertEqual(self.send(self.payload())[0], 201)
        self.store.save_analysis(self.doc['id'], 'failed', {'message': 'Mock provider error.'})
        history = self.store.document(self.doc['id'])['analyses']
        self.assertEqual(history[0]['review_state'], 'failed')
        self.assertEqual(history[1]['review_state'], 'reviewed')

    def test_changed_pdf_invalidates_review_and_cannot_be_downloaded_as_original(self):
        self.assertEqual(self.send(self.payload())[0], 201)
        path = self.store.pdf_path(self.doc['id'])
        content = path.read_bytes()
        # Same byte size, different content: size checks alone must not accept it.
        path.write_bytes(content.replace(b'Purpose:', b'Changed:', 1))
        self.assertEqual(self.store.document(self.doc['id'])['source_integrity'], 'changed')
        self.assertEqual(self.current()['review_state'], 'stale')
        self.assertEqual(self.send(self.payload())[0], 409)
        with self.assertRaises(ValueError):
            self.store.pdf_path(self.doc['id'])
        document = self.store.document(self.doc['id'])
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'mock-test-only'}), patch('analysis.request_model') as provider:
            with self.assertRaises(ValueError):
                analyze(document)
            provider.assert_not_called()

    def test_missing_original_preserves_history_but_blocks_review(self):
        self.assertEqual(self.send(self.payload())[0], 201)
        self.store.pdf_path(self.doc['id']).unlink()
        self.assertEqual(self.current()['review_state'], 'stale')
        self.assertEqual(len(self.current()['reviews']), 1)
        self.assertEqual(self.send(self.payload())[0], 409)

    def test_cross_origin_review_rejected(self):
        self.assertEqual(self.send(self.payload(), 'https://other.invalid')[0], 403)
        self.assertEqual(self.current()['reviews'], [])

    def test_unicode_notes_and_untrusted_reviewer_are_stored_as_text(self):
        payload = self.payload()
        payload['reviewer'] = '<script>not executable</script>'
        payload['note'] = '\U0001f4d6' * 2000
        status, body = self.send(payload)
        self.assertEqual(status, 201, body)
        self.assertEqual(body['details']['note'], payload['note'])
        self.assertEqual(body['details']['reviewer'], payload['reviewer'])
