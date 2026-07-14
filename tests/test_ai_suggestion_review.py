"""app.ai_suggestion_review has no fastapi/pydantic dependency (only
app.db + app.event_validation, both stdlib-only), so this actually runs."""
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from app import ai_suggestion_review as review
from app import db as db_module


class AcceptAiSuggestionTestCase(unittest.TestCase):
    def setUp(self):
        # accept_ai_suggestion() itself uses `with get_conn() as conn:`,
        # which (like the rest of the app) only commits/rolls back and never
        # closes - harmless on Linux, but Windows won't delete a still-open
        # temp db file, hence ignore_cleanup_errors here.
        self._tmp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._orig_db_path = db_module.DB_PATH
        db_module.DB_PATH = Path(self._tmp_dir.name) / "test_hoyo.db"

        with closing(db_module.get_conn()) as conn:
            schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
            conn.executescript(schema)
            conn.commit()

    def tearDown(self):
        db_module.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def _insert_suggestion(self, start_date=None, end_date=None, suggested_category="heavy"):
        timestamp = datetime.now(timezone.utc).isoformat()
        with closing(db_module.get_conn()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO ai_event_suggestions (
                    game_title, event_name, start_date, end_date, event_types,
                    suggested_category, reason, source_url, source_hash,
                    status, raw_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, NULL, ?, NULL, ?, ?, 'PENDING', NULL, ?, ?)
                """,
                (
                    "Genshin",
                    "Test Event",
                    start_date,
                    end_date,
                    suggested_category,
                    "http://example.com",
                    "hash123",
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def _count_events(self):
        with closing(db_module.get_conn()) as conn:
            return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def _suggestion_status(self, suggestion_id):
        with closing(db_module.get_conn()) as conn:
            row = conn.execute(
                "SELECT status FROM ai_event_suggestions WHERE id = ?",
                (suggestion_id,),
            ).fetchone()
            return row["status"]

    def test_valid_dates_accepted_and_event_created(self):
        suggestion_id = self._insert_suggestion(start_date="2026-07-04", end_date="2026-07-20")

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertTrue(result["ok"])
        self.assertEqual(self._count_events(), 1)
        self.assertEqual(self._suggestion_status(suggestion_id), "ACCEPTED")

    def test_valid_with_null_dates_accepted(self):
        suggestion_id = self._insert_suggestion(start_date=None, end_date=None)

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertTrue(result["ok"])
        self.assertEqual(self._count_events(), 1)

    def test_malformed_start_date_rejected_and_left_pending(self):
        suggestion_id = self._insert_suggestion(start_date="not-a-date", end_date="2026-07-20")

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertFalse(result["ok"])
        self.assertEqual(self._count_events(), 0)
        self.assertEqual(self._suggestion_status(suggestion_id), "PENDING")

    def test_malformed_end_date_rejected_and_left_pending(self):
        # "2026/07/20" survives clean_date() unchanged (not one of its
        # recognized placeholders) but fails strict YYYY-MM-DD validation.
        suggestion_id = self._insert_suggestion(start_date="2026-07-04", end_date="2026/07/20")

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertFalse(result["ok"])
        self.assertEqual(self._count_events(), 0)
        self.assertEqual(self._suggestion_status(suggestion_id), "PENDING")

    def test_tba_end_date_cleaned_to_null_and_accepted(self):
        # clean_date() normalizes "TBA"/"null"/"none"/"" to None before
        # validation runs, so this should NOT be rejected.
        suggestion_id = self._insert_suggestion(start_date="2026-07-04", end_date="TBA")

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertTrue(result["ok"])

    def test_duplicate_of_existing_event_is_auto_rejected_not_left_pending(self):
        # save_ai_event_suggestions now skips creating suggestions for
        # events that already exist, but a suggestion saved before that
        # check existed can still land here - it must not get stuck as
        # PENDING forever (the bug that caused endless "Event already
        # exists" spam every time it was re-accepted).
        with closing(db_module.get_conn()) as conn:
            conn.execute(
                """
                INSERT INTO events (
                    game_title, event_name, start_date, end_date,
                    category_tag, created_at, updated_at
                )
                VALUES ('Genshin', 'Test Event', '2026-07-04', '2026-07-20', 'HEAVY', 'ts', 'ts')
                """
            )
            conn.commit()

        suggestion_id = self._insert_suggestion(start_date="2026-07-04", end_date="2026-07-20")

        result = review.accept_ai_suggestion(suggestion_id)

        self.assertFalse(result["ok"])
        self.assertEqual(self._count_events(), 1)
        self.assertEqual(self._suggestion_status(suggestion_id), "REJECTED")

    def test_duplicate_rejection_does_not_affect_other_pending_suggestions(self):
        with closing(db_module.get_conn()) as conn:
            conn.execute(
                """
                INSERT INTO events (
                    game_title, event_name, start_date, end_date,
                    category_tag, created_at, updated_at
                )
                VALUES ('Genshin', 'Test Event', '2026-07-04', '2026-07-20', 'HEAVY', 'ts', 'ts')
                """
            )
            conn.commit()

        duplicate_id = self._insert_suggestion(start_date="2026-07-04", end_date="2026-07-20")
        other_id = self._insert_suggestion(start_date="2026-08-01", end_date="2026-08-20")

        review.accept_ai_suggestion(duplicate_id)

        self.assertEqual(self._suggestion_status(other_id), "PENDING")


if __name__ == "__main__":
    unittest.main()
