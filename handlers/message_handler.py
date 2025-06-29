import logging
import re
from database import DatabaseManager
from handlers.klugscheisser_handler import KlugscheisserHandler

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.klugscheisser_handler = KlugscheisserHandler(db_manager)

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
            "guten morgen", "moin",
            "servus", "hallo", "hi", "hey", "tach", "tag",
            "guten tag", "guten abend", "n8", "nacht",
            "gute nacht", "tschüss", "ciao", "bye", "tschau",
            "grüß dich", "na", "alles klar", "na du", "ey", "was geht",
            "hallihallo", "halöle", "mosche"
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

        # Combine all greetings and create regex patterns
        all_greetings = english_greetings + german_greetings + regional_greetings + international_greetings
        self.greeting_patterns = [rf'\b{re.escape(greeting)}\b' for greeting in all_greetings]

    async def handle_message(self, message):
        if message.author.bot:
            return
        
        content = message.content.lower().strip()
        
        # Handle greetings
        if self._is_greeting(content):
            await self._handle_greeting(message)
        
        # Handle potential klugscheißerei (independent of greetings)
        await self._handle_potential_klugscheisserei(message)

    def _is_greeting(self, content):
        words = content.split()
        
        for pattern in self.greeting_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                # Find the position of the matched greeting in the word list
                greeting_text = match.group()
                greeting_words = greeting_text.split()
                
                # Find where the greeting starts in the word list
                for i in range(len(words) - len(greeting_words) + 1):
                    if ' '.join(words[i:i+len(greeting_words)]).lower() == greeting_text.lower():
                        # Check words before greeting (max 2)
                        words_before = i
                        # Check words after greeting (max 2)
                        words_after = len(words) - (i + len(greeting_words))
                        
                        if words_before <= 2 and words_after <= 2:
                            return True
                        break
        return False

    async def _handle_greeting(self, message):
        try:
            user_id = message.author.id
            username = message.author.display_name
            greeting_message = message.content
            server_id = message.guild.id if message.guild else None
            channel_id = message.channel.id
            message_id = message.id
            
            greeting_id = self.db_manager.save_greeting(
                user_id=user_id,
                username=username,
                greeting_message=greeting_message,
                server_id=server_id,
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

    async def _handle_potential_klugscheisserei(self, message):
        """Handle potential klugscheißerei for a message."""
        try:
            # Check if message should be klugscheißed
            if await self.klugscheisser_handler.should_klugscheiss_message(message):
                # Process klugscheißerei asynchronously to avoid blocking other message handling
                await self.klugscheisser_handler.handle_klugscheisserei(message)
        except Exception as e:
            logger.error(f"Error in klugscheißer handling: {e}")
