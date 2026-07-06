import argparse
from datetime import datetime, timezone

from app.db import get_conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser(
        description="Reject one pending AI suggestion."
    )
    parser.add_argument("suggestion_id", type=int)

    args = parser.parse_args()
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
            (timestamp, args.suggestion_id),
        )
        conn.commit()

    if cursor.rowcount == 0:
        print(f"No pending suggestion found with id {args.suggestion_id}")
        return

    print(f"Rejected suggestion {args.suggestion_id}")


if __name__ == "__main__":
    main()
