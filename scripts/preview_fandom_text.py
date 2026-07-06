import argparse

from app.fandom_api import fetch_fandom_parse_text


def main():
    parser = argparse.ArgumentParser(
        description="Preview cleaned text from a Fandom API parse URL."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--limit", type=int, default=1200)

    args = parser.parse_args()

    page = fetch_fandom_parse_text(args.url)

    print(f"Title: {page.title}")
    print(f"Page ID: {page.page_id}")
    print(f"Text length: {page.text_length}")
    print()
    print(page.text[: args.limit])


if __name__ == "__main__":
    main()