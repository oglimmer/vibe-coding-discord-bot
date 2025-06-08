"""
Greetings command cog for the Discord bot.
"""
import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from typing import Optional
import pytz

from bot.config import Config
from utils.logger import setup_logger

logger = setup_logger('greetings')

class GreetingsCog(commands.Cog):
    """Cog for greeting-related commands."""
    
    def __init__(self, bot):
        self.bot = bot
        # Deutsche Zeitzone für lokale Anzeige
        timezone_name = Config.TIMEZONE
        self.local_timezone = pytz.timezone(timezone_name)
    
    def utc_to_local(self, utc_time: datetime) -> datetime:
        """
        Convert UTC datetime to local time (German timezone).
        
        Args:
            utc_time: UTC datetime object
            
        Returns:
            datetime object in local timezone
        """
        if utc_time.tzinfo is None:
            # Assume UTC if no timezone info
            utc_time = utc_time.replace(tzinfo=timezone.utc)
        elif utc_time.tzinfo != timezone.utc:
            # Convert to UTC first if it's in a different timezone
            utc_time = utc_time.astimezone(timezone.utc)
        
        # Convert to local timezone
        return utc_time.astimezone(self.local_timezone)
    
    def format_time(self, utc_time: datetime) -> str:
        """
        Format UTC time as local time string.
        
        Args:
            utc_time: UTC datetime object
            
        Returns:
            Formatted time string in local timezone
        """
        local_time = self.utc_to_local(utc_time)
        return local_time.strftime("%H:%M")
        
    @app_commands.command(
        name="greetings",
        description="Show users who have greeted today"
    )
    async def greetings_command(
        self, 
        interaction: discord.Interaction
    ):
        """
        Display users who have greeted today.
        
        Args:
            interaction: Discord interaction object
        """
        await interaction.response.defer()
        
        try:
            # Get today's greetings
            guild_id = interaction.guild.id if interaction.guild else None
            greetings = await self.bot.db_manager.get_todays_greetings(guild_id)
            
            # Create embed
            embed = discord.Embed(
                title="Today's Greetings 👋",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            if not greetings:
                embed.description = "No one has greeted today yet! Be the first to say good morning! 🌅"
                embed.color = discord.Color.orange()
            else:
                # Group greetings by user and count them
                user_greeting_counts = {}
                user_latest_time = {}
                
                for greeting in greetings:
                    username = greeting.username
                    if username not in user_greeting_counts:
                        user_greeting_counts[username] = 0
                        user_latest_time[username] = greeting.greeting_time
                    
                    user_greeting_counts[username] += 1
                    # Keep track of latest greeting time for each user
                    if greeting.greeting_time > user_latest_time[username]:
                        user_latest_time[username] = greeting.greeting_time
                
                # Sort users by greeting count (descending)
                sorted_users = sorted(user_greeting_counts.items(), key=lambda x: x[1], reverse=True)
                
                # Create list showing users and their greeting counts
                greeting_list = []
                for i, (username, count) in enumerate(sorted_users, 1):
                    latest_time = self.format_time(user_latest_time[username])
                    if count == 1:
                        greeting_list.append(f"{i}. **{username}** - {count}x (latest: {latest_time})")
                    else:
                        greeting_list.append(f"{i}. **{username}** - {count}x (latest: {latest_time})")
                
                embed.description = "\n".join(greeting_list)
                embed.add_field(
                    name="Total Greetings Today",
                    value=str(len(greetings)),
                    inline=True
                )
                
                embed.add_field(
                    name="Unique Users",
                    value=str(len(user_greeting_counts)),
                    inline=True
                )
                
                # Add first and last greeting times
                if greetings:
                    first_time = self.format_time(greetings[0].greeting_time)
                    last_time = self.format_time(greetings[-1].greeting_time)
                    
                    embed.add_field(
                        name="First Greeting",
                        value=f"{greetings[0].username} at {first_time}",
                        inline=True
                    )
                    
                    if len(greetings) > 1:
                        embed.add_field(
                            name="Latest Greeting",
                            value=f"{greetings[-1].username} at {last_time}",
                            inline=True
                        )
            
            # Add footer
            embed.set_footer(
                text=f"Say greetings like 'gm', 'moin', 'servus', 'guten morgen', 'n8', etc. to increase your count! Use /greeting-help for all options.",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Greetings command used by {interaction.user} in {interaction.guild}")
            
        except Exception as e:
            logger.error(f"Error in greetings command: {e}", exc_info=True)
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="Sorry, I couldn't retrieve the greetings data right now. Please try again later.",
                color=discord.Color.red()
            )
            
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @app_commands.command(
        name="greeting-help",
        description="Show all possible greetings that the bot recognizes"
    )
    async def greeting_help_command(
        self,
        interaction: discord.Interaction
    ):
        """
        Display all possible greetings that the bot recognizes.
        
        Args:
            interaction: Discord interaction object
        """
        await interaction.response.defer()
        
        try:
            embed = discord.Embed(
                title="🌍 Recognized Greetings",
                description="The bot recognizes all of these greetings and will react with 👋:",
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            # English greetings
            english_greetings = [
                "morning", "good morning", "gm", "gn", "good night",
                "hello", "hi", "hey", "good evening", "evening",
                "yo", "sup", "whatsup", "what's up", "howdy",
                "hiya", "heya", "hi there", "greetings", "hey there",
                "top of the morning", "nighty night", "good day"
            ]
            
            # German greetings
            german_greetings = [
                "guten morgen", "morgen", "moin", "moin moin",
                "servus", "hallo", "hi", "hey", "tach", "tag",
                "guten tag", "guten abend", "abend", "n8", "nacht",
                "gute nacht", "tschüss", "ciao", "bye", "tschau",
                "grüß dich", "na", "alles klar", "na du", "ey", "was geht"
            ]

            # Regional variations (Austria/Switzerland)
            regional_greetings = [
                "grüezi", "grüß gott", "pfiat di", "baba",
                "hoi", "salü", "servas", "ade", "tschau zäme",
                "griaß di", "grüzi mitenand", "habedere"
            ]

            # International greetings
            international_greetings = [
                "salut", "bonjour", "bonsoir", "buongiorno",
                "buenos días", "buenas noches", "hola",
                "namaste", "shalom", "ciao", "konnichiwa",
                "annyeong", "hej", "hallå", "hei", "hola amigo",
                "ola", "ahlan", "salaam", "merhaba", "dobry den"
            ]

            embed.add_field(
                name="🇺🇸 English",
                value=", ".join([f"`{g}`" for g in english_greetings]),
                inline=False
            )
            
            embed.add_field(
                name="🇩🇪 German",
                value=", ".join([f"`{g}`" for g in german_greetings]),
                inline=False
            )
            
            embed.add_field(
                name="🏔️ Regional (Austria/Switzerland)",
                value=", ".join([f"`{g}`" for g in regional_greetings]),
                inline=False
            )
            
            embed.add_field(
                name="🌐 International",
                value=", ".join([f"`{g}`" for g in international_greetings]),
                inline=False
            )
            
            embed.add_field(
                name="💡 How it works",
                value="Simply type any of these greetings in chat and the bot will:\n• React with 👋\n• Count it in your daily greeting stats\n• Show it in `/greetings` command",
                inline=False
            )
            
            embed.set_footer(
                text="New greetings can be added by request! Contact an admin.",
                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
            )
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Greeting help command used by {interaction.user}")
            
        except Exception as e:
            logger.error(f"Error in greeting help command: {e}", exc_info=True)
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="Sorry, I couldn't retrieve the greeting information right now. Please try again later.",
                color=discord.Color.red()
            )
            
            await interaction.followup.send(embed=error_embed, ephemeral=True)

    @app_commands.command(
        name="ping",
        description="Simple test command to check if bot is responding"
    )
    async def ping_command(self, interaction: discord.Interaction):
        """Simple ping command to test if slash commands work."""
        await interaction.response.send_message("🏓 Pong! Bot is working!", ephemeral=True)
        logger.info(f"Ping command used by {interaction.user}")

    @app_commands.command(
        name="say-greeting",
        description="Manually log a greeting (since auto-detection is disabled)"
    )
    @app_commands.describe(
        greeting_type="Type of greeting (morning, evening, etc.)"
    )
    async def say_greeting_command(
        self, 
        interaction: discord.Interaction,
        greeting_type: str = "morning"
    ):
        """
        Manually log a greeting for the user.
        
        Args:
            interaction: Discord interaction object
            greeting_type: Type of greeting to log
        """
        await interaction.response.defer()
        
        try:
            # Save greeting to database (multiple greetings per day allowed)
            success = await self.bot.db_manager.save_greeting(
                user_id=interaction.user.id,
                username=interaction.user.display_name,
                guild_id=interaction.guild.id if interaction.guild else None,
                channel_id=interaction.channel.id
            )
            
            if success:
                embed = discord.Embed(
                    title="👋 Greeting Logged!",
                    description=f"Thanks for saying {greeting_type}, {interaction.user.display_name}!",
                    color=discord.Color.green()
                )
                await interaction.followup.send(embed=embed)
                logger.info(f"Manual greeting logged for {interaction.user.display_name}")
            else:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Sorry, I couldn't save your greeting right now. Please try again later.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            logger.error(f"Error in say-greeting command: {e}", exc_info=True)
            
            error_embed = discord.Embed(
                title="❌ Error",
                description="Sorry, I couldn't save your greeting right now. Please try again later.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed, ephemeral=True)

async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(GreetingsCog(bot))
