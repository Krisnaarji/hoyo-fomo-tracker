import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup


@dataclass
class ScrapedPage:
    url: str
    title: str
    text: str
    content_hash: str
    content_length: int


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_text_from_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled"

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(" ", strip=True)

    return normalize_text(title), normalize_text(text)


def scrape_url(url: str, timeout: int = 20) -> ScrapedPage:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; HoYoFOMOTracker/0.1; "
            "+https://github.com/Krisnaarji/hoyo-fomo-tracker)"
        )
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    title, text = extract_text_from_html(response.text)

    return ScrapedPage(
        url=url,
        title=title,
        text=text,
        content_hash=hash_text(text),
        content_length=len(text),
    )