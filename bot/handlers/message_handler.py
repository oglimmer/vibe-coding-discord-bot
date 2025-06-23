import logging
from greeting_client import GreetingClient

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, greeting_client):
        self.greeting_client = greeting_client

    async def handle_message(self, message):
        if message.author.bot:
            return
        
        content = message.content.strip()
        
        is_greeting, matched_pattern = await self.greeting_client.detect_greeting(content)
        if is_greeting:
            await self._handle_greeting(message)

    async def _handle_greeting(self, message):
        try:
            user_id = str(message.author.id)
            username = message.author.display_name
            greeting_message = message.content
            server_id = str(message.guild.id) if message.guild else None
            channel_id = str(message.channel.id)
            message_id = str(message.id)
            
            greeting_id = await self.greeting_client.save_greeting(
                user_id=user_id,
                username=username,
                message_content=greeting_message,
                guild_id=server_id,
                channel_id=channel_id,
                message_id=message_id
            )
            
            if greeting_id:
                await message.add_reaction("👋")
                logger.info(f"Responded to greeting from {username} ({user_id}) with ID {greeting_id}")
            else:
                logger.error(f"Failed to save greeting from {username} ({user_id})")
                
        except Exception as e:
            logger.error(f"Error handling greeting: {e}")
            await message.add_reaction("👋")

    async def close(self):
        """Close the HTTP client session."""
        await self.greeting_client.close()
