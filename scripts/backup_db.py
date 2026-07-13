import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hoyo.db"
BACKUP_DIR = BASE_DIR / "backups"


def create_backup(source_path: Path, destination_path: Path) -> None:
    """Safely copies a live SQLite database using sqlite3's own backup API,
    instead of a raw file copy, avoiding inconsistent snapshots caused by
    concurrent database writes (from the FastAPI service, the Discord bot,
    or other cron jobs)."""
    with closing(sqlite3.connect(source_path)) as source:
        with closing(sqlite3.connect(destination_path)) as destination:
            source.backup(destination)


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"hoyo-{timestamp}.db"

    create_backup(DB_PATH, backup_path)

    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
