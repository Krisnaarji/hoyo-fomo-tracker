from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.db import get_conn, init_db

LOCAL_TZ = ZoneInfo("Asia/Makassar")


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def parse_date(value):
    if not value:
        return None

    # Handles "2026-07-04"
    if len(value) == 10:
        return date.fromisoformat(value)

    # Handles "2026-07-04T14:21:14+00:00"
    # Also handles old SQLite "2026-07-04 13:02:01"
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(LOCAL_TZ).date()


def is_active_event(event, today):
    start = parse_date(event["start_date"])
    end = parse_date(event["end_date"])

    if event["is_muted"]:
        return False

    if start and start > today:
        return False

    if end and end < today:
        return False

    return True


def daily_checkin_done_today(event, today):
    last_checkin = parse_date(event["last_daily_checkin"])
    return last_checkin == today


def reminder_already_logged(conn, event_id, reminder_type):
    row = conn.execute(
        """
        SELECT id
        FROM reminder_log
        WHERE event_id = ?
          AND reminder_type = ?
        """,
        (event_id, reminder_type),
    ).fetchone()

    return row is not None


def log_reminder(conn, event_id, reminder_type):
    conn.execute(
        """
        INSERT INTO reminder_log (
            event_id,
            reminder_type,
            sent_at
        )
        VALUES (?, ?, ?)
        """,
        (
            event_id,
            reminder_type,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def build_reminders(conn, event, today):
    reminders = []

    event_id = event["id"]
    category = event["category_tag"]
    end = parse_date(event["end_date"])

    if category == "DAILY":
        reminder_type = f"DAILY_{today.isoformat()}"

        if not daily_checkin_done_today(event, today):
            reminders.append(
                {
                    "event_id": event_id,
                    "game_title": event["game_title"],
                    "event_name": event["event_name"],
                    "category_tag": category,
                    "reminder_type": reminder_type,
                    "message": "Daily check-in has not been completed today.",
                }
            )

    elif category == "HEAVY":
        # Saturday = 5, Sunday = 6
        if today.weekday() in {5, 6}:
            reminder_type = f"HEAVY_WEEKEND_{today.isoformat()}"

            if not reminder_already_logged(conn, event_id, reminder_type):
                reminders.append(
                    {
                        "event_id": event_id,
                        "game_title": event["game_title"],
                        "event_name": event["event_name"],
                        "category_tag": category,
                        "reminder_type": reminder_type,
                        "message": "Weekend pacing reminder for heavy/lore event.",
                    }
                )

        if end:
            days_left = (end - today).days

            if days_left == 5:
                reminder_type = "HEAVY_T_MINUS_5"

                if not reminder_already_logged(conn, event_id, reminder_type):
                    reminders.append(
                        {
                            "event_id": event_id,
                            "game_title": event["game_title"],
                            "event_name": event["event_name"],
                            "category_tag": category,
                            "reminder_type": reminder_type,
                            "message": "Heavy event ends in 5 days. Do not speedrun this.",
                        }
                    )

    elif category == "SPEEDRUN":
        if end:
            days_left = (end - today).days

            if days_left in {1, 2}:
                reminder_type = f"SPEEDRUN_T_MINUS_{days_left}"

                if not reminder_already_logged(conn, event_id, reminder_type):
                    reminders.append(
                        {
                            "event_id": event_id,
                            "game_title": event["game_title"],
                            "event_name": event["event_name"],
                            "category_tag": category,
                            "reminder_type": reminder_type,
                            "message": f"Speedrun-able event ends in {days_left} day(s).",
                        }
                    )

    return reminders


def main():
    init_db()
    today = today_local()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM events
            ORDER BY end_date ASC
            """
        ).fetchall()

        active_events = [row for row in rows if is_active_event(row, today)]

        all_reminders = []
        for event in active_events:
            all_reminders.extend(build_reminders(conn, event, today))

    print(f"Local date: {today.isoformat()}")
    print(f"Active events checked: {len(active_events)}")

    if not all_reminders:
        print("No reminders needed.")
        return

    print(f"Reminders needed: {len(all_reminders)}")

    for reminder in all_reminders:
        print()
        print(f"[{reminder['category_tag']}] {reminder['game_title']} - {reminder['event_name']}")
        print(f"Event ID: {reminder['event_id']}")
        print(f"Type: {reminder['reminder_type']}")
        print(f"Message: {reminder['message']}")


if __name__ == "__main__":
    main()
