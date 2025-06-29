import asyncio
import logging
import signal
import sys
from discord.ext import commands
import discord

from config import Config, setup_logging
from database import DatabaseManager
from handlers.message_handler import MessageHandler
from handlers.factcheck_handler import FactCheckHandler
from commands.greetings_command import setup as setup_greetings_command
from commands.game_1337_command import setup as setup_game_1337_command
from commands.bet_1337_command import setup as setup_bet_1337_command
from commands.bet_1337_early_bird_command import setup as setup_bet_1337_early_bird_command
from commands.info_1337_command import setup as setup_info_1337_command
from commands.stats_1337_command import setup as setup_stats_1337_command
from commands.rules_1337_command import setup as setup_rules_1337_command
from commands.about_command import setup as setup_about_command
from commands.klugscheisser_command import setup as setup_klugscheisser_command

logger = setup_logging()

class DiscordBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        
        super().__init__(
            command_prefix='!',
            intents=intents,
            help_command=None
        )
        
        self.db_manager = None
        self.message_handler = None
        self.factcheck_handler = None
    
    async def setup_hook(self):
        try:
            self.db_manager = DatabaseManager()
            self.message_handler = MessageHandler(self.db_manager)
            self.factcheck_handler = FactCheckHandler(self.db_manager)
            
            await setup_greetings_command(self, self.db_manager)
            await setup_game_1337_command(self, self.db_manager)
            await setup_bet_1337_command(self, self.db_manager)
            await setup_bet_1337_early_bird_command(self, self.db_manager)
            await setup_info_1337_command(self, self.db_manager)
            await setup_stats_1337_command(self, self.db_manager)
            await setup_rules_1337_command(self, self.db_manager)
            await setup_about_command(self)
            await setup_klugscheisser_command(self, self.db_manager)
            
            await self.tree.sync()
            logger.info("Command tree synced successfully")
            
        except Exception as e:
            logger.error(f"Error in setup_hook: {e}")
            raise
    
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Create readiness indicator for k8s probes
        try:
            with open('/tmp/bot_ready', 'w') as f:
                f.write('ready')
        except Exception as e:
            logger.warning(f"Could not create readiness file: {e}")
        
        activity = discord.Game(name="Greeting everyone! =K")
        await self.change_presence(activity=activity)
    
    async def on_message(self, message):
        if self.message_handler:
            await self.message_handler.handle_message(message)
        
        await self.process_commands(message)

    async def on_reaction_add(self, reaction, user):
        """Handle when a user adds a reaction to a message"""
        if user.bot:
            return
        
        try:
            # Check if this is a fact-check reaction
            if self.factcheck_handler:
                factcheck_handled = await self.factcheck_handler.handle_factcheck_reaction(reaction, user)
                if factcheck_handled:
                    return  # Fact-check was processed, don't continue with other reaction handling
            
            # Check if this is a reaction to a greeting message
            greeting_id = self.db_manager.get_greeting_id_by_message(
                reaction.message.id, 
                reaction.message.guild.id if reaction.message.guild else None
            )
            
            if greeting_id:
                success = self.db_manager.save_greeting_reaction(
                    greeting_id=greeting_id,
                    user_id=user.id,
                    username=user.display_name,
                    reaction_emoji=str(reaction.emoji),
                    server_id=reaction.message.guild.id if reaction.message.guild else None
                )
                
                if success:
                    logger.info(f"Saved reaction {reaction.emoji} from {user.display_name} to greeting {greeting_id}")
                else:
                    logger.error(f"Failed to save reaction {reaction.emoji} from {user.display_name} to greeting {greeting_id}")
                    
        except Exception as e:
            logger.error(f"Error handling reaction add: {e}")

    async def on_reaction_remove(self, reaction, user):
        """Handle when a user removes a reaction from a message"""
        if user.bot:
            return
        
        try:
            # Check if this is a reaction to a greeting message
            greeting_id = self.db_manager.get_greeting_id_by_message(
                reaction.message.id, 
                reaction.message.guild.id if reaction.message.guild else None
            )
            
            if greeting_id:
                success = self.db_manager.remove_greeting_reaction(
                    greeting_id=greeting_id,
                    user_id=user.id,
                    reaction_emoji=str(reaction.emoji)
                )
                
                if success:
                    logger.info(f"Removed reaction {reaction.emoji} from {user.display_name} to greeting {greeting_id}")
                else:
                    logger.error(f"Failed to remove reaction {reaction.emoji} from {user.display_name} to greeting {greeting_id}")
                    
        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}")

    async def on_error(self, event, *args, **kwargs):
        logger.error(f'An error occurred in {event}', exc_info=True)
    
    async def close(self):
        if self.db_manager:
            self.db_manager.close()
        await super().close()

async def main():
    if not Config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables")
        sys.exit(1)
    
    bot = DiscordBot()
    
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, closing bot...")
        asyncio.create_task(bot.close())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        await bot.start(Config.DISCORD_TOKEN)
    except discord.LoginFailure:
        logger.error("Invalid Discord token")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error starting bot: {e}")
        sys.exit(1)
    finally:
        await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutdown by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
