"""
Discord Bot Main Entry Point
Professional Discord bot with greeting functionality and database integration.
"""

import os
import asyncio
import random
import discord
from dotenv import load_dotenv
from discord.ext import commands

from utils.logger import setup_logger
from database.connection import DatabaseManager
from database.models import Base

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logger('main')

class VibeBot(commands.Bot):
    """Main bot class with professional structure and error handling."""
    
    def __init__(self):
        # Configure intents - enabling message content for greeting detection
        intents = discord.Intents.default()
        intents.message_content = True  # Required for message content access
        intents.members = False  # Keep members intent disabled for now
        
        super().__init__(
            command_prefix='/',
            intents=intents,
            help_command=None  # We'll create our own help command
        )
        
        # Initialize database
        self.db_manager = None
        
    async def setup_hook(self):
        """Called when the bot is starting up."""
        logger.info("Setting up bot...")
        
        # Initialize database
        try:
            self.db_manager = DatabaseManager()
            await self.db_manager.initialize()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            await self.close()
            return
        
        # Load cogs (commands)
        try:
            await self.load_extension('commands.greetings')
            await self.load_extension('commands.game_1337')
            logger.info("Commands loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load commands: {e}")
        
        # Sync slash commands (both global and guild-specific)
        try:
            # First, sync globally (takes up to 1 hour to propagate)
            synced_global = await self.tree.sync()
            logger.info(f"Synced {len(synced_global)} global command(s)")
            
            # Also sync for each guild for immediate availability
            guild_syncs = 0
            for guild in self.guilds:
                try:
                    synced_guild = await self.tree.sync(guild=guild)
                    guild_syncs += len(synced_guild)
                    logger.info(f"Synced {len(synced_guild)} command(s) for guild {guild.name}")
                except Exception as guild_e:
                    logger.error(f"Failed to sync commands for guild {guild.name}: {guild_e}")
            
            logger.info(f"Total commands synced: {len(synced_global)} global, {guild_syncs} guild-specific")
            
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="for greetings 👋"
            )
        )

    async def on_message(self, message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
            
        # Check for greetings (expanded list with German and international greetings)
        greeting_keywords = [
            # English greetings
            "morning", "good morning", "gm", "gn", "good night", 
            "hello", "hi", "hey", "good evening", "evening",
            
            # German greetings
            "guten morgen", "morgen", "moin", "moin moin", 
            "servus", "hallo", "hi", "hey", "tach", "tag",
            "guten tag", "guten abend", "abend", "n8", "nacht",
            "gute nacht", "tschüss", "ciao", "bye", "tschau",
            
            # Austrian/Swiss variations
            "grüezi", "grüß gott", "pfiat di", "baba",
            
            # Other casual greetings
            "yo", "sup", "whatsup", "what's up", "howdy",
            "salut", "bonjour", "bonsoir", "buongiorno",
            "buenos días", "buenas noches", "hola"
        ]
        content_lower = message.content.lower().strip()
        
        # Check if the message contains any greeting keywords
        # This now detects "hidden" greetings in longer messages like "Ha? Hallo an alle!!"
        greeting_found = False
        
        # Method 1: Exact match or word boundary match
        if any(keyword == content_lower or keyword in content_lower.split() for keyword in greeting_keywords):
            greeting_found = True
        
        # Method 2: Check for greetings within the text (substring search)
        # This catches cases like "Ha? Hallo an alle!!" where "hallo" is part of a longer sentence
        if not greeting_found:
            import re  # Import here to avoid issues
            for keyword in greeting_keywords:
                # Use word boundary detection to avoid false positives
                # For example, "hallo" should match in "Hallo an alle" but not in "halloween"
                # Create pattern that matches the keyword with word boundaries
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, content_lower):
                    greeting_found = True
                    break
        
        if greeting_found:
            try:
                # Zufällige Emoji-Reaktion aus verschiedenen Begrüßungs-Emojis
                greeting_emojis = [
                    "👋", "🙋‍♂️", "🙋‍♀️", "👋🏻", "👋🏽", "👋🏿", 
                    "🤗", "😊", "😄", "🎉", "✨", "🌟", "🙌", "👍", 
                    "❤️", "💙", "💚", "💛", "🧡", "💜", "🤍", "🖤"
                ]
                random_emoji = random.choice(greeting_emojis)
                await message.add_reaction(random_emoji)
                
                # Save to database
                if self.db_manager:
                    success = await self.db_manager.save_greeting(
                        user_id=message.author.id,
                        username=message.author.display_name,
                        guild_id=message.guild.id if message.guild else None,
                        channel_id=message.channel.id
                    )
                    
                    if success:
                        logger.info(f"Saved greeting from {message.author.display_name} (ID: {message.author.id})")
                    else:
                        logger.debug(f"User {message.author.display_name} already greeted today")
                    
            except Exception as e:
                logger.error(f"Error handling greeting from {message.author}: {e}")
        
        # Process commands (for text commands if any)
        await self.process_commands(message)

    async def on_error(self, event, *args, **kwargs):
        """Handle errors."""
        logger.error(f"Error in event {event}", exc_info=True)

    async def close(self):
        """Clean shutdown."""
        logger.info("Shutting down bot...")
        if self.db_manager:
            await self.db_manager.close()
        await super().close()

async def main():
    """Main function to run the bot."""
    # Get token
    token = os.getenv('BOT_TOKEN')
    if not token:
        logger.error("BOT_TOKEN not found in environment variables!")
        return
    
    # Create and run bot
    bot = VibeBot()
    
    try:
        await bot.start(token)
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}", exc_info=True)
    finally:
        await bot.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Program terminated by user")