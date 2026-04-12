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

# Content presets with max players and default compositions
CONTENT_PRESETS = {
    "ava_road": {
        "name": "🛤️ Ava Road",
        "max_players": 7,
        "default": {"tank": 1, "healer": 1, "dps_melee": 2, "dps_ranged": 2, "support": 1, "scout": 0},
    },
    "rat_static": {
        "name": "🐀 Rat Static",
        "max_players": 5,
        "default": {"tank": 1, "healer": 1, "dps_melee": 1, "dps_ranged": 1, "support": 1, "scout": 0},
    },
    "fame_farm": {
        "name": "⭐ Fame Farm Static",
        "max_players": 8,
        "default": {"tank": 1, "healer": 1, "dps_melee": 3, "dps_ranged": 2, "support": 1, "scout": 0},
    },
    "zvz": {
        "name": "⚔️ ZvZ",
        "max_players": 20,
        "default": {"tank": 3, "healer": 4, "dps_melee": 4, "dps_ranged": 5, "support": 3, "scout": 1},
    },
    "gvg": {
        "name": "🏰 GvG",
        "max_players": 5,
        "default": {"tank": 1, "healer": 1, "dps_melee": 1, "dps_ranged": 1, "support": 1, "scout": 0},
    },
    "ganking": {
        "name": "🗡️ Ganking",
        "max_players": 10,
        "default": {"tank": 1, "healer": 1, "dps_melee": 3, "dps_ranged": 2, "support": 1, "scout": 2},
    },
    "dungeon": {
        "name": "🏚️ Dungeon",
        "max_players": 5,
        "default": {"tank": 1, "healer": 1, "dps_melee": 1, "dps_ranged": 1, "support": 1, "scout": 0},
    },
    "hce": {
        "name": "💀 HCE",
        "max_players": 5,
        "default": {"tank": 1, "healer": 1, "dps_melee": 1, "dps_ranged": 1, "support": 1, "scout": 0},
    },
    "arena": {
        "name": "🎯 Arena / Crystal",
        "max_players": 5,
        "default": {"tank": 1, "healer": 1, "dps_melee": 1, "dps_ranged": 1, "support": 1, "scout": 0},
    },
    "custom": {
        "name": "📌 Custom",
        "max_players": 20,
        "default": {"tank": 1, "healer": 1, "dps_melee": 2, "dps_ranged": 2, "support": 1, "scout": 0},
    },
}


class TeamBuilderView(discord.ui.View):
    """Persistent view with buttons for joining team roles."""

    def __init__(self, team_data: dict):
        super().__init__(timeout=None)
        self.team_data = team_data

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

        # Add cancel/leave button
        self.add_item(LeaveButton(team_data))


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
            self._update_all_buttons(signed)
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

        self._update_all_buttons(signed)
        await interaction.response.edit_message(embed=build_team_embed(self.team_data), view=self.view)

    def _update_all_buttons(self, signed):
        for item in self.view.children:
            if isinstance(item, RoleButton):
                count = len(signed.get(item.role_key, []))
                item.label = f"{ALBION_ROLES[item.role_key]['name']} ({count}/{item.limit})"
                if count >= item.limit:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary


