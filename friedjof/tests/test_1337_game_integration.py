"""
Integration tests for the 1337 Game system with role management.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import sys
import os
from datetime import datetime, timedelta

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

from database.models import Game1337PlayerStats, Game1337Bet, PlayType
from utils.game_1337 import Game1337Manager
from bot.config import Config


class TestGame1337Integration(unittest.TestCase):
    """Integration tests for the complete 1337 Game flow."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.mock_bot = MagicMock()
        self.mock_guild = MagicMock()
        
        # Setup config
        Config.GAME_1337_LEET_SERGEANT_ROLE_ID = "123456789"
        Config.GAME_1337_LEET_COMMANDER_ROLE_ID = "123456790" 
        Config.GAME_1337_LEET_GENERAL_ROLE_ID = "123456791"
        Config.GAME_1337_WINNER_ROLE_ID = "123456792"
        Config.GAME_1337_EARLY_BIRD_ROLE_ID = "123456793"
        Config.GUILD_ID = "999999999"
        
        self.game_manager = Game1337Manager(self.mock_db_manager)
        self.game_manager.set_bot(self.mock_bot)
        
        # Setup mock roles
        self.mock_roles = {
            "sergeant": MagicMock(name="Leet Sergeant", id=123456789),
            "commander": MagicMock(name="Leet Commander", id=123456790),
            "general": MagicMock(name="Leet General", id=123456791),
            "winner": MagicMock(name="Winner", id=123456792),
            "early_bird": MagicMock(name="Early Bird", id=123456793)
        }

    async def test_complete_game_flow_first_time_winner(self):
        """Test complete game flow for a first-time winner."""
        # Setup: New player wins their first game
        game_time = datetime(2025, 6, 8, 13, 37, 0)
        
        # Mock the bet
        mock_bet = MagicMock()
        mock_bet.user_id = "newplayer123"
        mock_bet.username = "NewPlayer"
        mock_bet.guild_id = "guild456"
        mock_bet.play_time = 30000  # 30 seconds
        mock_bet.play_type = MagicMock()
        mock_bet.play_type.value = "normal"
        
        # Mock winner determination
        mock_winner_info = {
            'winner': mock_bet,
            'win_time_ms': 30050,  # 50ms after target
            'delta_ms': 50
        }
        
        # Mock database session
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Mock member and guild
        mock_member = MagicMock()
        mock_member.roles = []  # No existing roles
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.side_effect = lambda role_id: {
            123456789: self.mock_roles["sergeant"],
            123456792: self.mock_roles["winner"]
        }.get(role_id)
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        # Mock player stats after first win
        mock_new_stats = Game1337PlayerStats(
            user_id="newplayer123",
            username="NewPlayer", 
            guild_id="guild456",
            total_wins=1,
            total_games=1,
            best_time_ms=30000,
            worst_time_ms=30000,
            avg_time_ms=30000,
            current_streak=1,
            max_streak=1
        )
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=[mock_bet]), \
             patch.object(self.game_manager, 'get_player_stats', return_value=mock_new_stats):
            
            await self.game_manager.process_game_completion(game_time)
        
        # Verify stats were updated
        mock_session.execute.assert_called()
        mock_session.commit.assert_called()
        
        # Verify winner role was assigned
        mock_member.add_roles.assert_any_call(
            self.mock_roles["winner"],
            reason="1337 Game winner"
        )
        
        # Verify sergeant rank role was assigned (first win)
        mock_member.add_roles.assert_any_call(
            self.mock_roles["sergeant"],
            reason="1337 Game rank promotion"
        )

    async def test_complete_game_flow_rank_promotion(self):
        """Test complete game flow with rank promotion."""
        game_time = datetime(2025, 6, 8, 13, 37, 0)
        
        # Setup: Player with 4 wins gets their 5th win (promotion to Commander)
        mock_bet = MagicMock()
        mock_bet.user_id = "veteran123"
        mock_bet.username = "VeteranPlayer"
        mock_bet.guild_id = "guild456"
        mock_bet.play_time = 25000
        mock_bet.play_type = MagicMock()
        mock_bet.play_type.value = "normal"
        
        mock_winner_info = {
            'winner': mock_bet,
            'win_time_ms': 25100,
            'delta_ms': 100
        }
        
        # Mock database session
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Mock member with existing Sergeant role
        mock_member = MagicMock()
        mock_member.roles = [self.mock_roles["sergeant"]]
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.side_effect = lambda role_id: {
            123456789: self.mock_roles["sergeant"],
            123456790: self.mock_roles["commander"],
            123456792: self.mock_roles["winner"]
        }.get(role_id)
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        # Mock updated stats (5 wins = Commander)
        mock_updated_stats = Game1337PlayerStats(
            user_id="veteran123",
            username="VeteranPlayer",
            guild_id="guild456",
            total_wins=5,
            total_games=8,
            best_time_ms=20000,
            worst_time_ms=35000,
            avg_time_ms=27500,
            current_streak=2,
            max_streak=3
        )
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=[mock_bet]), \
             patch.object(self.game_manager, 'get_player_stats', return_value=mock_updated_stats):
            
            await self.game_manager.process_game_completion(game_time)
        
        # Verify old rank role was removed
        mock_member.remove_roles.assert_called_with(
            self.mock_roles["sergeant"],
            reason="1337 Game rank update"
        )
        
        # Verify new rank role was assigned
        mock_member.add_roles.assert_any_call(
            self.mock_roles["commander"],
            reason="1337 Game rank promotion"
        )
        
        # Verify winner role was also assigned
        mock_member.add_roles.assert_any_call(
            self.mock_roles["winner"],
            reason="1337 Game winner"
        )

    async def test_early_bird_bet_processing(self):
        """Test early bird bet placement and immediate role assignment."""
        # Mock member and guild
        mock_member = MagicMock()
        mock_member.roles = []
        self.mock_guild.get_member.return_value = mock_member
        self.mock_guild.get_role.return_value = self.mock_roles["early_bird"]
        self.mock_bot.get_guild.return_value = self.mock_guild
        
        # Mock database operations
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        with patch.object(self.game_manager, 'assign_early_bird_role') as mock_assign_early:
            await self.game_manager.place_early_bet(
                user_id="earlybird123",
                username="EarlyBird",
                guild_id="guild456",
                play_time_ms=20000
            )
        
        # Verify early bird role was assigned immediately
        mock_assign_early.assert_called_once_with("earlybird123", "guild456")

    async def test_multiple_players_game_completion(self):
        """Test game completion with multiple players having different outcomes."""
        game_time = datetime(2025, 6, 8, 13, 37, 0)
        
        # Setup multiple players
        players = [
            {
                "user_id": "winner123", "username": "Winner", "play_time": 30000,
                "is_winner": True, "is_early": False, "current_wins": 0
            },
            {
                "user_id": "early123", "username": "EarlyBird", "play_time": 25000,
                "is_winner": False, "is_early": True, "current_wins": 4
            },
            {
                "user_id": "veteran123", "username": "Veteran", "play_time": 35000,
                "is_winner": False, "is_early": False, "current_wins": 9
            }
        ]
        
        # Create mock bets
        mock_bets = []
        for player in players:
            mock_bet = MagicMock()
            mock_bet.user_id = player["user_id"]
            mock_bet.username = player["username"]
            mock_bet.guild_id = "guild456"
            mock_bet.play_time = player["play_time"]
            mock_bet.play_type = MagicMock()
            mock_bet.play_type.value = "early" if player["is_early"] else "normal"
            mock_bets.append(mock_bet)
        
        # Winner is the first player
        mock_winner_info = {
            'winner': mock_bets[0],
            'win_time_ms': 30100,
            'delta_ms': 100
        }
        
        # Mock database session
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Mock player stats lookup
        def mock_get_stats(user_id, guild_id):
            player = next(p for p in players if p["user_id"] == user_id)
            wins = player["current_wins"] + (1 if player["is_winner"] else 0)
            return Game1337PlayerStats(
                user_id=user_id,
                username=player["username"],
                guild_id=guild_id,
                total_wins=wins,
                total_games=wins + 3,
                best_time_ms=20000,
                worst_time_ms=40000,
                avg_time_ms=30000,
                current_streak=1 if wins > 0 else 0,
                max_streak=wins
            )
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=mock_bets), \
             patch.object(self.game_manager, 'get_player_stats', side_effect=mock_get_stats), \
             patch.object(self.game_manager, 'assign_winner_role') as mock_assign_winner, \
             patch.object(self.game_manager, 'assign_early_bird_role') as mock_assign_early, \
             patch.object(self.game_manager, 'assign_rank_roles') as mock_assign_rank:
            
            await self.game_manager.process_game_completion(game_time)
        
        # Verify winner role assigned to correct player
        mock_assign_winner.assert_called_once_with("winner123", "guild456")
        
        # Verify early bird role assigned to correct player
        mock_assign_early.assert_called_once_with("early123", "guild456")
        
        # Verify rank roles assigned to all players
        self.assertEqual(mock_assign_rank.call_count, 3)
        
        # Verify stats updated for all players
        self.assertEqual(mock_session.execute.call_count, 3)

    async def test_error_recovery_during_game_completion(self):
        """Test error recovery during game completion processing."""
        game_time = datetime(2025, 6, 8, 13, 37, 0)
        
        # Mock a single bet
        mock_bet = MagicMock()
        mock_bet.user_id = "player123"
        mock_bet.username = "Player"
        mock_bet.guild_id = "guild456"
        mock_bet.play_time = 30000
        mock_bet.play_type = MagicMock()
        mock_bet.play_type.value = "normal"
        
        mock_winner_info = {
            'winner': mock_bet,
            'win_time_ms': 30100,
            'delta_ms': 100
        }
        
        # Mock database session with error on first call, success on retry
        mock_session = AsyncMock()
        mock_session.execute.side_effect = [Exception("Database error"), None]
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=[mock_bet]), \
             patch('utils.game_1337.logger') as mock_logger:
            
            await self.game_manager.process_game_completion(game_time)
        
        # Verify error was logged
        mock_logger.error.assert_called()

    def test_stats_calculation_accuracy(self):
        """Test accuracy of statistics calculations."""
        # Test various win rate scenarios
        test_cases = [
            {"wins": 0, "games": 0, "expected_rate": 0.0},
            {"wins": 5, "games": 10, "expected_rate": 50.0},
            {"wins": 1, "games": 3, "expected_rate": 33.33},
            {"wins": 10, "games": 10, "expected_rate": 100.0},
            {"wins": 7, "games": 23, "expected_rate": 30.43}
        ]
        
        for case in test_cases:
            stats = Game1337PlayerStats(
                user_id="test",
                username="Test",
                guild_id="guild",
                total_wins=case["wins"],
                total_games=case["games"],
                best_time_ms=20000 if case["wins"] > 0 else None,
                worst_time_ms=40000 if case["wins"] > 0 else None,
                avg_time_ms=30000 if case["wins"] > 0 else None,
                current_streak=1 if case["wins"] > 0 else 0,
                max_streak=case["wins"]
            )
            
            self.assertAlmostEqual(
                stats.win_percentage, 
                case["expected_rate"], 
                places=2,
                msg=f"Failed for wins={case['wins']}, games={case['games']}"
            )

    async def test_concurrent_game_completions(self):
        """Test handling of multiple concurrent game completions."""
        # This tests the system's robustness under concurrent load
        game_times = [
            datetime(2025, 6, 8, 13, 37, 0),
            datetime(2025, 6, 8, 14, 37, 0),
            datetime(2025, 6, 8, 15, 37, 0)
        ]
        
        # Mock minimal data for each game
        mock_bet = MagicMock()
        mock_bet.user_id = "player123"
        mock_bet.username = "Player"
        mock_bet.guild_id = "guild456"
        mock_bet.play_time = 30000
        mock_bet.play_type = MagicMock()
        mock_bet.play_type.value = "normal"
        
        mock_winner_info = {
            'winner': mock_bet,
            'win_time_ms': 30100,
            'delta_ms': 100
        }
        
        # Mock database operations
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        with patch.object(self.game_manager, 'determine_winner', return_value=mock_winner_info), \
             patch.object(self.game_manager, 'get_game_leaderboard', return_value=[mock_bet]), \
             patch.object(self.game_manager, 'get_player_stats', return_value=None), \
             patch.object(self.game_manager, 'assign_winner_role'), \
             patch.object(self.game_manager, 'assign_rank_roles'):
            
            # Process multiple games concurrently
            tasks = [
                self.game_manager.process_game_completion(game_time)
                for game_time in game_times
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Verify no exceptions occurred
            for result in results:
                self.assertIsNone(result, "No exceptions should occur during concurrent processing")


class TestRoleMigrationScenarios(unittest.TestCase):
    """Test scenarios for migrating from old role system to new three-tier system."""

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
        
        self.game_manager = Game1337Manager(self.mock_db_manager)
        self.game_manager.set_bot(self.mock_bot)

    async def test_player_with_old_system_stats(self):
        """Test handling players who have stats from the old two-role system."""
        # Simulate a player who had wins under the old system
        legacy_stats = Game1337PlayerStats(
            user_id="legacy123",
            username="LegacyPlayer",
            guild_id="guild456",
            total_wins=8,  # 8 wins = Commander rank in new system
            total_games=15,
            best_time_ms=18000,
            worst_time_ms=45000,
            avg_time_ms=31500,
            current_streak=3,
            max_streak=6
        )
        
        # Verify correct rank assignment under new system
        self.assertEqual(legacy_stats.rank_title, "Leet Commander")
        self.assertEqual(legacy_stats.win_percentage, 53.33)

    async def test_bulk_role_migration(self):
        """Test bulk migration of many players to the new role system."""
        # Simulate migrating 100 players with various win counts
        players_to_migrate = []
        
        for i in range(100):
            wins = i % 25  # 0-24 wins
            stats = Game1337PlayerStats(
                user_id=f"player{i}",
                username=f"Player{i}",
                guild_id="guild456",
                total_wins=wins,
                total_games=wins + 5,
                best_time_ms=20000,
                worst_time_ms=40000,
                avg_time_ms=30000,
                current_streak=1 if wins > 0 else 0,
                max_streak=min(wins, 10)
            )
            players_to_migrate.append(stats)
        
        # Count expected rank distribution
        rank_counts = {"Recruit": 0, "Leet Sergeant": 0, "Leet Commander": 0, "Leet General": 0}
        for stats in players_to_migrate:
            rank_counts[stats.rank_title] += 1
        
        # Verify expected distribution
        # 0 wins: Recruit (1 player: index 0)
        # 1-4 wins: Sergeant (4 players: index 1, 26, 51, 76) 
        # 5-9 wins: Commander (5 players: index 5, 30, 55, 80)
        # 10+ wins: General (remaining players)
        
        self.assertGreater(rank_counts["Recruit"], 0)
        self.assertGreater(rank_counts["Leet Sergeant"], 0)
        self.assertGreater(rank_counts["Leet Commander"], 0)
        self.assertGreater(rank_counts["Leet General"], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
