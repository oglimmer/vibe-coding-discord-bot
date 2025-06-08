import unittest
from unittest.mock import MagicMock, patch
from src.handlers.message_handler import MessageHandler

class TestMessageHandler(unittest.TestCase):

    @patch('src.handlers.message_handler.discord')
    def setUp(self, mock_discord):
        self.handler = MessageHandler()
        self.mock_message = MagicMock()
        self.mock_message.content = "Hello"
        self.mock_message.channel.send = MagicMock()

    def test_handle_greeting_message(self):
        self.handler.handle_message(self.mock_message)
        self.mock_message.channel.send.assert_called_once_with("👋")

    def test_handle_non_greeting_message(self):
        self.mock_message.content = "Goodbye"
        self.handler.handle_message(self.mock_message)
        self.mock_message.channel.send.assert_not_called()

if __name__ == '__main__':
    unittest.main()