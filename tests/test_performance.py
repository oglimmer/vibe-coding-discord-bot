"""
Performance tests for the 1337 Game role system.
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import time
import asyncio
import sys
import os
from datetime import datetime

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
from utils.game_1337 import Game1337Manager
from bot.config import Config


class TestPerformance(unittest.TestCase):
    """Test performance characteristics of the role system."""

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

    def test_rank_calculation_performance(self):
        """Test performance of rank calculation for many players."""
        start_time = time.time()
        
        # Create 10,000 player stats objects
        player_count = 10000
        stats_objects = []
        
        for i in range(player_count):
            stats = Game1337PlayerStats(
                user_id=f"user{i}",
                username=f"Player{i}",
                guild_id="guild123",
                total_wins=i % 50,  # 0-49 wins
                total_games=max((i % 50) + 10, 1),
                best_time_ms=15000 + (i % 5000),
                worst_time_ms=45000 + (i % 10000),
                avg_time_ms=30000 + (i % 7500),
                current_streak=i % 10,
                max_streak=i % 20
            )
            stats_objects.append(stats)
        
        creation_time = time.time() - start_time
        
        # Test rank calculation performance
        rank_start = time.time()
        rank_counts = {"Recruit": 0, "Leet Sergeant": 0, "Leet Commander": 0, "Leet General": 0}
        
        for stats in stats_objects:
            rank = stats.rank_title
            rank_counts[rank] += 1
        
        rank_calculation_time = time.time() - rank_start
        
        # Test win percentage calculation performance
        percentage_start = time.time()
        total_percentage = 0.0
        
        for stats in stats_objects:
            total_percentage += stats.win_percentage
        
        percentage_calculation_time = time.time() - percentage_start
        
        total_time = time.time() - start_time
        
        # Performance assertions (these are generous to account for test environment)
        self.assertLess(creation_time, 5.0, "Object creation should be fast")
        self.assertLess(rank_calculation_time, 1.0, "Rank calculation should be fast")
        self.assertLess(percentage_calculation_time, 1.0, "Percentage calculation should be fast")
        self.assertLess(total_time, 10.0, "Total processing should be fast")
        
        # Verify all ranks are represented
        for rank in rank_counts:
            self.assertGreater(rank_counts[rank], 0, f"Should have players with {rank} rank")
        
        print(f"Performance results for {player_count} players:")
        print(f"  Object creation: {creation_time:.3f}s")
        print(f"  Rank calculation: {rank_calculation_time:.3f}s")
        print(f"  Percentage calculation: {percentage_calculation_time:.3f}s")
        print(f"  Total time: {total_time:.3f}s")
        print(f"  Rank distribution: {rank_counts}")

    def test_role_mapping_performance(self):
        """Test performance of role ID mapping."""
        ranks = ["Leet Sergeant", "Leet Commander", "Leet General", "Recruit", "Invalid"]
        iterations = 100000
        
        start_time = time.time()
        
        for _ in range(iterations):
            for rank in ranks:
                self.game_manager.get_role_id_for_rank(rank)
        
        elapsed_time = time.time() - start_time
        
        # Should handle 500,000 lookups quickly
        self.assertLess(elapsed_time, 5.0, "Role mapping should be very fast")
        
        print(f"Role mapping performance: {iterations * len(ranks)} lookups in {elapsed_time:.3f}s")
        print(f"Average: {(elapsed_time / (iterations * len(ranks))) * 1000000:.2f} microseconds per lookup")

    async def test_concurrent_role_assignment_performance(self):
        """Test performance of concurrent role assignments."""
        # Mock database session
        mock_session = AsyncMock()
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Mock guild and roles
        mock_guild = MagicMock()
        mock_member = MagicMock()
        mock_member.roles = []
        mock_role = MagicMock()
        
        mock_guild.get_member.return_value = mock_member
        mock_guild.get_role.return_value = mock_role
        self.mock_bot.get_guild.return_value = mock_guild
        
        # Mock player stats
        mock_stats = Game1337PlayerStats(
            user_id="test", username="Test", guild_id="guild",
            total_wins=5, total_games=10, best_time_ms=30000,
            worst_time_ms=35000, avg_time_ms=32500, current_streak=2, max_streak=3
        )
        
        # Test concurrent assignments
        concurrent_count = 100
        start_time = time.time()
        
        with patch.object(self.game_manager, 'get_player_stats', return_value=mock_stats):
            tasks = []
            for i in range(concurrent_count):
                task = self.game_manager.assign_rank_roles(f"user{i}", "guild123")
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
        
        elapsed_time = time.time() - start_time
        
        # Should handle 100 concurrent assignments reasonably quickly
        self.assertLess(elapsed_time, 10.0, "Concurrent role assignments should be efficient")
        
        print(f"Concurrent role assignment performance: {concurrent_count} assignments in {elapsed_time:.3f}s")
        print(f"Average: {(elapsed_time / concurrent_count) * 1000:.2f} milliseconds per assignment")

    def test_serialization_performance(self):
        """Test performance of stats serialization."""
        # Create stats objects
        stats_objects = []
        for i in range(1000):
            stats = Game1337PlayerStats(
                user_id=f"user{i}",
                username=f"Player{i}",
                guild_id="guild123",
                total_wins=i % 25,
                total_games=max((i % 25) + 5, 1),
                best_time_ms=20000 + (i % 2000),
                worst_time_ms=40000 + (i % 4000),
                avg_time_ms=30000 + (i % 3000),
                current_streak=i % 8,
                max_streak=i % 15
            )
            stats_objects.append(stats)
        
        # Test serialization performance
        start_time = time.time()
        serialized_data = []
        
        for stats in stats_objects:
            serialized_data.append(stats.to_dict())
        
        serialization_time = time.time() - start_time
        
        # Should serialize 1000 objects quickly
        self.assertLess(serialization_time, 2.0, "Serialization should be fast")
        self.assertEqual(len(serialized_data), 1000)
        
        # Verify serialized data integrity
        for i, data in enumerate(serialized_data):
            self.assertEqual(data['user_id'], f"user{i}")
            self.assertIn('rank_title', data)
            self.assertIn('win_percentage', data)
        
        print(f"Serialization performance: 1000 objects in {serialization_time:.3f}s")
        print(f"Average: {(serialization_time / 1000) * 1000:.2f} milliseconds per object")

    async def test_database_operation_performance(self):
        """Test performance of database operations."""
        # Mock database session with realistic delay
        mock_session = AsyncMock()
        
        async def mock_execute(*args, **kwargs):
            await asyncio.sleep(0.001)  # Simulate 1ms database latency
        
        async def mock_commit(*args, **kwargs):
            await asyncio.sleep(0.001)  # Simulate 1ms commit time
        
        mock_session.execute = mock_execute
        mock_session.commit = mock_commit
        
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = mock_session
        self.mock_db_manager.get_session.return_value = mock_context_manager
        
        # Test multiple database operations
        operation_count = 50
        start_time = time.time()
        
        tasks = []
        for i in range(operation_count):
            task = self.game_manager.update_player_stats(
                user_id=f"user{i}",
                username=f"Player{i}",
                guild_id="guild123",
                is_winner=(i % 5 == 0),  # Every 5th player wins
                play_time_ms=30000 + (i * 100),
                is_early_bird=(i % 3 == 0),  # Every 3rd player is early bird
                game_date="2025-06-08"
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        elapsed_time = time.time() - start_time
        
        # Should handle 50 operations with mocked latency efficiently
        self.assertLess(elapsed_time, 5.0, "Database operations should be efficient")
        
        print(f"Database operation performance: {operation_count} operations in {elapsed_time:.3f}s")
        print(f"Average: {(elapsed_time / operation_count) * 1000:.2f} milliseconds per operation")

    def test_memory_usage_large_dataset(self):
        """Test memory usage with large datasets."""
        import gc
        
        # Get initial memory snapshot
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Create large dataset
        large_dataset = []
        dataset_size = 5000
        
        for i in range(dataset_size):
            stats = Game1337PlayerStats(
                user_id=f"user{i}",
                username=f"Player{i}",
                guild_id="guild123",
                total_wins=i % 30,
                total_games=max((i % 30) + 8, 1),
                best_time_ms=18000 + (i % 3000),
                worst_time_ms=42000 + (i % 6000),
                avg_time_ms=30000 + (i % 4500),
                current_streak=i % 12,
                max_streak=i % 25
            )
            large_dataset.append(stats)
        
        # Process all objects
        rank_distribution = {}
        for stats in large_dataset:
            rank = stats.rank_title
            rank_distribution[rank] = rank_distribution.get(rank, 0) + 1
        
        # Check memory usage
        gc.collect()
        final_objects = len(gc.get_objects())
        object_increase = final_objects - initial_objects
        
        # Memory usage should be reasonable (this is a rough check)
        self.assertLess(object_increase, dataset_size * 5, "Memory usage should be reasonable")
        
        # Clean up
        del large_dataset
        gc.collect()
        
        print(f"Memory usage test: {dataset_size} objects created")
        print(f"Object count increase: {object_increase}")
        print(f"Rank distribution: {rank_distribution}")

    def test_string_operations_performance(self):
        """Test performance of string operations in stats."""
        # Test string formatting performance
        stats_count = 10000
        start_time = time.time()
        
        formatted_strings = []
        for i in range(stats_count):
            stats = Game1337PlayerStats(
                user_id=f"user{i}",
                username=f"Player{i}",
                guild_id="guild123",
                total_wins=i % 20,
                total_games=max((i % 20) + 5, 1),
                best_time_ms=25000,
                worst_time_ms=35000,
                avg_time_ms=30000,
                current_streak=i % 5,
                max_streak=i % 10
            )
            
            formatted_strings.append(str(stats))
        
        elapsed_time = time.time() - start_time
        
        # String formatting should be fast
        self.assertLess(elapsed_time, 2.0, "String formatting should be fast")
        self.assertEqual(len(formatted_strings), stats_count)
        
        print(f"String formatting performance: {stats_count} objects in {elapsed_time:.3f}s")


class TestScalability(unittest.TestCase):
    """Test scalability of the role system."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db_manager = MagicMock()
        self.game_manager = Game1337Manager(self.mock_db_manager)

    def test_rank_calculation_scalability(self):
        """Test rank calculation with different dataset sizes."""
        dataset_sizes = [100, 1000, 5000, 10000]
        
        for size in dataset_sizes:
            start_time = time.time()
            
            rank_counts = {"Recruit": 0, "Leet Sergeant": 0, "Leet Commander": 0, "Leet General": 0}
            
            for i in range(size):
                stats = Game1337PlayerStats(
                    user_id=f"user{i}",
                    username=f"Player{i}",
                    guild_id="guild123",
                    total_wins=i % 40,  # 0-39 wins
                    total_games=max((i % 40) + 7, 1),
                    best_time_ms=20000,
                    worst_time_ms=40000,
                    avg_time_ms=30000,
                    current_streak=1,
                    max_streak=5
                )
                
                rank_counts[stats.rank_title] += 1
            
            elapsed_time = time.time() - start_time
            
            print(f"Dataset size {size}: {elapsed_time:.3f}s ({elapsed_time/size*1000:.2f}ms per object)")
            
            # Performance should scale linearly
            self.assertLess(elapsed_time, size * 0.001, f"Should scale well for {size} objects")

    def test_concurrent_processing_scalability(self):
        """Test concurrent processing with different concurrency levels."""
        async def run_concurrent_test(concurrency_level):
            # Mock database session
            mock_session = AsyncMock()
            mock_context_manager = AsyncMock()
            mock_context_manager.__aenter__.return_value = mock_session
            self.mock_db_manager.get_session.return_value = mock_context_manager
            
            start_time = time.time()
            
            tasks = []
            for i in range(concurrency_level):
                task = self.game_manager.update_player_stats(
                    user_id=f"user{i}",
                    username=f"Player{i}",
                    guild_id="guild123",
                    is_winner=(i % 10 == 0),
                    play_time_ms=30000,
                    is_early_bird=False,
                    game_date="2025-06-08"
                )
                tasks.append(task)
            
            await asyncio.gather(*tasks, return_exceptions=True)
            
            elapsed_time = time.time() - start_time
            return elapsed_time
        
        # Test different concurrency levels
        concurrency_levels = [10, 50, 100]
        
        for level in concurrency_levels:
            elapsed_time = asyncio.run(run_concurrent_test(level))
            print(f"Concurrency level {level}: {elapsed_time:.3f}s")
            
            # Should handle reasonable concurrency levels
            self.assertLess(elapsed_time, 10.0, f"Should handle {level} concurrent operations")

    def test_data_structure_efficiency(self):
        """Test efficiency of data structures used."""
        # Test dictionary access patterns used in role mapping
        role_mapping = {
            "Leet Sergeant": "123456789",
            "Leet Commander": "123456790", 
            "Leet General": "123456791"
        }
        
        lookup_count = 100000
        start_time = time.time()
        
        ranks = list(role_mapping.keys()) + ["Recruit", "Invalid"]
        
        for _ in range(lookup_count):
            for rank in ranks:
                result = role_mapping.get(rank)
        
        elapsed_time = time.time() - start_time
        
        # Dictionary lookups should be very fast
        self.assertLess(elapsed_time, 1.0, "Dictionary lookups should be very fast")
        
        print(f"Dictionary lookup efficiency: {lookup_count * len(ranks)} lookups in {elapsed_time:.3f}s")


if __name__ == '__main__':
    unittest.main(verbosity=2, buffer=True)
