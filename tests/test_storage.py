"""Connection lifecycle regression tests: SQLite transactions alone do not close handles."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from storage import ProjectStore


class ConnectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.connections = []
        original_connect = sqlite3.connect

        def connect(*args, **kwargs):
            connection = original_connect(*args, **kwargs)
            # Retain references so garbage collection cannot hide a leaked handle.
            self.connections.append(connection)
            return connection

        self.patcher = patch('storage.sqlite3.connect', side_effect=connect)
        self.patcher.start()
        self.store = ProjectStore(Path(self.tmp.name) / 'projects.sqlite3')

    def tearDown(self):
        self.patcher.stop()
        for connection in self.connections:
            connection.close()
        self.tmp.cleanup()

    def assert_connections_closed(self):
        for connection in self.connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def test_successful_transaction_commits_and_closes(self):
        with self.store.connect() as db:
            db.execute('INSERT INTO projects VALUES (?, ?, ?)', ('test-id', 'Judul uji', '2026-01-01'))
        self.assertEqual(self.store.project('test-id')['title'], 'Judul uji')
        self.assert_connections_closed()

    def test_failed_transaction_rolls_back_and_closes(self):
        with self.assertRaisesRegex(RuntimeError, 'abort transaction'):
            with self.store.connect() as db:
                db.execute('INSERT INTO projects VALUES (?, ?, ?)', ('test-id', 'Judul uji', '2026-01-01'))
                raise RuntimeError('abort transaction')
        self.assertEqual(self.store.list(), [])
        self.assert_connections_closed()

    def test_normal_store_operations_leave_no_open_handles(self):
        project = self.store.create('Proyek uji Windows')
        self.store.list()
        self.store.documents(project['id'])
        with self.assertRaises(LookupError):
            self.store.document('missing')
        self.assert_connections_closed()
        # Renaming/removing is blocked on Windows if a live connection remains.
        renamed = self.store.path.with_suffix('.moved')
        self.store.path.rename(renamed)
        renamed.unlink()
