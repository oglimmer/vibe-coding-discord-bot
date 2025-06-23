"""
Core game logic for the 1337 betting game.
Adapted for microservice architecture.
"""

import logging
from datetime import datetime, date, time, timedelta
import random
import re
from typing import Optional, Dict, List, Any
from config import Config
from database import DatabaseManager

logger = logging.getLogger(__name__)


class Game1337Logic:
    """Core logic for the 1337 betting game"""
    
    def __init__(self, db_manager: DatabaseManager):
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
        
        logger.debug(f"🎯 [TIMER] Requesting win time for date: {game_date}")
        logger.debug(f"🎯 [TIMER] Current cache contents: {list(self._daily_win_times.keys())}")
        
        # Check if we already have the win time for this date
        if game_date in self._daily_win_times:
            cached_time = self._daily_win_times[game_date]
            logger.debug(f"🎯 [TIMER] Using cached win time for {game_date}: {self.format_time_with_ms(cached_time)}")
            logger.debug(f"🎯 [TIMER] Cache hit - returning existing win time")
            return cached_time
        
        logger.debug(f"🎯 [TIMER] No cached win time found for {game_date}, generating new one")
        
        # Generate new win time for this date
        game_start_time = self.parse_game_start_time()
        game_datetime = datetime.combine(game_date, game_start_time)
        logger.debug(f"🎯 [TIMER] Game start base time: {self.format_time_with_ms(game_datetime)}")

        # Random time within 1 minute (60000ms) after game start
        random.seed(game_date.toordinal())  # Seed with date for consistency
        random_ms = random.randint(0, 60000)
        win_time = game_datetime + timedelta(milliseconds=random_ms)
        
        logger.debug(f"🎯 [TIMER] Random seed: {game_date.toordinal()} (date ordinal)")
        logger.debug(f"🎯 [TIMER] Random milliseconds offset: {random_ms}ms")
        logger.debug(f"🎯 [TIMER] Calculated win time: {self.format_time_with_ms(win_time)}")
        
        # Cache the win time
        self._daily_win_times[game_date] = win_time
        logger.debug(f"🎯 [TIMER] Win time cached for {game_date}")
        
        logger.info(
            f"🎯 [TIMER] Generated NEW win time for {game_date}: {self.format_time_with_ms(win_time)} "
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
                    game_start_time = self.parse_game_start_time()
                    hour, minute = str(game_start_time.hour), str(game_start_time.minute)
                    second, ms = groups
                    ms = ms.ljust(3, '0')[:3]
                else:  # ss
                    game_start_time = self.parse_game_start_time()
                    hour, minute = str(game_start_time.hour), str(game_start_time.minute)
                    second = groups[0]
                    ms = '000'

                try:
                    hour, minute, second = int(hour), int(minute), int(second)
                    microsecond = int(ms) * 1000

                    dt = datetime.combine(game_date, time(hour, minute, second, microsecond))
                    logger.debug(f"Successfully parsed timestamp: {self.format_time_with_ms(dt)}")
                    return dt
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
        
        logger.debug(f"🕐 [TIMER] Current time: {self.format_time_with_ms(current_time)}")
        logger.debug(f"🕐 [TIMER] Game start time: {self.format_time_with_ms(game_datetime)}")
        logger.debug(f"🕐 [TIMER] Game deadline (start + 1min): {self.format_time_with_ms(deadline)}")
        
        passed = current_time > deadline
        logger.debug(f"🕐 [TIMER] Game time passed: {passed}")
        
        return passed

    def is_win_time_passed(self, current_time: Optional[datetime] = None) -> bool:
        """Check if the actual WIN_TIME has passed (precise to milliseconds)"""
        if current_time is None:
            current_time = datetime.now()
        
        game_date = current_time.date()
        win_time = self.get_daily_win_time(game_date)
        
        logger.debug(f"🏆 [TIMER] Current time: {self.format_time_with_ms(current_time)}")
        logger.debug(f"🏆 [TIMER] Win time: {self.format_time_with_ms(win_time)}")
        
        passed = current_time > win_time
        logger.debug(f"🏆 [TIMER] Win time passed: {passed}")
        
        return passed

    def is_timestamp_in_future(self, timestamp: datetime, current_time: Optional[datetime] = None) -> bool:
        """Check if timestamp is in the future"""
        if current_time is None:
            current_time = datetime.now()
        return timestamp > current_time

    def calculate_millisecond_difference(self, bet_time: datetime, win_time: datetime) -> int:
        """Calculate millisecond difference between bet time and win time"""
        return int((win_time - bet_time).total_seconds() * 1000)

    async def determine_winner(self, game_date: date, win_time: datetime) -> Optional[Dict[str, Any]]:
        """
        Determine the winner for a given game date and win time.
        Returns the winner dict or None if no winner/catastrophic event.
        """
        logger.info(f"🏆 [WINNER] Starting winner determination for {game_date}")
        logger.info(f"🏆 [WINNER] Target win time: {self.format_time_with_ms(win_time)}")

        daily_bets = await self.db_manager.get_daily_bets(game_date)
        logger.debug(f"🏆 [WINNER] Found {len(daily_bets)} total bets for {game_date}")
        
        # Log all bets with detailed info
        logger.debug(f"🏆 [WINNER] All bets for {game_date}:")
        for i, bet in enumerate(daily_bets):
            logger.debug(f"🏆 [WINNER]   {i+1}. {bet['username']}: {self.format_time_with_ms(bet['play_time'])} ({bet['bet_type']}) [user_id: {bet['user_id']}]")

        valid_bets = [bet for bet in daily_bets if bet['play_time'] <= win_time]
        logger.info(f"🏆 [WINNER] Found {len(valid_bets)} valid bets (≤ win time) out of {len(daily_bets)} total")

        logger.debug(f"🏆 [WINNER] Bet validation details:")
        for bet in daily_bets:
            valid = "✓" if bet['play_time'] <= win_time else "✗"
            time_diff_ms = int((bet['play_time'] - win_time).total_seconds() * 1000)
            logger.debug(
                f"🏆 [WINNER]   {valid} {bet['username']}: {self.format_time_with_ms(bet['play_time'])} ({bet['bet_type']}) [{time_diff_ms:+d}ms from win time]"
            )

        if not valid_bets:
            logger.info(f"🏆 [WINNER] No valid bets for {game_date} - no winner")
            return None

        if len(valid_bets) == 1:
            winner = valid_bets[0]
            logger.info(f"🏆 [WINNER] Single valid bet, automatic winner: {winner['username']}")
        else:
            logger.debug(f"🏆 [WINNER] Multiple valid bets ({len(valid_bets)}), applying winner selection rules")
            winner = self._apply_winner_selection_rules(valid_bets, win_time)
            if not winner:
                logger.info(f"🏆 [WINNER] Winner selection rules returned no winner")
                return None

        # Check for catastrophic event (identical times)
        identical_times = [bet for bet in valid_bets if bet['play_time'] == winner['play_time']]
        if len(identical_times) > 1:
            logger.warning(
                f"💥 [WINNER] CATASTROPHIC EVENT! {len(identical_times)} players with identical time: "
                f"{self.format_time_with_ms(winner['play_time'])}"
            )
            logger.debug(f"💥 [WINNER] Players with identical times:")
            for bet in identical_times:
                logger.debug(f"💥 [WINNER]   - {bet['username']} ({bet['bet_type']}) [user_id: {bet['user_id']}]")
            return {'catastrophic_event': True, 'identical_count': len(identical_times)}

        millisecond_diff = self.calculate_millisecond_difference(winner['play_time'], win_time)
        logger.info(
            f"🏆 [WINNER] FINAL WINNER: {winner['username']} - {self.format_time_with_ms(winner['play_time'])} "
            f"({winner['bet_type']}) - {millisecond_diff}ms before win time [user_id: {winner['user_id']}]"
        )

        # Add calculated difference to winner data
        winner_data = winner.copy()
        winner_data['millisecond_diff'] = millisecond_diff
        winner_data['win_time'] = win_time
        
        logger.debug(f"🏆 [WINNER] Winner data prepared: {winner_data}")
        return winner_data

    def get_milliseconds_since_midnight(self, dt: datetime) -> int:
        """Get milliseconds since midnight for a datetime object"""
        return (dt.hour * 3600 + dt.minute * 60 + dt.second) * 1000 + dt.microsecond // 1000

    def _apply_winner_selection_rules(self, valid_bets: List[Dict], win_time: datetime) -> Optional[Dict]:
        """
        Apply the winner selection rules:
        1. Find the closest regular bet and closest early_bird bet
        2. If regular bet is closer, it wins
        3. If early_bird bet is closer, it only wins if more than 3 seconds apart from closest regular bet
        """
        if not valid_bets:
            logger.debug(f"🤔 [RULES] No valid bets provided to winner selection rules")
            return None

        logger.debug(f"🤔 [RULES] Applying winner selection rules to {len(valid_bets)} valid bets")
        logger.debug(f"🤔 [RULES] Win time: {self.format_time_with_ms(win_time)}")

        # Separate bets by type
        regular_bets = [bet for bet in valid_bets if bet['bet_type'] == 'regular']
        early_bird_bets = [bet for bet in valid_bets if bet['bet_type'] == 'early_bird']
        
        logger.debug(f"🤔 [RULES] Regular bets: {len(regular_bets)}, Early bird bets: {len(early_bird_bets)}")
        
        for bet in regular_bets:
            logger.debug(f"🤔 [RULES]   Regular: {bet['username']} - {self.format_time_with_ms(bet['play_time'])}")
        for bet in early_bird_bets:
            logger.debug(f"🤔 [RULES]   Early bird: {bet['username']} - {self.format_time_with_ms(bet['play_time'])}")

        # Find closest bets to win_time
        win_time_ms = self.get_milliseconds_since_midnight(win_time)
        logger.debug(f"🤔 [RULES] Win time in ms since midnight: {win_time_ms}")
        
        closest_regular = None
        if regular_bets:
            closest_regular = min(regular_bets, key=lambda x: abs(win_time_ms - self.get_milliseconds_since_midnight(x['play_time'])))
            regular_distance = abs(win_time_ms - self.get_milliseconds_since_midnight(closest_regular['play_time']))
            logger.debug(f"🤔 [RULES] Closest regular bet: {closest_regular['username']} - {self.format_time_with_ms(closest_regular['play_time'])} (distance: {regular_distance}ms)")
        
        closest_early_bird = None
        if early_bird_bets:
            closest_early_bird = min(early_bird_bets, key=lambda x: abs(win_time_ms - self.get_milliseconds_since_midnight(x['play_time'])))
            early_bird_distance = abs(win_time_ms - self.get_milliseconds_since_midnight(closest_early_bird['play_time']))
            logger.debug(f"🤔 [RULES] Closest early bird bet: {closest_early_bird['username']} - {self.format_time_with_ms(closest_early_bird['play_time'])} (distance: {early_bird_distance}ms)")

        # If no regular bets, early_bird wins (if exists)
        if not closest_regular:
            if closest_early_bird:
                logger.info(f"🏆 [RULES] Winner: {closest_early_bird['username']} (early_bird bet, no regular bets)")
                return closest_early_bird
            logger.debug(f"🤔 [RULES] No regular or early bird bets found")
            return None

        # If no early_bird bets, regular wins
        if not closest_early_bird:
            logger.info(f"🏆 [RULES] Winner: {closest_regular['username']} (regular bet, no early_bird bets)")
            return closest_regular

        # Compare distances to win_time
        regular_distance = abs(win_time_ms - self.get_milliseconds_since_midnight(closest_regular['play_time']))
        early_bird_distance = abs(win_time_ms - self.get_milliseconds_since_midnight(closest_early_bird['play_time']))
        
        logger.debug(f"🤔 [RULES] Distance comparison - Regular: {regular_distance}ms, Early bird: {early_bird_distance}ms")

        # If regular bet is closer, it wins
        if regular_distance <= early_bird_distance:
            logger.info(f"🏆 [RULES] Winner: {closest_regular['username']} (regular bet closer to win time - {regular_distance}ms vs {early_bird_distance}ms)")
            return closest_regular

        # Early_bird is closer, check if more than 3 seconds apart from closest regular
        time_diff = abs(self.get_milliseconds_since_midnight(closest_early_bird['play_time']) - 
                       self.get_milliseconds_since_midnight(closest_regular['play_time']))
        
        logger.debug(f"🤔 [RULES] Early bird is closer ({early_bird_distance}ms vs {regular_distance}ms)")
        logger.debug(f"🤔 [RULES] Time difference between early bird and regular: {time_diff}ms (threshold: 3000ms)")
        
        if time_diff > 3000:  # More than 3 seconds (3000ms)
            logger.info(f"🏆 [RULES] Winner: {closest_early_bird['username']} (early_bird closer and {time_diff}ms > 3000ms apart from regular)")
            return closest_early_bird
        else:
            logger.info(f"🏆 [RULES] Winner: {closest_regular['username']} (early_bird closer but only {time_diff}ms ≤ 3000ms from regular - rule override)")
            return closest_regular

    async def save_winner(self, winner_data: Dict[str, Any]) -> bool:
        """Save the winner to the database"""
        return await self.db_manager.save_1337_winner(
            winner_data['user_id'],
            winner_data['username'],
            winner_data['win_time'].date(),
            winner_data['win_time'],
            winner_data['play_time'],
            winner_data['bet_type'],
            winner_data['millisecond_diff'],
            winner_data.get('server_id')
        )

    async def validate_bet_placement(self, user_id: int, current_time: Optional[datetime] = None) -> Dict[str, Any]:
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
        existing_bet = await self.db_manager.get_user_bet(user_id, game_date)
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
                'message': f"❌ **Invalid timestamp format!**\n\nSupported formats:\n"
                          f"`3` → {Config.GAME_START_TIME[:-4]}03.000\n"
                          f"`3.45` → {Config.GAME_START_TIME[:-4]}03.450\n"
                          f"`{Config.GAME_START_TIME[:5]}3` → {Config.GAME_START_TIME[:-4]}03.000\n"
                          f"`{Config.GAME_START_TIME[:5]}3.333` → {Config.GAME_START_TIME[:-4]}03.333"
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

    async def save_bet(self, user_id: int, username: str, play_time: datetime, bet_type: str, 
                 guild_id: int, channel_id: int) -> bool:
        """Save a bet to the database"""
        game_date = self.get_game_date()
        return await self.db_manager.save_1337_bet(
            user_id, username, play_time, game_date, bet_type, guild_id, channel_id
        )

    async def get_user_bet_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's bet information for today"""
        game_date = self.get_game_date()
        return await self.db_manager.get_user_bet(user_id, game_date)

    async def get_daily_winner(self, game_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Get the daily winner for a specific date"""
        if game_date is None:
            game_date = self.get_game_date()
        return await self.db_manager.get_daily_winner(game_date)

    async def get_winner_stats(self, days: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get winner statistics"""
        return await self.db_manager.get_winner_stats(user_id=user_id, days=days)

    async def get_daily_bets(self, game_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get all bets for a specific date"""
        if game_date is None:
            game_date = self.get_game_date()
        return await self.db_manager.get_daily_bets(game_date)

    def determine_new_role_assignments(self, winner_today: Dict[str, Any], 
                                      top_14_day: Optional[Dict[str, Any]], 
                                      top_365_day: Optional[Dict[str, Any]]) -> Dict[str, int]:
        """Determine who should get which roles based on game statistics"""
        logger.info(f"🎖️ [ROLES] Starting role assignment determination")
        logger.debug(f"🎖️ [ROLES] Today's winner: {winner_today['username']} (user_id: {winner_today['user_id']})")
        logger.debug(f"🎖️ [ROLES] Top 14-day player: {top_14_day['username'] if top_14_day else 'None'} (user_id: {top_14_day['user_id'] if top_14_day else 'N/A'})")
        logger.debug(f"🎖️ [ROLES] Top 365-day player: {top_365_day['username'] if top_365_day else 'None'} (user_id: {top_365_day['user_id'] if top_365_day else 'N/A'})")
        
        assignments = {}
        
        # Start with today's winner getting Sergeant
        assignments['sergeant'] = winner_today['user_id']
        logger.debug(f"🎖️ [ROLES] Initial assignment - Sergeant: {winner_today['username']} ({winner_today['user_id']})")
        
        # Override with Commander if winner is top 14-day player
        if top_14_day and winner_today['user_id'] == top_14_day['user_id']:
            logger.debug(f"🎖️ [ROLES] Winner is also top 14-day player - upgrading to Commander")
            assignments['commander'] = winner_today['user_id']
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
                logger.debug(f"🎖️ [ROLES] Removed Sergeant role (upgraded to Commander)")
        
        # Override with General if winner is top 365-day player
        if top_365_day and winner_today['user_id'] == top_365_day['user_id']:
            logger.debug(f"🎖️ [ROLES] Winner is also top 365-day player - upgrading to General")
            assignments['general'] = winner_today['user_id']
            # Remove lower roles
            if 'commander' in assignments and assignments['commander'] == winner_today['user_id']:
                del assignments['commander']
                logger.debug(f"🎖️ [ROLES] Removed Commander role (upgraded to General)")
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
                logger.debug(f"🎖️ [ROLES] Removed Sergeant role (upgraded to General)")
        
        # Assign special roles to non-winners
        if top_365_day and top_365_day['user_id'] != winner_today['user_id']:
            assignments['general'] = top_365_day['user_id']
            logger.debug(f"🎖️ [ROLES] Assigning General to non-winner top 365-day player: {top_365_day['username']} ({top_365_day['user_id']})")
        
        if (top_14_day and top_14_day['user_id'] != winner_today['user_id'] and 
            top_14_day['user_id'] != (top_365_day['user_id'] if top_365_day else None)):
            assignments['commander'] = top_14_day['user_id']
            logger.debug(f"🎖️ [ROLES] Assigning Commander to non-winner top 14-day player: {top_14_day['username']} ({top_14_day['user_id']})")
        
        logger.info(f"🎖️ [ROLES] Final role assignments:")
        for role, user_id in assignments.items():
            # Find username for logging
            username = "Unknown"
            if user_id == winner_today['user_id']:
                username = winner_today['username']
            elif top_14_day and user_id == top_14_day['user_id']:
                username = top_14_day['username']
            elif top_365_day and user_id == top_365_day['user_id']:
                username = top_365_day['username']
            logger.info(f"🎖️ [ROLES]   {role.capitalize()}: {username} ({user_id})")
        
        return assignments

    async def create_user_info_embed_data(self, user_bet: Dict[str, Any]) -> Dict[str, Any]:
        """Create data for user bet info embed (Discord-independent)"""
        game_date = self.get_game_date()
        game_passed = self.is_game_time_passed()

        embed_data = {
            'title': '🎯 Your 1337 Bet Info',
            'color': 0x1337FF,
            'fields': []
        }

        bet_type_emoji = "🐦" if user_bet['bet_type'] == 'early_bird' else "⚡"
        embed_data['fields'].append({
            'name': 'Bet Type',
            'value': f"{bet_type_emoji} {user_bet['bet_type'].replace('_', ' ').title()}",
            'inline': True
        })

        embed_data['fields'].append({
            'name': 'Your Time',
            'value': f"`{self.format_time_with_ms(user_bet['play_time'])}`",
            'inline': True
        })

        if game_passed:
            winner = await self.get_daily_winner(game_date)
            if winner:
                embed_data['fields'].append({
                    'name': 'Win Time',
                    'value': f"`{self.format_time_with_ms(winner['win_time'])}`",
                    'inline': True
                })

                millisecond_diff = self.calculate_millisecond_difference(
                    user_bet['play_time'], winner['win_time']
                )
                embed_data['fields'].append({
                    'name': 'Difference',
                    'value': f"`{millisecond_diff}ms`",
                    'inline': True
                })

                if winner['user_id'] == user_bet['user_id']:
                    embed_data['fields'].append({
                        'name': 'Result',
                        'value': '🏆 **WINNER!**',
                        'inline': True
                    })
                    embed_data['color'] = 0x00FF00
                else:
                    embed_data['fields'].append({
                        'name': 'Result',
                        'value': '💔 Better luck tomorrow!',
                        'inline': True
                    })
                    embed_data['color'] = 0xFF6B6B
            else:
                embed_data['fields'].append({
                    'name': 'Status',
                    'value': '⏳ Waiting for results...',
                    'inline': False
                })
        else:
            embed_data['fields'].append({
                'name': 'Status',
                'value': f'⏳ Waiting for {Config.GAME_START_TIME[:5]}...',
                'inline': False
            })

        return embed_data

    async def create_winner_message(self, winner_data: Dict[str, Any], 
                             top_14_day: Optional[Dict[str, Any]], 
                             top_365_day: Optional[Dict[str, Any]],
                             guild_id: Optional[int] = None,
                             current_role_holders: Optional[Dict[str, Any]] = None) -> str:
        """Create plain text winner announcement message"""

        # Start with winner announcement
        bet_type = "early bird" if winner_data['bet_type'] == 'early_bird' else "regular"
        message_lines = [
            f"**{winner_data['username']}** won with a {bet_type} bet",
            f"Winners bet time: {self.format_time_with_ms(winner_data['play_time'])} - Win time: {self.format_time_with_ms(winner_data['win_time'])})",
            f"Performance: {winner_data['millisecond_diff']}ms before win time"
        ]
        
        # Add role assignments only if roles have actually changed
        if guild_id and current_role_holders:
            # Get new role assignments
            new_role_assignments = self.determine_new_role_assignments(winner_data, top_14_day, top_365_day)
            role_changes = []
            
            # Check each role for changes
            for role_type in ['general', 'commander', 'sergeant']:
                # Get current holder
                current_holder = current_role_holders.get(role_type)
                current_user_id = current_holder['user_id'] if current_holder else None
                
                # Get new holder
                new_user_id = new_role_assignments.get(role_type)
                
                # Only add to message if the user is actually changing
                if current_user_id != new_user_id:
                    # Find the appropriate user data for this role
                    user_to_display = None
                    if role_type == 'general' and top_365_day and top_365_day['user_id'] == new_user_id:
                        user_to_display = top_365_day
                    elif role_type == 'commander' and top_14_day and top_14_day['user_id'] == new_user_id:
                        user_to_display = top_14_day
                    elif role_type == 'sergeant' and winner_data['user_id'] == new_user_id:
                        user_to_display = winner_data
                    
                    if user_to_display:
                        role_name = role_type.capitalize()
                        if user_to_display == winner_data:
                            role_changes.append(f"New {role_name}: {user_to_display['username']}")
                        else:
                            role_changes.append(f"New {role_name}: {user_to_display['username']} ({user_to_display['wins']} wins)")
            
            if role_changes:
                message_lines.append("")
                message_lines.extend(role_changes)
        
        return "\n".join(message_lines)

    async def get_stats_page_data(self, page: int) -> Dict[str, Any]:
        """Get statistics page data (Discord-independent)"""
        pages = ["365 Days", "14 Days", "Daily Bets"]
        
        embed_data = {
            'title': '📊 1337 Game Statistics',
            'color': 0x1337FF,
            'fields': []
        }

        if page == 0:  # 365 Days
            stats = await self.get_winner_stats(days=365)
            embed_data['fields'].append({
                'name': '🏆 Top Players (Last 365 Days)',
                'value': self._format_stats_list(stats) if stats else 'No winners yet',
                'inline': False
            })

        elif page == 1:  # 14 Days
            stats = await self.get_winner_stats(days=14)
            embed_data['fields'].append({
                'name': '🔥 Top Players (Last 14 Days)',
                'value': self._format_stats_list(stats) if stats else 'No winners yet',
                'inline': False
            })

        elif page == 2:  # Daily Bets
            game_passed = self.is_game_time_passed()
            
            if game_passed:
                # Show today's bets
                today_bets = await self.get_daily_bets()
                embed_data['fields'].append({
                    'name': '📅 Today\'s Players',
                    'value': self._format_daily_bets(today_bets) if today_bets else 'No bets today',
                    'inline': False
                })
            else:
                # Show yesterday's bets
                yesterday_date = self.get_yesterday_date()
                yesterday_bets = await self.get_daily_bets(yesterday_date)
                embed_data['fields'].append({
                    'name': '📅 Yesterday\'s Players',
                    'value': self._format_daily_bets(yesterday_bets) if yesterday_bets else 'No bets yesterday',
                    'inline': False
                })

        embed_data['footer_text'] = f"Page {page + 1}/3 • {pages[page]}"
        return embed_data

    def _format_stats_list(self, stats: List[Dict[str, Any]]) -> str:
        """Format statistics list for display"""
        if not stats:
            return "No data available"

        lines = []
        for i, stat in enumerate(stats[:10]):
            rank = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
            rank_emoji = rank[i] if i < len(rank) else "🏅"
            lines.append(f"{rank_emoji} **{stat['username']}** - {stat['wins']} wins")

        return "\n".join(lines)

    def _format_daily_bets(self, bets: List[Dict[str, Any]]) -> str:
        """Format daily bets for display"""
        if not bets:
            return "No bets placed"

        lines = []
        for bet in bets[:15]:
            bet_type_emoji = "🐦" if bet['bet_type'] == 'early_bird' else "⚡"
            time_str = self.format_time_with_ms(bet['play_time'])
            lines.append(f"{bet_type_emoji} `{time_str}` **{bet['username']}**")

        if len(bets) > 15:
            lines.append(f"*+{len(bets) - 15} more players...*")

        return "\n".join(lines)

    async def get_winner_role_name(self, winner_data: Dict[str, Any]) -> str:
        """Determine winner's new role name based on their position"""
        logger.debug(f"🎖️ [ROLE_NAME] Determining role name for winner: {winner_data['username']} ({winner_data['user_id']})")
        
        winner_14_days = await self.get_winner_stats(days=14)
        winner_365_days = await self.get_winner_stats(days=365)
        
        top_14_day = winner_14_days[0] if winner_14_days else None
        top_365_day = winner_365_days[0] if winner_365_days else None
        
        logger.debug(f"🎖️ [ROLE_NAME] Top 14-day player: {top_14_day['username'] if top_14_day else 'None'} ({top_14_day['user_id'] if top_14_day else 'N/A'})")
        logger.debug(f"🎖️ [ROLE_NAME] Top 365-day player: {top_365_day['username'] if top_365_day else 'None'} ({top_365_day['user_id'] if top_365_day else 'N/A'})")
        
        if top_365_day and winner_data['user_id'] == top_365_day['user_id']:
            logger.info(f"🎖️ [ROLE_NAME] Winner is top 365-day player - assigning General role")
            return "🎖️ General"
        elif top_14_day and winner_data['user_id'] == top_14_day['user_id']:
            logger.info(f"🎖️ [ROLE_NAME] Winner is top 14-day player - assigning Commander role")
            return "🔥 Commander"
        else:
            logger.info(f"🎖️ [ROLE_NAME] Winner is not a top player - assigning Sergeant role")
            return "🏅 Sergeant"