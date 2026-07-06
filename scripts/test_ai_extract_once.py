import argparse
import json

from app.ai_event_extractor import extract_events_with_ai
from app.fandom_api import fetch_fandom_parse_text


def main():
    parser = argparse.ArgumentParser(
        description="Run one AI extraction test for a Fandom source."
    )
    parser.add_argument("--game", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-limit", type=int, default=3000)

    args = parser.parse_args()

    page = fetch_fandom_parse_text(args.url)
    source_text = page.text[: args.source_limit]

    result = extract_events_with_ai(args.game, source_text)

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
