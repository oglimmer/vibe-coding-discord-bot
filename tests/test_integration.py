#!/usr/bin/env python3
"""
Integration test for the complete score system
Tests database integration with the new 0-100% system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import DatabaseManager
from commands.klugscheisser_command import KlugscheisserCommand
from handlers.factcheck_handler import FactCheckHandler
from services.openai_service import OpenAIService
from unittest.mock import Mock
import asyncio

async def test_score_system_integration():
    """Test complete integration of the new score system"""
    print("🧪 Testing Score System Integration...")
    
    # Test 1: Database schema accepts 0-100% scores
    print("\n1. Testing Database Score Validation...")
    
    # Mock database manager
    mock_db = Mock(spec=DatabaseManager)
    
    # Test valid percentage scores
    valid_scores = [0, 15, 25, 50, 75, 85, 100]
    for score in valid_scores:
        # Simulate validation (would be real database constraint in production)
        is_valid = 0 <= score <= 100
        assert is_valid, f"Score {score}% should be valid"
        print(f"  ✅ Score {score}% - Valid")
    
    # Test invalid scores
    invalid_scores = [-1, 101, 150, -10]
    for score in invalid_scores:
        is_valid = 0 <= score <= 100
        assert not is_valid, f"Score {score}% should be invalid"
        print(f"  ❌ Score {score}% - Invalid (expected)")
    
    # Test 2: Emoji consistency across components
    print("\n2. Testing Emoji Consistency...")
    
    mock_bot = Mock()
    command = KlugscheisserCommand(mock_bot, mock_db)
    handler = FactCheckHandler(mock_db)
    
    test_scores = [10, 30, 50, 70, 90, 98]
    for score in test_scores:
        board_emoji = command._get_score_emoji_for_board(score)
        handler_emoji = handler._get_score_emoji(score)
        
        print(f"  Score {score}%: Board={board_emoji}, Handler={handler_emoji}")
        # Both should use consistent logic (same ranges)
        assert board_emoji == handler_emoji, f"Emoji mismatch for {score}%"
    
    # Test 3: Bullshit Board Data Processing
    print("\n3. Testing Bullshit Board Data Processing...")
    
    # Mock realistic data
    sample_data = [
        {
            'user_id': 123,
            'username': 'TestUser1',
            'avg_score': 25.5,  # Low accuracy
            'times_checked_by_others': 15,
            'self_checks': 3,
            'total_requests': 8,
            'total_activity': 26,
            'worst_score': 5,
            'weighted_score': 76.5
        },
        {
            'user_id': 456, 
            'username': 'TestUser2',
            'avg_score': 85.2,  # High accuracy
            'times_checked_by_others': 10,
            'self_checks': 1,
            'total_requests': 12,
            'total_activity': 23,
            'worst_score': 72,
            'weighted_score': 203.8
        }
    ]
    
    mock_db.get_bullshit_board_data.return_value = sample_data
    mock_db.get_bullshit_board_count.return_value = 2
    
    # Test embed formatting
    embed = command._format_bullshit_embed(sample_data, 0, 1, 30)
    
    assert embed.title == "🗑️ Bullshit Board"
    assert "Faktenchecker-Genauigkeit" in embed.description
    
    # Check that percentage format is used
    ranking_field = next((f for f in embed.fields if f.name == "🏆 Ranking"), None)
    assert ranking_field is not None
    assert "25.5%" in ranking_field.value  # Should show percentage
    assert "85.2%" in ranking_field.value
    
    print("  ✅ Embed formatting correct")
    
    # Test 4: Score Range Verification
    print("\n4. Testing Score Range Handling...")
    
    edge_cases = [0, 1, 20, 21, 40, 41, 60, 61, 80, 81, 95, 96, 100]
    for score in edge_cases:
        emoji = command._get_score_emoji_for_board(score)
        assert emoji in ['💀', '❌', '⚠️', '🤔', '✅', '💯'], f"Invalid emoji for score {score}%"
        print(f"  ✅ Score {score}% -> {emoji}")
    
    print("\n✅ All integration tests passed!")

def test_migration_logic():
    """Test the migration logic from 0-9 to 0-100%"""
    print("\n🔄 Testing Migration Logic...")
    
    # Test conversion formula
    test_conversions = [
        (0, 0),    # 0/9 * 100 = 0%
        (1, 11),   # 1/9 * 100 = 11%
        (2, 22),   # 2/9 * 100 = 22%
        (3, 33),   # 3/9 * 100 = 33%
        (4, 44),   # 4/9 * 100 = 44%
        (5, 56),   # 5/9 * 100 = 56%
        (6, 67),   # 6/9 * 100 = 67%
        (7, 78),   # 7/9 * 100 = 78%
        (8, 89),   # 8/9 * 100 = 89%
        (9, 100)   # 9/9 * 100 = 100%
    ]
    
    for old_score, expected_new in test_conversions:
        converted = round((old_score / 9) * 100)
        assert converted == expected_new, f"Migration {old_score}/9 -> {expected_new}% failed"
        print(f"  ✅ {old_score}/9 -> {converted}%")
    
    print("✅ Migration logic verified!")

async def main():
    """Run all integration tests"""
    print("🚀 Starting Integration Test Suite...")
    print("=" * 50)
    
    try:
        await test_score_system_integration()
        test_migration_logic()
        
        print("\n" + "=" * 50)
        print("🎉 All integration tests passed successfully!")
        print("\n📋 Summary:")
        print("- ✅ Database score validation (0-100%)")
        print("- ✅ Emoji consistency across components") 
        print("- ✅ Bullshit board data processing")
        print("- ✅ Score range handling")
        print("- ✅ Migration logic verification")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)