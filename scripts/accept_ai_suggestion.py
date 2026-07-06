import argparse

from app.ai_suggestion_review import accept_ai_suggestion


def main():
    parser = argparse.ArgumentParser(
        description="Accept one pending AI suggestion and create a real reminder event."
    )
    parser.add_argument("suggestion_id", type=int)

    args = parser.parse_args()
    result = accept_ai_suggestion(args.suggestion_id)

    print(result["message"])


if __name__ == "__main__":
    main()
