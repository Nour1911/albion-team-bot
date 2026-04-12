import discord
from discord import app_commands
from discord.ext import commands
import database as db

ALBION_ROLES = ["Tank", "Healer", "DPS", "Support", "Scout", "Gatherer", "Flex"]

ROLE_EMOJIS = {
    "Tank": "🛡️",
    "Healer": "💚",
    "DPS": "⚔️",
    "Support": "🔮",
    "Scout": "👁️",
    "Gatherer": "⛏️",
    "Flex": "🔄",
}


class Roles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    role_group = app_commands.Group(name="role", description="Manage team roles")

    @role_group.command(name="set", description="Set your role in the team")
    @app_commands.describe(role="Choose your role")
    @app_commands.choices(
        role=[app_commands.Choice(name=f"{ROLE_EMOJIS[r]} {r}", value=r) for r in ALBION_ROLES]
    )
    async def role_set(self, interaction: discord.Interaction, role: str):
        await db.add_player(interaction.user.id, interaction.user.display_name, role)
        await db.set_player_role(interaction.user.id, role)

        embed = discord.Embed(
            title="🎭 Role Updated!",
            description=f"{interaction.user.mention} is now **{ROLE_EMOJIS[role]} {role}**",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @role_group.command(name="list", description="Show available Albion roles")
    async def role_list(self, interaction: discord.Interaction):
        roles_text = "\n".join(
            f"{ROLE_EMOJIS[r]} **{r}**" for r in ALBION_ROLES
        )
        embed = discord.Embed(
            title="🎭 Available Roles",
            description=roles_text,
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Use /role set to choose your role")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="team", description="Show current team composition")
    async def team(self, interaction: discord.Interaction):
        players = await db.get_all_players()

        if not players:
            await interaction.response.send_message("No players registered yet! Use `/role set` to join.")
            return

        embed = discord.Embed(
            title="⚔️ Albion Team Roster",
            color=discord.Color.gold(),
        )

        for role_name in ALBION_ROLES:
            role_players = [p for p in players if p["role"] == role_name]
            if role_players:
                names = "\n".join(f"• {p['username']}" for p in role_players)
                embed.add_field(
                    name=f"{ROLE_EMOJIS[role_name]} {role_name} ({len(role_players)})",
                    value=names,
                    inline=True,
                )

        embed.set_footer(text=f"Total: {len(players)}/7 players")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Roles(bot))
