import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

# Albion Online roles with emojis
ALBION_ROLES = {
    "tank": {"emoji": "🛡️", "name": "Tank", "description": "Frontline tank (Mace, Hammer, Sword)"},
    "healer": {"emoji": "💚", "name": "Healer", "description": "Healer (Holy, Nature)"},
    "dps_melee": {"emoji": "⚔️", "name": "Melee DPS", "description": "Melee damage (Axe, Dagger, Spear)"},
    "dps_ranged": {"emoji": "🏹", "name": "Ranged DPS", "description": "Ranged damage (Bow, Crossbow, Fire, Frost)"},
    "support": {"emoji": "🔮", "name": "Support", "description": "Support/Utility (Arcane, Curse)"},
    "scout": {"emoji": "👁️", "name": "Scout", "description": "Scout/Dismounter"},
}

# Map emojis to role keys for reaction tracking
EMOJI_TO_ROLE = {v["emoji"]: k for k, v in ALBION_ROLES.items()}


class TeamBuilderView(discord.ui.View):
    """Persistent view with buttons for joining team roles."""

    def __init__(self, team_data: dict):
        super().__init__(timeout=None)
        self.team_data = team_data

        # Add a button for each role that has slots
        for role_key, limit in team_data["composition"].items():
            if limit > 0:
                role_info = ALBION_ROLES[role_key]
                button = RoleButton(
                    role_key=role_key,
                    emoji=role_info["emoji"],
                    label=f"{role_info['name']} (0/{limit})",
                    limit=limit,
                    team_data=team_data,
                )
                self.add_item(button)


class RoleButton(discord.ui.Button):
    def __init__(self, role_key: str, emoji: str, label: str, limit: int, team_data: dict):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, label=label)
        self.role_key = role_key
        self.limit = limit
        self.team_data = team_data

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        signed = self.team_data["signed"]

        # Check if user already signed for another role - remove them first
        for role, players in signed.items():
            if user_id in [p["id"] for p in players]:
                signed[role] = [p for p in players if p["id"] != user_id]
                break

        current_players = signed.get(self.role_key, [])

        # Check if user is already in this role (toggle off)
        if user_id in [p["id"] for p in current_players]:
            signed[self.role_key] = [p for p in current_players if p["id"] != user_id]
            await interaction.response.edit_message(embed=build_team_embed(self.team_data), view=self.view)
            return

        # Check limit
        if len(current_players) >= self.limit:
            await interaction.response.send_message(
                f"❌ {ALBION_ROLES[self.role_key]['name']} is full! ({self.limit}/{self.limit})",
                ephemeral=True,
            )
            return

        # Add player
        if self.role_key not in signed:
            signed[self.role_key] = []
        signed[self.role_key].append({"id": user_id, "name": user_name})

        # Update button labels
        for item in self.view.children:
            if isinstance(item, RoleButton):
                count = len(signed.get(item.role_key, []))
                item.label = f"{ALBION_ROLES[item.role_key]['name']} ({count}/{item.limit})"
                if count >= item.limit:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(embed=build_team_embed(self.team_data), view=self.view)


def build_team_embed(team_data: dict) -> discord.Embed:
    """Build the team composition embed."""
    total_slots = sum(team_data["composition"].values())
    total_signed = sum(len(players) for players in team_data["signed"].values())

    embed = discord.Embed(
        title=f"⚔️ {team_data['name']}",
        description=f"**{team_data['event_type']}** | Team Size: **{total_signed}/{total_slots}**",
        color=discord.Color.gold() if total_signed < total_slots else discord.Color.green(),
    )

    for role_key, limit in team_data["composition"].items():
        if limit <= 0:
            continue
        role_info = ALBION_ROLES[role_key]
        players = team_data["signed"].get(role_key, [])
        player_names = "\n".join(f"• {p['name']}" for p in players) if players else "*Empty*"
        empty_slots = limit - len(players)
        if empty_slots > 0 and players:
            player_names += f"\n⬜ × {empty_slots} slots open"
        elif empty_slots > 0:
            player_names = f"⬜ × {empty_slots} slots open"

        embed.add_field(
            name=f"{role_info['emoji']} {role_info['name']} ({len(players)}/{limit})",
            value=player_names,
            inline=True,
        )

    if total_signed >= total_slots:
        embed.set_footer(text="✅ Team is FULL! Ready to go!")
    else:
        embed.set_footer(text=f"🔽 Click a button to join | {total_slots - total_signed} slots remaining")

    return embed