class LeaveButton(discord.ui.Button):
    def __init__(self, team_data: dict):
        super().__init__(style=discord.ButtonStyle.danger, emoji="🚪", label="Leave")
        self.team_data = team_data

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        signed = self.team_data["signed"]
        found = False

        for role, players in signed.items():
            if user_id in [p["id"] for p in players]:
                signed[role] = [p for p in players if p["id"] != user_id]
                found = True
                break

        if not found:
            await interaction.response.send_message("❌ You're not in this team!", ephemeral=True)
            return

        # Update buttons
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
    max_players = team_data.get("max_players", total_slots)

    if total_signed >= total_slots:
        color = discord.Color.green()
    elif total_signed > 0:
        color = discord.Color.orange()
    else:
        color = discord.Color.gold()

    embed = discord.Embed(
        title=f"⚔️ {team_data['name']}",
        description=(
            f"**{team_data['event_type']}** | "
            f"Players: **{total_signed}/{total_slots}** | "
            f"Max: **{max_players}**"
        ),
        color=color,
    )

    for role_key, limit in team_data["composition"].items():
        if limit <= 0:
            continue
        role_info = ALBION_ROLES[role_key]
        players = team_data["signed"].get(role_key, [])

        if players:
            player_names = "\n".join(f"✅ {p['name']}" for p in players)
            empty_slots = limit - len(players)
            if empty_slots > 0:
                player_names += "\n" + "\n".join(["⬜ ..." for _ in range(empty_slots)])
        else:
            player_names = "\n".join(["⬜ ..." for _ in range(limit)])

        embed.add_field(
            name=f"{role_info['emoji']} {role_info['name']} ({len(players)}/{limit})",
            value=player_names,
            inline=True,
        )

    if total_signed >= total_slots:
        embed.set_footer(text="✅ Team is FULL! Ready to go! ⚔️")
    else:
        embed.set_footer(text=f"🔽 Click a role button to join | {total_slots - total_signed} slots remaining")

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

    def __init__(self, team_name: str, content_key: str, scout_count: int = 0):
        super().__init__()
        self.team_name = team_name
        self.content_key = content_key
        self.scout_count = scout_count

        # Set defaults from preset
        preset = CONTENT_PRESETS.get(content_key, CONTENT_PRESETS["custom"])
        self.tank_count.default = str(preset["default"]["tank"])
        self.healer_count.default = str(preset["default"]["healer"])
        self.melee_dps_count.default = str(preset["default"]["dps_melee"])
        self.ranged_dps_count.default = str(preset["default"]["dps_ranged"])
        self.support_count.default = str(preset["default"]["support"])
        if scout_count == 0:
            self.scout_count = preset["default"].get("scout", 0)

    async def on_submit(self, interaction: discord.Interaction):
        preset = CONTENT_PRESETS.get(self.content_key, CONTENT_PRESETS["custom"])
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
        max_players = preset["max_players"]

        if total == 0:
            await interaction.response.send_message("❌ Team must have at least 1 slot!", ephemeral=True)
            return
        if total > max_players:
            await interaction.response.send_message(
                f"❌ {preset['name']} max is **{max_players}** players! You set {total}.",
                ephemeral=True,
            )
            return

        team_data = {
            "name": self.team_name,
            "event_type": preset["name"],
            "composition": composition,
            "signed": {},
            "max_players": max_players,
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
        name="Team/Run name (e.g., Evening Ava Roads)",
        content="Type of content",
        scout="Number of scouts (0 if none)",
    )
    @app_commands.choices(
        content=[
            app_commands.Choice(name="🛤️ Ava Road (7 max)", value="ava_road"),
            app_commands.Choice(name="🐀 Rat Static (5 max)", value="rat_static"),
            app_commands.Choice(name="⭐ Fame Farm Static (8 max)", value="fame_farm"),
            app_commands.Choice(name="⚔️ ZvZ (20 max)", value="zvz"),
            app_commands.Choice(name="🏰 GvG (5 max)", value="gvg"),
            app_commands.Choice(name="🗡️ Ganking (10 max)", value="ganking"),
            app_commands.Choice(name="🏚️ Dungeon (5 max)", value="dungeon"),
            app_commands.Choice(name="💀 HCE (5 max)", value="hce"),
            app_commands.Choice(name="🎯 Arena / Crystal (5 max)", value="arena"),
            app_commands.Choice(name="📌 Custom (20 max)", value="custom"),
        ]
    )
    async def createteam(
        self,
        interaction: discord.Interaction,
        name: str,
        content: str,
        scout: Optional[int] = 0,
    ):
        modal = CompositionModal(team_name=name, content_key=content, scout_count=scout or 0)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="quickteam", description="⚡ Quick preset team - ready in one click!")
    @app_commands.describe(
        name="Team/Run name",
        content="Type of content (uses default composition)",
    )
    @app_commands.choices(
        content=[
            app_commands.Choice(name="🛤️ Ava Road (7 players)", value="ava_road"),
            app_commands.Choice(name="🐀 Rat Static (5 players)", value="rat_static"),
            app_commands.Choice(name="⭐ Fame Farm (8 players)", value="fame_farm"),
            app_commands.Choice(name="🗡️ Ganking (10 players)", value="ganking"),
            app_commands.Choice(name="🏚️ Dungeon (5 players)", value="dungeon"),
        ]
    )
    async def quickteam(self, interaction: discord.Interaction, name: str, content: str):
        preset = CONTENT_PRESETS.get(content, CONTENT_PRESETS["ava_road"])

        team_data = {
            "name": name,
            "event_type": preset["name"],
            "composition": preset["default"].copy(),
            "signed": {},
            "max_players": preset["max_players"],
            "created_by": interaction.user.id,
        }

        embed = build_team_embed(team_data)
        view = TeamBuilderView(team_data)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(TeamBuilder(bot))
