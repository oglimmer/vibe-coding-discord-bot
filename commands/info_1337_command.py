"""
Discord command handling for the 1337 info functionality.
Shows user's current bet information for today.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from database import DatabaseManager
from game.game_1337_logic import Game1337Logic

logger = logging.getLogger(__name__)


class Info1337Command(commands.Cog):
    """Discord command handler for the 1337 info functionality"""
    
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.game_logic = Game1337Logic(db_manager)

    @discord.app_commands.command(name="1337-info", description="Show your current bet information for today")
    async def info_1337(self, interaction: discord.Interaction):
        """Show user's bet information"""
        try:
            user_bet = self.game_logic.get_user_bet_info(interaction.user.id)

            if not user_bet:
                await interaction.response.send_message(
                    "❌ **No bet placed today!** Use `/1337` or `/1337-early-bird` to place a bet.",
                    ephemeral=True
                )
                return

            embed = self._create_user_info_embed(user_bet)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in 1337-info command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    def _create_user_info_embed(self, user_bet):
        """Create user bet info embed"""
        embed_data = self.game_logic.create_user_info_embed_data(user_bet)
        
        embed = discord.Embed(
            title=embed_data['title'],
            color=embed_data['color'],
            timestamp=datetime.now()
        )

        for field in embed_data['fields']:
            embed.add_field(
                name=field['name'],
                value=field['value'],
                inline=field['inline']
            )

        return embed


async def setup(bot, db_manager):
    """Setup function for the cog"""
    await bot.add_cog(Info1337Command(bot, db_manager))