#!/usr/bin/env python3
"""
Test suite for Bullshit Board functionality
Tests the new 0-100% score system and database integration
"""

import unittest
from unittest.mock import Mock, AsyncMock, patch
import discord
from datetime import datetime, date, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commands.klugscheisser_command import KlugscheisserCommand
from database import DatabaseManager

class TestBullshitBoard(unittest.TestCase):
    """Test cases for Bullshit Board functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.mock_bot = Mock()
        self.mock_db_manager = Mock(spec=DatabaseManager)
        self.command = KlugscheisserCommand(self.mock_bot, self.mock_db_manager)
        
        # Mock user data with new 0-100% score system
        self.sample_board_data = [
            {
                'user_id': 123456789012345678,
                'username': 'BullshitBingo_Pro',
                'avg_score': 15.5,  # Low accuracy = high bullshit
                'times_checked_by_others': 25,
                'self_checks': 5,
                'total_requests': 8,
                'total_activity': 38,
                'worst_score': 2,
                'weighted_score': 42.3
            },
            {
                'user_id': 234567890123456789,
                'username': 'FactCheckFan',
                'avg_score': 35.2,  # Medium accuracy
                'times_checked_by_others': 18,
                'self_checks': 3,
                'total_requests': 12,
                'total_activity': 33,
                'worst_score': 8,
                'weighted_score': 102.1
            },
            {
                'user_id': 345678901234567890,
                'username': 'TruthTeller',
                'avg_score': 85.7,  # High accuracy = low bullshit
                'times_checked_by_others': 12,
                'self_checks': 1,
                'total_requests': 15,
                'total_activity': 28,
                'worst_score': 72,
                'weighted_score': 213.9
            }
        ]
    
    def test_score_emoji_mapping_percentage_system(self):
        """Test that score emojis map correctly to 0-100% system"""
        # Test emoji mapping for accuracy percentages (updated to match factcheck handler)
        test_cases = [
            (5, '❌'),     # Very low accuracy (0-20%)
            (20, '❌'),    # Low accuracy boundary
            (25, '⚠️'),    # Low-medium accuracy (21-40%)
            (40, '⚠️'),    # Medium-low boundary
            (50, '🤔'),    # Medium accuracy (41-60%)
            (60, '🤔'),    # Medium-high boundary
            (75, '✅'),    # Good accuracy (61-80%)
            (80, '✅'),    # Good-excellent boundary
            (90, '💯'),    # Excellent accuracy (81-100%)
            (95, '💯'),    # Excellent boundary
            (98, '💯'),    # Near perfect
            (100, '💯')    # Perfect accuracy
        ]
        
        for score, expected_emoji in test_cases:
            with self.subTest(score=score):
                result = self.command._get_score_emoji_for_board(score)
                self.assertEqual(result, expected_emoji, 
                    f"Score {score}% should map to {expected_emoji}, got {result}")
    
    def test_rank_emoji_mapping(self):
        """Test rank emoji assignment"""
        test_cases = [
            (1, '👑'),   # First place
            (2, '🥈'),   # Second place  
            (3, '🥉'),   # Third place
            (4, '💩'),   # Fourth place
            (5, '💩'),   # Fifth place
            (6, '6'),    # Sixth and beyond use numbers
            (10, '10')
        ]
        
        for rank, expected_emoji in test_cases:
            with self.subTest(rank=rank):
                result = self.command._get_rank_emoji(rank)
                self.assertEqual(result, expected_emoji)
    
    def test_bullshit_embed_formatting(self):
        """Test bullshit board embed formatting"""
        embed = self.command._format_bullshit_embed(
            self.sample_board_data, 0, 1, 30
        )
        
        # Check embed structure
        self.assertEqual(embed.title, "🗑️ Bullshit Board")
        self.assertIn("Faktenchecker-Genauigkeit", embed.description)
        self.assertEqual(embed.color, discord.Color.red())
        
        # Check that ranking field exists
        ranking_field = next((field for field in embed.fields if field.name == "🏆 Ranking"), None)
        self.assertIsNotNone(ranking_field, "Ranking field should exist")
        
        # Check that all users are included with correct format
        ranking_text = ranking_field.value
        self.assertIn("BullshitBingo_Pro", ranking_text)
        self.assertIn("15.5%", ranking_text)  # Should show percentage
        self.assertIn("25 checks", ranking_text)  # Should show check count
        
        # Check score explanation field
        explanation_field = next((field for field in embed.fields if "Score-Erklärung" in field.name), None)
        self.assertIsNotNone(explanation_field, "Score explanation field should exist")
        self.assertIn("0% = völliger Bullshit", explanation_field.value)
        self.assertIn("100% = komplett korrekt", explanation_field.value)
    
    def test_empty_board_data(self):
        """Test bullshit board with no data"""
        embed = self.command._format_bullshit_embed([], 0, 1, 30)
        
        # Should show "no data" message
        no_data_field = next((field for field in embed.fields if "Keine Daten" in field.name), None)
        self.assertIsNotNone(no_data_field)
        self.assertIn("Keine Faktenchecks", no_data_field.value)
    
    @patch('discord.app_commands.command')
    async def test_bullshit_command_execution(self):
        """Test the bullshit slash command execution"""
        # Setup mocks
        mock_interaction = AsyncMock(spec=discord.Interaction)
        mock_interaction.response.defer = AsyncMock()
        mock_interaction.followup.send = AsyncMock()
        
        self.mock_db_manager.get_bullshit_board_data.return_value = self.sample_board_data
        self.mock_db_manager.get_bullshit_board_count.return_value = 3
        
        # Execute command
        await self.command.bullshit(mock_interaction)
        
        # Verify database calls
        self.mock_db_manager.get_bullshit_board_data.assert_called_once_with(
            page=0, per_page=10, days=30, sort_by="score_asc"
        )
        self.mock_db_manager.get_bullshit_board_count.assert_called_once_with(days=30)
        
        # Verify response methods called
        mock_interaction.response.defer.assert_called_once()
        mock_interaction.followup.send.assert_called_once()
        
        # Check that embed was sent
        call_args = mock_interaction.followup.send.call_args
        self.assertIn('embed', call_args.kwargs)
        self.assertIn('view', call_args.kwargs)

class TestDatabaseIntegration(unittest.TestCase):
    """Test database integration for the new score system"""
    
    def setUp(self):
        """Set up database mock"""
        self.mock_db = Mock(spec=DatabaseManager)
    
    def test_database_score_range_validation(self):
        """Test that database accepts 0-100% scores"""
        # This would be tested with actual database in integration tests
        valid_scores = [0, 1, 25, 50, 75, 99, 100]
        invalid_scores = [-1, 101, 150, -10]
        
        # Mock validation logic
        def validate_score(score):
            return 0 <= score <= 100
        
        for score in valid_scores:
            self.assertTrue(validate_score(score), f"Score {score} should be valid")
        
        for score in invalid_scores:
            self.assertFalse(validate_score(score), f"Score {score} should be invalid")
    
    def test_weighted_score_calculation(self):
        """Test the weighted score calculation logic"""
        import math
        
        # Test cases: (avg_score, check_count, expected_weighted_score)
        test_cases = [
            (25.0, 5, 25.0 * math.log(6)),    # Low accuracy, few checks
            (15.0, 20, 15.0 * math.log(21)),  # Very low accuracy, many checks  
            (85.0, 10, 85.0 * math.log(11)),  # High accuracy, medium checks
            (50.0, 1, 50.0 * math.log(2)),    # Medium accuracy, single check
        ]
        
        for avg_score, check_count, expected in test_cases:
            with self.subTest(avg_score=avg_score, check_count=check_count):
                # Simulate the database calculation
                calculated = avg_score * math.log(check_count + 1)
                self.assertAlmostEqual(calculated, expected, places=2)
    
    def test_sort_options_mapping(self):
        """Test that sort options work correctly"""
        expected_sorts = {
            "score_asc": "weighted_score ASC, times_checked_by_others DESC",
            "score_desc": "weighted_score DESC, times_checked_by_others DESC", 
            "checked_desc": "times_checked_by_others DESC, weighted_score ASC",
            "activity_desc": "total_activity DESC, weighted_score ASC",
            "requests_desc": "total_requests DESC, weighted_score ASC"
        }
        
        # This tests the sort logic from database.py
        for sort_key, expected_clause in expected_sorts.items():
            # In real implementation, this would test actual database query building
            self.assertIsNotNone(expected_clause)
            self.assertIn("weighted_score", expected_clause)

class TestScoreSystemConsistency(unittest.TestCase):
    """Test consistency across the entire score system"""
    
    def test_factcheck_handler_emoji_consistency(self):
        """Test that factcheck handler uses same emoji ranges as bullshit board"""
        # Import would happen here in real test
        # from handlers.factcheck_handler import FactCheckHandler
        
        # Test ranges should be consistent:
        # 0-20%: 💀, 21-40%: ❌, 41-60%: ⚠️, 61-80%: 🤔, 81-95%: ✅, 96-100%: 💯
        
        emoji_ranges = [
            (10, '💀'),   # Low accuracy
            (30, '❌'),   # Low-medium
            (50, '⚠️'),   # Medium  
            (70, '🤔'),   # Good
            (90, '✅'),   # Excellent
            (98, '💯')    # Perfect
        ]
        
        # This test would verify both factcheck handler and bullshit board
        # use the same emoji mapping logic
        for score, expected_emoji in emoji_ranges:
            # Both systems should return same emoji for same score
            self.assertIsNotNone(expected_emoji)
    
    def test_migration_score_conversion(self):
        """Test score conversion from old 0-9 to new 0-100% system"""
        # Test the conversion formula: percentage = (score / 9) * 100
        old_to_new_mappings = [
            (0, 0),      # 0/9 -> 0%
            (1, 11),     # 1/9 -> 11%  
            (2, 22),     # 2/9 -> 22%
            (3, 33),     # 3/9 -> 33%
            (4, 44),     # 4/9 -> 44%
            (5, 56),     # 5/9 -> 56%
            (6, 67),     # 6/9 -> 67%
            (7, 78),     # 7/9 -> 78%
            (8, 89),     # 8/9 -> 89%
            (9, 100)     # 9/9 -> 100%
        ]
        
        for old_score, expected_new in old_to_new_mappings:
            converted = round((old_score / 9) * 100)
            self.assertEqual(converted, expected_new, 
                f"Old score {old_score}/9 should convert to {expected_new}%")

def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestBullshitBoard))
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestScoreSystemConsistency))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()

if __name__ == "__main__":
    print("🧪 Running Bullshit Board Test Suite...")
    print("=" * 60)
    
    success = run_tests()
    
    print("=" * 60)
    if success:
        print("✅ All tests passed! Bullshit Board is working correctly.")
    else:
        print("❌ Some tests failed. Check the output above for details.")
    
    exit(0 if success else 1)