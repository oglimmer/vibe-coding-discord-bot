import asyncio
import logging
import random
import time
from typing import Dict, Optional
import discord

from config import Config
from services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

class KlugscheisserHandler:
    """Handler for managing AI-powered klugscheißer troll responses on Discord messages."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.openai_service = OpenAIService()
        self.user_cooldowns: Dict[int, float] = {}  # user_id -> last_klugscheisser_timestamp
        
    async def should_klugscheiss_message(self, message: discord.Message) -> bool:
        """
        Determine if a message should be klugscheißed based on various criteria.
        
        Args:
            message: The Discord message to evaluate
            
        Returns:
            True if the message should be klugscheißed, False otherwise
        """
        # Skip if klugscheißer is disabled
        if not Config.KLUGSCHEISSER_ENABLED:
            return False
            
        # Skip if OpenAI service is not available
        if not self.openai_service.is_available():
            return False
            
        # Skip bot messages
        if message.author.bot:
            return False
            
        # STEP 1: Check if user has opted in (privacy requirement)
        if Config.KLUGSCHEISSER_REQUIRE_OPTIN:
            user_preference = self.db_manager.get_klugscheisser_preference(message.author.id)
            if not user_preference['opted_in']:
                logger.debug(f"User {message.author.id} has not opted in to klugscheißer")
                return False
            
        # Check message length requirement
        if len(message.content) < Config.KLUGSCHEISSER_MIN_LENGTH:
            return False
            
        # Check user cooldown
        if self._is_user_on_cooldown(message.author.id):
            logger.debug(f"User {message.author.id} is on cooldown for klugscheißer")
            return False
            
        # STEP 2: Random probability check
        random_roll = random.randint(1, 100)
        should_trigger = random_roll <= Config.KLUGSCHEISSER_PROBABILITY
        
        if should_trigger:
            logger.info(f"Klugscheißer triggered for message from {message.author.display_name} "
                       f"(roll: {random_roll}/{Config.KLUGSCHEISSER_PROBABILITY}%)")
        else:
            logger.debug(f"Klugscheißer not triggered (roll: {random_roll}/{Config.KLUGSCHEISSER_PROBABILITY}%)")
            
        return should_trigger
    
    async def handle_klugscheisserei(self, message: discord.Message) -> bool:
        """
        Process a klugscheißerei for the given message using the new 4-step troll system.
        
        Args:
            message: The Discord message to klugscheiß
            
        Returns:
            True if klugscheißerei was successfully processed, False otherwise
        """
        try:
            # Set cooldown for this user immediately to prevent spam
            self._set_user_cooldown(message.author.id)
            
            # STEP 3: Check if message is worth trolling
            logger.info(f"Checking if message from {message.author.display_name} is worth trolling")
            should_troll = await self.openai_service.should_respond_with_klugscheiss(message.content)
            
            if not should_troll:
                logger.info(f"Message from {message.author.display_name} not worth trolling - skipping")
                return False  # Silent skip, no response
            
            # STEP 4: Generate troll response
            logger.info(f"Generating troll response for message from {message.author.display_name}")
            troll_response = await self.openai_service.generate_klugscheiss_response(
                message_content=message.content,
                user_name=message.author.display_name
            )
            
            if not troll_response:
                logger.warning("No troll response received from OpenAI service")
                return False
                
            # Format and send the troll response
            formatted_response = self._format_klugscheiss_response(troll_response)
            
            # Send as reply to the original message
            await message.reply(formatted_response, mention_author=False)
            
            logger.info(f"Successfully sent troll response for message from {message.author.display_name}")
            return True
            
        except discord.HTTPException as e:
            logger.error(f"Failed to send klugscheißer response due to Discord API error: {e}")
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error in klugscheißer handling: {e}")
            return False
    
    def _is_user_on_cooldown(self, user_id: int) -> bool:
        """Check if a user is currently on cooldown for klugscheißer."""
        if user_id not in self.user_cooldowns:
            return False
            
        time_since_last = time.time() - self.user_cooldowns[user_id]
        return time_since_last < Config.KLUGSCHEISSER_COOLDOWN_SECONDS
    
    def _set_user_cooldown(self, user_id: int) -> None:
        """Set cooldown timestamp for a user."""
        self.user_cooldowns[user_id] = time.time()
        
        # Clean up old cooldowns to prevent memory bloat
        current_time = time.time()
        expired_users = [
            uid for uid, timestamp in self.user_cooldowns.items()
            if current_time - timestamp > Config.KLUGSCHEISSER_COOLDOWN_SECONDS * 2
        ]
        for uid in expired_users:
            del self.user_cooldowns[uid]
    
    def _format_klugscheiss_response(self, response: str) -> str:
        """Format the klugscheißer troll response with minimal styling."""
        # For troll responses, we don't add extra formatting
        # The response already contains the 🤓 emoji and troll formatting
        
        # Ensure the response isn't too long for Discord
        if len(response) > 2000:
            # Truncate and add indicator
            response = response[:1990] + "... *(zu frech)*"
            
        return response
    
    async def get_statistics(self) -> Dict[str, int]:
        """Get statistics about klugscheißer usage."""
        return {
            "users_on_cooldown": len(self.user_cooldowns),
            "openai_available": self.openai_service.is_available(),
            "klugscheisser_enabled": Config.KLUGSCHEISSER_ENABLED,
            "probability_percent": Config.KLUGSCHEISSER_PROBABILITY,
            "min_length": Config.KLUGSCHEISSER_MIN_LENGTH
        }
