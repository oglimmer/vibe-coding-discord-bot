import unittest
from unittest.mock import Mock, AsyncMock, patch
import asyncio
import discord
from handlers.factcheck_handler import FactcheckHandler
from config import Config


class TestFactcheckHandler(unittest.TestCase):
    """Test cases for the FactcheckHandler class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.handler = FactcheckHandler()
        
        # Mock message object
        self.mock_message = Mock(spec=discord.Message)
        self.mock_message.author = Mock()
        self.mock_message.author.bot = False
        self.mock_message.author.id = 12345
        self.mock_message.author.display_name = "TestUser"
        self.mock_message.content = "This is a test message that is longer than 100 characters to trigger the factcheck feature. It contains some factual information about Python programming."
        
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', True)
    @patch('handlers.factcheck_handler.Config.FACTCHECK_MIN_LENGTH', 50)
    def test_should_factcheck_message_valid(self):
        """Test that valid messages should be factchecked."""
        # Mock OpenAI service availability
        with patch.object(self.handler.openai_service, 'is_available', return_value=True):
            # Run async test
            result = asyncio.run(self.handler.should_factcheck_message(self.mock_message))
            
            # Result depends on random roll, so we just check that it returns a boolean
            self.assertIsInstance(result, bool)
    
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', False)
    def test_should_factcheck_message_disabled(self):
        """Test that factcheck is skipped when disabled."""
        result = asyncio.run(self.handler.should_factcheck_message(self.mock_message))
        self.assertFalse(result)
    
    def test_should_factcheck_message_bot(self):
        """Test that bot messages are skipped."""
        self.mock_message.author.bot = True
        result = asyncio.run(self.handler.should_factcheck_message(self.mock_message))
        self.assertFalse(result)
    
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', True)
    @patch('handlers.factcheck_handler.Config.FACTCHECK_MIN_LENGTH', 200)
    def test_should_factcheck_message_too_short(self):
        """Test that short messages are skipped."""
        result = asyncio.run(self.handler.should_factcheck_message(self.mock_message))
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
    
    def test_format_factcheck_response(self):
        """Test factcheck response formatting."""
        test_response = "This is a test factcheck response."
        formatted = self.handler._format_factcheck_response(test_response)
        
        self.assertIn("🔍 **Faktencheck & Ergänzungen:**", formatted)
        self.assertIn(test_response, formatted)
    
    def test_format_factcheck_response_truncation(self):
        """Test that long responses are truncated."""
        # Create a response longer than 2000 characters
        long_response = "x" * 2500
        formatted = self.handler._format_factcheck_response(long_response)
        
        self.assertLessEqual(len(formatted), 2000)
        self.assertIn("*(gekürzt)*", formatted)
    
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', True)
    def test_get_statistics(self):
        """Test statistics gathering."""
        stats = asyncio.run(self.handler.get_statistics())
        
        self.assertIn("users_on_cooldown", stats)
        self.assertIn("openai_available", stats)
        self.assertIn("factcheck_enabled", stats)
        self.assertIn("probability_percent", stats)
        self.assertIn("min_length", stats)
        
        self.assertIsInstance(stats["users_on_cooldown"], int)
        self.assertIsInstance(stats["factcheck_enabled"], bool)
    
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', True)
    async def test_handle_factcheck_success(self):
        """Test successful factcheck handling."""
        # Mock OpenAI service
        mock_response = "Test factcheck response"
        with patch.object(self.handler.openai_service, 'get_factcheck', return_value=mock_response):
            # Mock message reply method
            self.mock_message.reply = AsyncMock()
            
            result = await self.handler.handle_factcheck(self.mock_message)
            
            self.assertTrue(result)
            self.mock_message.reply.assert_called_once()
    
    @patch('handlers.factcheck_handler.Config.FACTCHECK_ENABLED', True)
    async def test_handle_factcheck_no_response(self):
        """Test factcheck handling when no response is received."""
        # Mock OpenAI service to return None
        with patch.object(self.handler.openai_service, 'get_factcheck', return_value=None):
            result = await self.handler.handle_factcheck(self.mock_message)
            
            self.assertFalse(result)


if __name__ == '__main__':
    unittest.main()
