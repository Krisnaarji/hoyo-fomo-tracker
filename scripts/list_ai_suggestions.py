from app.ai_suggestion_review import fetch_pending_ai_suggestions


def main():
    suggestions = fetch_pending_ai_suggestions()

    if not suggestions:
        print("No pending AI suggestions.")
        return

    for row in suggestions:
        print(
            f"[{row['id']}] "
            f"{row['game_title']} | "
            f"{row['suggested_category']} | "
            f"{row['event_name']} | "
            f"{row['start_date']} → {row['end_date']} | "
            f"{row['status']}"
        )


if __name__ == "__main__":
    main()
