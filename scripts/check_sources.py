import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.db import get_conn, init_db
from app.scraper import scrape_url

BASE_DIR = Path(__file__).resolve().parent.parent
SOURCES_PATH = BASE_DIR / "config" / "sources.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_sources():
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"Source config not found: {SOURCES_PATH}")

    return json.loads(SOURCES_PATH.read_text())


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


def check_source(game_title: str, url: str, name: str | None = None):
    page = scrape_url(url)

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

    print("=" * 70)
    print(f"Status: {status}")
    print(f"Game: {game_title}")
    if name:
        print(f"Name: {name}")
    print(f"URL: {url}")
    print(f"Title: {page.title}")
    print(f"Content length: {page.content_length}")
    print(f"Hash: {page.content_hash}")

    if status in {"NEW", "CHANGED"}:
        print()
        print("Preview:")
        print(page.text[:700])

    return status


def check_all_sources():
    sources = load_sources()

    results = {
        "NEW": 0,
        "CHANGED": 0,
        "UNCHANGED": 0,
        "ERROR": 0,
    }

    for source in sources:
        try:
            status = check_source(
                game_title=source["game_title"],
                name=source.get("name"),
                url=source["url"],
            )
            results[status] += 1

        except Exception as exc:
            results["ERROR"] += 1
            print("=" * 70)
            print("Status: ERROR")
            print(f"Game: {source.get('game_title', 'Unknown')}")
            print(f"Name: {source.get('name', 'Unknown')}")
            print(f"URL: {source.get('url', 'Unknown')}")
            print(f"Error: {exc}")

    print("=" * 70)
    print("Summary:")
    for key, value in results.items():
        print(f"{key}: {value}")


def main():
    parser = argparse.ArgumentParser(
        description="Check whether source pages changed since the last scrape."
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Check all sources from config/sources.json.",
    )
    parser.add_argument(
        "--game",
        help="Game title, e.g. Genshin, HSR, or ZZZ.",
    )
    parser.add_argument(
        "--url",
        help="Source URL to scrape and hash.",
    )

    args = parser.parse_args()

    init_db()

    if args.all:
        check_all_sources()
        return

    if not args.game or not args.url:
        parser.error("Either use --all or provide both --game and --url.")

    check_source(args.game, args.url)


if __name__ == "__main__":
    main()