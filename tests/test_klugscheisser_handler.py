import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import discord
from handlers.klugscheisser_handler import KlugscheisserHandler
from config import Config


class TestKlugscheisserHandler(unittest.TestCase):
    """Test cases for the KlugscheisserHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = Mock()
        self.handler = KlugscheisserHandler(self.mock_db_manager)
        
        # Mock message object
        self.mock_message = Mock(spec=discord.Message)
        self.mock_message.author = Mock()
        self.mock_message.author.bot = False
        self.mock_message.author.id = 12345
        self.mock_message.author.display_name = "TestUser"
        self.mock_message.content = "This is a test message that is longer than 100 characters to trigger the factcheck feature. It contains some factual information about Python programming."
        
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', True)
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_MIN_LENGTH', 50)
    def test_should_klugscheiss_message_valid(self):
        """Test that valid messages should be klugscheißed."""
        # Mock OpenAI service availability
        with patch.object(self.handler.openai_service, 'is_available', return_value=True):
            # Mock db_manager get_klugscheisser_preference
            self.mock_db_manager.get_klugscheisser_preference.return_value = {'opted_in': True}
            # Run async test
            result = asyncio.run(self.handler.should_klugscheiss_message(self.mock_message))
            
            # Result depends on random roll, so we just check that it returns a boolean
            self.assertIsInstance(result, bool)
    
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', False)
    def test_should_klugscheiss_message_disabled(self):
        """Test that klugscheißer is skipped when disabled."""
        result = asyncio.run(self.handler.should_klugscheiss_message(self.mock_message))
        self.assertFalse(result)
    
    def test_should_klugscheiss_message_bot(self):
        """Test that bot messages are skipped."""
        self.mock_message.author.bot = True
        result = asyncio.run(self.handler.should_klugscheiss_message(self.mock_message))
        self.assertFalse(result)
    
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', True)
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_MIN_LENGTH', 200)
    def test_should_klugscheiss_message_too_short(self):
        """Test that short messages are skipped."""
        # Mock db_manager get_klugscheisser_preference
        self.mock_db_manager.get_klugscheisser_preference.return_value = {'opted_in': True}
        result = asyncio.run(self.handler.should_klugscheiss_message(self.mock_message))
        self.assertFalse(result)
    
    def test_is_user_on_cooldown(self):
        """Test user cooldown functionality."""
        user_id = 12345
        
        # User should not be on cooldown initially
        self.assertFalse(self.handler._is_user_on_cooldown(user_id))
        
        # Set cooldown
        self.handler._set_user_cooldown(user_id)
        
        # User should now be on cooldown
        self.assertTrue(self.handler._is_user_on_cooldown(user_id))
    
    def test_format_klugscheiss_response(self):
        """Test klugscheißer response formatting."""
        test_response = "This is a test klugscheißer response."
        formatted = self.handler._format_klugscheiss_response(test_response)
        
        self.assertIn(test_response, formatted)
    
    def test_format_klugscheiss_response_truncation(self):
        """Test that long responses are truncated."""
        # Create a response longer than 2000 characters
        long_response = "x" * 2500
        formatted = self.handler._format_klugscheiss_response(long_response)
        
        self.assertLessEqual(len(formatted), 2000)
        self.assertIn("*(zu frech)*", formatted)
    
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', True)
    def test_get_statistics(self):
        """Test statistics gathering."""
        stats = asyncio.run(self.handler.get_statistics())
        
        self.assertIn("users_on_cooldown", stats)
        self.assertIn("openai_available", stats)
        self.assertIn("klugscheisser_enabled", stats)
        self.assertIn("probability_percent", stats)
        self.assertIn("min_length", stats)
        
        self.assertIsInstance(stats["users_on_cooldown"], int)
        self.assertIsInstance(stats["klugscheisser_enabled"], bool)
    
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', True)
    def test_handle_klugscheisserei_success(self):
        """Test successful klugscheißerei handling."""
        async def async_test():
            # Mock OpenAI service methods
            with patch.object(self.handler.openai_service, 'should_respond_with_klugscheiss', return_value=True):
                with patch.object(self.handler.openai_service, 'generate_klugscheiss_response', return_value="Test klugscheißer response"):
                    # Mock message reply method
                    self.mock_message.reply = AsyncMock()
                    
                    result = await self.handler.handle_klugscheisserei(self.mock_message)
                    
                    self.assertTrue(result)
                    self.mock_message.reply.assert_called_once()
        
        asyncio.run(async_test())
    
    @patch('handlers.klugscheisser_handler.Config.KLUGSCHEISSER_ENABLED', True)
    def test_handle_klugscheisserei_no_response(self):
        """Test klugscheißerei handling when no response is received."""
        async def async_test():
            # Mock OpenAI service to return None
            with patch.object(self.handler.openai_service, 'should_respond_with_klugscheiss', return_value=True):
                with patch.object(self.handler.openai_service, 'generate_klugscheiss_response', return_value=None):
                    result = await self.handler.handle_klugscheisserei(self.mock_message)
                    
                    self.assertFalse(result)
        
        asyncio.run(async_test())


if __name__ == '__main__':
    unittest.main()
