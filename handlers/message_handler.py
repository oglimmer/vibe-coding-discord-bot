import logging
import re
from datetime import datetime
from database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.greeting_patterns = [
            r'\b(morning|good morning)\b',
            r'\bgn\b'
        ]
    
    async def handle_message(self, message):
        if message.author.bot:
            return
        
        content = message.content.lower().strip()
        
        if self._is_greeting(content):
            await self._handle_greeting(message)
    
    def _is_greeting(self, content):
        for pattern in self.greeting_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    async def _handle_greeting(self, message):
        try:
            user_id = message.author.id
            username = message.author.display_name
            greeting_message = message.content
            server_id = message.guild.id if message.guild else None
            channel_id = message.channel.id
            
            success = self.db_manager.save_greeting(
                user_id=user_id,
                username=username,
                greeting_message=greeting_message,
                server_id=server_id,
                channel_id=channel_id
            )
            
            if success:
                await message.reply("👋")
                logger.info(f"Responded to greeting from {username} ({user_id})")
            else:
                logger.error(f"Failed to save greeting from {username} ({user_id})")
                
        except Exception as e:
            logger.error(f"Error handling greeting: {e}")
            await message.reply("👋")