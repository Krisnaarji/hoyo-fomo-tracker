"""Pure-logic backend tests. Imports only stdlib + app.db/app.widget_logic -
no fastapi/pydantic - so this actually runs with the system Python, unlike
tests that import app.main (which needs the web framework installed)."""
import tempfile
import unittest
from contextlib import closing
from datetime import date, datetime, timedelta, timezone as dt_timezone
from pathlib import Path

from app import db as db_module
from app.widget_logic import build_widget_today_payload

# A fixed, arbitrary UTC+8 offset instead of ZoneInfo("Asia/Makassar") -
# this Windows machine has no tzdata installed, so constructing a real
# ZoneInfo raises ZoneInfoNotFoundError. Fixed-offset timezone is enough
# to exercise the date-boundary logic without needing tzdata.
FIXED_TZ = dt_timezone(timedelta(hours=8))
FIXED_TODAY = date(2026, 7, 14)


class WidgetLogicTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._orig_db_path = db_module.DB_PATH
        db_module.DB_PATH = Path(self._tmp_dir.name) / "test_hoyo.db"

        with closing(db_module.get_conn()) as conn:
            schema = (Path(__file__).resolve().parent.parent / "schema.sql").read_text()
            conn.executescript(schema)
            conn.commit()

    def tearDown(self):
        db_module.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def _now_iso(self):
        return datetime.now(dt_timezone.utc).isoformat()

    def _insert_event(
        self,
        game_title,
        event_name,
        category_tag,
        end_date=None,
        start_date=None,
        progress_status=0,
        is_muted=0,
        last_daily_checkin=None,
    ):
        timestamp = self._now_iso()
        with closing(db_module.get_conn()) as conn:
            cursor = conn.execute(
                """
                INSERT INTO events (
                    game_title, event_name, start_date, end_date, category_tag,
                    progress_status, last_daily_checkin, is_muted,
                    ai_summary, source_url, source_hash, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?)
                """,
                (
                    game_title,
                    event_name,
                    start_date,
                    end_date,
                    category_tag,
                    progress_status,
                    last_daily_checkin,
                    is_muted,
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def _payload(self, limit=5):
        with closing(db_module.get_conn()) as conn:
            return build_widget_today_payload(conn, limit, FIXED_TODAY, FIXED_TZ)

    def test_daily_action_when_not_checked_in(self):
        event_id = self._insert_event("Genshin", "Daily Login", "DAILY")

        result = self._payload()

        event_json = result["games"][0]["events"][0]
        self.assertEqual(result["total_actions"], 1)
        self.assertEqual(result["hidden_actions"], 0)
        self.assertEqual(
            event_json["action"],
            {
                "endpoint": f"/events/{event_id}/daily-checkin",
                "method": "POST",
                "label": "Check-in",
            },
        )

    def test_daily_action_hidden_when_checked_in_today(self):
        self._insert_event(
            "Genshin", "Daily Login", "DAILY",
            last_daily_checkin=FIXED_TODAY.isoformat(),
        )

        result = self._payload()

        event_json = result["games"][0]["events"][0]
        self.assertNotIn("action", event_json)
        self.assertEqual(result["total_actions"], 0)

    def test_daily_checkin_timezone_boundary_converts_utc_to_local_date(self):
        # 2026-07-13 20:00 UTC is 2026-07-14 04:00 in UTC+8 (FIXED_TZ) - i.e.
        # FIXED_TODAY locally, even though the UTC calendar date is different.
        # This only exercises the tz-conversion branch of parse_local_date
        # (a bare "YYYY-MM-DD" string never calls astimezone at all).
        self._insert_event(
            "Genshin", "Daily Login", "DAILY",
            last_daily_checkin="2026-07-13T20:00:00+00:00",
        )

        result = self._payload()

        event_json = result["games"][0]["events"][0]
        self.assertNotIn("action", event_json)
        self.assertEqual(result["total_actions"], 0)

    def test_speedrun_action_shape(self):
        self._insert_event("HSR", "Speedrun Boss", "SPEEDRUN")

        result = self._payload()

        action = result["games"][0]["events"][0]["action"]
        self.assertEqual(action["label"], "Done")
        self.assertEqual(action["body"], {"progress_status": 100})

    def test_heavy_action_shape(self):
        self._insert_event("ZZZ", "Lore Event", "HEAVY")

        result = self._payload()

        action = result["games"][0]["events"][0]["action"]
        self.assertEqual(action["body_options"], [25, 50, 75, 100])
        self.assertNotIn("label", action)

    def test_muted_event_excluded_entirely(self):
        self._insert_event("Genshin", "Old Event", "SPEEDRUN", is_muted=1)

        result = self._payload()

        self.assertEqual(result["games"], [])
        self.assertEqual(result["total_actions"], 0)

    def test_completed_event_hides_action_defensively(self):
        self._insert_event(
            "ZZZ", "Finished Heavy", "HEAVY", progress_status=100, is_muted=0
        )

        result = self._payload()

        event_json = result["games"][0]["events"][0]
        self.assertNotIn("action", event_json)
        self.assertEqual(result["total_actions"], 0)

    def test_days_left_computed_from_end_date(self):
        end = FIXED_TODAY + timedelta(days=3)
        self._insert_event("Genshin", "Ending Soon", "SPEEDRUN", end_date=end.isoformat())

        result = self._payload()

        self.assertEqual(result["games"][0]["events"][0]["days_left"], 3)

    def test_days_left_null_when_no_end_date(self):
        self._insert_event("Genshin", "No End Date", "SPEEDRUN")

        result = self._payload()

        self.assertIsNone(result["games"][0]["events"][0]["days_left"])

    def test_limit_caps_events_and_reports_hidden_actions(self):
        for i in range(3):
            self._insert_event("Genshin", f"Speedrun {i}", "SPEEDRUN")

        result = self._payload(limit=2)

        total_events = sum(len(g["events"]) for g in result["games"])
        self.assertEqual(total_events, 2)
        self.assertEqual(result["total_actions"], 3)
        self.assertEqual(result["hidden_actions"], 1)

    def test_hidden_actions_counts_omitted_actionable_event_in_capped_slot(self):
        self._insert_event(
            "Genshin", "Already Checked In", "DAILY",
            last_daily_checkin=FIXED_TODAY.isoformat(),
        )
        self._insert_event("HSR", "Speedrun Overflow", "SPEEDRUN")

        result = self._payload(limit=1)

        total_events = sum(len(g["events"]) for g in result["games"])
        self.assertEqual(total_events, 1)
        self.assertEqual(result["total_actions"], 1)
        self.assertEqual(result["hidden_actions"], 1)

    def test_emoji_values_match_category(self):
        self._insert_event("Genshin", "Daily", "DAILY")
        self._insert_event("HSR", "Heavy", "HEAVY")
        self._insert_event("ZZZ", "Speedrun", "SPEEDRUN")

        result = self._payload(limit=10)

        emojis = {
            event["category_tag"]: event["emoji"]
            for game in result["games"]
            for event in game["events"]
        }
        self.assertEqual(emojis, {"DAILY": "🎁", "HEAVY": "🔥", "SPEEDRUN": "⚡"})

    def test_limit_below_one_rejected(self):
        with closing(db_module.get_conn()) as conn:
            with self.assertRaises(ValueError):
                build_widget_today_payload(conn, 0, FIXED_TODAY, FIXED_TZ)

    def test_events_grouped_by_game_title(self):
        self._insert_event("Genshin", "Event A", "SPEEDRUN")
        self._insert_event("HSR", "Event B", "SPEEDRUN")
        self._insert_event("Genshin", "Event C", "DAILY")

        result = self._payload(limit=10)

        titles = [g["game_title"] for g in result["games"]]
        self.assertEqual(titles, ["Genshin", "HSR"])
        self.assertEqual(len(result["games"][0]["events"]), 2)

    def test_today_field_is_local_date(self):
        result = self._payload()
        self.assertEqual(result["today"], FIXED_TODAY.isoformat())

    def test_malformed_last_daily_checkin_does_not_crash(self):
        event_id = self._insert_event(
            "Genshin", "Weird Data", "DAILY", last_daily_checkin="not-a-date"
        )
        result = self._payload()
        # Malformed date should be treated as "not checked in today" rather
        # than raising - a defensive fix applied after the original review.
        event_json = result["games"][0]["events"][0]
        self.assertIn("action", event_json)
        self.assertTrue(event_id > 0)


if __name__ == "__main__":
    unittest.main()
