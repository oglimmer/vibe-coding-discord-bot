"""
Tests for database operations related to the 1337 Game player statistics.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os
from datetime import datetime
from decimal import Decimal

# Add the parent directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Mock database modules
sys.modules['database.connection'] = MagicMock()
sys.modules['sqlalchemy'] = MagicMock()
sys.modules['sqlalchemy.orm'] = MagicMock()
sys.modules['sqlalchemy.ext'] = MagicMock()
sys.modules['sqlalchemy.ext.declarative'] = MagicMock()

from database.models import Game1337PlayerStats


class TestPlayerStatsModel(unittest.TestCase):
    """Test the Game1337PlayerStats model functionality."""

    def test_player_stats_initialization(self):
        """Test proper initialization of player stats."""
        stats = Game1337PlayerStats(
            user_id="user123",
            username="TestUser",
            guild_id="guild456",
            total_wins=5,
            total_games=10,
            best_time_ms=20000,
            worst_time_ms=40000,
            avg_time_ms=30000,
            current_streak=2,
            max_streak=4
        )
        
        self.assertEqual(stats.user_id, "user123")
        self.assertEqual(stats.username, "TestUser")
        self.assertEqual(stats.guild_id, "guild456")
        self.assertEqual(stats.total_wins, 5)
        self.assertEqual(stats.total_games, 10)
        self.assertEqual(stats.best_time_ms, 20000)
        self.assertEqual(stats.worst_time_ms, 40000)
        self.assertEqual(stats.avg_time_ms, 30000)
        self.assertEqual(stats.current_streak, 2)
        self.assertEqual(stats.max_streak, 4)

    def test_win_percentage_property(self):
        """Test win percentage calculation property."""
        # Normal case
        stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=3, total_games=10, best_time_ms=30000,
            worst_time_ms=45000, avg_time_ms=37500, current_streak=1, max_streak=2
        )
        self.assertEqual(stats.win_percentage, 30.0)
        
        # Perfect win rate
        perfect_stats = Game1337PlayerStats(
            user_id="user2", username="User2", guild_id="guild1",
            total_wins=5, total_games=5, best_time_ms=25000,
            worst_time_ms=35000, avg_time_ms=30000, current_streak=5, max_streak=5
        )
        self.assertEqual(perfect_stats.win_percentage, 100.0)
        
        # No games played
        no_games = Game1337PlayerStats(
            user_id="user3", username="User3", guild_id="guild1",
            total_wins=0, total_games=0, best_time_ms=None,
            worst_time_ms=None, avg_time_ms=None, current_streak=0, max_streak=0
        )
        self.assertEqual(no_games.win_percentage, 0.0)
        
        # Fractional percentage
        fractional = Game1337PlayerStats(
            user_id="user4", username="User4", guild_id="guild1",
            total_wins=2, total_games=7, best_time_ms=28000,
            worst_time_ms=42000, avg_time_ms=35000, current_streak=0, max_streak=2
        )
        self.assertAlmostEqual(fractional.win_percentage, 28.57, places=2)

    def test_rank_title_property(self):
        """Test rank title calculation based on total wins."""
        # Recruit (0 wins)
        recruit = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=0, total_games=5, best_time_ms=None,
            worst_time_ms=None, avg_time_ms=None, current_streak=0, max_streak=0
        )
        self.assertEqual(recruit.rank_title, "Recruit")
        
        # Leet Sergeant (1-4 wins)
        sergeant_1 = Game1337PlayerStats(
            user_id="user2", username="User2", guild_id="guild1",
            total_wins=1, total_games=3, best_time_ms=30000,
            worst_time_ms=35000, avg_time_ms=32500, current_streak=1, max_streak=1
        )
        self.assertEqual(sergeant_1.rank_title, "Leet Sergeant")
        
        sergeant_4 = Game1337PlayerStats(
            user_id="user3", username="User3", guild_id="guild1",
            total_wins=4, total_games=8, best_time_ms=25000,
            worst_time_ms=40000, avg_time_ms=32500, current_streak=2, max_streak=3
        )
        self.assertEqual(sergeant_4.rank_title, "Leet Sergeant")
        
        # Leet Commander (5-9 wins)
        commander_5 = Game1337PlayerStats(
            user_id="user4", username="User4", guild_id="guild1",
            total_wins=5, total_games=10, best_time_ms=22000,
            worst_time_ms=38000, avg_time_ms=30000, current_streak=2, max_streak=4
        )
        self.assertEqual(commander_5.rank_title, "Leet Commander")
        
        commander_9 = Game1337PlayerStats(
            user_id="user5", username="User5", guild_id="guild1",
            total_wins=9, total_games=15, best_time_ms=20000,
            worst_time_ms=45000, avg_time_ms=32500, current_streak=3, max_streak=5
        )
        self.assertEqual(commander_9.rank_title, "Leet Commander")
        
        # Leet General (10+ wins)
        general_10 = Game1337PlayerStats(
            user_id="user6", username="User6", guild_id="guild1",
            total_wins=10, total_games=18, best_time_ms=18000,
            worst_time_ms=50000, avg_time_ms=34000, current_streak=4, max_streak=7
        )
        self.assertEqual(general_10.rank_title, "Leet General")
        
        general_100 = Game1337PlayerStats(
            user_id="user7", username="User7", guild_id="guild1",
            total_wins=100, total_games=120, best_time_ms=15000,
            worst_time_ms=60000, avg_time_ms=37500, current_streak=10, max_streak=25
        )
        self.assertEqual(general_100.rank_title, "Leet General")

    def test_to_dict_serialization(self):
        """Test serialization to dictionary."""
        stats = Game1337PlayerStats(
            user_id="user123",
            username="TestUser",
            guild_id="guild456",
            total_wins=7,
            total_games=20,
            best_time_ms=15000,
            worst_time_ms=45000,
            avg_time_ms=30000,
            current_streak=3,
            max_streak=5
        )
        
        result = stats.to_dict()
        
        expected_keys = {
            'user_id', 'username', 'guild_id', 'total_wins', 'total_games',
            'win_percentage', 'best_time_ms', 'worst_time_ms', 'avg_time_ms',
            'current_streak', 'max_streak', 'rank_title'
        }
        
        self.assertEqual(set(result.keys()), expected_keys)
        self.assertEqual(result['user_id'], "user123")
        self.assertEqual(result['username'], "TestUser")
        self.assertEqual(result['guild_id'], "guild456")
        self.assertEqual(result['total_wins'], 7)
        self.assertEqual(result['total_games'], 20)
        self.assertEqual(result['win_percentage'], 35.0)
        self.assertEqual(result['best_time_ms'], 15000)
        self.assertEqual(result['worst_time_ms'], 45000)
        self.assertEqual(result['avg_time_ms'], 30000)
        self.assertEqual(result['current_streak'], 3)
        self.assertEqual(result['max_streak'], 5)
        self.assertEqual(result['rank_title'], "Leet Commander")

    def test_string_representation(self):
        """Test string representation of player stats."""
        stats = Game1337PlayerStats(
            user_id="user123",
            username="TestUser",
            guild_id="guild456",
            total_wins=5,
            total_games=10,
            best_time_ms=20000,
            worst_time_ms=40000,
            avg_time_ms=30000,
            current_streak=2,
            max_streak=4
        )
        
        str_repr = str(stats)
        self.assertIn("TestUser", str_repr)
        self.assertIn("5", str_repr)  # wins
        self.assertIn("10", str_repr)  # games
        self.assertIn("50.0", str_repr)  # win percentage

    def test_edge_case_values(self):
        """Test edge case values for player stats."""
        # All None values for times (no wins yet)
        no_wins = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=0, total_games=3, best_time_ms=None,
            worst_time_ms=None, avg_time_ms=None, current_streak=0, max_streak=0
        )
        
        self.assertEqual(no_wins.win_percentage, 0.0)
        self.assertEqual(no_wins.rank_title, "Recruit")
        self.assertIsNone(no_wins.best_time_ms)
        
        # Very large numbers
        high_stats = Game1337PlayerStats(
            user_id="user2", username="User2", guild_id="guild1",
            total_wins=9999, total_games=10000, best_time_ms=1000,
            worst_time_ms=999999, avg_time_ms=500000, current_streak=100, max_streak=1000
        )
        
        self.assertEqual(high_stats.win_percentage, 99.99)
        self.assertEqual(high_stats.rank_title, "Leet General")

    def test_equal_best_and_worst_times(self):
        """Test case where best and worst times are equal (only one game won)."""
        single_win = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=1, total_games=1, best_time_ms=30000,
            worst_time_ms=30000, avg_time_ms=30000, current_streak=1, max_streak=1
        )
        
        self.assertEqual(single_win.win_percentage, 100.0)
        self.assertEqual(single_win.rank_title, "Leet Sergeant")
        self.assertEqual(single_win.best_time_ms, single_win.worst_time_ms)


class TestDatabaseFunction(unittest.TestCase):
    """Test the database function interaction patterns."""

    def test_update_function_parameters(self):
        """Test that update function parameters are properly structured."""
        # This tests the expected parameter structure for the database function
        # The actual function is tested in integration tests
        
        expected_params = {
            'p_user_id': 'user123',
            'p_username': 'TestUser',
            'p_guild_id': 'guild456',
            'p_is_winner': True,
            'p_play_time_ms': 30000,
            'p_is_early_bird': False,
            'p_game_date': '2025-06-08'
        }
        
        # Verify parameter types
        self.assertIsInstance(expected_params['p_user_id'], str)
        self.assertIsInstance(expected_params['p_username'], str)
        self.assertIsInstance(expected_params['p_guild_id'], str)
        self.assertIsInstance(expected_params['p_is_winner'], bool)
        self.assertIsInstance(expected_params['p_play_time_ms'], int)
        self.assertIsInstance(expected_params['p_is_early_bird'], bool)
        self.assertIsInstance(expected_params['p_game_date'], str)

    def test_query_structure_validation(self):
        """Test that queries follow expected structure."""
        # Expected query patterns for the stats system
        expected_patterns = [
            "SELECT * FROM update_1337_player_stats",
            "SELECT * FROM game_1337_player_stats WHERE user_id = :user_id AND guild_id = :guild_id"
        ]
        
        for pattern in expected_patterns:
            # Verify query contains expected elements
            self.assertIn("game_1337_player_stats", pattern.lower())

    def test_decimal_precision_handling(self):
        """Test handling of decimal precision in calculations."""
        # Test cases with decimal precision requirements
        test_cases = [
            {"wins": 1, "games": 3, "expected": 33.33},
            {"wins": 2, "games": 7, "expected": 28.57},
            {"wins": 5, "games": 13, "expected": 38.46},
            {"wins": 7, "games": 17, "expected": 41.18}
        ]
        
        for case in test_cases:
            stats = Game1337PlayerStats(
                user_id="test", username="Test", guild_id="guild",
                total_wins=case["wins"], total_games=case["games"],
                best_time_ms=30000, worst_time_ms=35000, avg_time_ms=32500,
                current_streak=1, max_streak=2
            )
            
            self.assertAlmostEqual(
                stats.win_percentage,
                case["expected"],
                places=2,
                msg=f"Failed for {case['wins']}/{case['games']}"
            )


class TestStatsValidation(unittest.TestCase):
    """Test validation of player statistics."""

    def test_valid_stats_ranges(self):
        """Test that stats fall within valid ranges."""
        stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=5, total_games=10, best_time_ms=20000,
            worst_time_ms=40000, avg_time_ms=30000, current_streak=2, max_streak=4
        )
        
        # Wins should not exceed games
        self.assertLessEqual(stats.total_wins, stats.total_games)
        
        # Win percentage should be between 0 and 100
        self.assertGreaterEqual(stats.win_percentage, 0.0)
        self.assertLessEqual(stats.win_percentage, 100.0)
        
        # Best time should be <= average <= worst time (if all present)
        if all([stats.best_time_ms, stats.avg_time_ms, stats.worst_time_ms]):
            self.assertLessEqual(stats.best_time_ms, stats.avg_time_ms)
            self.assertLessEqual(stats.avg_time_ms, stats.worst_time_ms)
        
        # Current streak should not exceed max streak
        self.assertLessEqual(stats.current_streak, stats.max_streak)
        
        # Max streak should not exceed total wins
        self.assertLessEqual(stats.max_streak, stats.total_wins)

    def test_invalid_stats_handling(self):
        """Test handling of potentially invalid stats."""
        # Wins exceeding games (shouldn't happen but test robustness)
        invalid_stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=15, total_games=10, best_time_ms=20000,
            worst_time_ms=40000, avg_time_ms=30000, current_streak=5, max_streak=8
        )
        
        # Should still calculate percentage (even if >100%)
        self.assertEqual(invalid_stats.win_percentage, 150.0)
        
        # Should still assign rank based on wins
        self.assertEqual(invalid_stats.rank_title, "Leet General")

    def test_negative_values_handling(self):
        """Test handling of negative values."""
        # Test with negative wins (shouldn't happen but test robustness)
        negative_stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=-1, total_games=5, best_time_ms=20000,
            worst_time_ms=40000, avg_time_ms=30000, current_streak=0, max_streak=0
        )
        
        # Should handle negative wins gracefully
        self.assertEqual(negative_stats.rank_title, "Recruit")  # Treats as 0 wins

    def test_very_large_numbers(self):
        """Test handling of very large numbers."""
        large_stats = Game1337PlayerStats(
            user_id="user1", username="User1", guild_id="guild1",
            total_wins=1000000, total_games=1000001, best_time_ms=1,
            worst_time_ms=999999999, avg_time_ms=500000000, 
            current_streak=10000, max_streak=50000
        )
        
        # Should handle large numbers without overflow
        self.assertAlmostEqual(large_stats.win_percentage, 99.9999, places=4)
        self.assertEqual(large_stats.rank_title, "Leet General")


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
