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

    def determine_new_role_assignments(self, winner_today: Dict[str, Any], 
                                      top_14_day: Optional[Dict[str, Any]], 
                                      top_365_day: Optional[Dict[str, Any]]) -> Dict[str, int]:
        """Determine who should get which roles based on game statistics"""
        assignments = {}
        
        # Start with today's winner getting Sergeant
        assignments['sergeant'] = winner_today['user_id']
        
        # Override with Commander if winner is top 14-day player
        if top_14_day and winner_today['user_id'] == top_14_day['user_id']:
            assignments['commander'] = winner_today['user_id']
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
        
        # Override with General if winner is top 365-day player
        if top_365_day and winner_today['user_id'] == top_365_day['user_id']:
            assignments['general'] = winner_today['user_id']
            # Remove lower roles
            if 'commander' in assignments and assignments['commander'] == winner_today['user_id']:
                del assignments['commander']
            if 'sergeant' in assignments and assignments['sergeant'] == winner_today['user_id']:
                del assignments['sergeant']
        
        # Assign special roles to non-winners
        if top_365_day and top_365_day['user_id'] != winner_today['user_id']:
            assignments['general'] = top_365_day['user_id']
        
        if (top_14_day and top_14_day['user_id'] != winner_today['user_id'] and 
            top_14_day['user_id'] != (top_365_day['user_id'] if top_365_day else None)):
            assignments['commander'] = top_14_day['user_id']
        
        return assignments

    def create_user_info_embed_data(self, user_bet: Dict[str, Any]) -> Dict[str, Any]:
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
            winner = self.get_daily_winner(game_date)
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
                'value': '⏳ Waiting for 13:37...',
                'inline': False
            })

        return embed_data

    def create_winner_embed_data(self, winner_data: Dict[str, Any], winner_role: str, 
                                top_14_day: Optional[Dict[str, Any]], 
                                top_365_day: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Create data for winner announcement embed (Discord-independent)"""
        embed_data = {
            'title': '🏆 Daily 1337 Winner Announced!',
            'color': 0x00FF00,
            'fields': []
        }
        
        # Winner info
        embed_data['fields'].append({
            'name': '🎯 Winner',
            'value': f"**{winner_data['username']}**",
            'inline': True
        })
        
        # Timing info
        embed_data['fields'].append({
            'name': '⏰ Bet Time',
            'value': f"`{self.format_time_with_ms(winner_data['play_time'])}`",
            'inline': True
        })
        
        embed_data['fields'].append({
            'name': '🎲 Win Time',
            'value': f"`{self.format_time_with_ms(winner_data['win_time'])}`",
            'inline': True
        })
        
        # Performance info
        bet_type_emoji = "🐦 Early Bird" if winner_data['bet_type'] == 'early_bird' else "⚡ Regular"
        embed_data['fields'].append({
            'name': '📊 Performance',
            'value': f"{bet_type_emoji}\n**{winner_data['millisecond_diff']}ms** before win time",
            'inline': True
        })
        
        # Role info
        embed_data['fields'].append({
            'name': '🏅 New Role',
            'value': winner_role,
            'inline': True
        })
        
        # Total wins
        user_total_wins = self.get_winner_stats(user_id=winner_data['user_id'])
        embed_data['fields'].append({
            'name': '🏆 Total Wins',
            'value': f"**{user_total_wins}** wins",
            'inline': True
        })
        
        # Add role hierarchy info if there are role changes
        role_updates = []
        if top_365_day:
            role_updates.append(f"🎖️ **General:** {top_365_day['username']} ({top_365_day['wins']} wins)")
        if top_14_day and (not top_365_day or top_14_day['user_id'] != top_365_day['user_id']):
            role_updates.append(f"🔥 **Commander:** {top_14_day['username']} ({top_14_day['wins']} wins)")
        
        if role_updates:
            embed_data['fields'].append({
                'name': '👑 Current Leaders',
                'value': "\n".join(role_updates),
                'inline': False
            })
        
        embed_data['footer_text'] = '🎮 Join tomorrow\'s battle at 13:37! Use /1337 or /1337-early-bird'
        
        return embed_data

    def get_stats_page_data(self, page: int) -> Dict[str, Any]:
        """Get statistics page data (Discord-independent)"""
        pages = ["365 Days", "14 Days", "Daily Bets"]
        
        embed_data = {
            'title': '📊 1337 Game Statistics',
            'color': 0x1337FF,
            'fields': []
        }

        if page == 0:  # 365 Days
            stats = self.get_winner_stats(days=365)
            embed_data['fields'].append({
                'name': '🏆 Top Players (Last 365 Days)',
                'value': self._format_stats_list(stats) if stats else 'No winners yet',
                'inline': False
            })

        elif page == 1:  # 14 Days
            stats = self.get_winner_stats(days=14)
            embed_data['fields'].append({
                'name': '🔥 Top Players (Last 14 Days)',
                'value': self._format_stats_list(stats) if stats else 'No winners yet',
                'inline': False
            })

        elif page == 2:  # Daily Bets
            game_passed = self.is_game_time_passed()
            
            if game_passed:
                # Show today's bets
                today_bets = self.get_daily_bets()
                embed_data['fields'].append({
                    'name': '📅 Today\'s Players',
                    'value': self._format_daily_bets(today_bets) if today_bets else 'No bets today',
                    'inline': False
                })
            else:
                # Show yesterday's bets
                yesterday_date = self.get_yesterday_date()
                yesterday_bets = self.get_daily_bets(yesterday_date)
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

    def get_winner_role_name(self, winner_data: Dict[str, Any]) -> str:
        """Determine winner's new role name based on their position"""
        winner_14_days = self.get_winner_stats(days=14)
        winner_365_days = self.get_winner_stats(days=365)
        
        top_14_day = winner_14_days[0] if winner_14_days else None
        top_365_day = winner_365_days[0] if winner_365_days else None
        
        if top_365_day and winner_data['user_id'] == top_365_day['user_id']:
            return "🎖️ General"
        elif top_14_day and winner_data['user_id'] == top_14_day['user_id']:
            return "🔥 Commander"
        else:
            return "🏅 Sergeant"