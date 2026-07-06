import argparse

from app.ai_event_extractor import build_event_extraction_prompt
from app.fandom_api import fetch_fandom_parse_text


def main():
    parser = argparse.ArgumentParser(
        description="Preview the prompt that will be sent to DeepSeek without calling the API."
    )
    parser.add_argument("--game", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--source-limit", type=int, default=3000)
    parser.add_argument("--prompt-limit", type=int, default=5000)

    args = parser.parse_args()

    page = fetch_fandom_parse_text(args.url)
    source_text = page.text[: args.source_limit]

    prompt = build_event_extraction_prompt(args.game, source_text)

    print(f"Game: {args.game}")
    print(f"Source title: {page.title}")
    print(f"Original text length: {page.text_length}")
    print(f"Text sent to prompt: {len(source_text)}")
    print()
    print(prompt[: args.prompt_limit])


if __name__ == "__main__":
    main()