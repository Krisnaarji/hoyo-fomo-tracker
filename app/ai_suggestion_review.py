import json
from datetime import datetime, timezone

from app.db import get_conn, row_to_dict


CATEGORY_MAP = {
    "daily": "DAILY",
    "heavy": "HEAVY",
    "speedrun": "SPEEDRUN",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_date(value):
    if value is None:
        return None

    value = str(value).strip()

    if value.lower() in {"", "null", "none", "tba"}:
        return None

    return value


def fetch_pending_ai_suggestions(limit: int = 25):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_event_suggestions
            WHERE status = 'PENDING'
            ORDER BY game_title, start_date, end_date, event_name
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [row_to_dict(row) for row in rows]


def get_pending_ai_suggestion(suggestion_id: int):
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM ai_event_suggestions
            WHERE id = ?
              AND status = 'PENDING'
            """,
            (suggestion_id,),
        ).fetchone()

    return row_to_dict(row)


def format_suggestion_summary(suggestion: dict) -> str:
    event_types = suggestion.get("event_types") or "[]"

    try:
        event_types_value = ", ".join(json.loads(event_types))
    except json.JSONDecodeError:
        event_types_value = event_types

    return (
        f"**{suggestion['game_title']} — {suggestion['event_name']}**\n"
        f"Category: `{suggestion['suggested_category']}`\n"
        f"Date: `{suggestion.get('start_date')}` → `{suggestion.get('end_date')}`\n"
        f"Types: `{event_types_value}`\n"
        f"Reason: {suggestion.get('reason') or '-'}"
    )


def accept_ai_suggestion(suggestion_id: int):
    timestamp = now_iso()

    with get_conn() as conn:
        suggestion = conn.execute(
            """
            SELECT *
            FROM ai_event_suggestions
            WHERE id = ?
              AND status = 'PENDING'
            """,
            (suggestion_id,),
        ).fetchone()

        if suggestion is None:
            return {
                "ok": False,
                "message": f"No pending suggestion found with id {suggestion_id}",
            }

        suggestion = row_to_dict(suggestion)
        suggested_category = suggestion["suggested_category"]

        if suggested_category not in CATEGORY_MAP:
            return {
                "ok": False,
                "message": (
                    f"Suggestion {suggestion_id} is category '{suggested_category}', "
                    "so it cannot become a real reminder."
                ),
            }

        category_tag = CATEGORY_MAP[suggested_category]

        ai_summary_parts = []

        if suggestion.get("reason"):
            ai_summary_parts.append(suggestion["reason"])

        if suggestion.get("event_types"):
            try:
                event_types = json.loads(suggestion["event_types"])
                ai_summary_parts.append(f"Types: {', '.join(event_types)}")
            except json.JSONDecodeError:
                ai_summary_parts.append(f"Types: {suggestion['event_types']}")

        ai_summary = " | ".join(ai_summary_parts) if ai_summary_parts else None

        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO events (
                game_title,
                event_name,
                start_date,
                end_date,
                category_tag,
                progress_status,
                last_daily_checkin,
                is_muted,
                ai_summary,
                source_url,
                source_hash,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 0, NULL, 0, ?, ?, ?, ?, ?)
            """,
            (
                suggestion["game_title"],
                suggestion["event_name"],
                clean_date(suggestion["start_date"]),
                clean_date(suggestion["end_date"]),
                category_tag,
                ai_summary,
                suggestion["source_url"],
                suggestion["source_hash"],
                timestamp,
                timestamp,
            ),
        )

        if cursor.rowcount == 0:
            return {
                "ok": False,
                "message": "Event already exists. Suggestion left as PENDING.",
            }

        conn.execute(
            """
            UPDATE ai_event_suggestions
            SET status = 'ACCEPTED',
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, suggestion_id),
        )

        conn.commit()

    return {
        "ok": True,
        "message": f"Accepted suggestion {suggestion_id} → event id {cursor.lastrowid}",
        "event_id": cursor.lastrowid,
    }


def reject_ai_suggestion(suggestion_id: int):
    timestamp = now_iso()

    with get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE ai_event_suggestions
            SET status = 'REJECTED',
                updated_at = ?
            WHERE id = ?
              AND status = 'PENDING'
            """,
            (timestamp, suggestion_id),
        )
        conn.commit()

    if cursor.rowcount == 0:
        return {
            "ok": False,
            "message": f"No pending suggestion found with id {suggestion_id}",
        }

    return {
        "ok": True,
        "message": f"Rejected suggestion {suggestion_id}",
    }
