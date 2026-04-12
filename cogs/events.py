import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import database as db

EVENT_TYPES = ["GvG", "ZvZ", "Ganking", "Dungeon", "HCE", "Gathering", "Practice", "Other"]

EVENT_EMOJIS = {
    "GvG": "⚔️",
    "ZvZ": "🏰",
    "Ganking": "🗡️",
    "Dungeon": "🏚️",
    "HCE": "💀",
    "Gathering": "⛏️",
    "Practice": "🎯",
    "Other": "📌",
}


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reminder_check.start()

    def cog_unload(self):
        self.reminder_check.cancel()

    event_group = app_commands.Group(name="event", description="Manage team events")

    @event_group.command(name="create", description="Create a new event")
    @app_commands.describe(
        name="Event name",
        event_type="Type of event",
        date="Date (DD/MM/YYYY)",
        time="Time (HH:MM) - 24h format",
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name=f"{EVENT_EMOJIS[t]} {t}", value=t)
            for t in EVENT_TYPES
        ]
    )
    async def event_create(
        self,
        interaction: discord.Interaction,
        name: str,
        event_type: str,
        date: str,
        time: str,
    ):
        try:
            date_time = datetime.strptime(f"{date} {time}", "%d/%m/%Y %H:%M")
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid date/time format! Use DD/MM/YYYY for date and HH:MM for time.",
                ephemeral=True,
            )
            return

        if date_time < datetime.now():
            await interaction.response.send_message(
                "❌ Can't create an event in the past!", ephemeral=True
            )
            return

        event_id = await db.create_event(
            name, event_type, date_time.strftime("%Y-%m-%d %H:%M"), interaction.user.id
        )

        emoji = EVENT_EMOJIS.get(event_type, "📌")
        embed = discord.Embed(
            title=f"{emoji} {name}",
            color=discord.Color.blue(),
        )
        embed.add_field(name="📋 Type", value=event_type, inline=True)
        embed.add_field(
            name="📅 Date", value=date_time.strftime("%d/%m/%Y"), inline=True
        )
        embed.add_field(
            name="⏰ Time", value=date_time.strftime("%H:%M"), inline=True
        )
        embed.add_field(name="🆔 Event ID", value=str(event_id), inline=True)
        embed.set_footer(
            text=f"Created by {interaction.user.display_name} | React ✅ to attend, ❌ to skip"
        )

        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")

        await db.update_event_message(event_id, interaction.channel_id, msg.id)

    @event_group.command(name="list", description="Show upcoming events")
    async def event_list(self, interaction: discord.Interaction):
        events = await db.get_upcoming_events()

        if not events:
            await interaction.response.send_message("📭 No upcoming events! Use `/event create` to make one.")
            return

        embed = discord.Embed(
            title="📅 Upcoming Events",
            color=discord.Color.purple(),
        )

        for event in events:
            dt = datetime.strptime(event["date_time"], "%Y-%m-%d %H:%M")
            emoji = EVENT_EMOJIS.get(event["event_type"], "📌")
            embed.add_field(
                name=f"{emoji} {event['name']} (ID: {event['id']})",
                value=f"**Type:** {event['event_type']}\n**Date:** {dt.strftime('%d/%m/%Y %H:%M')}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @event_group.command(name="delete", description="Delete an event")
    @app_commands.describe(event_id="The event ID to delete")
    async def event_delete(self, interaction: discord.Interaction, event_id: int):
        event = await db.get_event(event_id)
        if not event:
            await interaction.response.send_message("❌ Event not found!", ephemeral=True)
            return

        await db.delete_event(event_id)
        await interaction.response.send_message(f"🗑️ Event **{event['name']}** (ID: {event_id}) deleted!")

    @tasks.loop(minutes=1)
    async def reminder_check(self):
        events = await db.get_upcoming_events()
        now = datetime.now()

        for event in events:
            dt = datetime.strptime(event["date_time"], "%Y-%m-%d %H:%M")
            diff = dt - now

            if timedelta(minutes=29) <= diff <= timedelta(minutes=31):
                if event["channel_id"]:
                    channel = self.bot.get_channel(event["channel_id"])
                    if channel:
                        emoji = EVENT_EMOJIS.get(event["event_type"], "📌")
                        embed = discord.Embed(
                            title=f"⏰ Reminder! {emoji} {event['name']}",
                            description=f"Event starts in **30 minutes**!\n**Time:** {dt.strftime('%H:%M')}",
                            color=discord.Color.orange(),
                        )
                        await channel.send("@here", embed=embed)

    @reminder_check.before_loop
    async def before_reminder(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(Events(bot))
