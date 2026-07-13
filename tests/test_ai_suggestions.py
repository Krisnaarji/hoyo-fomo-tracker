"""app.ai_suggestions has no fastapi/pydantic dependency (only app.db,
stdlib-only), so this actually runs."""
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from app import ai_suggestions
from app import db as db_module


class SaveAiEventSuggestionsTestCase(unittest.TestCase):
    def setUp(self):
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

    def _fetch_all(self):
        with closing(db_module.get_conn()) as conn:
            return [dict(row) for row in conn.execute("SELECT * FROM ai_event_suggestions")]

    def test_valid_event_inserted_as_pending(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Test Event", "suggested_category": "heavy"}]},
        )

        self.assertEqual(result, {"inserted": 1, "skipped": 0})
        rows = self._fetch_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "PENDING")
        self.assertEqual(rows[0]["suggested_category"], "heavy")

    def test_event_name_key_used_as_fallback_for_title(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"event_name": "Fallback Name"}]},
        )

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(self._fetch_all()[0]["event_name"], "Fallback Name")

    def test_missing_event_name_is_skipped(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"suggested_category": "heavy"}]},
        )

        self.assertEqual(result, {"inserted": 0, "skipped": 1})
        self.assertEqual(self._fetch_all(), [])

    def test_blank_event_name_is_skipped(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "   "}]},
        )

        self.assertEqual(result, {"inserted": 0, "skipped": 1})

    def test_invalid_category_normalized_to_info(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Weird Category", "suggested_category": "not_real"}]},
        )

        self.assertEqual(result["inserted"], 1)
        self.assertEqual(self._fetch_all()[0]["suggested_category"], "info")

    def test_missing_category_defaults_to_info(self):
        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "No Category"}]},
        )

        self.assertEqual(self._fetch_all()[0]["suggested_category"], "info")

    def test_category_matching_is_case_insensitive(self):
        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Loud Category", "suggested_category": "HEAVY"}]},
        )

        self.assertEqual(self._fetch_all()[0]["suggested_category"], "heavy")

    def test_event_types_serialized_as_json(self):
        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Typed Event", "event_types": ["In-Game", "Web"]}]},
        )

        stored = json.loads(self._fetch_all()[0]["event_types"])
        self.assertEqual(stored, ["In-Game", "Web"])

    def test_duplicate_suggestion_skipped_not_double_inserted(self):
        ai_result = {"events": [{"title": "Dup Event", "start_date": "2026-07-04"}]}

        first = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )
        second = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        self.assertEqual(first, {"inserted": 1, "skipped": 0})
        self.assertEqual(second, {"inserted": 0, "skipped": 1})
        self.assertEqual(len(self._fetch_all()), 1)

    def test_duplicate_with_both_dates_null_still_detected(self):
        # The exact NULL-vs-NULL case that defeated the raw UNIQUE
        # constraint before this fix.
        ai_result = {"events": [{"title": "Dateless Event"}]}

        first = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )
        second = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        self.assertEqual(first["inserted"], 1)
        self.assertEqual(second, {"inserted": 0, "skipped": 1})
        self.assertEqual(len(self._fetch_all()), 1)

    def test_duplicate_with_only_end_date_null_still_detected(self):
        ai_result = {"events": [{"title": "Open Ended Event", "start_date": "2026-07-04"}]}

        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )
        second = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        self.assertEqual(second, {"inserted": 0, "skipped": 1})

    def test_duplicate_still_prevented_after_status_changes(self):
        ai_result = {"events": [{"title": "Reviewed Event", "start_date": "2026-07-04"}]}

        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        with closing(db_module.get_conn()) as conn:
            conn.execute("UPDATE ai_event_suggestions SET status = 'ACCEPTED'")
            conn.commit()

        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        # Re-scraping the same source shouldn't resurrect a suggestion that
        # was already reviewed (accepted or rejected), not just PENDING ones.
        self.assertEqual(result, {"inserted": 0, "skipped": 1})
        self.assertEqual(len(self._fetch_all()), 1)

    def test_different_end_date_is_not_a_duplicate(self):
        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Same Name", "start_date": "2026-07-04", "end_date": "2026-07-20"}]},
        )
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": [{"title": "Same Name", "start_date": "2026-07-04", "end_date": "2026-07-25"}]},
        )

        self.assertEqual(result, {"inserted": 1, "skipped": 0})
        self.assertEqual(len(self._fetch_all()), 2)

    def test_different_source_hash_is_not_a_duplicate(self):
        ai_result = {"events": [{"title": "Same Name", "start_date": "2026-07-04"}]}

        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash2", ai_result=ai_result,
        )

        self.assertEqual(result, {"inserted": 1, "skipped": 0})

    def test_different_game_title_is_not_a_duplicate(self):
        ai_result = {"events": [{"title": "Same Name", "start_date": "2026-07-04"}]}

        ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="HSR", source_url="http://example.com", source_hash="hash1", ai_result=ai_result,
        )

        self.assertEqual(result, {"inserted": 1, "skipped": 0})

    def test_multiple_events_mixed_valid_and_invalid(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={
                "events": [
                    {"title": "Valid One"},
                    {"title": ""},
                    {"title": "Valid Two"},
                ]
            },
        )

        self.assertEqual(result, {"inserted": 2, "skipped": 1})

    def test_empty_events_list_inserts_nothing(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={"events": []},
        )

        self.assertEqual(result, {"inserted": 0, "skipped": 0})

    def test_missing_events_key_inserts_nothing(self):
        result = ai_suggestions.save_ai_event_suggestions(
            game_title="Genshin",
            source_url="http://example.com",
            source_hash="hash1",
            ai_result={},
        )

        self.assertEqual(result, {"inserted": 0, "skipped": 0})


if __name__ == "__main__":
    unittest.main()
