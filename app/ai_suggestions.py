import json
from datetime import datetime, timezone
from typing import Any

from app.db import get_conn


VALID_CATEGORIES = {"daily", "heavy", "speedrun", "info"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_category(category: str | None) -> str:
    category = (category or "info").strip().lower()

    if category not in VALID_CATEGORIES:
        return "info"

    return category


def save_ai_event_suggestions(
    *,
    game_title: str,
    source_url: str,
    source_hash: str,
    ai_result: dict[str, Any],
) -> dict[str, int]:
    timestamp = now_iso()
    inserted = 0
    skipped = 0

    events = ai_result.get("events", [])

    with get_conn() as conn:
        for event in events:
            event_name = (event.get("title") or event.get("event_name") or "").strip()

            if not event_name:
                skipped += 1
                continue

            start_date = event.get("start_date")
            end_date = event.get("end_date")
            event_types = event.get("event_types", [])
            suggested_category = normalize_category(event.get("suggested_category"))
            reason = event.get("reason")

            # UNIQUE(game_title, event_name, start_date, end_date, source_hash)
            # does NOT catch duplicates when start_date/end_date is NULL (SQL
            # NULL is never equal to NULL), which is common for dateless
            # events - INSERT OR IGNORE alone would silently re-insert the
            # same suggestion on every re-scrape. This does a NULL-safe
            # ("IS" instead of "=") existence check atomically in the same
            # statement, regardless of the suggestion's review status.
            #
            # The second NOT EXISTS guards against a different case: the
            # source page's content hash changes for reasons that have
            # nothing to do with the event list itself (wiki formatting
            # edits, ad content, relative-date text), which makes the AI
            # re-extract the *entire* current event list - including events
            # already accepted from a previous scrape under a different
            # source_hash. Without this check, those come back as "new"
            # suggestions for an event that already exists, which can never
            # be accepted (see accept_ai_suggestion's duplicate handling).
            cursor = conn.execute(
                """
                INSERT INTO ai_event_suggestions (
                    game_title,
                    event_name,
                    start_date,
                    end_date,
                    event_types,
                    suggested_category,
                    reason,
                    source_url,
                    source_hash,
                    status,
                    raw_json,
                    created_at,
                    updated_at
                )
                SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM ai_event_suggestions
                    WHERE game_title = ?
                      AND event_name = ?
                      AND start_date IS ?
                      AND end_date IS ?
                      AND source_hash = ?
                )
                AND NOT EXISTS (
                    SELECT 1 FROM events
                    WHERE game_title = ?
                      AND event_name = ?
                      AND start_date IS ?
                      AND end_date IS ?
                )
                """,
                (
                    game_title,
                    event_name,
                    start_date,
                    end_date,
                    json.dumps(event_types, ensure_ascii=False),
                    suggested_category,
                    reason,
                    source_url,
                    source_hash,
                    json.dumps(event, ensure_ascii=False),
                    timestamp,
                    timestamp,
                    game_title,
                    event_name,
                    start_date,
                    end_date,
                    source_hash,
                    game_title,
                    event_name,
                    start_date,
                    end_date,
                ),
            )

            if cursor.rowcount == 1:
                inserted += 1
            else:
                skipped += 1

        conn.commit()

    return {
        "inserted": inserted,
        "skipped": skipped,
    }
