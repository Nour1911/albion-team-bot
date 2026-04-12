import os
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
import database as db

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)


@bot.event
async def on_ready():
    await db.init_db()
    # Set bot status so it appears online in sidebar
    activity = discord.Activity(type=discord.ActivityType.playing, name="Albion Online ⚔️")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f"✅ {bot.user.name} is online!")
    try:
        synced = await bot.tree.sync()
        print(f"🔄 Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


@bot.tree.command(name="ping", description="Check if the bot is alive")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"🏓 Pong! Latency: {round(bot.latency * 1000)}ms"
    )


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚔️ Albion Team Bot - Commands",
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="⚔️ Team Builder",
        value=(
            "`/createteam` - Create a new team for a run\n"
            "`/myteams` - Show your active teams"
        ),
        inline=False,
    )
    embed.add_field(
        name="📅 Events",
        value=(
            "`/event create` - Create a new event\n"
            "`/event list` - Show upcoming events\n"
            "`/event delete` - Delete an event"
        ),
        inline=False,
    )
    embed.add_field(
        name="📊 Attendance",
        value=(
            "React with role emojis on team messages to join\n"
            "`/attendance stats` - Show attendance stats\n"
            "`/attendance me` - Show your stats"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔧 Other",
        value="`/ping` - Check bot latency\n`/help` - Show this message",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


async def main():
    async with bot:
        await bot.load_extension("cogs.team_builder")
        await bot.load_extension("cogs.events")
        await bot.load_extension("cogs.attendance")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
