import json
import os
from typing import Any

import requests


GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)

DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"


class GeminiConfigError(RuntimeError):
    pass


class GeminiResponseError(RuntimeError):
    pass


def get_gemini_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is not set. Add it to .env before running AI extraction."
        )

    return api_key


def call_gemini_json(prompt: str, model: str = DEFAULT_GEMINI_MODEL, timeout: int = 60) -> dict[str, Any]:
    api_key = get_gemini_api_key()
    url = GEMINI_API_URL_TEMPLATE.format(model=model)

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt,
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
        },
    }

    response = requests.post(
        url,
        params={"key": api_key},
        json=payload,
        timeout=timeout,
    )

    if response.status_code >= 400:
        raise GeminiResponseError(
            f"Gemini API error {response.status_code}: {response.text[:500]}"
        )

    data = response.json()

    try:
        content = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise GeminiResponseError(
            f"Could not parse Gemini JSON response: {data}"
        ) from exc
