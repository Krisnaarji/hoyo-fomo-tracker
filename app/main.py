from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.db import get_conn, init_db, row_to_dict
from app.event_validation import is_valid_iso_date
from app.widget_logic import build_widget_today_payload, today_local

app = FastAPI(
    title="HoYo FOMO Tracker",
    description="Lightweight anti-FOMO event tracker for HoYoverse games.",
    version="0.1.0",
)

LOCAL_TZ = ZoneInfo("Asia/Makassar")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventCreate(BaseModel):
    game_title: str = Field(..., examples=["Genshin", "HSR", "ZZZ"])
    event_name: str
    start_date: Optional[str] = Field(None, examples=["2026-07-04"])
    end_date: Optional[str] = Field(None, examples=["2026-07-20"])
    category_tag: str = Field(..., examples=["HEAVY", "SPEEDRUN", "DAILY"])
    ai_summary: Optional[str] = None
    source_url: Optional[str] = None
    source_hash: Optional[str] = None

    @field_validator("start_date", "end_date")
    @classmethod
    def validate_date_format(cls, value: Optional[str]) -> Optional[str]:
        if not is_valid_iso_date(value):
            raise ValueError("must be an exact YYYY-MM-DD date or omitted")
        return value


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

    today = today_local(LOCAL_TZ)

    with get_conn() as conn:
        return build_widget_today_payload(conn, limit, today, LOCAL_TZ)


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


# Convenience aliases already deployed on the Pi (kept for compatibility -
# not currently called by the Android client, which uses the /events/...
# endpoints named directly in each widget action's "endpoint" field).
@app.post("/widget/events/{event_id}/checkin")
def widget_checkin_event(event_id: int):
    return mark_daily_checkin(event_id)


@app.post("/widget/events/{event_id}/done")
def widget_done_event(event_id: int):
    return update_progress(event_id, ProgressUpdate(progress_status=100))


@app.post("/widget/events/{event_id}/progress/{progress_status}")
def widget_progress_event(event_id: int, progress_status: int):
    if progress_status not in {25, 50, 75, 100}:
        raise HTTPException(
            status_code=400,
            detail="progress_status must be 25, 50, 75, or 100",
        )

    return update_progress(event_id, ProgressUpdate(progress_status=progress_status))


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
