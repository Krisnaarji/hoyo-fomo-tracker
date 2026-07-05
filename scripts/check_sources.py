import argparse
from datetime import datetime, timezone

from app.db import get_conn, init_db
from app.scraper import scrape_url


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_snapshot(conn, game_title: str, source_url: str):
    return conn.execute(
        """
        SELECT *
        FROM source_snapshots
        WHERE game_title = ?
          AND source_url = ?
        """,
        (game_title, source_url),
    ).fetchone()


def insert_snapshot(conn, game_title: str, source_url: str, content_hash: str, content_length: int):
    timestamp = now_iso()

    conn.execute(
        """
        INSERT INTO source_snapshots (
            game_title,
            source_url,
            content_hash,
            content_length,
            last_seen_at,
            last_changed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            game_title,
            source_url,
            content_hash,
            content_length,
            timestamp,
            timestamp,
        ),
    )


def update_snapshot_seen(conn, snapshot_id: int):
    conn.execute(
        """
        UPDATE source_snapshots
        SET last_seen_at = ?
        WHERE id = ?
        """,
        (now_iso(), snapshot_id),
    )


def update_snapshot_changed(conn, snapshot_id: int, content_hash: str, content_length: int):
    timestamp = now_iso()

    conn.execute(
        """
        UPDATE source_snapshots
        SET content_hash = ?,
            content_length = ?,
            last_seen_at = ?,
            last_changed_at = ?
        WHERE id = ?
        """,
        (
            content_hash,
            content_length,
            timestamp,
            timestamp,
            snapshot_id,
        ),
    )


def check_source(game_title: str, url: str):
    page = scrape_url(url)

    init_db()

    with get_conn() as conn:
        snapshot = get_snapshot(conn, game_title, url)

        if snapshot is None:
            insert_snapshot(
                conn=conn,
                game_title=game_title,
                source_url=url,
                content_hash=page.content_hash,
                content_length=page.content_length,
            )
            conn.commit()

            status = "NEW"

        elif snapshot["content_hash"] != page.content_hash:
            update_snapshot_changed(
                conn=conn,
                snapshot_id=snapshot["id"],
                content_hash=page.content_hash,
                content_length=page.content_length,
            )
            conn.commit()

            status = "CHANGED"

        else:
            update_snapshot_seen(conn, snapshot["id"])
            conn.commit()

            status = "UNCHANGED"

    print(f"Status: {status}")
    print(f"Game: {game_title}")
    print(f"URL: {url}")
    print(f"Title: {page.title}")
    print(f"Content length: {page.content_length}")
    print(f"Hash: {page.content_hash}")

    if status in {"NEW", "CHANGED"}:
        print()
        print("Preview:")
        print(page.text[:700])


def main():
    parser = argparse.ArgumentParser(
        description="Check whether a source page changed since the last scrape."
    )
    parser.add_argument(
        "--game",
        required=True,
        help="Game title, e.g. Genshin, HSR, or ZZZ.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Source URL to scrape and hash.",
    )

    args = parser.parse_args()

    try:
        check_source(args.game, args.url)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()import argparse
from datetime import datetime, timezone

from app.db import get_conn, init_db
from app.scraper import scrape_url


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_snapshot(conn, game_title: str, source_url: str):
    return conn.execute(
        """
        SELECT *
        FROM source_snapshots
        WHERE game_title = ?
          AND source_url = ?
        """,
        (game_title, source_url),
    ).fetchone()


def insert_snapshot(conn, game_title: str, source_url: str, content_hash: str, content_length: int):
    timestamp = now_iso()

    conn.execute(
        """
        INSERT INTO source_snapshots (
            game_title,
            source_url,
            content_hash,
            content_length,
            last_seen_at,
            last_changed_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            game_title,
            source_url,
            content_hash,
            content_length,
            timestamp,
            timestamp,
        ),
    )


def update_snapshot_seen(conn, snapshot_id: int):
    conn.execute(
        """
        UPDATE source_snapshots
        SET last_seen_at = ?
        WHERE id = ?
        """,
        (now_iso(), snapshot_id),
    )


def update_snapshot_changed(conn, snapshot_id: int, content_hash: str, content_length: int):
    timestamp = now_iso()

    conn.execute(
        """
        UPDATE source_snapshots
        SET content_hash = ?,
            content_length = ?,
            last_seen_at = ?,
            last_changed_at = ?
        WHERE id = ?
        """,
        (
            content_hash,
            content_length,
            timestamp,
            timestamp,
            snapshot_id,
        ),
    )


def check_source(game_title: str, url: str):
    page = scrape_url(url)

    init_db()

    with get_conn() as conn:
        snapshot = get_snapshot(conn, game_title, url)

        if snapshot is None:
            insert_snapshot(
                conn=conn,
                game_title=game_title,
                source_url=url,
                content_hash=page.content_hash,
                content_length=page.content_length,
            )
            conn.commit()

            status = "NEW"

        elif snapshot["content_hash"] != page.content_hash:
            update_snapshot_changed(
                conn=conn,
                snapshot_id=snapshot["id"],
                content_hash=page.content_hash,
                content_length=page.content_length,
            )
            conn.commit()

            status = "CHANGED"

        else:
            update_snapshot_seen(conn, snapshot["id"])
            conn.commit()

            status = "UNCHANGED"

    print(f"Status: {status}")
    print(f"Game: {game_title}")
    print(f"URL: {url}")
    print(f"Title: {page.title}")
    print(f"Content length: {page.content_length}")
    print(f"Hash: {page.content_hash}")

    if status in {"NEW", "CHANGED"}:
        print()
        print("Preview:")
        print(page.text[:700])


def main():
    parser = argparse.ArgumentParser(
        description="Check whether a source page changed since the last scrape."
    )
    parser.add_argument(
        "--game",
        required=True,
        help="Game title, e.g. Genshin, HSR, or ZZZ.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="Source URL to scrape and hash.",
    )

    args = parser.parse_args()

    try:
        check_source(args.game, args.url)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()