"""Pure stdlib tests (sqlite3 + tempfile only) for scripts.backup_db."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from scripts.backup_db import create_backup


class CreateBackupTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.source_path = Path(self._tmp_dir.name) / "source.db"
        self.dest_path = Path(self._tmp_dir.name) / "backup.db"

    def tearDown(self):
        self._tmp_dir.cleanup()

    def test_schema_and_committed_rows_are_copied(self):
        with closing(sqlite3.connect(self.source_path)) as conn:
            conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO events (name) VALUES ('Test Event')")
            conn.commit()

        create_backup(self.source_path, self.dest_path)

        with closing(sqlite3.connect(self.dest_path)) as conn:
            rows = conn.execute("SELECT name FROM events").fetchall()
            self.assertEqual(rows, [("Test Event",)])

    def test_backup_passes_integrity_check(self):
        with closing(sqlite3.connect(self.source_path)) as conn:
            conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT)")
            conn.execute("INSERT INTO events (name) VALUES ('A')")
            conn.commit()

        create_backup(self.source_path, self.dest_path)

        with closing(sqlite3.connect(self.dest_path)) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()[0]
            self.assertEqual(result, "ok")

    def test_uncommitted_write_excluded_from_backup(self):
        with closing(sqlite3.connect(self.source_path)) as setup_conn:
            setup_conn.execute("PRAGMA journal_mode=WAL")
            setup_conn.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, name TEXT)")
            setup_conn.execute("INSERT INTO events (name) VALUES ('Committed Row')")
            setup_conn.commit()

        # A separate connection holding an uncommitted write, simulating a
        # concurrent writer (the FastAPI service or Discord bot) at the
        # moment the backup runs.
        writer_conn = sqlite3.connect(self.source_path)
        writer_conn.execute("BEGIN")
        writer_conn.execute("INSERT INTO events (name) VALUES ('Uncommitted Row')")
        try:
            create_backup(self.source_path, self.dest_path)

            with closing(sqlite3.connect(self.dest_path)) as conn:
                names = {row[0] for row in conn.execute("SELECT name FROM events")}
                self.assertIn("Committed Row", names)
                self.assertNotIn("Uncommitted Row", names)
        finally:
            writer_conn.rollback()
            writer_conn.close()

if __name__ == "__main__":
    unittest.main()
