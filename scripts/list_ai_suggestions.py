from app.db import get_conn


def main():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                game_title,
                suggested_category,
                event_name,
                start_date,
                end_date,
                status
            FROM ai_event_suggestions
            WHERE status = 'PENDING'
            ORDER BY game_title, start_date, end_date, event_name
            """
        ).fetchall()

    if not rows:
        print("No pending AI suggestions.")
        return

    for row in rows:
        print(
            f"[{row['id']}] "
            f"{row['game_title']} | "
            f"{row['suggested_category']} | "
            f"{row['event_name']} | "
            f"{row['start_date']} → {row['end_date']} | "
            f"{row['status']}"
        )


if __name__ == "__main__":
    main()
