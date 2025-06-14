import unittest
from unittest.mock import Mock, patch
from datetime import datetime, date, time, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from game.game_1337_logic import Game1337Logic


class TestGame1337Logic(unittest.TestCase):
    """Test the core logic of the 1337 game without Discord dependencies"""
    
    def setUp(self):
        self.db_manager = Mock()
        self.logic = Game1337Logic(self.db_manager)

    def test_parse_game_start_time_basic(self):
        """Test parsing basic game start time"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            result = self.logic.parse_game_start_time()
            expected = time(13, 37, 0, 0)
            self.assertEqual(result, expected)

    def test_parse_game_start_time_with_microseconds(self):
        """Test parsing game start time with microseconds"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:05.500'):
            result = self.logic.parse_game_start_time()
            expected = time(13, 37, 5, 500000)
            self.assertEqual(result, expected)

    def test_parse_timestamp_full_format(self):
        """Test parsing full timestamp format (hh:mm:ss.SSS)"""
        game_date = date(2023, 12, 25)
        result = self.logic.parse_timestamp("13:37:05.250", game_date)
        expected = datetime(2023, 12, 25, 13, 37, 5, 250000)
        self.assertEqual(result, expected)

    def test_parse_timestamp_seconds_only(self):
        """Test parsing seconds-only format (ss)"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            game_date = date(2023, 12, 25)
            result = self.logic.parse_timestamp("42", game_date)
            expected = datetime(2023, 12, 25, 13, 37, 42, 0)
            self.assertEqual(result, expected)

    def test_parse_timestamp_seconds_with_ms(self):
        """Test parsing seconds with milliseconds (ss.SSS)"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            game_date = date(2023, 12, 25)
            result = self.logic.parse_timestamp("25.750", game_date)
            expected = datetime(2023, 12, 25, 13, 37, 25, 750000)
            self.assertEqual(result, expected)

    def test_parse_timestamp_invalid_format(self):
        """Test parsing invalid timestamp format returns None"""
        game_date = date(2023, 12, 25)
        result = self.logic.parse_timestamp("invalid", game_date)
        self.assertIsNone(result)

    def test_parse_timestamp_invalid_hour(self):
        """Test parsing timestamp with invalid hour returns None"""
        game_date = date(2023, 12, 25)
        result = self.logic.parse_timestamp("25:37:05.000", game_date)
        self.assertIsNone(result)

    def test_parse_timestamp_invalid_minute(self):
        """Test parsing timestamp with invalid minute returns None"""
        game_date = date(2023, 12, 25)
        result = self.logic.parse_timestamp("13:70:05.000", game_date)
        self.assertIsNone(result)

    def test_parse_timestamp_invalid_second(self):
        """Test parsing timestamp with invalid second returns None"""
        game_date = date(2023, 12, 25)
        result = self.logic.parse_timestamp("13:37:70.000", game_date)
        self.assertIsNone(result)

    def test_parse_timestamp_edge_case_13_37_59(self):
        """Test parsing edge case of 13:37:59"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            game_date = date(2023, 12, 25)
            result = self.logic.parse_timestamp("59", game_date)
            expected = datetime(2023, 12, 25, 13, 37, 59, 0)
            self.assertEqual(result, expected)

    def test_parse_timestamp_edge_case_13_37_00(self):
        """Test parsing edge case of 13:37:00"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            game_date = date(2023, 12, 25)
            result = self.logic.parse_timestamp("0", game_date)
            expected = datetime(2023, 12, 25, 13, 37, 0, 0)
            self.assertEqual(result, expected)

    def test_format_time_with_ms(self):
        """Test time formatting with milliseconds"""
        dt = datetime(2023, 12, 25, 13, 37, 5, 250000)
        result = self.logic.format_time_with_ms(dt)
        self.assertEqual(result, "13:37:05.250")

    def test_format_time_with_ms_zero_ms(self):
        """Test time formatting with zero milliseconds"""
        dt = datetime(2023, 12, 25, 13, 37, 5, 0)
        result = self.logic.format_time_with_ms(dt)
        self.assertEqual(result, "13:37:05.000")

    def test_get_game_date(self):
        """Test getting current game date"""
        with patch('game.game_1337_logic.datetime') as mock_datetime:
            mock_now = Mock()
            mock_now.date.return_value = date(2023, 12, 25)
            mock_datetime.now.return_value = mock_now
            result = self.logic.get_game_date()
            self.assertEqual(result, date(2023, 12, 25))

    def test_get_yesterday_date(self):
        """Test getting yesterday's date logic"""
        with patch('game.game_1337_logic.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2023, 12, 25, 14, 30)
            result = self.logic.get_yesterday_date()
            self.assertEqual(result, date(2023, 12, 24))

    def test_winner_determination_logic_single_bet(self):
        """Test winner determination logic with single valid bet"""
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        
        daily_bets = [{
            'user_id': 12345,
            'username': 'TestUser',
            'play_time': datetime(2023, 12, 25, 13, 37, 25),  # 5 seconds before win
            'bet_type': 'regular',
            'server_id': 67890
        }]
        
        # Filter valid bets (same logic as in _determine_daily_winner)
        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        
        self.assertEqual(len(valid_bets), 1)
        self.assertEqual(valid_bets[0]['username'], 'TestUser')

    def test_winner_determination_logic_no_valid_bets(self):
        """Test winner determination logic with no valid bets"""
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        
        daily_bets = [{
            'user_id': 12345,
            'username': 'TestUser',
            'play_time': datetime(2023, 12, 25, 13, 37, 35),  # 5 seconds after win
            'bet_type': 'regular',
            'server_id': 67890
        }]
        
        # Filter valid bets
        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        
        self.assertEqual(len(valid_bets), 0)

    def test_winner_determination_logic_priority_system(self):
        """Test winner determination priority system"""
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        three_seconds_before = win_time - timedelta(seconds=3)  # 13:37:27
        
        daily_bets = [
            {
                'user_id': 12345,
                'username': 'EarlyBird',
                'play_time': datetime(2023, 12, 25, 13, 37, 20),
                'bet_type': 'early_bird',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'RegularOld',
                'play_time': datetime(2023, 12, 25, 13, 37, 25),  # Before 3-second window
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12347,
                'username': 'RegularRecent',
                'play_time': datetime(2023, 12, 25, 13, 37, 28),  # Within 3-second window
                'bet_type': 'regular',
                'server_id': 67890
            }
        ]
        
        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        regular_bets = [bet for bet in valid_bets if bet['bet_type'] == 'regular']
        early_bird_bets = [bet for bet in valid_bets if bet['bet_type'] == 'early_bird']
        recent_regular_bets = [bet for bet in regular_bets if bet['play_time'] >= three_seconds_before]
        
        # Test the priority logic
        self.assertEqual(len(valid_bets), 3)
        self.assertEqual(len(regular_bets), 2)
        self.assertEqual(len(early_bird_bets), 1)
        self.assertEqual(len(recent_regular_bets), 1)
        
        # Winner should be the most recent regular bet within 3 seconds
        if recent_regular_bets:
            winner = max(regular_bets, key=lambda x: x['play_time'])
        elif regular_bets:
            winner = max(regular_bets, key=lambda x: x['play_time'])
        elif early_bird_bets:
            winner = max(early_bird_bets, key=lambda x: x['play_time'])
        else:
            winner = None
            
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularRecent')

    def test_catastrophic_event_detection(self):
        """Test detection of catastrophic events (identical timestamps)"""
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        identical_time = datetime(2023, 12, 25, 13, 37, 25)
        
        daily_bets = [
            {
                'user_id': 12345,
                'username': 'TestUser1',
                'play_time': identical_time,
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'TestUser2',
                'play_time': identical_time,
                'bet_type': 'regular',
                'server_id': 67890
            }
        ]
        
        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        winner = valid_bets[0] if valid_bets else None
        
        # Check for catastrophic event (identical times)
        if winner:
            identical_times = [bet for bet in valid_bets if bet['play_time'] == winner['play_time']]
            is_catastrophic = len(identical_times) > 1
        else:
            is_catastrophic = False
            
        self.assertTrue(is_catastrophic)
        self.assertEqual(len(identical_times), 2)

    def test_millisecond_difference_calculation(self):
        """Test calculation of millisecond difference between bet and win time"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 500000)  # 30.5 seconds
        bet_time = datetime(2023, 12, 25, 13, 37, 25, 250000)  # 25.25 seconds
        
        millisecond_diff = int((win_time - bet_time).total_seconds() * 1000)
        
        self.assertEqual(millisecond_diff, 5250)  # 5.25 seconds = 5250ms

    def test_bet_validation_future_timestamp(self):
        """Test validation that early bird timestamps must be in future"""
        current_time = datetime(2023, 12, 25, 13, 30, 0)
        bet_time = datetime(2023, 12, 25, 13, 37, 5)  # Future time
        past_time = datetime(2023, 12, 25, 13, 25, 0)  # Past time
        
        is_future_valid = bet_time > current_time
        is_past_valid = past_time > current_time
        
        self.assertTrue(is_future_valid)
        self.assertFalse(is_past_valid)

    def test_game_deadline_validation(self):
        """Test validation of game deadline (1 minute buffer after 13:37)"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            before_deadline = datetime(2023, 12, 25, 13, 37, 30)
            after_deadline = datetime(2023, 12, 25, 13, 38, 30)
            
            is_before_passed = self.logic.is_game_time_passed(before_deadline)
            is_after_passed = self.logic.is_game_time_passed(after_deadline)
            
            self.assertFalse(is_before_passed)
            self.assertTrue(is_after_passed)

    def test_validate_bet_placement_success(self):
        """Test successful bet placement validation"""
        self.db_manager.get_user_bet.return_value = None  # No existing bet
        
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            current_time = datetime(2023, 12, 25, 13, 30, 0)  # Before deadline
            result = self.logic.validate_bet_placement(12345, current_time)
            
            self.assertTrue(result['valid'])

    def test_validate_bet_placement_game_passed(self):
        """Test bet placement validation when game time has passed"""
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            current_time = datetime(2023, 12, 25, 13, 40, 0)  # After deadline
            result = self.logic.validate_bet_placement(12345, current_time)
            
            self.assertFalse(result['valid'])
            self.assertEqual(result['reason'], 'game_time_passed')

    def test_validate_bet_placement_existing_bet(self):
        """Test bet placement validation when user already has a bet"""
        existing_bet = {
            'bet_type': 'regular',
            'play_time': datetime(2023, 12, 25, 13, 30, 0)
        }
        self.db_manager.get_user_bet.return_value = existing_bet
        
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'):
            current_time = datetime(2023, 12, 25, 13, 30, 0)
            result = self.logic.validate_bet_placement(12345, current_time)
            
            self.assertFalse(result['valid'])
            self.assertEqual(result['reason'], 'existing_bet')

    def test_validate_early_bird_timestamp_success(self):
        """Test successful early bird timestamp validation"""
        current_time = datetime(2023, 12, 25, 13, 30, 0)
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'), \
             patch.object(self.logic, 'get_game_date', return_value=date(2023, 12, 25)):
            result = self.logic.validate_early_bird_timestamp("37.500", current_time)
            
            self.assertTrue(result['valid'])
            self.assertEqual(result['timestamp'], datetime(2023, 12, 25, 13, 37, 37, 500000))

    def test_validate_early_bird_timestamp_invalid_format(self):
        """Test early bird timestamp validation with invalid format"""
        current_time = datetime(2023, 12, 25, 13, 30, 0)
        with patch.object(self.logic, 'get_game_date', return_value=date(2023, 12, 25)):
            result = self.logic.validate_early_bird_timestamp("invalid", current_time)
            
            self.assertFalse(result['valid'])
            self.assertEqual(result['reason'], 'invalid_format')

    def test_validate_early_bird_timestamp_not_future(self):
        """Test early bird timestamp validation when timestamp is not in future"""
        current_time = datetime(2023, 12, 25, 13, 40, 0)  # After the proposed bet time
        with patch('game.game_1337_logic.Config.GAME_START_TIME', '13:37:00.000'), \
             patch.object(self.logic, 'get_game_date', return_value=date(2023, 12, 25)):
            result = self.logic.validate_early_bird_timestamp("5", current_time)  # 13:37:05
            
            self.assertFalse(result['valid'])
            self.assertEqual(result['reason'], 'not_future')

    def test_determine_winner_logic(self):
        """Test winner determination with game logic"""
        game_date = date(2023, 12, 25)
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        
        daily_bets = [{
            'user_id': 12345,
            'username': 'TestUser',
            'play_time': datetime(2023, 12, 25, 13, 37, 25),
            'bet_type': 'regular',
            'server_id': 67890
        }]
        
        self.db_manager.get_daily_bets.return_value = daily_bets
        
        result = self.logic.determine_winner(game_date, win_time)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['username'], 'TestUser')
        self.assertEqual(result['millisecond_diff'], 5000)  # 5 seconds difference

    def test_determine_winner_catastrophic_event(self):
        """Test winner determination with catastrophic event"""
        game_date = date(2023, 12, 25)
        win_time = datetime(2023, 12, 25, 13, 37, 30)
        identical_time = datetime(2023, 12, 25, 13, 37, 25)
        
        daily_bets = [
            {
                'user_id': 12345,
                'username': 'TestUser1',
                'play_time': identical_time,
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'TestUser2',
                'play_time': identical_time,
                'bet_type': 'regular',
                'server_id': 67890
            }
        ]
        
        self.db_manager.get_daily_bets.return_value = daily_bets
        
        result = self.logic.determine_winner(game_date, win_time)
        
        self.assertIsNotNone(result)
        self.assertTrue(result.get('catastrophic_event'))
        self.assertEqual(result['identical_count'], 2)

    def test_apply_winner_selection_rules_regular_closer(self):
        """Test when regular bet is closer to win time"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 500000)  # 30.5 seconds
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularCloser',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 100000),  # 2.4s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdFar',
                'play_time': datetime(2023, 12, 25, 13, 37, 25, 0),  # 5.5s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularCloser')
        self.assertEqual(winner['bet_type'], 'regular')

    def test_apply_winner_selection_rules_early_bird_closer_no_penalty(self):
        """Test when early_bird is closer and more than 3 seconds apart from regular"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)  # 30.0 seconds
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularFar',
                'play_time': datetime(2023, 12, 25, 13, 37, 20, 0),  # 10s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdCloser',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),  # 2s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'EarlyBirdCloser')
        self.assertEqual(winner['bet_type'], 'early_bird')

    def test_apply_winner_selection_rules_early_bird_closer_with_penalty(self):
        """Test when early_bird is closer but within 3 seconds of regular (penalty applies)"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)  # 30.0 seconds
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularNear',
                'play_time': datetime(2023, 12, 25, 13, 37, 26, 0),  # 4s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdCloser',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),  # 2s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularNear')
        self.assertEqual(winner['bet_type'], 'regular')

    def test_apply_winner_selection_rules_millisecond_precision(self):
        """Test millisecond precision in winner selection"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 500000)  # 30.5 seconds
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularPrecise',
                'play_time': datetime(2023, 12, 25, 13, 37, 30, 100000),  # 0.4s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdPrecise',
                'play_time': datetime(2023, 12, 25, 13, 37, 30, 200000),  # 0.3s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularPrecise')
        self.assertEqual(winner['bet_type'], 'regular')

    def test_apply_winner_selection_rules_exact_3_seconds_penalty(self):
        """Test edge case: exactly 3 seconds apart (penalty should apply)"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)  # 30.0 seconds
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularExact',
                'play_time': datetime(2023, 12, 25, 13, 37, 25, 0),  # 5s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdExact',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),  # 2s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularExact')
        self.assertEqual(winner['bet_type'], 'regular')

    def test_apply_winner_selection_rules_only_regular_bets(self):
        """Test when only regular bets exist"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'Regular1',
                'play_time': datetime(2023, 12, 25, 13, 37, 25, 0),
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'Regular2',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),
                'bet_type': 'regular',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'Regular2')  # Closer to win time
        self.assertEqual(winner['bet_type'], 'regular')

    def test_apply_winner_selection_rules_only_early_bird_bets(self):
        """Test when only early_bird bets exist"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'EarlyBird1',
                'play_time': datetime(2023, 12, 25, 13, 37, 25, 0),
                'bet_type': 'early_bird',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBird2',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'EarlyBird2')  # Closer to win time
        self.assertEqual(winner['bet_type'], 'early_bird')

    def test_apply_winner_selection_rules_no_valid_bets(self):
        """Test when no valid bets exist"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)
        valid_bets = []
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNone(winner)

    def test_apply_winner_selection_rules_tie_regular_wins(self):
        """Test when regular and early_bird are equally close, regular wins"""
        win_time = datetime(2023, 12, 25, 13, 37, 30, 0)
        
        valid_bets = [
            {
                'user_id': 12345,
                'username': 'RegularTie',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),  # 2s before win
                'bet_type': 'regular',
                'server_id': 67890
            },
            {
                'user_id': 12346,
                'username': 'EarlyBirdTie',
                'play_time': datetime(2023, 12, 25, 13, 37, 28, 0),  # 2s before win
                'bet_type': 'early_bird',
                'server_id': 67890
            }
        ]
        
        winner = self.logic._apply_winner_selection_rules(valid_bets, win_time)
        
        self.assertIsNotNone(winner)
        self.assertEqual(winner['username'], 'RegularTie')
        self.assertEqual(winner['bet_type'], 'regular')

    def test_get_milliseconds_since_midnight(self):
        """Test the millisecond calculation method"""
        dt = datetime(2023, 12, 25, 13, 37, 25, 123456)
        ms = self.logic.get_milliseconds_since_midnight(dt)
        
        # 13:37:25.123456 = (13*3600 + 37*60 + 25)*1000 + 123 = 49,045,123ms
        expected = (13 * 3600 + 37 * 60 + 25) * 1000 + 123
        self.assertEqual(ms, expected)

    def test_get_milliseconds_since_midnight_zero_time(self):
        """Test millisecond calculation for midnight"""
        dt = datetime(2023, 12, 25, 0, 0, 0, 0)
        ms = self.logic.get_milliseconds_since_midnight(dt)
        
        self.assertEqual(ms, 0)

    def test_get_milliseconds_since_midnight_end_of_day(self):
        """Test millisecond calculation for end of day"""
        dt = datetime(2023, 12, 25, 23, 59, 59, 999999)
        ms = self.logic.get_milliseconds_since_midnight(dt)
        
        # 23:59:59.999999 = (23*3600 + 59*60 + 59)*1000 + 999 = 86,399,999ms
        expected = (23 * 3600 + 59 * 60 + 59) * 1000 + 999
        self.assertEqual(ms, expected)


if __name__ == '__main__':
    unittest.main()