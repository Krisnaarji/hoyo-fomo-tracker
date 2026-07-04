import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "hoyo.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        schema = SCHEMA_PATH.read_text()
        conn.executescript(schema)
        conn.commit()


def row_to_dict(row):
    return dict(row) if row is not None else None
