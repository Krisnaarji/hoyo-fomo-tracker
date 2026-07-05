import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"


def load_env_file() -> None:
    if not ENV_PATH.exists():
        return

    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        os.environ.setdefault(key, value)


def get_env(key: str, default: str | None = None) -> str | None:
    load_env_file()
    return os.environ.get(key, default)