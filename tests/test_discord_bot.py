"""Tests for the pure grouping logic and persistent buttons in app.discord_bot.

Requires discord.py installed (see requirements.txt), and app.discord_bot
itself sets up a ZoneInfo("Asia/Makassar") at import time, so these tests
are skipped (not failed) when either dependency is unavailable, same as
tests/test_widget_today.py and tests/test_reminder_check.py.
"""
import asyncio
import unittest
from zoneinfo import ZoneInfoNotFoundError

try:
    from app.discord_bot import (
        DISCORD_SELECT_MAX_OPTIONS,
        SuggestionActionButton,
        SuggestionActionView,
        group_events_by_game,
    )

    RUNTIME_AVAILABLE = True
except (ImportError, ZoneInfoNotFoundError):
    RUNTIME_AVAILABLE = False


def make_event(id, game_title, category_tag, end_date, event_name="Event"):
    return {
        "id": id,
        "game_title": game_title,
        "category_tag": category_tag,
        "end_date": end_date,
        "event_name": event_name,
    }


@unittest.skipUnless(RUNTIME_AVAILABLE, "discord.py and/or Asia/Makassar tzdata not available")
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


@unittest.skipUnless(RUNTIME_AVAILABLE, "discord.py and/or Asia/Makassar tzdata not available")
class SuggestionActionButtonTestCase(unittest.TestCase):
    def test_view_is_persistent(self):
        view = SuggestionActionView({"id": 42, "suggested_category": "heavy"})
        self.assertTrue(view.is_persistent())

    def test_info_suggestions_omit_accept_button(self):
        view = SuggestionActionView({"id": 7, "suggested_category": "info"})
        actions = {child.action for child in view.children}
        self.assertEqual(actions, {"reject"})

    def test_non_info_suggestions_get_both_buttons(self):
        view = SuggestionActionView({"id": 7, "suggested_category": "daily"})
        actions = {child.action for child in view.children}
        self.assertEqual(actions, {"accept", "reject"})

    def test_custom_id_encodes_suggestion_id_and_action(self):
        button = SuggestionActionButton(99, "accept")
        self.assertEqual(button.custom_id, "suggestion:accept:99")

    def test_from_custom_id_reconstructs_button_after_restart(self):
        match = SuggestionActionButton.__discord_ui_compiled_template__.match(
            "suggestion:reject:123"
        )

        reconstructed = asyncio.run(
            SuggestionActionButton.from_custom_id(None, None, match)
        )

        self.assertEqual(reconstructed.suggestion_id, 123)
        self.assertEqual(reconstructed.action, "reject")
        self.assertTrue(reconstructed.is_persistent())

    def test_accept_callback_calls_accept_ai_suggestion(self):
        from unittest.mock import AsyncMock, patch

        button = SuggestionActionButton(5, "accept")
        interaction = AsyncMock()

        with patch(
            "app.discord_bot.accept_ai_suggestion",
            return_value={"message": "Accepted."},
        ) as accept_mock:
            asyncio.run(button.callback(interaction))

        accept_mock.assert_called_once_with(5)
        interaction.response.edit_message.assert_awaited_once_with(
            content="Accepted.", view=None
        )

    def test_reject_callback_calls_reject_ai_suggestion(self):
        from unittest.mock import AsyncMock, patch

        button = SuggestionActionButton(5, "reject")
        interaction = AsyncMock()

        with patch(
            "app.discord_bot.reject_ai_suggestion",
            return_value={"message": "Rejected."},
        ) as reject_mock:
            asyncio.run(button.callback(interaction))

        reject_mock.assert_called_once_with(5)
        interaction.response.edit_message.assert_awaited_once_with(
            content="Rejected.", view=None
        )


if __name__ == "__main__":
    unittest.main()
