from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.db import get_conn, init_db, row_to_dict

app = FastAPI(
    title="HoYo FOMO Tracker",
    description="Lightweight anti-FOMO event tracker for HoYoverse games.",
    version="0.1.0",
)

LOCAL_TZ = ZoneInfo("Asia/Makassar")

CATEGORY_EMOJI = {
    "DAILY": "🎁",
    "HEAVY": "🔥",
    "SPEEDRUN": "⚡",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def parse_local_date(value: Optional[str]) -> Optional[date]:
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

    return dt.astimezone(LOCAL_TZ).date()


def daily_checkin_done_today(event: dict, today: date) -> bool:
    return parse_local_date(event.get("last_daily_checkin")) == today


def days_left_for(event: dict, today: date) -> Optional[int]:
    end = parse_local_date(event.get("end_date"))
    if end is None:
        return None
    return (end - today).days


def build_widget_action(event: dict, today: date) -> Optional[dict]:
    if event["is_muted"] or int(event["progress_status"]) >= 100:
        return None

    category = event["category_tag"]
    event_id = event["id"]

    if category == "DAILY":
        if daily_checkin_done_today(event, today):
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
            "body_options": [25, 50, 75, 100],
        }

    return None


def build_widget_event(event: dict, today: date) -> dict:
    result = {
        "event_name": event["event_name"],
        "emoji": CATEGORY_EMOJI.get(event["category_tag"], "📌"),
        "category_tag": event["category_tag"],
        "days_left": days_left_for(event, today),
    }

    action = build_widget_action(event, today)
    if action is not None:
        result["action"] = action

    return result


def fetch_widget_active_events(conn, today_iso: str) -> list[dict]:
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

    return [row_to_dict(row) for row in rows]


class EventCreate(BaseModel):
    game_title: str = Field(..., examples=["Genshin", "HSR", "ZZZ"])
    event_name: str
    start_date: Optional[str] = Field(None, examples=["2026-07-04"])
    end_date: Optional[str] = Field(None, examples=["2026-07-20"])
    category_tag: str = Field(..., examples=["HEAVY", "SPEEDRUN", "DAILY"])
    ai_summary: Optional[str] = None
    source_url: Optional[str] = None
    source_hash: Optional[str] = None


class ProgressUpdate(BaseModel):
    progress_status: int = Field(..., ge=0, le=100)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {
        "message": "HoYo FOMO Tracker API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "hoyo-fomo-tracker",
        "time": now_iso(),
    }


@app.get("/events")
def list_events(active_only: bool = False):
    query = """
        SELECT *
        FROM events
    """
    params = []

    if active_only:
        today = datetime.now(timezone.utc).date().isoformat()
        query += """
            WHERE
                (start_date IS NULL OR date(start_date) <= date(?))
                AND
                (end_date IS NULL OR date(end_date) >= date(?))
                AND is_muted = 0
        """
        params.extend([today, today])

    query += """
        ORDER BY
            is_muted ASC,
            end_date IS NULL,
            end_date ASC,
            game_title ASC
    """

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
        return [row_to_dict(row) for row in rows]


@app.get("/widget/today")
def widget_today(limit: int = 5):
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")

    today = today_local()
    today_iso = today.isoformat()

    with get_conn() as conn:
        events = fetch_widget_active_events(conn, today_iso)

    actions = [build_widget_action(event, today) for event in events]
    total_actions = sum(1 for action in actions if action is not None)

    capped_events = events[:limit]
    capped_actionable = sum(
        1 for action in actions[:limit] if action is not None
    )
    hidden_actions = total_actions - capped_actionable

    games: dict[str, list[dict]] = {}
    for event in capped_events:
        games.setdefault(event["game_title"], []).append(
            build_widget_event(event, today)
        )

    return {
        "today": today_iso,
        "total_actions": total_actions,
        "hidden_actions": hidden_actions,
        "games": [
            {"game_title": title, "events": events}
            for title, events in games.items()
        ],
    }


@app.get("/events/{event_id}")
def get_event(event_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return row_to_dict(row)


@app.post("/events")
def create_event(event: EventCreate):
    valid_categories = {"HEAVY", "SPEEDRUN", "DAILY"}

    if event.category_tag not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail="category_tag must be HEAVY, SPEEDRUN, or DAILY",
        )

    timestamp = now_iso()

    try:
        with get_conn() as conn:
            cursor = conn.execute(
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
                VALUES (?, ?, ?, ?, ?, 0, NULL, 0, ?, ?, ?, ?, ?)
                """,
                (
                    event.game_title,
                    event.event_name,
                    event.start_date,
                    event.end_date,
                    event.category_tag,
                    event.ai_summary,
                    event.source_url,
                    event.source_hash,
                    timestamp,
                    timestamp,
                ),
            )
            conn.commit()

            return {
                "id": cursor.lastrowid,
                "message": "Event created",
            }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.patch("/events/{event_id}/progress")
def update_progress(event_id: int, update: ProgressUpdate):
    timestamp = now_iso()
    is_muted = 1 if update.progress_status >= 100 else 0

    with get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET
                progress_status = ?,
                is_muted = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                update.progress_status,
                is_muted,
                timestamp,
                event_id,
            ),
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": event_id,
        "progress_status": update.progress_status,
        "is_muted": is_muted,
        "message": "Progress updated",
    }


@app.post("/events/{event_id}/daily-checkin")
def mark_daily_checkin(event_id: int):
    timestamp = now_iso()

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")

        if row["category_tag"] != "DAILY":
            raise HTTPException(
                status_code=400,
                detail="Only DAILY events can use daily check-in",
            )

        conn.execute(
            """
            UPDATE events
            SET
                last_daily_checkin = ?,
                progress_status = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                timestamp,
                timestamp,
                event_id,
            ),
        )
        conn.commit()

    return {
        "id": event_id,
        "last_daily_checkin": timestamp,
        "message": "Daily check-in marked",
    }


@app.post("/events/{event_id}/mute")
def mute_event(event_id: int):
    timestamp = now_iso()

    with get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET
                is_muted = 1,
                updated_at = ?
            WHERE id = ?
            """,
            (
                timestamp,
                event_id,
            ),
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": event_id,
        "is_muted": 1,
        "message": "Event muted",
    }


@app.delete("/events/{event_id}")
def delete_event(event_id: int):
    with get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM events WHERE id = ?",
            (event_id,),
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "id": event_id,
        "message": "Event deleted",
    }
