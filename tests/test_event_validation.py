"""Pure stdlib tests for date validation - no fastapi/pydantic needed."""
import unittest

from app.event_validation import is_valid_iso_date


class EventValidationTestCase(unittest.TestCase):
    def test_none_is_valid(self):
        self.assertTrue(is_valid_iso_date(None))

    def test_normal_date_is_valid(self):
        self.assertTrue(is_valid_iso_date("2026-07-14"))

    def test_leap_day_is_valid(self):
        self.assertTrue(is_valid_iso_date("2024-02-29"))

    def test_non_leap_year_feb29_is_invalid(self):
        self.assertFalse(is_valid_iso_date("2026-02-29"))

    def test_impossible_month_is_invalid(self):
        self.assertFalse(is_valid_iso_date("2026-13-01"))

    def test_impossible_day_is_invalid(self):
        self.assertFalse(is_valid_iso_date("2026-04-31"))

    def test_empty_string_is_invalid(self):
        self.assertFalse(is_valid_iso_date(""))

    def test_whitespace_only_is_invalid(self):
        self.assertFalse(is_valid_iso_date("   "))

    def test_datetime_string_is_invalid(self):
        self.assertFalse(is_valid_iso_date("2026-07-14T10:00:00"))

    def test_compact_date_is_invalid(self):
        self.assertFalse(is_valid_iso_date("20260714"))

    def test_iso_week_date_is_invalid(self):
        self.assertFalse(is_valid_iso_date("2026-W29-2"))

    def test_tba_placeholder_is_invalid(self):
        self.assertFalse(is_valid_iso_date("TBA"))

    def test_date_with_surrounding_whitespace_is_invalid(self):
        self.assertFalse(is_valid_iso_date(" 2026-07-14 "))


if __name__ == "__main__":
    unittest.main()
