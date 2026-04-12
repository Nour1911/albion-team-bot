import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import database as db

# Default Albion Online roles
DEFAULT_ROLES = {
    "tank": {"emoji": "🛡️", "name": "Tank", "description": "Frontline tank (Mace, Hammer, Sword)"},
    "healer": {"emoji": "💚", "name": "Healer", "description": "Healer (Holy, Nature)"},
    "dps_melee": {"emoji": "⚔️", "name": "Melee DPS", "description": "Melee damage (Axe, Dagger, Spear)"},
    "dps_ranged": {"emoji": "🏹", "name": "Ranged DPS", "description": "Ranged damage (Bow, Crossbow, Fire, Frost)"},
    "support": {"emoji": "🔮", "name": "Support", "description": "Support/Utility (Arcane, Curse)"},
    "scout": {"emoji": "👁️", "name": "Scout", "description": "Scout/Dismounter"},
}

# Content presets
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


async def get_guild_roles(guild_id: int) -> dict:
    """Get roles for a guild - custom roles merged with defaults."""
    roles = dict(DEFAULT_ROLES)
    custom = await db.get_custom_roles(guild_id)
    for r in custom:
        roles[r["role_key"]] = {
            "emoji": r["emoji"],
            "name": r["name"],
            "description": r["description"] or "",
        }
    return roles


class TeamBuilderView(discord.ui.View):
    """Persistent view with buttons for joining team roles."""

    def __init__(self, team_data: dict, roles: dict):
        super().__init__(timeout=None)
        self.team_data = team_data
        self.roles = roles

        for role_key, limit in team_data["composition"].items():
            if limit > 0 and role_key in roles:
                role_info = roles[role_key]
                button = RoleButton(
                    role_key=role_key,
                    emoji=role_info["emoji"],
                    label=f"{role_info['name']} (0/{limit})",
                    limit=limit,
                    team_data=team_data,
                    roles=roles,
                )
                self.add_item(button)

        self.add_item(LeaveButton(team_data, roles))


class RoleButton(discord.ui.Button):
    def __init__(self, role_key: str, emoji: str, label: str, limit: int, team_data: dict, roles: dict):
        super().__init__(style=discord.ButtonStyle.secondary, emoji=emoji, label=label)
        self.role_key = role_key
        self.limit = limit
        self.team_data = team_data
        self.roles = roles

    async def callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        user_name = interaction.user.display_name
        signed = self.team_data["signed"]

        # Remove user from any other role first
        for role, players in signed.items():
            if user_id in [p["id"] for p in players]:
                signed[role] = [p for p in players if p["id"] != user_id]
                break

        current_players = signed.get(self.role_key, [])

        # Toggle off if already in this role
        if user_id in [p["id"] for p in current_players]:
            signed[self.role_key] = [p for p in current_players if p["id"] != user_id]
            self._update_all_buttons(signed)
            await interaction.response.edit_message(
                embed=build_team_embed(self.team_data, self.roles), view=self.view
            )
            return

        # Check limit
        if len(current_players) >= self.limit:
            await interaction.response.send_message(
                f"❌ {self.roles[self.role_key]['name']} is full! ({self.limit}/{self.limit})",
                ephemeral=True,
            )
            return

        # Add player
        if self.role_key not in signed:
            signed[self.role_key] = []
        signed[self.role_key].append({"id": user_id, "name": user_name})

        self._update_all_buttons(signed)
        await interaction.response.edit_message(
            embed=build_team_embed(self.team_data, self.roles), view=self.view
        )

    def _update_all_buttons(self, signed):
        for item in self.view.children:
            if isinstance(item, RoleButton):
                count = len(signed.get(item.role_key, []))
                item.label = f"{self.roles[item.role_key]['name']} ({count}/{item.limit})"
                if count >= item.limit:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary


class LeaveButton(discord.ui.Button):
    def __init__(self, team_data: dict, roles: dict):
        super().__init__(style=discord.ButtonStyle.danger, emoji="🚪", label="Leave")
        self.team_data = team_data
        self.roles = roles

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

        for item in self.view.children:
            if isinstance(item, RoleButton):
                count = len(signed.get(item.role_key, []))
                item.label = f"{self.roles[item.role_key]['name']} ({count}/{item.limit})"
                if count >= item.limit:
                    item.style = discord.ButtonStyle.success
                else:
                    item.style = discord.ButtonStyle.secondary

        await interaction.response.edit_message(
            embed=build_team_embed(self.team_data, self.roles), view=self.view
        )


