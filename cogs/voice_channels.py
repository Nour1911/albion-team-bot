import asyncio
from typing import Dict, Optional
import discord
from discord import app_commands
from discord.ext import commands
import database as db


class VoiceChannels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_channels: Dict[int, int] = {}   # user_id -> channel_id
        self.delete_tasks: Dict[int, asyncio.Task] = {}

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        guild_id = member.guild.id
        creation_channel_id = await db.get_voice_creation_channel(guild_id)
        if not creation_channel_id:
            return

        # User joined or moved to the creation channel
        if after.channel and after.channel.id == creation_channel_id:
            await self._create_channel_for(member)
            return

        # User left a channel — check if it needs cleanup
        if before.channel and before.channel.id != creation_channel_id:
            await self._schedule_cleanup(before.channel)

    async def _create_channel_for(self, member: discord.Member):
        # If they already have a channel, move them there
        if member.id in self.user_channels:
            existing = member.guild.get_channel(self.user_channels[member.id])
            if existing:
                try:
                    await member.move_to(existing)
                except discord.HTTPException:
                    pass
                return
            else:
                del self.user_channels[member.id]

        creation_ch_id = await db.get_voice_creation_channel(member.guild.id)
        creation_ch = member.guild.get_channel(creation_ch_id)
        category = creation_ch.category if creation_ch else None

        try:
            channel = await member.guild.create_voice_channel(
                name=f"🔊 {member.display_name}",
                category=category,
            )
            self.user_channels[member.id] = channel.id
            await member.move_to(channel)
        except discord.HTTPException as e:
            print(f"[VoiceChannels] Failed to create channel for {member}: {e}")

    async def _schedule_cleanup(self, channel: discord.VoiceChannel):
        if channel.id not in self.user_channels.values():
            return

        existing_task = self.delete_tasks.get(channel.id)
        if existing_task:
            existing_task.cancel()

        task = asyncio.create_task(self._delete_if_empty(channel, delay=10))
        self.delete_tasks[channel.id] = task

    async def _delete_if_empty(self, channel: discord.VoiceChannel, delay: int):
        await asyncio.sleep(delay)
        try:
            updated = channel.guild.get_channel(channel.id)
            if updated and len(updated.members) == 0:
                await updated.delete()
                for uid, cid in list(self.user_channels.items()):
                    if cid == channel.id:
                        del self.user_channels[uid]
                        break
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            print(f"[VoiceChannels] Failed to delete {channel.name}: {e}")
        finally:
            self.delete_tasks.pop(channel.id, None)

    @app_commands.command(name="setup_voice", description="🔊 Set the voice channel that creates personal rooms on join")
    @app_commands.describe(channel="Voice channel users join to get their own personal channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_voice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        await db.set_voice_creation_channel(interaction.guild_id, channel.id)
        embed = discord.Embed(
            title="✅ Voice Setup Done!",
            description=(
                f"**Creation channel:** {channel.mention}\n\n"
                "When any member joins this channel:\n"
                "🔊 A personal voice channel is created with their name\n"
                "🚀 They are moved to it automatically\n"
                "🗑️ It is deleted 10 seconds after they leave"
            ),
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="voice_status", description="🔊 Show current voice channel setup")
    async def voice_status(self, interaction: discord.Interaction):
        ch_id = await db.get_voice_creation_channel(interaction.guild_id)
        if not ch_id:
            await interaction.response.send_message(
                "❌ No voice creation channel set. Use `/setup_voice` first.", ephemeral=True
            )
            return

        ch = interaction.guild.get_channel(ch_id)
        ch_mention = ch.mention if ch else f"(deleted — id {ch_id})"

        embed = discord.Embed(title="🔊 Voice Channel Status", color=discord.Color.blue())
        embed.add_field(name="Creation Channel", value=ch_mention, inline=False)
        embed.add_field(name="Active Personal Channels", value=str(len(self.user_channels)), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(VoiceChannels(bot))
