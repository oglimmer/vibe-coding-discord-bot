"""
Discord command for displaying 1337 game rules.
Shows comprehensive game rules and mechanics in a formatted embed.
"""

import logging
import discord
from discord.ext import commands
from config import Config

logger = logging.getLogger(__name__)


class Rules1337Command(commands.Cog):
    """Discord command handler for the 1337 rules display"""
    
    def __init__(self, bot, game_service):
        self.bot = bot
        self.game_service = game_service

    @discord.app_commands.command(name="1337-rules", description="Display the complete 1337 game rules and mechanics")
    async def rules_1337(self, interaction: discord.Interaction):
        """Display comprehensive game rules"""
        try:
            logger.debug(f"User {interaction.user.display_name} (ID: {interaction.user.id}) requested 1337 rules")
            
            embed = self._create_rules_embed()
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
        except Exception as e:
            logger.error(f"Error in 1337-rules command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    def _create_rules_embed(self) -> discord.Embed:
        """Create the rules embed with comprehensive game information"""
        embed = discord.Embed(
            title='🎯 1337 Game Rules & Mechanics',
            description='Complete guide to the daily precision timing competition',
            color=0x1337FF
        )

        # Game Overview
        embed.add_field(
            name='📋 Game Overview',
            value='Daily precision timing competition where players attempt to place bets as close as possible to a randomly generated "win time" at 13:37 each day.',
            inline=False
        )

        # Game Schedule
        embed.add_field(
            name='⏰ Game Schedule',
            value=f'• **Daily Game Time**: 13:37:00.000 (1:37 PM)\n'
                  f'• **Win Time Window**: Randomly generated between 13:37:00.000 and 13:38:00.000\n'
                  f'• **Frequency**: One game per day\n'
                  f'• **Winner Determination**: Automatic at exact win time with millisecond precision',
            inline=False
        )

        # Betting Mechanics
        embed.add_field(
            name='🎲 Betting Mechanics',
            value='**Regular Bet** (`/1337`): Place a bet at the current moment\n'
                  '**Early Bird Bet** (`/1337-early-bird`): Schedule a bet for a specific timestamp\n\n'
                  '**Rules**:\n'
                  '• One bet per day per player\n'
                  '• No late bets (after win time)\n'
                  '• No future bets for early bird\n'
                  '• Millisecond precision tracking',
            inline=False
        )

        # Winner Determination
        embed.add_field(
            name='🏆 Winner Determination',
            value='1. **Find Closest Bets**: Find closest regular and early_bird bets to win time\n'
                  '2. **Regular Priority**: If regular bet is closer, it wins\n'
                  '3. **Early Bird Penalty**: Early bird only wins if >3 seconds apart from closest regular\n'
                  '4. **Tie Breaking**: If equally close, regular bet wins',
            inline=False
        )

        # 3-Second Penalty
        embed.add_field(
            name='⚠️ 3-Second Penalty for Early Bird',
            value='Early bird bets can only win if they are more than 3 seconds apart from the closest regular bet.\n\n'
                  '**Example**: \n'
                  '• Early bird at 13:37:25, Regular at 13:37:28, Win time at 13:37:30\n'
                  '• Regular is closer (2s vs 5s from win time)\n'
                  '• **Result**: Regular bet wins (closer to win time)\n'
                  '\n'
                  '**Example with Penalty**:\n'
                  '• Early bird at 13:37:28, Regular at 13:37:25, Win time at 13:37:30\n'
                  '• Early bird is closer (2s vs 5s from win time), but only 3s apart from regular\n'
                  '• **Result**: Regular bet wins (early bird closer but within 3s of regular)\n',
            inline=False
        )

        # Role System
        embed.add_field(
            name='🎖️ Role System',
            value='**Sergeant**: Daily winner\n'
                  '**Commander**: Most wins in last 14 days\n'
                  '**General**: Most wins in last 365 days\n\n'
                  'Roles are automatically assigned and provide special privileges.',
            inline=False
        )

        # Commands
        embed.add_field(
            name='⌨️ Available Commands',
            value='• `/1337` - Place a regular bet\n'
                  '• `/1337-early-bird <timestamp>` - Place a scheduled bet\n'
                  '• `/1337-info` - View today\'s game information\n'
                  '• `/1337-stats` - View game statistics\n'
                  '• `/1337-rules` - Display these rules',
            inline=False
        )

        # Strategy Tips
        embed.add_field(
            name='💡 Strategy Tips',
            value='• **Early Bird Advantage**: Schedule bets in advance for consistent timing\n'
                  '• **Real-time Precision**: Use regular bets for last-minute adjustments\n'
                  '• **Risk Management**: Balance early timing with avoiding the 3-second penalty\n'
                  '• **Role Strategy**: Aim for consistent wins to earn Discord roles',
            inline=False
        )

        # Technical Details
        embed.add_field(
            name='🔧 Technical Details',
            value='• **Precision**: Millisecond accuracy throughout\n'
                  '• **Randomization**: Cryptographically secure win time generation\n'
                  '• **Reliability**: Automatic scheduling and error recovery\n'
                  '• **Fair Play**: Server-based timing, no client manipulation',
            inline=False
        )

        embed.set_footer(text="The 1337 game combines precision timing, strategic planning, and community competition!")

        return embed


async def setup(bot, game_service):
    """Setup function for the cog"""
    await bot.add_cog(Rules1337Command(bot, game_service)) 