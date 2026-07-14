import argparse
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.db import get_conn, init_db
from app.notifiers import send_discord_webhook

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


DIGEST_CATEGORY_EMOJI = {
    "DAILY": "🎁",
    "SPEEDRUN": "⚡",
    "HEAVY": "🔥",
}

DIGEST_CATEGORY_PRIORITY = {
    "DAILY": 0,
    "SPEEDRUN": 1,
    "HEAVY": 2,
}

DIGEST_HEADER = "# HoYo FOMO Reminder"
DIGEST_CONTINUATION_HEADER = "# HoYo FOMO Reminder (cont.)"

# Discord webhook `content` is capped at 2000 characters; stay comfortably
# under that so a busy day's digest can never be silently rejected.
DIGEST_MAX_LENGTH = 1900


def _digest_entry_line(reminder):
    category = reminder["category_tag"]
    emoji = DIGEST_CATEGORY_EMOJI.get(category, "📌")

    return (
        f"- {emoji} **{category}** — {reminder['event_name']}\n"
        f"  {reminder['message']} `#{reminder['event_id']}`"
    )


def build_discord_digests(reminders, max_length=DIGEST_MAX_LENGTH):
    """Formats reminders into one or more Discord messages, grouped by game
    and kept under Discord's per-message content limit. Returns a list of
    (message_text, reminders_in_message) pairs so the caller can mark only
    the reminders that were actually sent if a chunk fails to send."""
    grouped = {}
    for reminder in reminders:
        grouped.setdefault(reminder["game_title"], []).append(reminder)

    digests = []
    block_lines = [DIGEST_HEADER]
    block_reminders = []

    def flush():
        nonlocal block_lines, block_reminders
        digests.append(("\n".join(block_lines), block_reminders))
        block_lines = [DIGEST_CONTINUATION_HEADER]
        block_reminders = []

    for game_title in sorted(grouped):
        game_header = f"## {game_title}"
        header_in_block = False

        sorted_reminders = sorted(
            grouped[game_title],
            key=lambda reminder: (
                DIGEST_CATEGORY_PRIORITY.get(reminder["category_tag"], 9),
                reminder["event_name"].lower(),
            ),
        )

        for reminder in sorted_reminders:
            entry_lines = [] if header_in_block else [game_header]
            entry_lines.append(_digest_entry_line(reminder))

            projected = block_lines + entry_lines
            if block_reminders and len("\n".join(projected)) > max_length:
                flush()
                header_in_block = False
                entry_lines = [game_header, _digest_entry_line(reminder)]

            block_lines.extend(entry_lines)
            block_reminders.append(reminder)
            header_in_block = True

    if block_reminders:
        flush()

    return digests


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
    parser.add_argument(
        "--send-discord",
        action="store_true",
        help="Send generated reminders to Discord webhook.",
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

        if not reminders:
            return

        sent_reminders = []

        if args.send_discord:
            failed = 0

            for digest_text, digest_reminders in build_discord_digests(reminders):
                try:
                    send_discord_webhook(digest_text)
                    sent_reminders.extend(digest_reminders)
                    print(f"Sent Discord reminder digest: {len(digest_reminders)} reminder(s)")
                except RuntimeError as exc:
                    failed += len(digest_reminders)
                    print(f"Failed Discord reminder digest: {len(digest_reminders)} reminder(s)")
                    print(f"Reason: {exc}")

            if failed:
                print(f"Discord send failures: {failed}")

        else:
            sent_reminders = reminders

        if args.mark_sent and sent_reminders:
            logged = 0

            for reminder in sent_reminders:
                if log_reminder(conn, reminder["event_id"], reminder["reminder_type"]):
                    logged += 1

            conn.commit()
            print()
            print(f"Marked reminders as sent: {logged}")


if __name__ == "__main__":
    main()