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

            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO ai_event_suggestions (
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
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?)
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
