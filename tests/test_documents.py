import hashlib
import io
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

from pypdf import PdfWriter

from app import MAX_UPLOAD, ProjectStore, make_handler
from analysis import AnalysisError, FIELDS, analyze, validate_result
from scripts.make_test_pdf import TEST_PAGES, make_pdf


def valid_result():
    result = {field: {'status': 'not_found', 'claims': []} for field in FIELDS}
    for field, page, quote in [
        ('tujuan', 1, TEST_PAGES[0][1]), ('metode', 1, TEST_PAGES[0][2]),
        ('sampel', 1, TEST_PAGES[0][3]), ('temuan', 2, TEST_PAGES[1][1]),
    ]:
        result[field] = {'status': 'found', 'claims': [{'text': quote, 'evidence': [{'pdf_page': page, 'quote': quote}]}]}
    return result


class DocumentTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {'OPENAI_API_KEY': '', 'SKRIPSI_AI_API_KEY': ''})
        self.environment.start()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'projects.sqlite3'
        self.store = ProjectStore(self.path)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store))
        self.thread = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'
        self.project = self.call('/api/projects', {'title': 'Proyek uji'})[1]
        self.pdf = make_pdf(TEST_PAGES)

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.tmp.cleanup()
        self.environment.stop()

    def call(self, path, payload=None, headers=None, raw=None):
        headers = dict(headers or {})
        if payload is not None:
            raw = json.dumps(payload).encode()
            headers.setdefault('Content-Type', 'application/json')
        req = Request(self.base + path, data=raw, headers=headers)
        try:
            response = urlopen(req, timeout=35)
        except HTTPError as error:
            response = error
        with response:
            body = response.read()
            if response.headers.get_content_type() == 'application/json':
                body = json.loads(body)
            return response.status, body

    def upload(self, content=None, name='journal.pdf', content_type='application/pdf'):
        return self.call(f'/api/projects/{self.project["id"]}/documents',
                         headers={'Content-Type': content_type, 'X-Filename': name},
                         raw=self.pdf if content is None else content)

    def test_pdf_full_workflow_preserves_original_and_pages_after_reopen(self):
        status, doc = self.upload()
        self.assertEqual(status, 201, doc)
        self.assertEqual(doc['status'], 'ready')
        self.assertEqual(doc['sha256'], hashlib.sha256(self.pdf).hexdigest())
        self.assertEqual([p['pdf_page'] for p in doc['extraction']['pages']], [1, 2])
        self.assertIn(TEST_PAGES[0][3], doc['extraction']['pages'][0]['text'])
        self.assertIn(TEST_PAGES[1][1], doc['extraction']['pages'][1]['text'])
        self.assertEqual(ProjectStore(self.path).document(doc['id']), doc)
        self.assertEqual(self.call(f'/api/documents/{doc["id"]}/pdf'), (200, self.pdf))
        other = self.store.create('Proyek lain')
        self.assertEqual(self.call(f'/api/projects/{other["id"]}/documents')[1]['documents'], [])
        self.assertEqual(len(self.call(f'/api/projects/{self.project["id"]}/documents')[1]['documents']), 1)

    def test_mime_extension_magic_and_path_validation(self):
        for content, name, mime, status in [
            (self.pdf, 'x.pdf', 'text/plain', 415), (self.pdf, 'x.txt', 'application/pdf', 400),
            (b'fake PDF', 'x.pdf', 'application/pdf', 400), (self.pdf, '..%2Fx.pdf', 'application/pdf', 400),
            (b'', 'x.pdf', 'application/pdf', 413), (b'%PDF-1.4\ncorrupt', 'x.pdf', 'application/pdf', 400),
        ]:
            with self.subTest(name=name, mime=mime, length=len(content)):
                self.assertEqual(self.upload(content, name, mime)[0], status)
        self.assertEqual(list(self.store.files.iterdir()), [])

    def test_oversized_upload_rejected_before_reading(self):
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request('POST', f'/api/projects/{self.project["id"]}/documents', body=b'',
                         headers={'Content-Type': 'application/pdf', 'X-Filename': 'x.pdf',
                                  'Content-Length': str(MAX_UPLOAD+1)})
            response = conn.getresponse()
            self.assertEqual(response.status, 413)
            response.read()
        finally:
            conn.close()

    def test_encrypted_pdf_rejected_without_storing(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('test-password')
        output = io.BytesIO()
        writer.write(output)
        status, body = self.upload(output.getvalue())
        self.assertEqual(status, 400)
        self.assertIn('terenkripsi', body['error'])
        self.assertEqual(list(self.store.files.iterdir()), [])

    def test_blank_page_is_not_claimed_as_read(self):
        status, doc = self.upload(make_pdf([[]]))
        self.assertEqual(status, 201)
        self.assertEqual(doc['status'], 'unreadable')
        self.assertEqual(doc['extraction']['pages'][0]['status'], 'needs_ocr')
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'test-only'}):
            status, body = self.call(f'/api/documents/{doc["id"]}/analyze', {'consent': True})
        self.assertEqual(status, 400)
        self.assertIn('OCR', body['error'])

    def test_partial_reading_has_explicit_page_coverage(self):
        _, doc = self.upload(make_pdf([TEST_PAGES[0], []]))
        self.assertEqual(doc['status'], 'partial')
        raw = {field: {'status': 'not_found', 'claims': []} for field in FIELDS}
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'test-only'}), patch('analysis.request_model', return_value=(raw, 'mock-model', {})):
            status, result = analyze(doc)
        self.assertEqual(result['read_pages'], [1])
        self.assertEqual(result['unread_pages'], [2])
        self.assertEqual(status, 'needs_review')

    def test_page_limit(self):
        status, body = self.upload(make_pdf([[]]*101))
        self.assertEqual(status, 400)
        self.assertIn('100', body['error'])

    def test_ai_unconfigured_no_fake_analysis_and_no_key_exposure(self):
        _, doc = self.upload()
        self.assertEqual(self.call('/api/ai/status')[1]['status'], 'not_configured')
        status, response = self.call(f'/api/documents/{doc["id"]}/analyze', {'consent': True})
        self.assertEqual(status, 503)
        self.assertEqual(response['status'], 'not_configured')
        self.assertEqual(self.store.document(doc['id'])['analyses'], [])
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'never-expose-this-key'}):
            body = self.call('/api/ai/status')[1]
        self.assertNotIn('never-expose', json.dumps(body))
        self.assertEqual(body['status'], 'configured')

    def test_consent_required_and_cross_origin_blocked(self):
        _, doc = self.upload()
        self.assertEqual(self.call(f'/api/documents/{doc["id"]}/analyze', {})[0], 400)
        status, _ = self.call('/api/projects', {'title': 'x'}, {'Origin': 'https://evil.invalid'})
        self.assertEqual(status, 403)
        status, _ = self.call('/api/projects', headers={'Host': 'evil.invalid'})
        self.assertEqual(status, 403)

    def test_missing_project_and_document(self):
        self.assertEqual(self.call('/api/projects/missing/documents')[0], 404)
        self.assertEqual(self.call('/api/documents/missing')[0], 404)

    def test_mock_ai_validates_quotes_and_persists_versioned_history(self):
        _, doc = self.upload()
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'test-only'}), patch('analysis.request_model', return_value=(valid_result(), 'mock-model', {'total_tokens': 30})):
            for _ in range(2):
                status, record = self.call(f'/api/documents/{doc["id"]}/analyze', {'consent': True})
                self.assertEqual(status, 201, record)
        history = ProjectStore(self.path).document(doc['id'])['analyses']
        self.assertEqual(len(history), 2)
        self.assertNotEqual(history[0]['id'], history[1]['id'])
        self.assertEqual(record['result']['source_sha256'], doc['sha256'])
        self.assertEqual(record['status'], 'needs_review')
        self.assertEqual(record['result']['fields']['keterbatasan']['status'], 'not_found')

    def test_mock_fabricated_quote_rejected_and_failure_logged(self):
        _, doc = self.upload()
        raw = valid_result()
        raw['temuan']['claims'][0]['evidence'][0]['quote'] = 'Invented statement absent from the PDF.'
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'test-only'}), patch('analysis.request_model', return_value=(raw, 'mock-model', {})):
            status, response = self.call(f'/api/documents/{doc["id"]}/analyze', {'consent': True})
        self.assertEqual(status, 502)
        self.assertIn('ditolak', response['error'])
        self.assertEqual(self.store.document(doc['id'])['analyses'][0]['status'], 'failed')

    def test_malformed_and_wrong_page_evidence_rejected(self):
        _, doc = self.upload()
        mutations = [lambda r: r.pop('sampel'),
                     lambda r: r['sampel']['claims'][0].update(evidence=[]),
                     lambda r: r['tujuan']['claims'][0]['evidence'][0].update(pdf_page=2),
                     lambda r: r['tujuan']['claims'][0]['evidence'][0].update(pdf_page=True),
                     lambda r: r['metode'].update(status='not_found')]
        for mutate in mutations:
            raw = valid_result()
            mutate(raw)
            with self.assertRaises(AnalysisError):
                validate_result(raw, doc['extraction']['pages'])

    def test_text_limit_does_not_silently_truncate(self):
        _, doc = self.upload()
        doc['extraction']['pages'][0]['text'] = 'a' * 100_001
        with patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': 'test-only'}), patch('analysis.request_model') as provider:
            with self.assertRaisesRegex(ValueError, 'tidak dipotong'):
                analyze(doc)
            provider.assert_not_called()


class ProviderTests(unittest.TestCase):
    def test_backend_uses_https_structured_output_and_does_not_expose_key(self):
        from analysis import request_model
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(valid_result())}}],
            'model': 'provider-model', 'usage': {'total_tokens': 20}}).encode()
        with patch('analysis.urlopen', return_value=response) as send:
            raw, model, usage = request_model('server-test-key', 'requested-model', [{'pdf_page': 1, 'text': 'source'}])
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'), 'Bearer server-test-key')
        payload = json.loads(request.data)
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertIn('tidak tepercaya', payload['messages'][0]['content'])
        self.assertNotIn('server-test-key', json.dumps((raw, model, usage)))

    def test_provider_failure_is_not_a_research_result(self):
        from analysis import request_model
        with patch('analysis.urlopen', side_effect=HTTPError('https://api.openai.com', 401, 'secret response', {}, None)):
            with self.assertRaisesRegex(AnalysisError, 'HTTP 401') as error:
                request_model('secret-key', 'model', [])
        self.assertNotIn('secret', str(error.exception))
        with patch('analysis.urlopen', side_effect=TimeoutError()):
            with self.assertRaisesRegex(AnalysisError, 'batas waktu'):
                request_model('secret-key', 'model', [])
