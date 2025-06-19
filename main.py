import asyncio
import logging
import signal
import sys
from discord.ext import commands, tasks
import discord

from config import Config, setup_logging
from database import DatabaseManager
from handlers.message_handler import MessageHandler
from commands.greetings_command import setup as setup_greetings_command
from commands.game_1337_command import setup as setup_game_1337_command
from commands.bet_1337_command import setup as setup_bet_1337_command
from commands.bet_1337_early_bird_command import setup as setup_bet_1337_early_bird_command
from commands.info_1337_command import setup as setup_info_1337_command
from commands.stats_1337_command import setup as setup_stats_1337_command
from commands.rules_1337_command import setup as setup_rules_1337_command
from commands.about_command import setup as setup_about_command

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
        self.db_health_check_failures = 0
        self.max_health_check_failures = 3
    
    async def setup_hook(self):
        try:
            # Initialize database with retry logic
            retry_count = 3
            for attempt in range(retry_count):
                try:
                    self.db_manager = DatabaseManager()
                    break
                except Exception as e:
                    if attempt < retry_count - 1:
                        logger.warning(f"Database initialization attempt {attempt + 1} failed: {e}. Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        logger.error(f"Failed to initialize database after {retry_count} attempts: {e}")
                        raise
            
            self.message_handler = MessageHandler(self.db_manager)
            
            await setup_greetings_command(self, self.db_manager)
            await setup_game_1337_command(self, self.db_manager)
            await setup_bet_1337_command(self, self.db_manager)
            await setup_bet_1337_early_bird_command(self, self.db_manager)
            await setup_info_1337_command(self, self.db_manager)
            await setup_stats_1337_command(self, self.db_manager)
            await setup_rules_1337_command(self, self.db_manager)
            await setup_about_command(self)
            
            await self.tree.sync()
            logger.info("Command tree synced successfully")
            
        except Exception as e:
            logger.error(f"Error in setup_hook: {e}")
            raise
    
    async def on_ready(self):
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot is in {len(self.guilds)} guilds')
        
        # Start database health monitoring
        if self.db_manager:
            self.database_health_monitor.start()
            logger.info("Database health monitoring started")
        
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
    
    @tasks.loop(minutes=5)
    async def database_health_monitor(self):
        """Monitor database health and attempt recovery if needed"""
        if not self.db_manager:
            return
            
        try:
            if self.db_manager.health_check():
                # Reset failure counter on successful health check
                if self.db_health_check_failures > 0:
                    logger.info("Database health restored")
                    self.db_health_check_failures = 0
            else:
                self.db_health_check_failures += 1
                logger.warning(f"Database health check failed (attempt {self.db_health_check_failures}/{self.max_health_check_failures})")
                
                if self.db_health_check_failures >= self.max_health_check_failures:
                    logger.error("Database health check failed multiple times, attempting force reconnect")
                    if self.db_manager.force_reconnect():
                        logger.info("Database force reconnect successful")
                        self.db_health_check_failures = 0
                    else:
                        logger.error("Database force reconnect failed")
                        
        except Exception as e:
            logger.error(f"Error in database health monitor: {e}")
            self.db_health_check_failures += 1
    
    @database_health_monitor.before_loop
    async def before_database_health_monitor(self):
        await self.wait_until_ready()
    
    async def close(self):
        # Stop health monitoring
        if hasattr(self, 'database_health_monitor'):
            self.database_health_monitor.cancel()
            logger.info("Database health monitoring stopped")
        
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