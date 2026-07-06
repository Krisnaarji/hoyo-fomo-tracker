from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from app.ai_suggestion_review import (
    accept_ai_suggestion,
    fetch_pending_ai_suggestions,
    fetch_unposted_ai_suggestions,
    format_suggestion_summary,
    get_pending_ai_suggestion,
    mark_ai_suggestion_posted,
    reject_ai_suggestion,
)
from app.db import get_conn, init_db, row_to_dict
from app.settings import get_env

LOCAL_TZ = ZoneInfo("Asia/Makassar")

CATEGORY_EMOJI = {
    "DAILY": "⚠️",
    "HEAVY": "🔥",
    "SPEEDRUN": "⚡",
}

SUGGESTION_EMOJI = {
    "daily": "⚠️",
    "heavy": "🔥",
    "speedrun": "⚡",
    "info": "ℹ️",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_local() -> date:
    return datetime.now(LOCAL_TZ).date()


def parse_date(value):
    if not value:
        return None

    if len(value) == 10:
        return date.fromisoformat(value)

    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(LOCAL_TZ).date()


def daily_checkin_done_today(event: dict) -> bool:
    last_checkin = parse_date(event.get("last_daily_checkin"))
    return last_checkin == today_local()


def fetch_active_events():
    today = today_local().isoformat()

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM events
            WHERE
                is_muted = 0
                AND (start_date IS NULL OR date(start_date) <= date(?))
                AND (end_date IS NULL OR date(end_date) >= date(?))
            ORDER BY
                CASE category_tag
                    WHEN 'HEAVY' THEN 0
                    WHEN 'DAILY' THEN 1
                    WHEN 'SPEEDRUN' THEN 2
                    ELSE 3
                END,
                end_date IS NULL,
                end_date ASC,
                game_title ASC
            LIMIT 25
            """,
            (today, today),
        ).fetchall()

    return [row_to_dict(row) for row in rows]


def get_event(event_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

    return row_to_dict(row)


def set_event_progress(event_id: int, progress_status: int):
    timestamp = now_iso()
    is_muted = 1 if progress_status >= 100 else 0

    with get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET
                progress_status = ?,
                is_muted = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (progress_status, is_muted, timestamp, event_id),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return None

        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

    return row_to_dict(row)


def mark_daily_checkin(event_id: int):
    timestamp = now_iso()

    with get_conn() as conn:
        cursor = conn.execute(
            """
            UPDATE events
            SET
                last_daily_checkin = ?,
                progress_status = 1,
                updated_at = ?
            WHERE id = ?
              AND category_tag = 'DAILY'
            """,
            (timestamp, timestamp, event_id),
        )
        conn.commit()

        if cursor.rowcount == 0:
            return None

        row = conn.execute(
            "SELECT * FROM events WHERE id = ?",
            (event_id,),
        ).fetchone()

    return row_to_dict(row)


def format_event_card(event: dict) -> str:
    emoji = CATEGORY_EMOJI.get(event["category_tag"], "📌")
    muted = "Muted" if event["is_muted"] else "Active"

    start_date = event["start_date"] or "Unknown"
    end_date = event["end_date"] or "Unknown"
    summary = event["ai_summary"] or "No summary yet."

    return (
        f"{emoji} **{event['game_title']} — {event['event_name']}**\n"
        f"Category: `{event['category_tag']}`\n"
        f"Progress: `{event['progress_status']}%`\n"
        f"Status: `{muted}`\n"
        f"Start: `{start_date}`\n"
        f"End: `{end_date}`\n\n"
        f"{summary}"
    )


def should_show_actions(event: dict) -> bool:
    category = event["category_tag"]

    if event["is_muted"] or int(event["progress_status"]) >= 100:
        return False

    if category == "DAILY" and daily_checkin_done_today(event):
        return False

    return True


class EventActionView(discord.ui.View):
    def __init__(self, event: dict):
        super().__init__(timeout=180)
        self.event = event
        self.event_id = int(event["id"])

        if not should_show_actions(event):
            return

        category = event["category_tag"]

        if category == "DAILY":
            button = discord.ui.Button(
                label="✅ Check-in Today",
                style=discord.ButtonStyle.success,
            )
            button.callback = self.daily_checkin_callback
            self.add_item(button)

        elif category == "HEAVY":
            for value in [25, 50, 75, 100]:
                label = "✅ 100%" if value == 100 else f"{value}%"
                style = (
                    discord.ButtonStyle.success
                    if value == 100
                    else discord.ButtonStyle.primary
                )

                button = discord.ui.Button(label=label, style=style)

                if int(event["progress_status"]) == value:
                    button.disabled = True

                button.callback = self.make_progress_callback(value)
                self.add_item(button)

        elif category == "SPEEDRUN":
            button = discord.ui.Button(
                label="✅ Done",
                style=discord.ButtonStyle.success,
            )
            button.callback = self.speedrun_done_callback
            self.add_item(button)

    async def daily_checkin_callback(self, interaction: discord.Interaction):
        updated = mark_daily_checkin(self.event_id)

        if not updated:
            await interaction.response.edit_message(
                content="Could not mark daily check-in. Event may not exist or is not DAILY.",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=format_event_card(updated) + "\n\n✅ Checked in for today.",
            view=None,
        )

    def make_progress_callback(self, value: int):
        async def callback(interaction: discord.Interaction):
            updated = set_event_progress(self.event_id, value)

            if not updated:
                await interaction.response.edit_message(
                    content="Could not update progress. Event may not exist.",
                    view=None,
                )
                return

            extra = ""
            next_view = EventActionView(updated)

            if value >= 100:
                extra = "\n\n✅ Completed. Reminders for this event are now muted."
                next_view = None
            else:
                extra = f"\n\nProgress updated to {value}%."

            await interaction.response.edit_message(
                content=format_event_card(updated) + extra,
                view=next_view,
            )

        return callback

    async def speedrun_done_callback(self, interaction: discord.Interaction):
        updated = set_event_progress(self.event_id, 100)

        if not updated:
            await interaction.response.edit_message(
                content="Could not complete event. Event may not exist.",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=format_event_card(updated)
            + "\n\n✅ Speedrun event completed. Reminders muted.",
            view=None,
        )


class HoyoEventSelect(discord.ui.Select):
    def __init__(self, events: list[dict]):
        options = []

        for event in events:
            emoji = CATEGORY_EMOJI.get(event["category_tag"], "📌")
            label = f"{emoji} {event['game_title']}: {event['event_name']}"

            if len(label) > 100:
                label = label[:97] + "..."

            description = (
                f"{event['category_tag']} | "
                f"End: {event['end_date'] or 'Unknown'} | "
                f"{event['progress_status']}%"
            )

            if len(description) > 100:
                description = description[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(event["id"]),
                    description=description,
                )
            )

        super().__init__(
            placeholder="Choose an active HoYo event...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        event_id = int(self.values[0])
        event = get_event(event_id)

        if not event:
            await interaction.response.edit_message(
                content="Event not found.",
                view=None,
            )
            return

        next_view = EventActionView(event)
        extra = ""

        if len(next_view.children) == 0:
            next_view = None

            if event["category_tag"] == "DAILY" and daily_checkin_done_today(event):
                extra = "\n\n✅ Already checked in today."
            elif event["is_muted"] or int(event["progress_status"]) >= 100:
                extra = "\n\n✅ This event is already completed."

        await interaction.response.edit_message(
            content=format_event_card(event) + extra,
            view=next_view,
        )


class HoyoSelectView(discord.ui.View):
    def __init__(self, events: list[dict]):
        super().__init__(timeout=180)
        self.add_item(HoyoEventSelect(events))


class SuggestionActionView(discord.ui.View):
    def __init__(self, suggestion: dict):
        super().__init__(timeout=180)
        self.suggestion_id = int(suggestion["id"])

        if suggestion["suggested_category"] != "info":
            accept_button = discord.ui.Button(
                label="✅ Accept",
                style=discord.ButtonStyle.success,
            )
            accept_button.callback = self.accept_callback
            self.add_item(accept_button)

        reject_button = discord.ui.Button(
            label="🗑️ Reject",
            style=discord.ButtonStyle.danger,
        )
        reject_button.callback = self.reject_callback
        self.add_item(reject_button)

    async def accept_callback(self, interaction: discord.Interaction):
        result = accept_ai_suggestion(self.suggestion_id)
        await interaction.response.edit_message(
            content=result["message"],
            view=None,
        )

    async def reject_callback(self, interaction: discord.Interaction):
        result = reject_ai_suggestion(self.suggestion_id)
        await interaction.response.edit_message(
            content=result["message"],
            view=None,
        )


class SuggestionSelect(discord.ui.Select):
    def __init__(self, suggestions: list[dict]):
        options = []

        for suggestion in suggestions:
            emoji = SUGGESTION_EMOJI.get(suggestion["suggested_category"], "📌")
            label = f"{emoji} {suggestion['game_title']}: {suggestion['event_name']}"

            if len(label) > 100:
                label = label[:97] + "..."

            description = (
                f"{suggestion['suggested_category']} | "
                f"{suggestion['start_date'] or 'Unknown'} → "
                f"{suggestion['end_date'] or 'Unknown'}"
            )

            if len(description) > 100:
                description = description[:97] + "..."

            options.append(
                discord.SelectOption(
                    label=label,
                    value=str(suggestion["id"]),
                    description=description,
                )
            )

        super().__init__(
            placeholder="Choose a pending AI suggestion...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        suggestion_id = int(self.values[0])
        suggestion = get_pending_ai_suggestion(suggestion_id)

        if not suggestion:
            await interaction.response.edit_message(
                content="Suggestion not found or already reviewed.",
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=format_suggestion_summary(suggestion),
            view=SuggestionActionView(suggestion),
        )


class SuggestionSelectView(discord.ui.View):
    def __init__(self, suggestions: list[dict]):
        super().__init__(timeout=180)
        self.add_item(SuggestionSelect(suggestions))


class HoyoBot(commands.Bot):
    async def setup_hook(self):
        guild_id = get_env("DISCORD_GUILD_ID")

        if guild_id:
            guild = discord.Object(id=int(guild_id))

            # Copy globally-defined commands like /hoyo into this private server
            # so they appear immediately instead of waiting for global sync.
            self.tree.copy_global_to(guild=guild)

            synced = await self.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {guild_id}")
        else:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} global command(s)")


intents = discord.Intents.default()
bot = HoyoBot(command_prefix="!", intents=intents)


@tasks.loop(minutes=5)
async def suggestion_review_poster():
    channel_id = get_env("DISCORD_REVIEW_CHANNEL_ID")

    if not channel_id:
        return

    suggestions = fetch_unposted_ai_suggestions(limit=5)

    if not suggestions:
        return

    channel = bot.get_channel(int(channel_id))

    if channel is None:
        channel = await bot.fetch_channel(int(channel_id))

    for suggestion in suggestions:
        message = await channel.send(
            content=format_suggestion_summary(suggestion),
            view=SuggestionActionView(suggestion),
        )
        mark_ai_suggestion_posted(suggestion["id"], message.id)


@bot.event
async def on_ready():
    init_db()

    if not suggestion_review_poster.is_running():
        suggestion_review_poster.start()

    print(f"Logged in as {bot.user}")


@bot.tree.command(name="hoyo-suggestions", description="Review pending AI event suggestions")
async def hoyo_suggestions(interaction: discord.Interaction):
    suggestions = fetch_pending_ai_suggestions()

    if not suggestions:
        await interaction.response.send_message(
            "No pending AI suggestions.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        f"Pending AI suggestions: `{len(suggestions)}`",
        view=SuggestionSelectView(suggestions),
        ephemeral=True,
    )


@bot.tree.command(name="hoyo", description="Show active HoYo events checklist")
async def hoyo(interaction: discord.Interaction):
    events = fetch_active_events()

    if not events:
        await interaction.response.send_message(
            "No active HoYo events right now. Peace... for now.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        "Choose an active HoYo event:",
        view=HoyoSelectView(events),
        ephemeral=True,
    )


def main():
    init_db()

    token = get_env("DISCORD_BOT_TOKEN")

    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set in .env")

    bot.run(token)


if __name__ == "__main__":
    main()