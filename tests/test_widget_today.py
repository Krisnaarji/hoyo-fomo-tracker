"""Integration-layer tests for the /widget/today FastAPI route itself.

Requires fastapi/pydantic installed (see requirements.txt) - unlike
tests/test_widget_logic.py, which covers the actual business logic
(action rules, date math, counters) using only stdlib and runs
anywhere. These tests only cover the thin route wiring: registration,
limit parameter handling, and invalid-limit HTTPException handling.
"""
import importlib
import tempfile
import unittest
from pathlib import Path

from app import db as db_module


class WidgetTodayRouteTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._orig_db_path = db_module.DB_PATH
        db_module.DB_PATH = Path(self._tmp_dir.name) / "test_hoyo.db"

        global main
        main = importlib.import_module("app.main")
        importlib.reload(main)
        main.init_db()

    def tearDown(self):
        db_module.DB_PATH = self._orig_db_path
        self._tmp_dir.cleanup()

    def test_widget_today_route_is_registered(self):
        matching = [
            route
            for route in main.app.routes
            if getattr(route, "path", None) == "/widget/today"
            and "GET" in getattr(route, "methods", set())
        ]
        self.assertEqual(len(matching), 1)

    def test_widget_today_returns_empty_payload_shape_with_no_events(self):
        result = main.widget_today(limit=5)

        self.assertEqual(result["total_actions"], 0)
        self.assertEqual(result["hidden_actions"], 0)
        self.assertEqual(result["games"], [])
        self.assertIn("today", result)

    def test_limit_below_one_returns_400(self):
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as ctx:
            main.widget_today(limit=0)

        self.assertEqual(ctx.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