def build_team_embed(team_data: dict, roles: dict) -> discord.Embed:
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
        if limit <= 0 or role_key not in roles:
            continue
        role_info = roles[role_key]
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

    tank_count = discord.ui.TextInput(label="Tank", placeholder="0", default="1", max_length=2, required=True)
    healer_count = discord.ui.TextInput(label="Healer", placeholder="0", default="1", max_length=2, required=True)
    melee_dps_count = discord.ui.TextInput(label="Melee DPS", placeholder="0", default="2", max_length=2, required=True)
    ranged_dps_count = discord.ui.TextInput(label="Ranged DPS", placeholder="0", default="2", max_length=2, required=True)
    support_count = discord.ui.TextInput(label="Support", placeholder="0", default="1", max_length=2, required=True)

    def __init__(self, team_name: str, content_key: str, guild_id: int, roles: dict, scout_count: int = 0):
        super().__init__()
        self.team_name = team_name
        self.content_key = content_key
        self.guild_id = guild_id
        self.all_roles = roles
        self.scout_count = scout_count

        # Update labels with custom role names
        self.tank_count.label = f"{roles['tank']['emoji']} {roles['tank']['name']}"
        self.healer_count.label = f"{roles['healer']['emoji']} {roles['healer']['name']}"
        self.melee_dps_count.label = f"{roles['dps_melee']['emoji']} {roles['dps_melee']['name']}"
        self.ranged_dps_count.label = f"{roles['dps_ranged']['emoji']} {roles['dps_ranged']['name']}"
        self.support_count.label = f"{roles['support']['emoji']} {roles['support']['name']}"

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

        # Add custom roles with 0 default
        for role_key in self.all_roles:
            if role_key not in composition:
                composition[role_key] = 0

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

        embed = build_team_embed(team_data, self.all_roles)
        view = TeamBuilderView(team_data, self.all_roles)
        await interaction.response.send_message(embed=embed, view=view)


class TeamBuilder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Role Management Commands ---

    role_mgmt = app_commands.Group(name="role", description="Manage custom roles/weapons")

    @role_mgmt.command(name="add", description="➕ Add or edit a custom role/weapon")
    @app_commands.describe(
        key="Unique key for this role (lowercase, no spaces, e.g. battlemount)",
        name="Display name (e.g. Battlemount, Locus, Grailseeker)",
        emoji="Emoji for this role (e.g. 🐎, 🔥, ❄️)",
        description="Optional description",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def role_add(self, interaction: discord.Interaction, key: str, name: str, emoji: str, description: str = ""):
        key = key.lower().replace(" ", "_")
        await db.add_custom_role(interaction.guild_id, key, name, emoji, description)

        embed = discord.Embed(
            title="✅ Role Added!",
            description=f"{emoji} **{name}** (`{key}`)\n{description}",
            color=discord.Color.green(),
        )
        embed.set_footer(text="This role will now appear in /createteam")
        await interaction.response.send_message(embed=embed)

    @role_mgmt.command(name="remove", description="➖ Remove a custom role")
    @app_commands.describe(key="The role key to remove")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def role_remove(self, interaction: discord.Interaction, key: str):
        key = key.lower().replace(" ", "_")
        if key in DEFAULT_ROLES:
            await interaction.response.send_message("❌ Can't remove default roles! You can rename them with `/role add` using the same key.", ephemeral=True)
            return
        await db.remove_custom_role(interaction.guild_id, key)
        await interaction.response.send_message(f"🗑️ Role `{key}` removed!")

    @role_mgmt.command(name="list", description="📋 Show all available roles")
    async def role_list(self, interaction: discord.Interaction):
        roles = await get_guild_roles(interaction.guild_id)

        embed = discord.Embed(title="📋 Available Roles", color=discord.Color.blue())

        default_text = ""
        custom_text = ""

        for key, info in roles.items():
            line = f"{info['emoji']} **{info['name']}** (`{key}`)"
            if info.get("description"):
                line += f"\n  ↳ {info['description']}"
            if key in DEFAULT_ROLES:
                # Check if it was customized
                custom_roles = await db.get_custom_roles(interaction.guild_id)
                customized = any(r["role_key"] == key for r in custom_roles)
                if customized:
                    line += " ✏️"
                default_text += line + "\n"
            else:
                custom_text += line + "\n"

        embed.add_field(name="Default Roles", value=default_text or "None", inline=False)
        if custom_text:
            embed.add_field(name="Custom Roles", value=custom_text, inline=False)

        embed.set_footer(text="✏️ = customized | Use /role add to add/edit, /role remove to delete")
        await interaction.response.send_message(embed=embed)

    # --- Team Commands ---

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
        roles = await get_guild_roles(interaction.guild_id)
        modal = CompositionModal(
            team_name=name,
            content_key=content,
            guild_id=interaction.guild_id,
            roles=roles,
            scout_count=scout or 0,
        )
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
        roles = await get_guild_roles(interaction.guild_id)

        team_data = {
            "name": name,
            "event_type": preset["name"],
            "composition": preset["default"].copy(),
            "signed": {},
            "max_players": preset["max_players"],
            "created_by": interaction.user.id,
        }

        embed = build_team_embed(team_data, roles)
        view = TeamBuilderView(team_data, roles)
        await interaction.response.send_message(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(TeamBuilder(bot))
