import argparse

from app.ai_suggestion_review import reject_ai_suggestion


def main():
    parser = argparse.ArgumentParser(
        description="Reject one pending AI suggestion."
    )
    parser.add_argument("suggestion_id", type=int)

    args = parser.parse_args()
    result = reject_ai_suggestion(args.suggestion_id)

    print(result["message"])


if __name__ == "__main__":
    main()
