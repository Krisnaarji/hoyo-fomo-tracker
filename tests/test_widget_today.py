"""Requires the project's existing requirements.txt installed (fastapi et al.)."""
import importlib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from app import db as db_module


class WidgetTodayTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._orig_db_path = db_module.DB_PATH
        db_module.DB_PATH = Path(self._tmp_dir.name) / "test_hoyo.db"

        global main
        main = importlib.import_module("app.main")
        importlib.reload(main)
        main.init_db()

        self.today = main.today_local()

    def tearDown(self):
        db_module.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

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
        timestamp = main.now_iso()
        with db_module.get_conn() as conn:
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

    def test_daily_action_when_not_checked_in(self):
        event_id = self._insert_event("Genshin", "Daily Login", "DAILY")

        result = main.widget_today(limit=5)

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
            "Genshin",
            "Daily Login",
            "DAILY",
            last_daily_checkin=self.today.isoformat(),
        )

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertNotIn("action", event_json)
        self.assertEqual(result["total_actions"], 0)

    def test_speedrun_action_shape(self):
        self._insert_event("HSR", "Speedrun Boss", "SPEEDRUN")

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertEqual(event_json["action"]["label"], "Done")
        self.assertEqual(event_json["action"]["body"], {"progress_status": 100})

    def test_heavy_action_shape(self):
        self._insert_event("ZZZ", "Lore Event", "HEAVY")

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertEqual(event_json["action"]["body_options"], [25, 50, 75, 100])
        self.assertNotIn("label", event_json["action"])

    def test_muted_event_excluded_entirely(self):
        self._insert_event("Genshin", "Old Event", "SPEEDRUN", is_muted=1)

        result = main.widget_today(limit=5)

        self.assertEqual(result["games"], [])
        self.assertEqual(result["total_actions"], 0)

    def test_completed_event_hides_action_defensively(self):
        # is_muted should already be 1 once progress hits 100 in real usage,
        # but build_widget_action stays defensive in case data drifts.
        event_id = self._insert_event(
            "ZZZ", "Finished Heavy", "HEAVY", progress_status=100, is_muted=0
        )

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertNotIn("action", event_json)
        self.assertEqual(result["total_actions"], 0)
        self.assertEqual(event_id > 0, True)

    def test_days_left_computed_from_end_date(self):
        end = self.today + timedelta(days=3)
        self._insert_event("Genshin", "Ending Soon", "SPEEDRUN", end_date=end.isoformat())

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertEqual(event_json["days_left"], 3)

    def test_days_left_null_when_no_end_date(self):
        self._insert_event("Genshin", "No End Date", "SPEEDRUN")

        result = main.widget_today(limit=5)

        event_json = result["games"][0]["events"][0]
        self.assertIsNone(event_json["days_left"])

    def test_limit_caps_events_and_reports_hidden_actions(self):
        for i in range(3):
            self._insert_event("Genshin", f"Speedrun {i}", "SPEEDRUN")

        result = main.widget_today(limit=2)

        total_events = sum(len(g["events"]) for g in result["games"])
        self.assertEqual(total_events, 2)
        self.assertEqual(result["total_actions"], 3)
        self.assertEqual(result["hidden_actions"], 1)

    def test_hidden_actions_counts_omitted_actionable_event_in_capped_slot(self):
        self._insert_event(
            "Genshin",
            "Already Checked In",
            "DAILY",
            last_daily_checkin=self.today.isoformat(),
        )
        self._insert_event("HSR", "Speedrun Overflow", "SPEEDRUN")

        result = main.widget_today(limit=1)

        total_events = sum(len(g["events"]) for g in result["games"])
        self.assertEqual(total_events, 1)
        self.assertEqual(result["total_actions"], 1)
        self.assertEqual(result["hidden_actions"], 1)

    def test_widget_today_route_is_registered(self):
        matching = [
            route
            for route in main.app.routes
            if getattr(route, "path", None) == "/widget/today"
            and "GET" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matching), 1)

    def test_emoji_values_match_category(self):
        self._insert_event("Genshin", "Daily", "DAILY")
        self._insert_event("HSR", "Heavy", "HEAVY")
        self._insert_event("ZZZ", "Speedrun", "SPEEDRUN")

        result = main.widget_today(limit=10)

        emojis = {
            event["category_tag"]: event["emoji"]
            for game in result["games"]
            for event in game["events"]
        }
        self.assertEqual(emojis, {"DAILY": "🎁", "HEAVY": "🔥", "SPEEDRUN": "⚡"})

    def test_limit_below_one_rejected(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException):
            main.widget_today(limit=0)

    def test_events_grouped_by_game_title(self):
        self._insert_event("Genshin", "Event A", "SPEEDRUN")
        self._insert_event("HSR", "Event B", "SPEEDRUN")
        self._insert_event("Genshin", "Event C", "DAILY")

        result = main.widget_today(limit=10)

        titles = [g["game_title"] for g in result["games"]]
        self.assertEqual(titles, ["Genshin", "HSR"])
        self.assertEqual(len(result["games"][0]["events"]), 2)

    def test_today_field_is_local_date(self):
        result = main.widget_today(limit=5)
        self.assertEqual(result["today"], self.today.isoformat())


if __name__ == "__main__":
    unittest.main()
