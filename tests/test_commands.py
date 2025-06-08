import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import sys
import os

# Add the parent directory to the Python path so we can import src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock the database connection module before importing anything that uses it
sys.modules['src.database.connection'] = MagicMock()

from src.commands.greetings import GreetingsCommand

class TestGreetingsCommand(unittest.TestCase):

    def setUp(self):
        # Create a mock database connection for each test
        self.mock_db_connection = MagicMock()

    def test_greetings_command_with_users(self):
        # Arrange
        command = GreetingsCommand(self.mock_db_connection)
        mock_ctx = MagicMock()
        mock_ctx.send = AsyncMock()
        
        # Mock the get_greeted_users method to return test data
        with patch.object(command, 'get_greeted_users', return_value=['User1', 'User2']):
            # Act
            asyncio.run(command.execute(mock_ctx))

            # Assert
            mock_ctx.send.assert_called_once()
            call_args = mock_ctx.send.call_args[0][0]
            self.assertIn('User1', call_args)
            self.assertIn('User2', call_args)
            self.assertIn('greeted today', call_args)

    def test_greetings_command_no_users(self):
        # Arrange
        command = GreetingsCommand(self.mock_db_connection)
        mock_ctx = MagicMock()
        mock_ctx.send = AsyncMock()
        
        # Mock the get_greeted_users method to return empty list
        with patch.object(command, 'get_greeted_users', return_value=[]):
            # Act
            asyncio.run(command.execute(mock_ctx))

            # Assert
            mock_ctx.send.assert_called_once_with("No one has greeted today yet.")

    def test_greet_user(self):
        # Arrange
        command = GreetingsCommand(self.mock_db_connection)
        user = "TestUser"
        
        # Mock the save_greeting_to_db method
        with patch.object(command, 'save_greeting_to_db') as mock_save:
            # Act
            asyncio.run(command.greet_user(user))

            # Assert
            mock_save.assert_called_once_with(user)

if __name__ == '__main__':
    unittest.main()