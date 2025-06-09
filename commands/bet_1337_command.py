"""
Discord command for placing regular /1337 bets.
Part of the 1337 betting game system.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from config import Config
from database import DatabaseManager
from game.game_1337_logic import Game1337Logic

logger = logging.getLogger(__name__)


class Bet1337Command(commands.Cog):
    """Discord command handler for regular /1337 betting"""
    
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.game_logic = Game1337Logic(db_manager)

    async def _announce_general_bet(self, user, play_time):
        """Announce when a General places a bet"""
        message = f"🎖️ **The General has placed their bet at {self.game_logic.format_time_with_ms(play_time)}!** 🎖️"

        for guild in self.bot.guilds:
            if guild.get_member(user.id):
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(message)
                        break

    @discord.app_commands.command(name="1337", description="Place a regular bet for today's 1337 game")
    async def bet_1337(self, interaction: discord.Interaction):
        """Handle regular bet placement"""
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) attempting regular bet")
            
            # Validate bet placement
            validation = self.game_logic.validate_bet_placement(interaction.user.id)
            if not validation['valid']:
                await interaction.response.send_message(validation['message'], ephemeral=True)
                return

            # Place the bet
            play_time = datetime.now()
            logger.debug(f"Current time: {self.game_logic.format_time_with_ms(play_time)}")

            success = self.game_logic.save_bet(
                interaction.user.id,
                interaction.user.display_name,
                play_time,
                'regular',
                interaction.guild_id,
                interaction.channel_id
            )

            if success:
                logger.info(f"Regular bet saved successfully for {interaction.user.display_name} at {self.game_logic.format_time_with_ms(play_time)}")

                # Check if user is General and announce
                if Config.GENERAL_ROLE_ID:
                    general_role = interaction.guild.get_role(Config.GENERAL_ROLE_ID)
                    if general_role and general_role in interaction.user.roles:
                        logger.debug(f"User is General, announcing bet")
                        await self._announce_general_bet(interaction.user, play_time)

                await interaction.response.send_message(
                    f"✅ **Bet placed!** Your time: {self.game_logic.format_time_with_ms(play_time)}\nGood luck! 🍀",
                    ephemeral=True
                )
            else:
                logger.error(f"Failed to save regular bet for {interaction.user.display_name}")
                await interaction.response.send_message(
                    "❌ **Error placing bet.** Please try again later.",
                    ephemeral=True
                )

        except Exception as e:
            logger.error(f"Error in 1337 command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )


async def setup(bot, db_manager):
    """Setup function for the cog"""
    await bot.add_cog(Bet1337Command(bot, db_manager))