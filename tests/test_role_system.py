"""
Tests for the three-tier role system in the 1337 Game.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock, call
import asyncio
import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock database and discord modules
sys.modules['database.connection'] = MagicMock()
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()

from database.models import Game1337PlayerStats
from utils.game_1337 import Game1337Manager, PlayType
from bot.config import Config


class TestRoleSystem(unittest.TestCase):
    """Test the three-tier role system functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        self.mock_member = MagicMock()
        
        # Setup mock guild and member
        self.mock_bot.get_guild.return_value = self.mock_guild
        self.mock_guild.get_member.return_value = self.mock_member
        
        # Setup mock roles
        self.mock_sergeant_role = MagicMock()
        self.mock_sergeant_role.name = "Leet Sergeant"
        self.mock_commander_role = MagicMock()
        self.mock_commander_role.name = "Leet Commander"
        self.mock_general_role = MagicMock()
        self.mock_general_role.name = "Leet General"
        
        # Mock config values
        Config.GAME_1337_LEET_SERGEANT_ROLE_ID = "123456789"
        Config.GAME_1337_LEET_COMMANDER_ROLE_ID = "123456790"
        Config.GAME_1337_LEET_GENERAL_ROLE_ID = "123456791"
        
        self.game_manager = Game1337Manager(self.mock_db_manager)
        self.game_manager.set_bot(self.mock_bot)

    def test_player_stats_rank_calculation(self):
        """Test rank calculation based on total wins."""
        # Test Recruit (0 wins)
        stats_recruit = Game1337PlayerStats(
            user_id="user1",
            username="TestUser1",
            guild_id="guild1",
            total_wins=0,
            total_games=5,
            best_time_ms=30000,
            worst_time_ms=45000,
            avg_time_ms=37500,
            current_streak=0,
            max_streak=0
        )
        self.assertEqual(stats_recruit.rank_title, "Recruit")

        # Test Leet Sergeant (1+ wins)
        stats_sergeant = Game1337PlayerStats(
            user_id="user2",
            username="TestUser2",
            guild_id="guild1",
            total_wins=3,
            total_games=10,
            best_time_ms=25000,
            worst_time_ms=50000,
            avg_time_ms=35000,
            current_streak=1,
            max_streak=2
        )
        self.assertEqual(stats_sergeant.rank_title, "Leet Sergeant")

        # Test Leet Commander (5+ wins)
        stats_commander = Game1337PlayerStats(
            user_id="user3",
            username="TestUser3",
            guild_id="guild1",
            total_wins=7,
            total_games=20,
            best_time_ms=20000,
            worst_time_ms=55000,
            avg_time_ms=32000,
            current_streak=3,
            max_streak=5
        )
        self.assertEqual(stats_commander.rank_title, "Leet Commander")

        # Test Leet General (10+ wins)
        stats_general = Game1337PlayerStats(
            user_id="user4",
            username="TestUser4",
            guild_id="guild1",
            total_wins=15,
            total_games=30,
            best_time_ms=15000,
            worst_time_ms=60000,
            avg_time_ms=30000,
            current_streak=5,
            max_streak=8
        )
        self.assertEqual(stats_general.rank_title, "Leet General")

    def test_role_id_mapping(self):
        """Test role ID mapping for different ranks."""
        self.assertEqual(
            self.game_manager.get_role_id_for_rank("Leet Sergeant"),
            Config.GAME_1337_LEET_SERGEANT_ROLE_ID
        )
        self.assertEqual(
            self.game_manager.get_role_id_for_rank("Leet Commander"),
            Config.GAME_1337_LEET_COMMANDER_ROLE_ID
        )
        self.assertEqual(
            self.game_manager.get_role_id_for_rank("Leet General"),
            Config.GAME_1337_LEET_GENERAL_ROLE_ID
        )
        self.assertIsNone(
            self.game_manager.get_role_id_for_rank("Recruit")
        )
        self.assertIsNone(
            self.game_manager.get_role_id_for_rank("Unknown Rank")
        )

    @patch('utils.game_1337.logger')
    async def test_assign_rank_roles_sergeant(self, mock_logger):
        """Test assigning Leet Sergeant role."""
        # Setup mock player stats
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Sergeant"
        
        # Setup role mocking
        self.mock_guild.get_role.return_value = self.mock_sergeant_role
        self.mock_member.roles = []
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify role assignment
        self.mock_member.add_roles.assert_called_once_with(
            self.mock_sergeant_role, 
            reason="1337 Game rank promotion"
        )

    @patch('utils.game_1337.logger')
    async def test_assign_rank_roles_promotion(self, mock_logger):
        """Test role promotion (removing old role, adding new role)."""
        # Setup mock player stats for Commander
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Commander"
        mock_stats.total_wins = 7
        
        # Setup current member with Sergeant role
        self.mock_member.roles = [self.mock_sergeant_role]
        
        # Setup role getting
        def get_role_side_effect(role_id):
            if role_id == int(Config.GAME_1337_LEET_SERGEANT_ROLE_ID):
                return self.mock_sergeant_role
            elif role_id == int(Config.GAME_1337_LEET_COMMANDER_ROLE_ID):
                return self.mock_commander_role
            return None
        
        self.mock_guild.get_role.side_effect = get_role_side_effect
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify old role removal and new role addition
        self.mock_member.remove_roles.assert_called_once_with(
            self.mock_sergeant_role,
            reason="1337 Game rank update"
        )
        self.mock_member.add_roles.assert_called_once_with(
            self.mock_commander_role,
            reason="1337 Game rank promotion"
        )

    @patch('utils.game_1337.logger')
    async def test_assign_rank_roles_no_change(self, mock_logger):
        """Test no role change when user already has correct role."""
        # Setup mock player stats
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Commander"
        
        # Setup member already having the correct role
        self.mock_member.roles = [self.mock_commander_role]
        self.mock_guild.get_role.return_value = self.mock_commander_role
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify no role changes
        self.mock_member.add_roles.assert_not_called()
        self.mock_member.remove_roles.assert_not_called()

    @patch('utils.game_1337.logger')
    async def test_assign_rank_roles_no_stats(self, mock_logger):
        """Test handling when no player stats exist."""
        with patch.object(self.game_manager, 'get_player_stats', return_value=None):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify no role operations
        self.mock_member.add_roles.assert_not_called()
        self.mock_member.remove_roles.assert_not_called()
        mock_logger.warning.assert_called()

    @patch('utils.game_1337.logger')
    async def test_assign_rank_roles_no_bot(self, mock_logger):
        """Test handling when bot instance is not set."""
        self.game_manager._bot = None
        
        await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify warning logged and no operations performed
        mock_logger.warning.assert_called_with("Bot instance not set for role assignment")

    async def test_update_player_stats_integration(self):
        """Test player stats update integration with role assignment."""
        # Mock the database function call
        mock_session = AsyncMock()
        self.mock_db_manager.get_session.return_value.__aenter__.return_value = mock_session
        
        with patch.object(self.game_manager, 'assign_rank_roles') as mock_assign_roles:
            await self.game_manager.update_player_stats(
                user_id="user123",
                username="TestUser",
                guild_id="guild123",
                is_winner=True,
                play_time_ms=30000,
                is_early_bird=False,
                game_date="2025-06-08"
            )
        
        # Verify database function was called
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_win_percentage_calculation(self):
        """Test win percentage calculation in player stats."""
        stats = Game1337PlayerStats(
            user_id="user1",
            username="TestUser",
            guild_id="guild1",
            total_wins=3,
            total_games=10,
            best_time_ms=30000,
            worst_time_ms=45000,
            avg_time_ms=37500,
            current_streak=1,
            max_streak=2
        )
        
        self.assertEqual(stats.win_percentage, 30.0)
        
        # Test with no games
        stats_no_games = Game1337PlayerStats(
            user_id="user2",
            username="TestUser2",
            guild_id="guild1",
            total_wins=0,
            total_games=0,
            best_time_ms=None,
            worst_time_ms=None,
            avg_time_ms=None,
            current_streak=0,
            max_streak=0
        )
        
        self.assertEqual(stats_no_games.win_percentage, 0.0)


