from datetime import date, datetime, timezone
from typing import Optional

CATEGORY_EMOJI = {
    "DAILY": "🎁",
    "HEAVY": "🔥",
    "SPEEDRUN": "⚡",
}


def today_local(tz) -> date:
    return datetime.now(tz).date()


def parse_local_date(value: Optional[str], tz) -> Optional[date]:
    if not value:
        return None

    if len(value) == 10:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(tz).date()


def daily_checkin_done_today(event: dict, today: date, tz) -> bool:
    return parse_local_date(event.get("last_daily_checkin"), tz) == today


def days_left_for(event: dict, today: date, tz) -> Optional[int]:
    end = parse_local_date(event.get("end_date"), tz)
    if end is None:
        return None
    return (end - today).days


def build_widget_action(event: dict, today: date, tz) -> Optional[dict]:
    if event["is_muted"] or int(event["progress_status"]) >= 100:
        return None

    category = event["category_tag"]
    event_id = event["id"]

    if category == "DAILY":
        if daily_checkin_done_today(event, today, tz):
            return None
        return {
            "endpoint": f"/events/{event_id}/daily-checkin",
            "method": "POST",
            "label": "Check-in",
        }

    if category == "SPEEDRUN":
        return {
            "endpoint": f"/events/{event_id}/progress",
            "method": "PATCH",
            "label": "Done",
            "body": {"progress_status": 100},
        }

    if category == "HEAVY":
        return {
            "endpoint": f"/events/{event_id}/progress",
            "method": "PATCH",
            "label": "Update progress",
            "body_options": [
                {"progress_status": 25},
                {"progress_status": 50},
                {"progress_status": 75},
                {"progress_status": 100},
            ],
        }

    return None


def build_widget_event(event: dict, today: date, tz, action: dict) -> dict:
    return {
        "id": event["id"],
        "game_title": event["game_title"],
        "event_name": event["event_name"],
        "category_tag": event["category_tag"],
        "emoji": CATEGORY_EMOJI.get(event["category_tag"], "📌"),
        "progress_status": event["progress_status"],
        "start_date": event["start_date"],
        "end_date": event["end_date"],
        "days_left": days_left_for(event, today, tz),
        "action": action,
    }


def fetch_widget_active_events(conn, today_iso: str) -> list:
    rows = conn.execute(
        """
        SELECT *
        FROM events
        WHERE
            is_muted = 0
            AND (start_date IS NULL OR date(start_date) <= date(?))
            AND (end_date IS NULL OR date(end_date) >= date(?))
        ORDER BY
            CASE category_tag
                WHEN 'HEAVY' THEN 0
                WHEN 'DAILY' THEN 1
                WHEN 'SPEEDRUN' THEN 2
                ELSE 3
            END,
            end_date IS NULL,
            end_date ASC,
            game_title ASC
        """,
        (today_iso, today_iso),
    ).fetchall()

    return [dict(row) for row in rows]


def build_widget_today_payload(conn, limit: int, today: date, tz) -> dict:
    if limit < 1:
        raise ValueError("limit must be >= 1")

    today_iso = today.isoformat()
    events = fetch_widget_active_events(conn, today_iso)

    # Only actionable events are ever included - once an event is checked
    # in / completed / muted, it drops out of the response entirely rather
    # than lingering with no action, so it can never occupy a capped slot
    # that a still-actionable event could otherwise use.
    actionable = []
    for event in events:
        action = build_widget_action(event, today, tz)
        if action is not None:
            actionable.append((event, action))

    total_actions = len(actionable)
    shown = actionable[:limit]
    hidden_actions = max(total_actions - len(shown), 0)

    games: dict = {}
    for event, action in shown:
        games.setdefault(event["game_title"], []).append(
            build_widget_event(event, today, tz, action)
        )

    return {
        "today": today_iso,
        "total_actions": total_actions,
        "shown_actions": len(shown),
        "hidden_actions": hidden_actions,
        "limit": limit,
        "games": [
            {"game_title": title, "events": events}
            for title, events in games.items()
        ],
    }
