"""
Core game logic for the 1337 betting game.
Separated from Discord command handling for better testability and modularity.
"""

import logging
from datetime import datetime, date, time, timedelta
import random
import re
from typing import Optional, Dict, List, Any
from config import Config

logger = logging.getLogger(__name__)


class Game1337Logic:
    """Core logic for the 1337 betting game"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self._daily_win_times = {}  # Cache for daily win times: {date: datetime}
    
    def parse_game_start_time(self) -> time:
        """Parse the game start time from configuration"""
        time_str = Config.GAME_START_TIME
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second_parts = parts[2].split('.')
        second = int(second_parts[0])
        microsecond = int(second_parts[1]) * 1000 if len(second_parts) > 1 else 0
        return time(hour, minute, second, microsecond)

    def get_game_date(self) -> date:
        """Get the current game date"""
        return datetime.now().date()

    def get_yesterday_date(self) -> date:
        """Get yesterday's date"""
        return (datetime.now() - timedelta(days=1)).date()

    def get_daily_win_time(self, game_date: Optional[date] = None) -> datetime:
        """
        Get or generate the daily win time for a specific date.
        The win time is generated only once per day and cached in memory.
        """
        if game_date is None:
            game_date = self.get_game_date()
        
        # Check if we already have the win time for this date
        if game_date in self._daily_win_times:
            logger.debug(f"Using cached win time for {game_date}: {self.format_time_with_ms(self._daily_win_times[game_date])}")
            return self._daily_win_times[game_date]
        
        # Generate new win time for this date
        game_start_time = self.parse_game_start_time()
        game_datetime = datetime.combine(game_date, game_start_time)

        # Random time within 1 minute (60000ms) after game start
        random_ms = random.randint(0, 60000)
        win_time = game_datetime + timedelta(milliseconds=random_ms)
        
        # Cache the win time
        self._daily_win_times[game_date] = win_time
        
        logger.info(
            f"Generated NEW win time for {game_date}: {self.format_time_with_ms(win_time)} "
            f"(base: {self.format_time_with_ms(game_datetime)}, +{random_ms}ms)"
        )
        return win_time

    def parse_timestamp(self, timestamp_str: str, game_date: date) -> Optional[datetime]:
        """Parse various timestamp formats into a datetime object"""
        timestamp_str = timestamp_str.strip()
        logger.debug(f"Parsing timestamp: '{timestamp_str}' for date {game_date}")

        patterns = [
            r'^(\d{1,2}):(\d{2}):(\d{1,2})\.(\d{1,3})$',  # hh:mm:ss.SSS
            r'^(\d{1,2}):(\d{2}):(\d{1,2})$',  # hh:mm:ss
            r'^(\d{1,2})\.(\d{1,3})$',  # ss.SSS
            r'^(\d{1,2})$'  # ss
        ]

        for i, pattern in enumerate(patterns):
            match = re.match(pattern, timestamp_str)
            if match:
                groups = match.groups()
                logger.debug(f"Matched pattern {i}: {groups}")

                if len(groups) == 4:  # hh:mm:ss.SSS
                    hour, minute, second, ms = groups
                    ms = ms.ljust(3, '0')[:3]
                elif len(groups) == 3:  # hh:mm:ss
                    hour, minute, second = groups
                    ms = '000'
                elif len(groups) == 2:  # ss.SSS
                    hour, minute = '13', '37'
                    second, ms = groups
                    ms = ms.ljust(3, '0')[:3]
                else:  # ss
                    hour, minute = '13', '37'
                    second = groups[0]
                    ms = '000'

                try:
                    hour, minute, second = int(hour), int(minute), int(second)
                    microsecond = int(ms) * 1000

                    if hour == 13 and minute == 37 and 0 <= second <= 59:
                        dt = datetime.combine(game_date, time(hour, minute, second, microsecond))
                        logger.debug(f"Successfully parsed timestamp: {self.format_time_with_ms(dt)}")
                        return dt
                    else:
                        logger.debug(f"Invalid time components: {hour}:{minute}:{second}")
                except ValueError as e:
                    logger.debug(f"ValueError parsing time components: {e}")
                    continue

        logger.debug("No patterns matched, returning None")
        return None

    def format_time_with_ms(self, dt: datetime) -> str:
        """Format datetime with milliseconds"""
        return dt.strftime('%H:%M:%S.%f')[:-3]

    def is_game_time_passed(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the game time has passed (with 1 minute buffer)"""
        if current_time is None:
            current_time = datetime.now()
        
        game_start_time = self.parse_game_start_time()
        game_datetime = datetime.combine(current_time.date(), game_start_time)
        deadline = game_datetime + timedelta(minutes=1)
        
        return current_time > deadline

    def is_timestamp_in_future(self, timestamp: datetime, current_time: Optional[datetime] = None) -> bool:
        """Check if timestamp is in the future"""
        if current_time is None:
            current_time = datetime.now()
        return timestamp > current_time

    def calculate_millisecond_difference(self, bet_time: datetime, win_time: datetime) -> int:
        """Calculate millisecond difference between bet time and win time"""
        return int((win_time - bet_time).total_seconds() * 1000)

    def determine_winner(self, game_date: date, win_time: datetime) -> Optional[Dict[str, Any]]:
        """
        Determine the winner for a given game date and win time.
        Returns the winner dict or None if no winner/catastrophic event.
        """
        logger.info(f"Determining winner for {game_date}, win time: {self.format_time_with_ms(win_time)}")

        daily_bets = self.db_manager.get_daily_bets(game_date)
        logger.debug(f"Found {len(daily_bets)} total bets for {game_date}")

        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        logger.debug(f"Found {len(valid_bets)} valid bets (≤ win time)")

        for bet in daily_bets:
            valid = "✓" if bet['play_time'] <= win_time else "✗"
            logger.debug(
                f"  {valid} {bet['username']}: {self.format_time_with_ms(bet['play_time'])} ({bet['bet_type']})"
            )

        if not valid_bets:
            logger.info(f"No valid bets for {game_date}")
            return None

        if len(valid_bets) == 1:
            winner = valid_bets[0]
            logger.debug("Single valid bet, automatic winner")
        else:
            winner = self._apply_winner_selection_rules(valid_bets, win_time)
            if not winner:
                logger.info("No winner determined")
                return None

        # Check for catastrophic event (identical times)
        identical_times = [bet for bet in valid_bets if bet['play_time'] == winner['play_time']]
        if len(identical_times) > 1:
            logger.warning(
                f"Catastrophic event! {len(identical_times)} players with identical time: "
                f"{self.format_time_with_ms(winner['play_time'])}"
            )
            return {'catastrophic_event': True, 'identical_count': len(identical_times)}

        millisecond_diff = self.calculate_millisecond_difference(winner['play_time'], win_time)
        logger.info(
            f"Winner: {winner['username']} - {self.format_time_with_ms(winner['play_time'])} "
            f"({winner['bet_type']}) - {millisecond_diff}ms before win time"
        )

        # Add calculated difference to winner data
        winner_data = winner.copy()
        winner_data['millisecond_diff'] = millisecond_diff
        winner_data['win_time'] = win_time
        
        return winner_data

    def _apply_winner_selection_rules(self, valid_bets: List[Dict], win_time: datetime) -> Optional[Dict]:
        """
        Apply the winner selection rules:
        1. Recent regular bets (within 3 seconds of win time)
        2. All regular bets (latest wins)
        3. Early bird bets (latest wins)
        """
        regular_bets = [bet for bet in valid_bets if bet['bet_type'] == 'regular']
        early_bird_bets = [bet for bet in valid_bets if bet['bet_type'] == 'early_bird']

        logger.debug(f"Regular bets: {len(regular_bets)}, Early bird bets: {len(early_bird_bets)}")

        three_seconds_before = win_time - timedelta(seconds=3)
        recent_regular_bets = [bet for bet in regular_bets if bet['play_time'] >= three_seconds_before]

        logger.debug(f"Recent regular bets (within 3s of win): {len(recent_regular_bets)}")
        logger.debug(f"Three seconds before win time: {self.format_time_with_ms(three_seconds_before)}")

        if recent_regular_bets:
            winner = max(regular_bets, key=lambda x: x['play_time'])
            logger.debug(f"Winner from recent regular bets: {winner['username']}")
            return winner
        elif regular_bets:
            winner = max(regular_bets, key=lambda x: x['play_time'])
            logger.debug(f"Winner from all regular bets: {winner['username']}")
            return winner
        elif early_bird_bets:
            winner = max(early_bird_bets, key=lambda x: x['play_time'])
            logger.debug(f"Winner from early bird bets: {winner['username']}")
            return winner
        else:
            return None

    def save_winner(self, winner_data: Dict[str, Any]) -> bool:
        """Save the winner to the database"""
        return self.db_manager.save_1337_winner(
            winner_data['user_id'],
            winner_data['username'],
            winner_data['win_time'].date(),
            winner_data['win_time'],
            winner_data['play_time'],
            winner_data['bet_type'],
            winner_data['millisecond_diff'],
            winner_data['server_id']
        )

    def validate_bet_placement(self, user_id: int, current_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Validate if a bet can be placed.
        Returns dict with 'valid' bool and 'reason' string if invalid.
        """
        if current_time is None:
            current_time = datetime.now()
        
        game_date = self.get_game_date()
        
        # Check if game time has passed
        if self.is_game_time_passed(current_time):
            return {
                'valid': False,
                'reason': 'game_time_passed',
                'message': "❌ **Game time has passed!** The 1337 window is closed for today. Try again tomorrow!"
            }
        
        # Check if user already has a bet
        existing_bet = self.db_manager.get_user_bet(user_id, game_date)
        if existing_bet:
            return {
                'valid': False,
                'reason': 'existing_bet',
                'message': f"❌ **You've already placed a bet today!** Your {existing_bet['bet_type']} bet is at {self.format_time_with_ms(existing_bet['play_time'])}",
                'existing_bet': existing_bet
            }
        
        return {'valid': True}

    def validate_early_bird_timestamp(self, timestamp_str: str, current_time: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Validate early bird timestamp.
        Returns dict with 'valid' bool, 'timestamp' datetime if valid, and 'reason'/'message' if invalid.
        """
        if current_time is None:
            current_time = datetime.now()
        
        game_date = self.get_game_date()
        
        # Parse the timestamp
        parsed_timestamp = self.parse_timestamp(timestamp_str, game_date)
        if not parsed_timestamp:
            return {
                'valid': False,
                'reason': 'invalid_format',
                'message': "❌ **Invalid timestamp format!**\n\nSupported formats:\n"
                          "`3` → 13:37:03.000\n"
                          "`3.45` → 13:37:03.450\n"
                          "`13:37:3` → 13:37:03.000\n"
                          "`13:37:3.333` → 13:37:03.333"
            }
        
        # Check if timestamp is in the future
        if not self.is_timestamp_in_future(parsed_timestamp, current_time):
            return {
                'valid': False,
                'reason': 'not_future',
                'message': "❌ **Timestamp must be in the future!** Early bird bets must be scheduled ahead of time."
            }
        
        return {
            'valid': True,
            'timestamp': parsed_timestamp
        }

    def save_bet(self, user_id: int, username: str, play_time: datetime, bet_type: str, 
                 guild_id: int, channel_id: int) -> bool:
        """Save a bet to the database"""
        game_date = self.get_game_date()
        return self.db_manager.save_1337_bet(
            user_id, username, play_time, game_date, bet_type, guild_id, channel_id
        )

    def get_user_bet_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's bet information for today"""
        game_date = self.get_game_date()
        return self.db_manager.get_user_bet(user_id, game_date)

    def get_daily_winner(self, game_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Get the daily winner for a specific date"""
        if game_date is None:
            game_date = self.get_game_date()
        return self.db_manager.get_daily_winner(game_date)

    def get_winner_stats(self, days: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get winner statistics"""
        if user_id:
            return self.db_manager.get_winner_stats(user_id=user_id)
        else:
            return self.db_manager.get_winner_stats(days=days)

    def get_daily_bets(self, game_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get all bets for a specific date"""
        if game_date is None:
            game_date = self.get_game_date()
        return self.db_manager.get_daily_bets(game_date)