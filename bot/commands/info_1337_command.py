"""
Discord command handling for the 1337 info functionality.
Shows user's current bet information for today.
"""

import logging
import discord
from discord.ext import commands
from datetime import datetime
from game_service_client import GameServiceAdapter

logger = logging.getLogger(__name__)


class Info1337Command(commands.Cog):
    """Discord command handler for the 1337 info functionality"""
    
    def __init__(self, bot, game_service: GameServiceAdapter):
        self.bot = bot
        self.game_service = game_service

    @discord.app_commands.command(name="1337-info", description="Show information about today's 1337 game")
    async def info_1337(self, interaction: discord.Interaction):
        """Show user's bet information and game status"""
        try:
            game_date = self.game_service.get_game_date()
            user_bet = await self.game_service.get_user_bet_info(interaction.user.id)
            game_passed = False  # Will be determined by service
            
            if game_passed:
                # AFTER WIN_TIME: Show game results and user performance
                embed = await self._create_post_game_embed(user_bet, game_date)
            else:
                # BEFORE WIN_TIME: Show user bet or prompt to bet
                embed = await self._create_pre_game_embed(user_bet)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in 1337-info command: {e}")
            await interaction.response.send_message(
                "❌ **Something went wrong.** Please try again later.",
                ephemeral=True
            )

    async def _create_pre_game_embed(self, user_bet):
        """Create embed for before game time (before WIN_TIME)"""
        embed = discord.Embed(
            title='🎯 1337 Game Info',
            color=0x1337FF,
            timestamp=datetime.now()
        )
        
        if user_bet:
            # User has placed a bet - show bet details
            bet_type_emoji = "🐦" if user_bet['bet_type'] == 'early_bird' else "⚡"
            
            embed.add_field(
                name='Your Bet',
                value=f"{bet_type_emoji} **{user_bet['bet_type'].replace('_', ' ').title()}**",
                inline=True
            )
            
            embed.add_field(
                name='Your Time',
                value=f"`{self.game_service.format_time_with_ms(user_bet['play_time'])}`",
                inline=True
            )
            
            embed.add_field(
                name='Status',
                value='✅ **Bet placed!** Good luck!',
                inline=False
            )
        else:
            # User has not placed a bet - prompt to bet
            embed.add_field(
                name='Status',
                value='❌ **No bet placed yet!**',
                inline=False
            )
            
            embed.add_field(
                name='How to Bet',
                value='Use `/1337` for regular bet or `/1337-early-bird` for scheduled bet',
                inline=False
            )
        
        start_time = await self.game_service.get_game_start_time()
        embed.set_footer(text=f'Game starts at {start_time} - Place your bets!')
        return embed
    
    async def _create_post_game_embed(self, user_bet, game_date):
        """Create embed for after game time (after WIN_TIME)"""
        embed = discord.Embed(
            title='🔚 Today\'s 1337 Game Has Ended',
            color=0x1337FF,
            timestamp=datetime.now()
        )
        
        # Get game information  
        winner = await self.game_service.get_daily_winner(game_date)
        daily_bets = await self.game_service.get_daily_bets(game_date)
        num_players = len(daily_bets)
        
        if winner:
            win_time = winner['win_time']
            
            # Clear game status
            embed.add_field(
                name='📅 Game Status',
                value='✅ **Game completed for today**',
                inline=False
            )
            
            # Win time and winner info
            embed.add_field(
                name='🎯 Win Time',
                value=f"`{self.game_service.format_time_with_ms(win_time)}`",
                inline=True
            )
            
            embed.add_field(
                name='🏆 Winner',
                value=f"**{winner['username']}**",
                inline=True
            )
            
            embed.add_field(
                name='👥 Total Players',
                value=f"**{num_players}**",
                inline=True
            )
            
            # User-specific information
            if user_bet:
                # User placed a bet - show their performance
                millisecond_diff = self.game_service.calculate_millisecond_difference(
                    user_bet['play_time'], win_time
                )
                
                bet_type_emoji = "🐦" if user_bet['bet_type'] == 'early_bird' else "⚡"
                
                # Check if user won first to determine color
                user_won = winner['user_id'] == user_bet['user_id']
                
                embed.add_field(
                    name='📊 Your Performance',
                    value=f"{bet_type_emoji} **Your bet:** `{self.game_service.format_time_with_ms(user_bet['play_time'])}`\n"
                          f"⏱️ **Distance from win:** `{abs(millisecond_diff)}ms` {'before' if millisecond_diff > 0 else 'after'}",
                    inline=False
                )
                
                if user_won:
                    embed.add_field(
                        name='🎉 Result',
                        value='**🏆 YOU WON TODAY\'S GAME! 🏆**\nCongratulations!',
                        inline=False
                    )
                    embed.color = 0x00FF00  # Green for winner
                else:
                    embed.add_field(
                        name='💔 Result',
                        value='**You didn\'t win this time.**\nBetter luck tomorrow!',
                        inline=False
                    )
                    embed.color = 0xFF6B6B  # Red for non-winner
            else:
                # User didn't place a bet
                embed.add_field(
                    name='❌ Your Status',
                    value='**You didn\'t participate in today\'s game.**\nDon\'t miss tomorrow\'s chance!',
                    inline=False
                )
                embed.color = 0x888888  # Gray for non-participant
        else:
            # No winner yet or catastrophic event
            embed.add_field(
                name='⏳ Status',
                value='**Game ended but results are still being calculated...**\nCheck back in a moment!',
                inline=False
            )
            embed.color = 0xFFAA00  # Orange for pending
        
        start_time = await self.game_service.get_game_start_time()
        embed.set_footer(text=f'Next game starts tomorrow at {start_time}!')
        return embed


async def setup(bot, game_service):
    """Setup function for the cog"""
    await bot.add_cog(Info1337Command(bot, game_service))