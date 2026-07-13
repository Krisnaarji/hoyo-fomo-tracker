import shutil
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hoyo.db"
BACKUP_DIR = BASE_DIR / "backups"


def main():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    BACKUP_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"hoyo-{timestamp}.db"

    shutil.copy2(DB_PATH, backup_path)

    print(f"Backup created: {backup_path}")


if __name__ == "__main__":
    main()
