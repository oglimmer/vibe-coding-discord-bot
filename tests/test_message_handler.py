import unittest
from unittest.mock import Mock, AsyncMock
from handlers.message_handler import MessageHandler

class TestMessageHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.db_manager = Mock()
        self.message_handler = MessageHandler(self.db_manager)
    
    def test_is_greeting_morning(self):
        self.assertTrue(self.message_handler._is_greeting("good morning"))
        self.assertTrue(self.message_handler._is_greeting("morning"))
        self.assertTrue(self.message_handler._is_greeting("Good Morning everyone!"))
    
    def test_is_greeting_gn(self):
        self.assertTrue(self.message_handler._is_greeting("gn"))
        self.assertTrue(self.message_handler._is_greeting("gn everyone"))
        self.assertTrue(self.message_handler._is_greeting("GN"))

    def test_is_not_greeting(self):
        self.assertFalse(self.message_handler._is_greeting("huhu"))
        self.assertFalse(self.message_handler._is_greeting("gnome"))
        self.assertFalse(self.message_handler._is_greeting("mourning coffee"))
    
    def test_greeting_word_limit_validation(self):
        # Valid greetings (2 words or less on each side)
        self.assertTrue(self.message_handler._is_greeting("hey there friend"))  # 0 before, 1 after
        self.assertTrue(self.message_handler._is_greeting("oh hi there"))  # 1 before, 1 after
        self.assertTrue(self.message_handler._is_greeting("well good morning everyone"))  # 1 before, 1 after
        self.assertTrue(self.message_handler._is_greeting("so hey buddy"))  # 1 before, 1 after
        
        # Invalid greetings (more than 2 words on either side)
        self.assertFalse(self.message_handler._is_greeting("I was just thinking good morning everyone today"))  # 4 before, 2 after
        self.assertFalse(self.message_handler._is_greeting("hey there my good friend today"))  # 0 before, 4 after
        self.assertFalse(self.message_handler._is_greeting("well I think hey there sounds nice today"))  # 3 before, 3 after

    async def test_handle_greeting_message(self):
        message = Mock()
        message.author.bot = False
        message.author.id = 12345
        message.author.display_name = "TestUser"
        message.content = "good morning"
        message.guild.id = 67890
        message.channel.id = 54321
        message.reply = AsyncMock()
        message.add_reaction = AsyncMock()

        self.db_manager.save_greeting.return_value = True

        await self.message_handler._handle_greeting(message)

        self.db_manager.save_greeting.assert_called_once()
        message.add_reaction.assert_called_once_with("👋")

if __name__ == '__main__':
    unittest.main()