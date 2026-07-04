from datetime import datetime, timezone

from app.db import get_conn, init_db


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


SEED_EVENTS = [
    {
        "game_title": "Genshin",
        "event_name": "Test Daily Login Event",
        "start_date": "2026-07-04",
        "end_date": "2026-07-20",
        "category_tag": "DAILY",
        "ai_summary": "A test daily login event that requires checking in every day.",
    },
    {
        "game_title": "HSR",
        "event_name": "Test Heavy Lore Event",
        "start_date": "2026-07-04",
        "end_date": "2026-07-25",
        "category_tag": "HEAVY",
        "ai_summary": "A test heavy event with long story content and multiple stages.",
    },
    {
        "game_title": "ZZZ",
        "event_name": "Test Speedrun Event",
        "start_date": "2026-07-04",
        "end_date": "2026-07-15",
        "category_tag": "SPEEDRUN",
        "ai_summary": "A test short event that can be completed quickly in one sitting.",
    },
]


def event_exists(conn, event):
    row = conn.execute(
        """
        SELECT id
        FROM events
        WHERE game_title = ?
          AND event_name = ?
          AND start_date = ?
          AND end_date = ?
        """,
        (
            event["game_title"],
            event["event_name"],
            event["start_date"],
            event["end_date"],
        ),
    ).fetchone()

    return row is not None


def insert_event(conn, event):
    timestamp = now_iso()

    conn.execute(
        """
        INSERT INTO events (
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
        VALUES (?, ?, ?, ?, ?, 0, NULL, 0, ?, NULL, NULL, ?, ?)
        """,
        (
            event["game_title"],
            event["event_name"],
            event["start_date"],
            event["end_date"],
            event["category_tag"],
            event["ai_summary"],
            timestamp,
            timestamp,
        ),
    )


def main():
    init_db()

    inserted = 0
    skipped = 0

    with get_conn() as conn:
        for event in SEED_EVENTS:
            if event_exists(conn, event):
                print(f"Skipped existing event: {event['event_name']}")
                skipped += 1
                continue

            insert_event(conn, event)
            print(f"Inserted event: {event['event_name']}")
            inserted += 1

        conn.commit()

    print(f"Done. Inserted: {inserted}, skipped: {skipped}")


if __name__ == "__main__":
    main()
