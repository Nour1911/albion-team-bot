import discord
from discord import app_commands
from discord.ext import commands
import database as db


class Attendance(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id:
            return

        emoji = str(payload.emoji)
        if emoji not in ("✅", "❌"):
            return

        # Check if this message is an event message
        events = await db.get_all_events()
        event = None
        for e in events:
            if e["message_id"] == payload.message_id:
                event = e
                break

        if not event:
            return

        # Register the player if not already registered
        member = payload.member
        if member:
            await db.add_player(payload.user_id, member.display_name)

        status = "present" if emoji == "✅" else "absent"
        await db.set_attendance(event["id"], payload.user_id, status)

    attendance_group = app_commands.Group(
        name="attendance", description="Attendance tracking"
    )

    @attendance_group.command(name="stats", description="Show attendance stats for all players")
    async def attendance_stats(self, interaction: discord.Interaction):
        stats = await db.get_all_player_stats()

        if not stats:
            await interaction.response.send_message("📭 No attendance data yet!")
            return

        embed = discord.Embed(
            title="📊 Team Attendance Stats",
            color=discord.Color.green(),
        )

        for player in stats:
            total = player["total"] or 0
            present = player["present"] or 0
            absent = player["absent"] or 0
            rate = (present / total * 100) if total > 0 else 0

            bar_length = 10
            filled = round(rate / 100 * bar_length)
            bar = "🟩" * filled + "⬜" * (bar_length - filled)

            embed.add_field(
                name=f"{player['username']} ({player['role']})",
                value=f"{bar} {rate:.0f}%\n✅ {present} | ❌ {absent} | Total: {total}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @attendance_group.command(name="me", description="Show your personal attendance stats")
    async def attendance_me(self, interaction: discord.Interaction):
        player = await db.get_player(interaction.user.id)
        if not player:
            await interaction.response.send_message(
                "❌ You're not registered! Use `/role set` first.", ephemeral=True
            )
            return

        stats = await db.get_player_stats(interaction.user.id)
        total = stats["total"] or 0
        present = stats["present"] or 0
        absent = stats["absent"] or 0
        rate = (present / total * 100) if total > 0 else 0

        bar_length = 10
        filled = round(rate / 100 * bar_length)
        bar = "🟩" * filled + "⬜" * (bar_length - filled)

        embed = discord.Embed(
            title=f"📊 {interaction.user.display_name}'s Attendance",
            color=discord.Color.green(),
        )
        embed.add_field(name="Role", value=player["role"], inline=True)
        embed.add_field(name="Attendance Rate", value=f"{rate:.0f}%", inline=True)
        embed.add_field(name="Progress", value=bar, inline=False)
        embed.add_field(name="✅ Present", value=str(present), inline=True)
        embed.add_field(name="❌ Absent", value=str(absent), inline=True)
        embed.add_field(name="📋 Total Events", value=str(total), inline=True)

        await interaction.response.send_message(embed=embed)

    @attendance_group.command(name="event", description="Show attendance for a specific event")
    @app_commands.describe(event_id="The event ID")
    async def attendance_event(self, interaction: discord.Interaction, event_id: int):
        event = await db.get_event(event_id)
        if not event:
            await interaction.response.send_message("❌ Event not found!", ephemeral=True)
            return

        records = await db.get_event_attendance(event_id)

        embed = discord.Embed(
            title=f"📋 Attendance: {event['name']}",
            color=discord.Color.blue(),
        )

        present_list = []
        absent_list = []

        for r in records:
            if r["status"] == "present":
                present_list.append(f"• {r['username']} ({r['role']})")
            else:
                absent_list.append(f"• {r['username']} ({r['role']})")

        embed.add_field(
            name=f"✅ Present ({len(present_list)})",
            value="\n".join(present_list) if present_list else "None",
            inline=True,
        )
        embed.add_field(
            name=f"❌ Absent ({len(absent_list)})",
            value="\n".join(absent_list) if absent_list else "None",
            inline=True,
        )

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Attendance(bot))
