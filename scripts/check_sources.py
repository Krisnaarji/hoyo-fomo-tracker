import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.db import get_conn, init_db
from app.notifiers import send_discord_webhook
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

    result = {
        "status": status,
        "game_title": game_title,
        "name": name,
        "url": url,
        "title": page.title,
        "content_length": page.content_length,
        "content_hash": page.content_hash,
        "preview": page.text[:700],
    }

    print_source_result(result)
    return result


def print_source_result(result: dict):
    print("=" * 70)
    print(f"Status: {result['status']}")
    print(f"Game: {result['game_title']}")

    if result.get("name"):
        print(f"Name: {result['name']}")

    print(f"URL: {result['url']}")
    print(f"Title: {result['title']}")
    print(f"Content length: {result['content_length']}")
    print(f"Hash: {result['content_hash']}")

    if result["status"] in {"NEW", "CHANGED"}:
        print()
        print("Preview:")
        print(result["preview"])


def print_error_result(source: dict, exc: Exception):
    print("=" * 70)
    print("Status: ERROR")
    print(f"Game: {source.get('game_title', 'Unknown')}")
    print(f"Name: {source.get('name', 'Unknown')}")
    print(f"URL: {source.get('url', 'Unknown')}")
    print(f"Error: {exc}")


def format_discord_source_alert(result: dict) -> str:
    status_emoji = {
        "NEW": "🆕",
        "CHANGED": "📡",
        "ERROR": "🚨",
    }.get(result["status"], "📌")

    name = result.get("name") or "Unnamed source"

    message = (
        f"{status_emoji} **HoYo Source {result['status']}**\n"
        f"Game: `{result['game_title']}`\n"
        f"Source: **{name}**\n"
        f"Length: `{result.get('content_length', 'Unknown')}`\n"
    )

    if result.get("content_hash"):
        message += f"Hash: `{result['content_hash'][:12]}`\n"

    message += f"URL: {result['url']}"

    return message


def format_discord_error_alert(source: dict, exc: Exception) -> str:
    name = source.get("name", "Unknown")
    game_title = source.get("game_title", "Unknown")
    url = source.get("url", "Unknown")

    return (
        "🚨 **HoYo Source Check ERROR**\n"
        f"Game: `{game_title}`\n"
        f"Source: **{name}**\n"
        f"URL: {url}\n"
        f"Error: `{exc}`"
    )


def check_all_sources(send_discord: bool = False):
    sources = load_sources()

    results = {
        "NEW": 0,
        "CHANGED": 0,
        "UNCHANGED": 0,
        "ERROR": 0,
    }

    for source in sources:
        try:
            result = check_source(
                game_title=source["game_title"],
                name=source.get("name"),
                url=source["url"],
            )

            results[result["status"]] += 1

            if send_discord and result["status"] in {"NEW", "CHANGED"}:
                send_discord_webhook(format_discord_source_alert(result))
                print(f"Discord alert sent for {result['status']}: {source.get('name')}")

        except Exception as exc:
            results["ERROR"] += 1
            print_error_result(source, exc)

            if send_discord:
                try:
                    send_discord_webhook(format_discord_error_alert(source, exc))
                    print(f"Discord error alert sent: {source.get('name')}")
                except Exception as discord_exc:
                    print(f"Failed to send Discord error alert: {discord_exc}")

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
    parser.add_argument(
        "--send-discord",
        action="store_true",
        help="Send Discord alert when a source is NEW, CHANGED, or ERROR.",
    )

    args = parser.parse_args()

    init_db()

    if args.all:
        check_all_sources(send_discord=args.send_discord)
        return

    if not args.game or not args.url:
        parser.error("Either use --all or provide both --game and --url.")

    result = check_source(args.game, args.url)

    if args.send_discord and result["status"] in {"NEW", "CHANGED"}:
        send_discord_webhook(format_discord_source_alert(result))
        print(f"Discord alert sent for {result['status']}: {args.game}")


if __name__ == "__main__":
    main()