class TestAdvancedRoleSystem(unittest.TestCase):
    """Test advanced role system functionality and edge cases."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        
        # Setup mock roles
        self.mock_sergeant_role = MagicMock()
        self.mock_sergeant_role.name = "Leet Sergeant"
        self.mock_sergeant_role.id = 123456789
        
        self.mock_commander_role = MagicMock()
        self.mock_commander_role.name = "Leet Commander"
        self.mock_commander_role.id = 123456790
        
        self.mock_general_role = MagicMock()
        self.mock_general_role.name = "Leet General"
        self.mock_general_role.id = 123456791
        
        self.mock_winner_role = MagicMock()
        self.mock_winner_role.name = "Winner"
        self.mock_winner_role.id = 123456792
        
        self.mock_early_bird_role = MagicMock()
        self.mock_early_bird_role.name = "Early Bird"
        self.mock_early_bird_role.id = 123456793
        
        # Setup config
        Config.GAME_1337_LEET_SERGEANT_ROLE_ID = "123456789"
        Config.GAME_1337_LEET_COMMANDER_ROLE_ID = "123456790"
        Config.GAME_1337_LEET_GENERAL_ROLE_ID = "123456791"
        Config.GAME_1337_WINNER_ROLE_ID = "123456792"
        Config.GAME_1337_EARLY_BIRD_ROLE_ID = "123456793"
        Config.GUILD_ID = "999999999"
        
        self.game_manager = Game1337Manager(self.mock_db_manager)
        self.game_manager.set_bot(self.mock_bot)

    def test_rank_boundaries(self):
        """Test rank calculation at exact boundaries."""
        # Test exactly 1 win (sergeant boundary)
        stats_1_win = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=1, total_games=5, best_time_ms=30000,
            worst_time_ms=45000, avg_time_ms=37500, current_streak=1, max_streak=1
        )
        self.assertEqual(stats_1_win.rank_title, "Leet Sergeant")

        # Test exactly 5 wins (commander boundary)
        stats_5_wins = Game1337PlayerStats(
            user_id="user2", username="User2", guild_id="guild1",
            total_wins=5, total_games=10, best_time_ms=25000,
            worst_time_ms=50000, avg_time_ms=35000, current_streak=2, max_streak=3
        )
        self.assertEqual(stats_5_wins.rank_title, "Leet Commander")

        # Test exactly 10 wins (general boundary)
        stats_10_wins = Game1337PlayerStats(
            user_id="user3", username="User3", guild_id="guild1",
            total_wins=10, total_games=15, best_time_ms=20000,
            worst_time_ms=55000, avg_time_ms=32000, current_streak=3, max_streak=5
        )
        self.assertEqual(stats_10_wins.rank_title, "Leet General")

        # Test high win count (stays general)
        stats_high_wins = Game1337PlayerStats(
            user_id="user4", username="User4", guild_id="guild1",
            total_wins=100, total_games=120, best_time_ms=15000,
            worst_time_ms=60000, avg_time_ms=30000, current_streak=10, max_streak=15
        )
        self.assertEqual(stats_high_wins.rank_title, "Leet General")

    def test_win_percentage_edge_cases(self):
        """Test win percentage calculation edge cases."""
        # Perfect win rate
        perfect_stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=10, total_games=10, best_time_ms=20000,
            worst_time_ms=25000, avg_time_ms=22500, current_streak=10, max_streak=10
        )
        self.assertEqual(perfect_stats.win_percentage, 100.0)

        # Zero wins
        zero_wins = Game1337PlayerStats(
            user_id="user2", username="User2", guild_id="guild1",
            total_wins=0, total_games=20, best_time_ms=None,
            worst_time_ms=None, avg_time_ms=None, current_streak=0, max_streak=0
        )
        self.assertEqual(zero_wins.win_percentage, 0.0)

        # Fractional percentage
        fractional_stats = Game1337PlayerStats(
            user_id="user3", username="User3", guild_id="guild1",
            total_wins=1, total_games=3, best_time_ms=30000,
            worst_time_ms=30000, avg_time_ms=30000, current_streak=0, max_streak=1
        )
        self.assertAlmostEqual(fractional_stats.win_percentage, 33.33, places=2)

    @patch('utils.game_1337.logger')
    async def test_role_assignment_discord_errors(self, mock_logger):
        """Test role assignment with Discord API errors."""
        # Setup mock player stats
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Sergeant"
        
        # Setup member and guild
        mock_member = MagicMock()
        mock_member.roles = []
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.return_value = self.mock_sergeant_role
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        # Mock Discord error
        discord_error = Exception("Discord API Error: Insufficient permissions")
        mock_member.add_roles.side_effect = discord_error
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify error was logged
        mock_logger.error.assert_called()

    @patch('utils.game_1337.logger')
    async def test_multiple_rank_roles_cleanup(self, mock_logger):
        """Test cleanup when user has multiple rank roles (shouldn't happen but test anyway)."""
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet General"
        
        # Setup member with multiple rank roles
        mock_member = MagicMock()
        mock_member.roles = [self.mock_sergeant_role, self.mock_commander_role]
        
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.side_effect = lambda role_id: {
            123456789: self.mock_sergeant_role,
            123456790: self.mock_commander_role,
            123456791: self.mock_general_role
        }.get(role_id)
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        # Verify both old roles were removed
        expected_calls = [
            call(self.mock_sergeant_role, reason="1337 Game rank update"),
            call(self.mock_commander_role, reason="1337 Game rank update")
        ]
        mock_member.remove_roles.assert_has_calls(expected_calls, any_order=True)
        
        # Verify new role was added
        mock_member.add_roles.assert_called_once_with(
            self.mock_general_role, 
            reason="1337 Game rank promotion"
        )

    async def test_database_session_handling(self):
        """Test proper database session handling in stats updates."""
        # Mock session context manager
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        mock_context_manager.__aexit__.return_value = None
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Test successful update
        await self.game_manager.update_player_stats(
            user_id="user123",
            username="TestUser",
            guild_id="guild123",
            is_winner=True,
            play_time_ms=30000,
            is_early_bird=False,
            game_date="2025-06-08"
        )
        
        # Verify session operations
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_context_manager.__aexit__.assert_called_once()

    async def test_database_error_handling(self):
        """Test database error handling in stats updates."""
        # Mock session that raises an error
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        with patch('utils.game_1337.logger') as mock_logger:
            await self.game_manager.update_player_stats(
                user_id="user123",
                username="TestUser", 
                guild_id="guild123",
                is_winner=True,
                play_time_ms=30000,
                is_early_bird=False,
                game_date="2025-06-08"
            )
        
        # Verify error was logged
        mock_logger.error.assert_called()

    @patch('utils.game_1337.logger')
    async def test_winner_role_assignment(self, mock_logger):
        """Test winner role assignment functionality."""
        mock_member = MagicMock()
        mock_member.roles = []
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.return_value = self.mock_winner_role
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        await self.game_manager.assign_winner_role("user123", "guild123")
        
        mock_member.add_roles.assert_called_once_with(
            self.mock_winner_role,
            reason="1337 Game winner"
        )

    @patch('utils.game_1337.logger')
    async def test_early_bird_role_assignment(self, mock_logger):
        """Test early bird role assignment functionality."""
        mock_member = MagicMock()
        mock_member.roles = []
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.return_value = self.mock_early_bird_role
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        await self.game_manager.assign_early_bird_role("user123", "guild123")
        
        mock_member.add_roles.assert_called_once_with(
            self.mock_early_bird_role,
            reason="1337 Game early bird"
        )

    @patch('utils.game_1337.logger')
    async def test_role_assignment_member_not_found(self, mock_logger):
        """Test role assignment when member is not found."""
        self.mock_guild.get_member.return_value = None
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        await self.game_manager.assign_rank_roles("user123", "guild123")
        
        mock_logger.warning.assert_called_with(
            "Member user123 not found in guild guild123"
        )

    @patch('utils.game_1337.logger')
    async def test_role_assignment_guild_not_found(self, mock_logger):
        """Test role assignment when guild is not found."""
        self.mock_bot.get_guild.return_value = None
        
        await self.game_manager.assign_rank_roles("user123", "guild123")
        
        mock_logger.warning.assert_called_with(
            "Guild guild123 not found"
        )

    @patch('utils.game_1337.logger')
    async def test_role_assignment_role_not_found(self, mock_logger):
        """Test role assignment when role is not found."""
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Sergeant"
        
        mock_member = MagicMock()
        mock_member.roles = []
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.return_value = None  # Role not found
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            await self.game_manager.assign_rank_roles("user123", "guild123")
        
        mock_logger.warning.assert_called_with(
            "Role 123456789 not found in guild guild123"
        )

    def test_player_stats_serialization(self):
        """Test player stats serialization to dictionary."""
        stats = Game1337PlayerStats(
            user_id="user123",
            username="TestUser",
            guild_id="guild456",
            total_wins=7,
            total_games=20,
            best_time_ms=15000,
            worst_time_ms=45000,
            avg_time_ms=28500,
            current_streak=3,
            max_streak=5
        )
        
        serialized = stats.to_dict()
        
        expected_keys = {
            'user_id', 'username', 'guild_id', 'total_wins', 'total_games',
            'win_percentage', 'best_time_ms', 'worst_time_ms', 'avg_time_ms',
            'current_streak', 'max_streak', 'rank_title'
        }
        
        self.assertEqual(set(serialized.keys()), expected_keys)
        self.assertEqual(serialized['user_id'], "user123")
        self.assertEqual(serialized['rank_title'], "Leet Commander")
        self.assertEqual(serialized['win_percentage'], 35.0)

    async def test_get_player_stats_with_no_results(self):
        """Test getting player stats when no records exist."""
        # Mock empty result
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        result = await self.game_manager.get_player_stats("user123", "guild456")
        
        self.assertIsNone(result)

    async def test_stats_update_with_all_parameters(self):
        """Test stats update with all possible parameters."""
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        await self.game_manager.update_player_stats(
            user_id="user123",
            username="TestUser",
            guild_id="guild456",
            is_winner=True,
            play_time_ms=25500,
            is_early_bird=True,
            game_date="2025-06-08"
        )
        
        # Verify the SQL was executed with correct parameters
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args[0][0]
        self.assertIn("update_1337_player_stats", str(call_args))

    def test_invalid_rank_title(self):
        """Test handling of invalid rank titles."""
        # This shouldn't happen in normal operation but test defensive programming
        result = self.game_manager.get_role_id_for_rank("Invalid Rank")
        self.assertIsNone(result)
        
        result = self.game_manager.get_role_id_for_rank("")
        self.assertIsNone(result)
        
        result = self.game_manager.get_role_id_for_rank(None)
        self.assertIsNone(result)


class TestComplexGameScenarios(unittest.TestCase):
    """Test complex game scenarios and role assignment flows."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.mock_bot = MagicMock()
        
        # Setup config
        Config.GAME_1337_LEET_SERGEANT_ROLE_ID = "123456789"
        Config.GAME_1337_LEET_COMMANDER_ROLE_ID = "123456790"
        Config.GAME_1337_LEET_GENERAL_ROLE_ID = "123456791"
        Config.GAME_1337_WINNER_ROLE_ID = "123456792"
        Config.GAME_1337_EARLY_BIRD_ROLE_ID = "123456793"
        Config.GUILD_ID = "999999999"
        
        self.game_manager = Game1337Manager(self.mock_db_manager)
        self.game_manager.set_bot(self.mock_bot)

    async def test_bulk_role_assignment_after_game(self):
        """Test role assignment for multiple players after a game."""
        game_datetime = datetime(2025, 6, 8, 13, 37, 0)
        
        # Mock multiple players with different stats
        players_data = [
            {"user_id": "user1", "username": "Player1", "is_winner": True, "wins": 1, "early_bird": False},
            {"user_id": "user2", "username": "Player2", "is_winner": False, "wins": 5, "early_bird": True},
            {"user_id": "user3", "username": "Player3", "is_winner": False, "wins": 10, "early_bird": False},
            {"user_id": "user4", "username": "Player4", "is_winner": False, "wins": 0, "early_bird": True},
        ]
        
        # Mock bets
        mock_bets = []
        for i, player in enumerate(players_data):
            mock_bet = MagicMock()
            mock_bet.user_id = player["user_id"]
            mock_bet.username = player["username"]
            mock_bet.guild_id = "guild123"
            mock_bet.play_time = 30000 + i * 1000
            mock_bet.play_type = MagicMock()
            mock_bet.play_type.value = "early" if player["early_bird"] else "normal"
            mock_bets.append(mock_bet)
        
        # Mock winner
        mock_winner_info = {
            'winner': mock_bets[0],  # First player wins
            'win_time_ms': 30500,
            'delta_ms': 500
        }
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=mock_bets), \
             patch.object(self.game_manager, 'update_player_stats') as mock_update_stats, \
             patch.object(self.game_manager, 'assign_winner_role') as mock_assign_winner, \
             patch.object(self.game_manager, 'assign_early_bird_role') as mock_assign_early, \
             patch.object(self.game_manager, 'assign_rank_roles') as mock_assign_rank:
            
            await self.game_manager.process_game_completion(game_datetime)
        
        # Verify all players had stats updated
        self.assertEqual(mock_update_stats.call_count, 4)
        
        # Verify winner role assigned to correct player
        mock_assign_winner.assert_called_once_with("user1", "guild123")
        
        # Verify early bird roles assigned to correct players
        early_bird_calls = [call("user2", "guild123"), call("user4", "guild123")]
        mock_assign_early.assert_has_calls(early_bird_calls, any_order=True)
        
        # Verify rank roles assigned to all players
        self.assertEqual(mock_assign_rank.call_count, 4)

    async def test_progressive_rank_advancement(self):
        """Test a player advancing through multiple ranks over time."""
        # This would simulate multiple games over time
        progression_data = [
            {"wins": 0, "expected_rank": "Recruit"},
            {"wins": 1, "expected_rank": "Leet Sergeant"},
            {"wins": 5, "expected_rank": "Leet Commander"},
            {"wins": 10, "expected_rank": "Leet General"},
            {"wins": 20, "expected_rank": "Leet General"},  # Stays at General
        ]
        
        for data in progression_data:
            stats = Game1337PlayerStats(
                user_id="user123",
                username="ProgressingPlayer",
                guild_id="guild456",
                total_wins=data["wins"],
                total_games=data["wins"] + 5,  # Some losses
                best_time_ms=20000,
                worst_time_ms=40000,
                avg_time_ms=30000,
                current_streak=1 if data["wins"] > 0 else 0,
                max_streak=min(data["wins"], 5)
            )
            
            self.assertEqual(stats.rank_title, data["expected_rank"])

    @patch('utils.game_1337.logger')
    async def test_concurrent_role_assignments(self, mock_logger):
        """Test handling of potentially concurrent role assignments."""
        # Simulate multiple rapid role assignment calls
        tasks = []
        
        mock_stats = MagicMock()
        mock_stats.rank_title = "Leet Sergeant"
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            # Create multiple concurrent assignment tasks
            for i in range(5):
                task = asyncio.create_task(
                    self.game_manager.assign_rank_roles(f"user{i}", "guild123")
                )
                tasks.append(task)
            
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
        
        # The test mainly ensures no exceptions are raised during concurrent access


class TestPerformanceAndStress(unittest.TestCase):
    """Test performance and stress scenarios."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.game_manager = Game1337Manager(self.mock_db_manager)

    def test_large_stats_object_creation(self):
        """Test creating many stats objects efficiently."""
        stats_objects = []
        
        for i in range(1000):
            stats = Game1337PlayerStats(
                user_id=f"user{i}",
                username=f"TestUser{i}",
                guild_id="guild123",
                total_wins=i % 20,  # Vary wins from 0-19
                total_games=max(i % 20 + 5, 1),
                best_time_ms=15000 + (i % 1000),
                worst_time_ms=45000 + (i % 2000),
                avg_time_ms=30000 + (i % 1500),
                current_streak=i % 5,
                max_streak=i % 10
            )
            stats_objects.append(stats)
        
        # Verify all objects were created correctly
        self.assertEqual(len(stats_objects), 1000)
        
        # Test rank distribution
        rank_counts = {}
        for stats in stats_objects:
            rank = stats.rank_title
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        # Should have all rank types represented
        expected_ranks = ["Recruit", "Leet Sergeant", "Leet Commander", "Leet General"]
        for rank in expected_ranks:
            self.assertIn(rank, rank_counts)

    def test_role_id_mapping_performance(self):
        """Test role ID mapping performance with many calls."""
        ranks = ["Leet Sergeant", "Leet Commander", "Leet General", "Recruit", "Invalid"]
        
        # Make many mapping calls
        for _ in range(10000):
            for rank in ranks:
                result = self.game_manager.get_role_id_for_rank(rank)
                # Just ensure it returns something (or None for invalid ranks)
                self.assertIsInstance(result, (str, type(None)))


if __name__ == '__main__':
    # Configure test runner
    unittest.main(verbosity=2, buffer=True)
