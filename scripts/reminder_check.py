import argparse
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.db import get_conn, init_db

LOCAL_TZ = ZoneInfo("Asia/Makassar")


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def parse_date(value):
    if not value:
        return None

    if len(value) == 10:
        return date.fromisoformat(value)

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
    if reminder_already_logged(conn, event_id, reminder_type):
        return False

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

    return True


def build_reminders(conn, event, today):
    reminders = []

    event_id = event["id"]
    category = event["category_tag"]
    end = parse_date(event["end_date"])

    if category == "DAILY":
        reminder_type = f"DAILY_{today.isoformat()}"

        if (
            not daily_checkin_done_today(event, today)
            and not reminder_already_logged(conn, event_id, reminder_type)
        ):
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


def print_reminders(today, active_count, reminders):
    print(f"Local date: {today.isoformat()}")
    print(f"Active events checked: {active_count}")

    if not reminders:
        print("No reminders needed.")
        return

    print(f"Reminders needed: {len(reminders)}")

    for reminder in reminders:
        print()
        print(f"[{reminder['category_tag']}] {reminder['game_title']} - {reminder['event_name']}")
        print(f"Event ID: {reminder['event_id']}")
        print(f"Type: {reminder['reminder_type']}")
        print(f"Message: {reminder['message']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mark-sent",
        action="store_true",
        help="Save generated reminders into reminder_log to prevent duplicate reminders.",
    )
    args = parser.parse_args()

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

        reminders = []
        for event in active_events:
            reminders.extend(build_reminders(conn, event, today))

        print_reminders(today, len(active_events), reminders)

        if args.mark_sent and reminders:
            logged = 0

            for reminder in reminders:
                if log_reminder(conn, reminder["event_id"], reminder["reminder_type"]):
                    logged += 1

            conn.commit()
            print()
            print(f"Marked reminders as sent: {logged}")


if __name__ == "__main__":
    main()
