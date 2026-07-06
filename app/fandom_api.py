import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup


@dataclass
class FandomPageText:
    title: str
    page_id: int | None
    text: str
    text_length: int


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    text = soup.get_text(" ", strip=True)
    return normalize_text(text)


def fetch_fandom_parse_text(url: str, timeout: int = 20) -> FandomPageText:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HoYoFOMOTracker/0.1; "
            "+https://github.com/Krisnaarji/hoyo-fomo-tracker)"
        ),
        "Accept": "application/json",
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    data = response.json()
    parse = data.get("parse", {})

    title = parse.get("title", "Untitled")
    page_id = parse.get("pageid")

    raw_html = parse.get("text", {}).get("*", "")
    clean_text = html_to_text(raw_html)

    return FandomPageText(
        title=title,
        page_id=page_id,
        text=clean_text,
        text_length=len(clean_text),
    )