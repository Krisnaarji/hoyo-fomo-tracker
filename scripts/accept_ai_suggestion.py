import argparse
import json
from datetime import datetime, timezone

from app.db import get_conn


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


def main():
    parser = argparse.ArgumentParser(
        description="Accept one pending AI suggestion and create a real reminder event."
    )
    parser.add_argument("suggestion_id", type=int)

    args = parser.parse_args()
    timestamp = now_iso()

    with get_conn() as conn:
        suggestion = conn.execute(
            """
            SELECT *
            FROM ai_event_suggestions
            WHERE id = ?
              AND status = 'PENDING'
            """,
            (args.suggestion_id,),
        ).fetchone()

        if suggestion is None:
            print(f"No pending suggestion found with id {args.suggestion_id}")
            return

        suggested_category = suggestion["suggested_category"]

        if suggested_category not in CATEGORY_MAP:
            print(
                f"Suggestion {args.suggestion_id} has category '{suggested_category}', "
                "so it cannot become a real reminder yet."
            )
            return

        category_tag = CATEGORY_MAP[suggested_category]

        ai_summary_parts = []

        if suggestion["reason"]:
            ai_summary_parts.append(suggestion["reason"])

        if suggestion["event_types"]:
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
            print("Event already exists. Suggestion left as PENDING.")
            return

        conn.execute(
            """
            UPDATE ai_event_suggestions
            SET status = 'ACCEPTED',
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, args.suggestion_id),
        )

        conn.commit()

    print(f"Accepted suggestion {args.suggestion_id} → event id {cursor.lastrowid}")


if __name__ == "__main__":
    main()