class CompositionModal(discord.ui.Modal, title="⚔️ Team Composition"):
    """Modal to set how many of each role."""

    tank_count = discord.ui.TextInput(
        label="🛡️ Tank (Mace, Hammer, Sword)",
        placeholder="0",
        default="1",
        max_length=2,
        required=True,
    )
    healer_count = discord.ui.TextInput(
        label="💚 Healer (Holy, Nature)",
        placeholder="0",
        default="1",
        max_length=2,
        required=True,
    )
    melee_dps_count = discord.ui.TextInput(
        label="⚔️ Melee DPS (Axe, Dagger, Spear)",
        placeholder="0",
        default="2",
        max_length=2,
        required=True,
    )
    ranged_dps_count = discord.ui.TextInput(
        label="🏹 Ranged DPS (Bow, Crossbow, Fire, Frost)",
        placeholder="0",
        default="2",
        max_length=2,
        required=True,
    )
    support_count = discord.ui.TextInput(
        label="🔮 Support (Arcane, Curse)",
        placeholder="0",
        default="1",
        max_length=2,
        required=True,
    )

    def __init__(self, team_name: str, event_type: str, scout_count: int = 0):
        super().__init__()
        self.team_name = team_name
        self.event_type = event_type
        self.scout_count = scout_count

    async def on_submit(self, interaction: discord.Interaction):
        try:
            composition = {
                "tank": int(self.tank_count.value),
                "healer": int(self.healer_count.value),
                "dps_melee": int(self.melee_dps_count.value),
                "dps_ranged": int(self.ranged_dps_count.value),
                "support": int(self.support_count.value),
                "scout": self.scout_count,
            }
        except ValueError:
            await interaction.response.send_message("❌ Please enter numbers only!", ephemeral=True)
            return

        total = sum(composition.values())
        if total == 0:
            await interaction.response.send_message("❌ Team must have at least 1 slot!", ephemeral=True)
            return
        if total > 20:
            await interaction.response.send_message("❌ Maximum team size is 20!", ephemeral=True)
            return

        team_data = {
            "name": self.team_name,
            "event_type": self.event_type,
            "composition": composition,
            "signed": {},
            "created_by": interaction.user.id,
        }

        embed = build_team_embed(team_data)
        view = TeamBuilderView(team_data)

        await interaction.response.send_message(embed=embed, view=view)


class TeamBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="createteam", description="⚔️ Create a team for a run")
    @app_commands.describe(
        name="Team/Run name (e.g., ZvZ Evening Run)",
        event_type="Type of content",
        scout="Number of scouts (0 if none)",
    )
    @app_commands.choices(
        event_type=[
            app_commands.Choice(name="⚔️ ZvZ (Zerg vs Zerg)", value="ZvZ"),
            app_commands.Choice(name="🏰 GvG (Guild vs Guild)", value="GvG"),
            app_commands.Choice(name="🗡️ Ganking", value="Ganking"),
            app_commands.Choice(name="🏚️ Dungeon", value="Dungeon"),
            app_commands.Choice(name="💀 HCE (Hardcore Expedition)", value="HCE"),
            app_commands.Choice(name="🎯 Arena / Crystal", value="Arena"),
            app_commands.Choice(name="📌 Other", value="Other"),
        ]
    )
    async def createteam(
        self,
        interaction: discord.Interaction,
        name: str,
        event_type: str,
        scout: Optional[int] = 0,
    ):
        modal = CompositionModal(team_name=name, event_type=event_type, scout_count=scout or 0)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="quickteam", description="⚡ Quick 7-man team (1 Tank, 1 Healer, 3 DPS, 1 Support, 1 Scout)")
    @app_commands.describe(name="Team/Run name")
    async def quickteam(self, interaction: discord.Interaction, name: str):
        team_data = {
            "name": name,
            "event_type": "Quick Team",
            "composition": {
                "tank": 1,
                "healer": 1,
                "dps_melee": 2,
                "dps_ranged": 2,
                "support": 1,
                "scout": 0,
            },
            "signed": {},
            "created_by": interaction.user.id,
        }

        embed = build_team_embed(team_data)
        view = TeamBuilderView(team_data)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(TeamBuilder(bot))
