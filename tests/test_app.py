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
from app import ProjectStore, make_handler


class AppTests(unittest.TestCase):
    def setUp(self):
        credentials = patch.dict(os.environ, {'SKRIPSI_AI_API_KEY': '', 'OPENAI_API_KEY': ''})
        credentials.start()
        self.addCleanup(credentials.stop)
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'projects.sqlite3'
        self.store = ProjectStore(self.path)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()
        self.tmp.cleanup()

    def test_health_does_not_claim_ai_ready(self):
        with urlopen(self.base + '/api/health') as response:
            self.assertEqual(json.load(response)['ai_status'], 'not_configured')

    def test_project_survives_store_reopen(self):
        request = Request(self.base + '/api/projects', data=json.dumps({'title': 'Kepercayaan konsumen'}).encode(), headers={'Content-Type': 'application/json'})
        with urlopen(request) as response:
            self.assertEqual(response.status, 201)
            created = json.load(response)
        self.assertEqual(ProjectStore(self.path).list()[0], created)

    def test_empty_title_rejected(self):
        request = Request(self.base + '/api/projects', data=b'{"title":" "}', headers={'Content-Type': 'application/json'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 400)
        self.assertEqual(self.store.list(), [])

    def test_cross_origin_write_rejected(self):
        request = Request(self.base + '/api/projects', data=b'{"title":"x"}', headers={'Content-Type': 'application/json', 'Origin': 'https://example.invalid'})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)


if __name__ == '__main__':
    unittest.main()
