import json
import os
from pathlib import Path
from typing import Any

import requests

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-v4-flash"


if load_dotenv is not None:
    load_dotenv(ENV_PATH)


class DeepSeekConfigError(RuntimeError):
    pass


class DeepSeekResponseError(RuntimeError):
    pass


def get_deepseek_api_key() -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

    if not api_key:
        raise DeepSeekConfigError(
            "DEEPSEEK_API_KEY is not set. Add it to .env before running AI extraction."
        )

    return api_key


def keep_current_and_upcoming_only(source_text: str) -> str:
    start_markers = [
        "Current Event Duration Type(s)",
        "Current Duration Type(s)",
    ]

    end_markers = [
        "Permanent Event Release Date",
        "Permanent Event Duration Type(s)",
        "Permanent Event",
        "List of Event Types [",
        "List of Recurring Events [",
        "Other Languages",
        "Navigation",
    ]

    trimmed = source_text

    for marker in start_markers:
        index = trimmed.find(marker)
        if index != -1:
            trimmed = trimmed[index:]
            break

    upcoming_index = trimmed.find("Upcoming Event Duration Type(s)")

    best_end_index = None
    for marker in end_markers:
        index = trimmed.find(marker)

        if index == -1:
            continue

        if upcoming_index != -1 and index < upcoming_index:
            continue

        if best_end_index is None or index < best_end_index:
            best_end_index = index

    if best_end_index is not None:
        trimmed = trimmed[:best_end_index]

    return trimmed.strip()


def build_event_extraction_prompt(game_title: str, source_text: str) -> str:
    source_text = keep_current_and_upcoming_only(source_text)

    return f"""
You are helping maintain a personal HoYoverse event reminder tracker.

Game: {game_title}

Task:
Extract the CURRENT and UPCOMING limited-time events from the source text.
Ignore permanent events, indefinite events, archived events, navigation text, and unrelated page sections.

Return ONLY valid JSON with this shape:

{{
  "game_title": "{game_title}",
  "events": [
    {{
      "title": "Event name",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or TBA/null",
      "event_types": ["In-Game", "Login", "Web"],
      "suggested_category": "daily | heavy | speedrun | info",
      "reason": "short reason for the category"
    }}
  ]
}}

Category rules:
- daily = login/check-in/repeated daily reward event
- heavy = event likely requiring multiple sessions, quests, stages, farming, or story
- speedrun = short event ending soon or simple one-time claim
- info = collaboration, permanent, unclear, TBA, or not actionable

Source text:
{source_text}
""".strip()


def call_deepseek_json(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 60) -> dict[str, Any]:
    api_key = get_deepseek_api_key()

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You extract event data and return strict JSON only.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {"type": "json_object"},
        "stream": False,
    }

    response = requests.post(
        DEEPSEEK_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise DeepSeekResponseError(
            f"DeepSeek API error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()

    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise DeepSeekResponseError(
            f"Could not parse DeepSeek JSON response: {data}"
        ) from exc


def extract_events_with_ai(game_title: str, source_text: str) -> dict[str, Any]:
    prompt = build_event_extraction_prompt(game_title, source_text)
    return call_deepseek_json(prompt)