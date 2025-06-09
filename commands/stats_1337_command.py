"""
Discord command handling for the 1337 statistics functionality.
Shows game statistics with interactive pagination.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from database import DatabaseManager
from game.game_1337_logic import Game1337Logic

logger = logging.getLogger(__name__)


class Stats1337Command(commands.Cog):
    """Discord command handler for the 1337 statistics functionality"""
    
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
        self.game_logic = Game1337Logic(db_manager)

    @discord.app_commands.command(name="1337-stats", description="Show 1337 game statistics")
    async def stats_1337(self, interaction: discord.Interaction):
        """Show game statistics"""
        try:
            view = StatsView(self.game_logic)
            embed = await view.get_page_embed(0)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in 1337-stats command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )


class StatsView(discord.ui.View):
    """Discord UI for statistics display"""
    
    def __init__(self, game_logic: Game1337Logic):
        super().__init__(timeout=300)
        self.game_logic = game_logic
        self.current_page = 0
        self.pages = ["365 Days", "14 Days", "Daily Bets"]

    async def get_page_embed(self, page: int):
        """Get embed for specific page"""
        embed_data = self.game_logic.get_stats_page_data(page)
        
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
        
        embed.set_footer(text=embed_data['footer_text'])
        return embed

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.gray)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle previous page button"""
        self.current_page = (self.current_page - 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.gray)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle next page button"""
        self.current_page = (self.current_page + 1) % len(self.pages)
        embed = await self.get_page_embed(self.current_page)
        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot, db_manager):
    """Setup function for the cog"""
    await bot.add_cog(Stats1337Command(bot, db_manager))