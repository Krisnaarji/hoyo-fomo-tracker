"""Pure stdlib tests for the Discord digest chunking in scripts.reminder_check.

scripts.reminder_check sets up a ZoneInfo("Asia/Makassar") at import time,
so these tests are skipped (not failed) when tzdata isn't available, same
as tests/test_widget_today.py.
"""
import unittest
from zoneinfo import ZoneInfoNotFoundError

try:
    from scripts.reminder_check import build_discord_digests

    RUNTIME_AVAILABLE = True
except ZoneInfoNotFoundError:
    RUNTIME_AVAILABLE = False


def make_reminder(event_id, game_title, category_tag, event_name="Event", message="Do the thing."):
    return {
        "event_id": event_id,
        "game_title": game_title,
        "event_name": event_name,
        "category_tag": category_tag,
        "reminder_type": f"{category_tag}_TEST",
        "message": message,
    }


@unittest.skipUnless(RUNTIME_AVAILABLE, "tzdata not available")
class BuildDiscordDigestsTestCase(unittest.TestCase):
    def test_empty_reminders_returns_no_digests(self):
        self.assertEqual(build_discord_digests([]), [])

    def test_small_reminder_set_fits_in_a_single_digest(self):
        reminders = [
            make_reminder(1, "Genshin", "DAILY"),
            make_reminder(2, "ZZZ", "HEAVY"),
        ]

        digests = build_discord_digests(reminders)

        self.assertEqual(len(digests), 1)
        text, digest_reminders = digests[0]
        self.assertIn("Genshin", text)
        self.assertIn("ZZZ", text)
        self.assertEqual(len(digest_reminders), 2)

    def test_every_reminder_appears_exactly_once_across_chunks(self):
        reminders = [
            make_reminder(i, "ZZZ", "DAILY", event_name=f"Event {i}")
            for i in range(20)
        ]

        digests = build_discord_digests(reminders, max_length=200)

        all_ids = [r["event_id"] for _, digest_reminders in digests for r in digest_reminders]
        self.assertEqual(sorted(all_ids), list(range(20)))

    def test_no_chunk_exceeds_max_length(self):
        reminders = [
            make_reminder(i, "Genshin", "HEAVY", event_name=f"Long Event Name Number {i}")
            for i in range(15)
        ]

        digests = build_discord_digests(reminders, max_length=300)

        for text, _ in digests:
            self.assertLessEqual(len(text), 300)

    def test_splitting_produces_more_than_one_chunk_when_needed(self):
        reminders = [
            make_reminder(i, "HSR", "SPEEDRUN", event_name=f"Event {i}")
            for i in range(30)
        ]

        digests = build_discord_digests(reminders, max_length=200)

        self.assertGreater(len(digests), 1)

    def test_continuation_chunks_still_include_a_game_header(self):
        reminders = [
            make_reminder(i, "HSR", "SPEEDRUN", event_name=f"Event {i}")
            for i in range(30)
        ]

        digests = build_discord_digests(reminders, max_length=200)

        for text, _ in digests[1:]:
            self.assertIn("## HSR", text)

    def test_single_oversized_reminder_still_gets_its_own_chunk(self):
        reminders = [
            make_reminder(1, "ZZZ", "HEAVY", message="x" * 5000),
        ]

        digests = build_discord_digests(reminders, max_length=200)

        self.assertEqual(len(digests), 1)
        self.assertEqual(len(digests[0][1]), 1)


if __name__ == "__main__":
    unittest.main()
