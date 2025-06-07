import logging
import discord
from discord.ext import commands
from datetime import datetime
from database import DatabaseManager

logger = logging.getLogger(__name__)

class GreetingsCommand(commands.Cog):
    def __init__(self, bot, db_manager: DatabaseManager):
        self.bot = bot
        self.db_manager = db_manager
    
    @discord.app_commands.command(name="greetings", description="Show all users who have greeted today")
    async def greetings(self, interaction: discord.Interaction):
        try:
            today = datetime.now().date()
            greetings_data = self.db_manager.get_daily_greetings(today)
            
            if not greetings_data:
                embed = discord.Embed(
                    title="Daily Greetings 👋",
                    description="No greetings recorded for today yet!",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"Date: {today}")
                await interaction.response.send_message(embed=embed)
                return
            
            greeting_count = len(greetings_data)
            unique_users = len(set(g['user_id'] for g in greetings_data))
            
            embed = discord.Embed(
                title="Daily Greetings 👋",
                description=f"**{greeting_count}** greetings from **{unique_users}** unique users today!",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            
            greeting_list = []
            for greeting in greetings_data[:20]:  # Limit to first 20 to avoid embed limits
                # Convert timedelta to time string (MariaDB TIME columns return as timedelta)
                td = greeting['greeting_time']
                hours, remainder = divmod(td.total_seconds(), 3600)
                minutes, _ = divmod(remainder, 60)
                time_str = f"{int(hours):02d}:{int(minutes):02d}"
                greeting_text = greeting['greeting_message'][:30] + "..." if len(greeting['greeting_message']) > 30 else greeting['greeting_message']
                greeting_list.append(f"**{greeting['username']}** at {time_str}: {greeting_text}")
            
            if greeting_list:
                embed.add_field(
                    name="Recent Greetings:",
                    value="\n".join(greeting_list),
                    inline=False
                )
            
            if len(greetings_data) > 20:
                embed.add_field(
                    name="Note:",
                    value=f"Showing first 20 of {len(greetings_data)} total greetings",
                    inline=False
                )
            
            embed.set_footer(text=f"Date: {today}")
            
            await interaction.response.send_message(embed=embed)
            logger.info(f"Greetings command executed by {interaction.user.display_name}")
            
        except Exception as e:
            logger.error(f"Error in greetings command: {e}")
            await interaction.response.send_message(
                "Sorry, there was an error retrieving the greetings data.", 
                ephemeral=True
            )

async def setup(bot, db_manager):
    await bot.add_cog(GreetingsCommand(bot, db_manager))