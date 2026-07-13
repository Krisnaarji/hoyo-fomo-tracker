"""app.ai_event_extractor is importable without network access (only needs
requests + optional python-dotenv, both present or gracefully absent here).
These tests cover keep_current_and_upcoming_only's pure text trimming -
zero network calls, zero API keys needed."""
import unittest

from app.ai_event_extractor import keep_current_and_upcoming_only


class KeepCurrentAndUpcomingOnlyTestCase(unittest.TestCase):
    def test_trims_everything_before_start_marker(self):
        text = "Navigation junk\nCurrent Event Duration Type(s)\nReal content here"

        result = keep_current_and_upcoming_only(text)

        self.assertTrue(result.startswith("Current Event Duration Type(s)"))
        self.assertIn("Real content here", result)
        self.assertNotIn("Navigation junk", result)

    def test_alternate_start_marker_also_recognized(self):
        text = "Header\nCurrent Duration Type(s)\nSome content"

        result = keep_current_and_upcoming_only(text)

        self.assertTrue(result.startswith("Current Duration Type(s)"))

    def test_no_start_marker_keeps_text_from_beginning(self):
        text = "No markers here, just plain content"

        result = keep_current_and_upcoming_only(text)

        self.assertEqual(result, text)

    def test_trims_everything_after_end_marker(self):
        text = (
            "Current Event Duration Type(s)\n"
            "Real event content\n"
            "Permanent Event Release Date\n"
            "Unrelated permanent event junk"
        )

        result = keep_current_and_upcoming_only(text)

        self.assertIn("Real event content", result)
        self.assertNotIn("Unrelated permanent event junk", result)

    def test_picks_earliest_end_marker_when_multiple_present(self):
        text = (
            "Current Event Duration Type(s)\n"
            "Real content\n"
            "Navigation\n"
            "middle junk\n"
            "Other Languages\n"
            "more junk"
        )

        result = keep_current_and_upcoming_only(text)

        self.assertIn("Real content", result)
        self.assertNotIn("middle junk", result)
        self.assertNotIn("more junk", result)

    def test_end_marker_before_upcoming_marker_is_ignored(self):
        # A page listing an "Upcoming" section's own boilerplate (e.g. its
        # own "Navigation" footer reference) shouldn't truncate the text
        # before we ever reach the upcoming-events content that follows it.
        text = (
            "Current Event Duration Type(s)\n"
            "Current event content\n"
            "Navigation\n"
            "Upcoming Event Duration Type(s)\n"
            "Upcoming event content\n"
            "Other Languages\n"
            "real trailing junk"
        )

        result = keep_current_and_upcoming_only(text)

        # "Navigation" appears before the Upcoming marker, so it must NOT be
        # used as the cut point - only "Other Languages" (after Upcoming)
        # should end up truncating the text.
        self.assertIn("Current event content", result)
        self.assertIn("Upcoming event content", result)
        self.assertNotIn("real trailing junk", result)

    def test_end_marker_appearing_both_before_and_after_upcoming_uses_later_one(self):
        # "Navigation" appears once before the Upcoming marker (correctly
        # ignored) and once after it (the actual, valid cutoff point). A
        # bare find() would locate only the first occurrence, see it's
        # before the Upcoming marker, and skip the marker entirely -
        # missing the later, valid occurrence and failing to truncate.
        text = (
            "Current Event Duration Type(s)\n"
            "Current event content\n"
            "Navigation\n"
            "Upcoming Event Duration Type(s)\n"
            "Upcoming event content\n"
            "Navigation\n"
            "real trailing junk"
        )

        result = keep_current_and_upcoming_only(text)

        self.assertIn("Current event content", result)
        self.assertIn("Upcoming event content", result)
        self.assertNotIn("real trailing junk", result)

    def test_no_end_marker_keeps_rest_of_text(self):
        text = "Current Event Duration Type(s)\nAll of this should remain"

        result = keep_current_and_upcoming_only(text)

        self.assertEqual(result, text)

    def test_result_is_stripped(self):
        text = "Current Event Duration Type(s)\n   content with padding   "

        result = keep_current_and_upcoming_only(text)

        self.assertEqual(result, result.strip())


if __name__ == "__main__":
    unittest.main()
