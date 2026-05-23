import discord
from discord import app_commands
from discord.ext import commands
import database as db

COMP = {
    "main_tank": {
        "label": "Main Tank",
        "emoji": "🛡️",
        "build": "Hammer | Mist Walker Hood | Armor of Valor | Hunter Shoes | Bridge Watch Cape | Cabbage Soup",
        "swap":  "Incubus | Assassin Hood | Mist Caller | Mist Walker Jacket | Astral Aegis",
        "note":  "Maps / Melee  •  🐎 T8 Horse",
    },
    "off_tank": {
        "label": "Off Tank",
        "emoji": "⚔️",
        "build": "Incubus | Druid Cowl | Royal Armor | Cultist Sandal | Mist Caller | Lym Hurst | Pork Omelet",
        "swap":  "Enigmatic / Specter Hood / Guardian Armor",
        "note":  "Treasures / Artifact  •  🐗 T8 Boar",
    },
    "healer": {
        "label": "Healer",
        "emoji": "💚",
        "build": "Iron Root | Specter Hood | Royal Jacket | Shoes Sprint | Mist Caller | Lym Hurst Cape | Pork Omelet",
        "swap":  "Fallen (Cape - Bag)",
        "note":  "🐎 T8 Horse",
    },
    "shadow_support": {
        "label": "Shadow Support",
        "emoji": "🌑",
        "build": "Shadow Caller | Specter Hood | Royal Jacket | Shoes Sprint | Mist Caller | Demon Cape | Pork Omelet",
        "swap":  "",
        "note":  "",
    },
    "looter": {
        "label": "Looter",
        "emoji": "💰",
        "build": "Frost Staff | Stalker Hood | Guardian Armor | Shoes Sprint | Fort Sterling Cape",
        "swap":  "Enigmatic | Rooter Caller | Astral Aegis | Specter Hood | Guardian Helmet",
        "note":  "AVA Energy / Books / T6 Runes / Relics T5+ / Souls T6 / Shards T6+  •  🐗 T8 Boar",
    },
    "reaper_1": {
        "label": "Reaper 1",
        "emoji": "☠️",
        "build": "Assassin Hood | Druid Robe | Stalker Shoes | Lym Cape",
        "swap":  "Druid Cowl",
        "note":  "Loot: Armor",
    },
    "reaper_2": {
        "label": "Reaper 2",
        "emoji": "☠️",
        "build": "Assassin Hood | Druid Robe | Stalker Shoes | Lym Cape",
        "swap":  "Druid Cowl",
        "note":  "Loot: Shoes",
    },
    "reaper_3": {
        "label": "Reaper 3",
        "emoji": "☠️",
        "build": "Assassin Hood | Druid Robe | Stalker Shoes | Lym Cape",
        "swap":  "Stalker Hood",
        "note":  "Loot: Helmet",
    },
    "reaper_4": {
        "label": "Reaper 4",
        "emoji": "☠️",
        "build": "Assassin Hood | Druid Robe | Stalker Shoes | Lym Cape",
        "swap":  "Cultist Cowl",
        "note":  "Loot: Ranged",
    },
    "reaper_5": {
        "label": "Reaper 5",
        "emoji": "☠️",
        "build": "Assassin Hood | Druid Robe | Stalker Shoes | Lym Cape",
        "swap":  "Mage Cowl",
        "note":  "Loot: Melee",
    },
}


def _build_embed(title: str, signups: dict) -> discord.Embed:
    total = sum(len(v) for v in signups.values())
    embed = discord.Embed(title=f"⚔️  {title}", color=0xC8AA6E)
    embed.set_footer(text=f"👥 {total} signed up  •  Click your role to register  •  Click again to cancel")

    for key, info in COMP.items():
        registered = signups.get(key, [])
        names = "  •  ".join(n for _, n in registered) if registered else "—"

        lines = [f"`{info['build']}`"]
        if info["swap"]:
            lines.append(f"🔄  `{info['swap']}`")
        if info["note"]:
            lines.append(f"📌  {info['note']}")
        lines.append(f"👥  **{names}**")

        embed.add_field(
            name=f"{info['emoji']}  {info['label']}",
            value="\n".join(lines),
            inline=False,
        )

    return embed


class RoleButton(discord.ui.Button):
    def __init__(self, role_key: str, info: dict, row: int, style: discord.ButtonStyle):
        super().__init__(
            label=info["label"],
            emoji=info["emoji"],
            style=style,
            custom_id=f"comp_btn_{role_key}",
            row=row,
        )
        self.role_key = role_key

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        msg_id  = interaction.message.id
        user_id = interaction.user.id
        name    = interaction.user.display_name

        try:
            current = await db.get_comp_signup_role(msg_id, user_id)

            if current == self.role_key:
                await db.remove_comp_signup(msg_id, user_id)
            else:
                await db.set_comp_signup(msg_id, self.role_key, user_id, name)

            post    = await db.get_comp_post(msg_id)
            title   = post["title"] if post else "AVA Comp"
            signups = await db.get_comp_signups(msg_id)
            await interaction.message.edit(
                embed=_build_embed(title, signups),
                view=_build_view(signups),
            )
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


class PingSignupsButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ping Signed Up",
            emoji="📣",
            style=discord.ButtonStyle.primary,
            custom_id="comp_ping_signups",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer()
        msg_id  = interaction.message.id
        signups = await db.get_comp_signups(msg_id)

        seen = set()
        all_ids = []
        for users in signups.values():
            for uid, _ in users:
                if uid not in seen:
                    seen.add(uid)
                    all_ids.append(uid)

        if not all_ids:
            await interaction.followup.send("No one signed up yet.", ephemeral=True)
            return

        post     = await db.get_comp_post(msg_id)
        title    = post["title"] if post else "AVA Comp"
        mentions = " ".join(f"<@{uid}>" for uid in all_ids)
        await interaction.followup.send(f"⚔️ **{title}** — Everyone report!\n{mentions}")


class PingPveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Ping @PVE",
            emoji="📢",
            style=discord.ButtonStyle.primary,
            custom_id="comp_ping_pve",
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admins only!", ephemeral=True)
            return

        await interaction.response.defer()
        pve_role = discord.utils.get(interaction.guild.roles, name="PVE")
        if not pve_role:
            await interaction.followup.send(
                "❌ No role named **PVE** found in this server.", ephemeral=True
            )
            return

        post  = await db.get_comp_post(interaction.message.id)
        title = post["title"] if post else "AVA Comp"
        await interaction.followup.send(
            f"⚔️ **{title}** — Sign-up is open! {pve_role.mention}"
        )


def _build_view(signups: dict) -> discord.ui.View:
    view = discord.ui.View(timeout=None)

    for i, (key, info) in enumerate(COMP.items()):
        style = discord.ButtonStyle.success if signups.get(key) else discord.ButtonStyle.secondary
        view.add_item(RoleButton(key, info, row=i // 5, style=style))

    view.add_item(PingSignupsButton())
    view.add_item(PingPveButton())
    return view


class CompPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(_build_view({}))

    @app_commands.command(name="postcomp", description="⚔️ Post the AVA comp sign-up sheet")
    @app_commands.describe(title="Event title  e.g.  AVA Friday Night")
    async def postcomp(self, interaction: discord.Interaction, title: str = "AVA Comp"):
        await interaction.response.defer()
        try:
            embed = _build_embed(title, {})
            msg   = await interaction.followup.send(embed=embed, view=_build_view({}))
            await db.create_comp_post(msg.id, interaction.channel_id, title)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(CompPost(bot))
