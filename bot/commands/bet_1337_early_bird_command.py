"""
Discord command for placing /1337-early-bird bets with timestamps.
Part of the 1337 betting game system.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from config import Config
from game_service_client import GameServiceAdapter

logger = logging.getLogger(__name__)


class Bet1337EarlyBirdCommand(commands.Cog):
    """Discord command handler for /1337-early-bird betting"""
    
    def __init__(self, bot, game_service: GameServiceAdapter):
        self.bot = bot
        self.game_service = game_service

    async def _announce_general_bet(self, user, play_time):
        """Announce when a General places a bet"""
        message = f"🎖️ **The General has placed their bet at {self.game_service.format_time_with_ms(play_time)}!** 🎖️"

        for guild in self.bot.guilds:
            if guild.get_member(user.id):
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        break

    @discord.app_commands.command(name="1337-early-bird", description="Place an early bird bet with a specific timestamp")
    async def bet_1337_early_bird(self, interaction: discord.Interaction, timestamp: str):
        """Handle early bird bet placement"""
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting early bird bet with timestamp: '{timestamp}'")
            
            # Validate bet placement
            bet_validation = await self.game_service.validate_bet_placement(interaction.user.id)
            if not bet_validation['valid']:
                await interaction.response.send_message(bet_validation['message'], ephemeral=True)
                return

            # Validate timestamp
            timestamp_validation = await self.game_service.validate_early_bird_timestamp(timestamp)
            if not timestamp_validation['valid']:
                await interaction.response.send_message(timestamp_validation['message'], ephemeral=True)
                return

            play_time = timestamp_validation['timestamp']
            
            # Save the bet
            success = await self.game_service.save_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                'early_bird',
                interaction.guild_id,
                interaction.channel_id
            )

            if success:
                # Check if user is General and announce
                if Config.GENERAL_ROLE_ID:
                    general_role = interaction.guild.get_role(Config.GENERAL_ROLE_ID)
                    if general_role and general_role in interaction.user.roles:
                        await self._announce_general_bet(interaction.user, play_time)

                await interaction.response.send_message(
                    f"✅ **Early bird bet scheduled!** Your time: {self.game_service.format_time_with_ms(play_time)}\nGood luck! 🍀",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ **Error placing bet.** Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in 1337-early-bird command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )


async def setup(bot, game_service):
    """Setup function for the cog"""
    await bot.add_cog(Bet1337EarlyBirdCommand(bot, game_service))