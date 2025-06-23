import asyncio
import logging
import signal
import sys
from discord.ext import commands
import discord
from aiohttp import web
import threading

from config import Config, setup_logging
from handlers.message_handler import MessageHandler
from commands.greetings_command import setup as setup_greetings_command
from greeting_client import GreetingClient
from game_service_client import GameServiceAdapter
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
        
        self.message_handler = None
        self.greeting_client = None
        self.game_service = None
        self.webhook_server = None
        self.webhook_task = None
    
    async def setup_hook(self):
        try:
            self.greeting_client = GreetingClient(Config.GREETING_SERVICE_URL)
            self.message_handler = MessageHandler(self.greeting_client)
            self.game_service = GameServiceAdapter(Config.GAME_SERVICE_URL)
            
            await setup_greetings_command(self)
            await setup_game_1337_command(self, self.game_service)
            await setup_bet_1337_command(self, self.game_service)
            await setup_bet_1337_early_bird_command(self, self.game_service)
            await setup_info_1337_command(self, self.game_service)
            await setup_stats_1337_command(self, self.game_service)
            await setup_rules_1337_command(self, self.game_service)
            await setup_about_command(self)
            
            # Start webhook server
            await self.start_webhook_server()
            
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
            success = await self.greeting_client.save_greeting_reaction(
                message_id=str(reaction.message.id),
                user_id=str(user.id),
                username=user.display_name,
                emoji=str(reaction.emoji)
            )
            
            if success:
                logger.info(f"Saved reaction {reaction.emoji} from {user.display_name} to message {reaction.message.id}")
            else:
                logger.debug(f"Message {reaction.message.id} is not a greeting or failed to save reaction")
                    
        except Exception as e:
            logger.error(f"Error handling reaction add: {e}")

    async def on_reaction_remove(self, reaction, user):
        """Handle when a user removes a reaction from a message"""
        if user.bot:
            return
        
        try:
            success = await self.greeting_client.remove_greeting_reaction(
                message_id=str(reaction.message.id),
                user_id=str(user.id),
                emoji=str(reaction.emoji)
            )
            
            if success:
                logger.info(f"Removed reaction {reaction.emoji} from {user.display_name} to message {reaction.message.id}")
            else:
                logger.debug(f"Message {reaction.message.id} is not a greeting or failed to remove reaction")
                    
        except Exception as e:
            logger.error(f"Error handling reaction remove: {e}")

    async def on_error(self, event, *args, **kwargs):
        logger.error(f'An error occurred in {event}', exc_info=True)
    
    async def start_webhook_server(self):
        """Start the webhook server to receive notifications from game service"""
        try:
            app = web.Application()
            app.router.add_post('/webhook/winner', self.handle_winner_webhook)
            app.router.add_post('/webhook/catastrophic', self.handle_catastrophic_webhook)
            app.router.add_get('/webhook/health', self.handle_health_webhook)
            
            self.webhook_server = web.AppRunner(app)
            await self.webhook_server.setup()
            
            site = web.TCPSite(self.webhook_server, '0.0.0.0', Config.WEBHOOK_PORT)
            await site.start()
            
            logger.info(f"Webhook server started on port {Config.WEBHOOK_PORT}")
            
        except Exception as e:
            logger.error(f"Error starting webhook server: {e}")
    
    async def handle_winner_webhook(self, request):
        """Handle winner notification from game service"""
        try:
            # Verify webhook secret if configured
            if Config.WEBHOOK_SECRET:
                auth_header = request.headers.get('Authorization', '')
                if not auth_header.startswith('Bearer ') or auth_header[7:] != Config.WEBHOOK_SECRET:
                    logger.warning("Webhook request with invalid or missing secret")
                    return web.Response(status=401, text="Unauthorized")
            
            data = await request.json()
            
            if data.get('event') == 'winner_determined':
                winner_data = data.get('winner')
                if winner_data:
                    logger.info(f"🔔 Received winner webhook: {winner_data['username']}")
                    logger.debug(f"🔔 Winner data: {winner_data}")
                    await self.process_winner_notification(winner_data)
                    return web.Response(status=200, text="OK")
            
            logger.warning(f"Unknown webhook event: {data.get('event')}")
            return web.Response(status=400, text="Unknown event")
            
        except Exception as e:
            logger.error(f"Error handling winner webhook: {e}")
            return web.Response(status=500, text="Internal error")
    
    async def handle_catastrophic_webhook(self, request):
        """Handle catastrophic event notification from game service"""
        try:
            # Verify webhook secret if configured
            if Config.WEBHOOK_SECRET:
                auth_header = request.headers.get('Authorization', '')
                if not auth_header.startswith('Bearer ') or auth_header[7:] != Config.WEBHOOK_SECRET:
                    logger.warning("Webhook request with invalid or missing secret")
                    return web.Response(status=401, text="Unauthorized")
            
            data = await request.json()
            
            if data.get('event') == 'catastrophic_event':
                catastrophic_data = data.get('catastrophic_data')
                if catastrophic_data:
                    logger.info(f"🔔 Received catastrophic event webhook")
                    await self.process_catastrophic_notification(catastrophic_data)
                    return web.Response(status=200, text="OK")
            
            logger.warning(f"Unknown catastrophic webhook event: {data.get('event')}")
            return web.Response(status=400, text="Unknown event")
            
        except Exception as e:
            logger.error(f"Error handling catastrophic webhook: {e}")
            return web.Response(status=500, text="Internal error")
    
    async def handle_health_webhook(self, request):
        """Health check for webhook server"""
        return web.Response(status=200, text="OK")
    
    async def process_winner_notification(self, winner_data):
        """Process winner notification and update Discord"""
        try:
            # Find the game command cog to handle the winner processing
            game_cog = self.get_cog('Game1337Command')
            if game_cog:
                await game_cog.process_external_winner_notification(winner_data)
            else:
                logger.error("Game1337Command cog not found")
                
        except Exception as e:
            logger.error(f"Error processing winner notification: {e}")
    
    async def process_catastrophic_notification(self, catastrophic_data):
        """Process catastrophic event notification"""
        try:
            # Find the game command cog to handle the catastrophic event
            game_cog = self.get_cog('Game1337Command')
            if game_cog:
                await game_cog.announce_catastrophic_event()
            else:
                logger.error("Game1337Command cog not found")
                
        except Exception as e:
            logger.error(f"Error processing catastrophic notification: {e}")
    
    async def close(self):
        if self.webhook_server:
            await self.webhook_server.cleanup()
            logger.info("Webhook server stopped")
        if self.greeting_client:
            await self.greeting_client.close()
        if self.message_handler:
            await self.message_handler.close()
        if self.game_service:
            await self.game_service.close()
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