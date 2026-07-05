import json
import urllib.error
import urllib.request

from app.settings import get_env


def send_discord_webhook(content: str) -> None:
    webhook_url = get_env("DISCORD_WEBHOOK_URL")

    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL is not set in .env")

    payload = {
        "username": "HoYo FOMO Tracker",
        "content": content,
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "hoyo-fomo-tracker/0.1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status not in {200, 204}:
                raise RuntimeError(f"Discord webhook returned HTTP {response.status}")

    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to send Discord webhook: {exc}") from exc