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


async def auto_upload_emojis():
    """Auto-upload AVA RAID emojis to all guilds the bot is in."""
    from cogs.team_builder import AVA_RAID_ROLES, AVA_RAID_IMAGES_PATH

    if not os.path.exists(AVA_RAID_IMAGES_PATH):
        print("⚠️ Emoji images folder not found, skipping auto-upload")
        return

    for guild in bot.guilds:
        existing_names = {e.name.lower() for e in guild.emojis}
        for role_key, role_info in AVA_RAID_ROLES.items():
            if role_key in existing_names:
                continue
            image_file = os.path.join(AVA_RAID_IMAGES_PATH, role_info["image"])
            if not os.path.exists(image_file):
                continue
            try:
                with open(image_file, "rb") as f:
                    image_data = f.read()
                await guild.create_custom_emoji(name=role_key[:32], image=image_data)
                print(f"  📤 Uploaded emoji: {role_key} -> {guild.name}")
            except Exception as e:
                print(f"  ⚠️ Failed {role_key} in {guild.name}: {e}")


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

    # Auto-upload emojis
    print("📤 Checking emojis...")
    await auto_upload_emojis()
    print("✅ Emoji check complete!")


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
            "`/createteam` - Create a team (with modal editor)\n"
            "`/quickteam` - Quick preset team in one click\n"
            "`/build` - Build team with dropdown weapon selection\n"
            "`/quickadd` - Quick single-weapon team"
        ),
        inline=False,
    )
    embed.add_field(
        name="🗡️ Weapons & Roles",
        value=(
            "`/weapons` - Show all available weapons/roles\n"
            "`/upload_emojis` - Upload weapon emojis to server\n"
            "`/role add` - Add custom role\n"
            "`/role remove` - Remove custom role\n"
            "`/role list` - List all roles\n"
            "`/role emoji` - Change role emoji"
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
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
