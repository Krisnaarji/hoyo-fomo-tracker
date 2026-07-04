CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_title TEXT NOT NULL,
    event_name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    category_tag TEXT NOT NULL CHECK(category_tag IN ('HEAVY', 'SPEEDRUN', 'DAILY')),
    progress_status INTEGER NOT NULL DEFAULT 0,
    last_daily_checkin TEXT,
    is_muted INTEGER NOT NULL DEFAULT 0,
    ai_summary TEXT,
    source_url TEXT,
    source_hash TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(game_title, event_name, start_date, end_date)
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_title TEXT NOT NULL,
    source_url TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_length INTEGER NOT NULL,
    last_seen_at TEXT NOT NULL,
    last_changed_at TEXT,
    UNIQUE(game_title, source_url)
);

CREATE TABLE IF NOT EXISTS reminder_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    reminder_type TEXT NOT NULL,
    sent_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id)
);
