import argparse
import json

from app.ai_event_extractor import extract_events_with_ai
from app.ai_suggestions import save_ai_event_suggestions
from app.scraper import hash_text
from app.fandom_api import fetch_fandom_parse_text


def main():
    parser = argparse.ArgumentParser(
        description="Run AI extraction once and save results as pending suggestions."
    )
    parser.add_argument("--game", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-limit", type=int, default=3000)

    args = parser.parse_args()

    page = fetch_fandom_parse_text(args.url)
    source_text = page.text[: args.source_limit]
    source_hash = hash_text(page.text)

    ai_result = extract_events_with_ai(args.game, source_text)

    save_result = save_ai_event_suggestions(
        game_title=args.game,
        source_url=args.url,
        source_hash=source_hash,
        ai_result=ai_result,
    )

    print(json.dumps(ai_result, indent=2, ensure_ascii=False))
    print()
    print(f"Saved suggestions: {save_result}")


if __name__ == "__main__":
    main()
