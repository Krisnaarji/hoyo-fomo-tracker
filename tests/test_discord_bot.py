"""Tests for the pure grouping logic in app.discord_bot.

Requires discord.py installed (see requirements.txt). Skipped (not
failed) when it isn't, so `python -m unittest discover` reports this
gap honestly instead of as an import error.
"""
import unittest

try:
    import discord  # noqa: F401

    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

if DISCORD_AVAILABLE:
    from app.discord_bot import DISCORD_SELECT_MAX_OPTIONS, group_events_by_game


def make_event(id, game_title, category_tag, end_date, event_name="Event"):
    return {
        "id": id,
        "game_title": game_title,
        "category_tag": category_tag,
        "end_date": end_date,
        "event_name": event_name,
    }


@unittest.skipUnless(DISCORD_AVAILABLE, "discord.py not available")
class GroupEventsByGameTestCase(unittest.TestCase):
    def test_groups_by_game_title(self):
        events = [
            make_event(1, "Genshin", "DAILY", "2026-07-20"),
            make_event(2, "ZZZ", "HEAVY", "2026-07-25"),
            make_event(3, "Genshin", "SPEEDRUN", "2026-07-18"),
        ]

        grouped = group_events_by_game(events)

        self.assertEqual(set(grouped.keys()), {"Genshin", "ZZZ"})
        self.assertEqual({e["id"] for e in grouped["Genshin"]}, {1, 3})
        self.assertEqual({e["id"] for e in grouped["ZZZ"]}, {2})

    def test_sorted_by_category_priority_then_end_date_then_name(self):
        events = [
            make_event(1, "Genshin", "HEAVY", "2026-07-20", "Z Heavy"),
            make_event(2, "Genshin", "DAILY", "2026-07-20", "Daily"),
            make_event(3, "Genshin", "SPEEDRUN", "2026-07-18", "Speedrun"),
        ]

        grouped = group_events_by_game(events)

        self.assertEqual([e["id"] for e in grouped["Genshin"]], [2, 3, 1])

    def test_truncates_each_group_to_max_per_group(self):
        events = [
            make_event(i, "ZZZ", "DAILY", "2026-07-20", f"Event {i}")
            for i in range(30)
        ]

        grouped = group_events_by_game(events, max_per_group=25)

        self.assertEqual(len(grouped["ZZZ"]), 25)

    def test_default_max_per_group_matches_discord_select_cap(self):
        events = [
            make_event(i, "ZZZ", "DAILY", "2026-07-20", f"Event {i}")
            for i in range(30)
        ]

        grouped = group_events_by_game(events)

        self.assertEqual(len(grouped["ZZZ"]), DISCORD_SELECT_MAX_OPTIONS)

    def test_truncation_keeps_highest_priority_events(self):
        events = [
            make_event(0, "ZZZ", "HEAVY", "2026-08-01", "Low priority")
        ] + [
            make_event(i, "ZZZ", "DAILY", "2026-07-20", f"Event {i}")
            for i in range(1, 26)
        ]

        grouped = group_events_by_game(events, max_per_group=25)

        self.assertNotIn(0, {e["id"] for e in grouped["ZZZ"]})

    def test_events_without_end_date_sort_last_within_category(self):
        events = [
            make_event(1, "HSR", "HEAVY", None, "No end date"),
            make_event(2, "HSR", "HEAVY", "2026-07-20", "Has end date"),
        ]

        grouped = group_events_by_game(events)

        self.assertEqual([e["id"] for e in grouped["HSR"]], [2, 1])

    def test_games_are_returned_in_alphabetical_order(self):
        events = [
            make_event(1, "ZZZ", "DAILY", "2026-07-20"),
            make_event(2, "Genshin", "DAILY", "2026-07-20"),
            make_event(3, "HSR", "DAILY", "2026-07-20"),
        ]

        grouped = group_events_by_game(events)

        self.assertEqual(list(grouped.keys()), ["Genshin", "HSR", "ZZZ"])


if __name__ == "__main__":
    unittest.main()
