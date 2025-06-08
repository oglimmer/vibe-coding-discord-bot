"""
1337 Game Logic with Cron-based Scheduling.
"""

import asyncio
import random
from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Tuple, Callable
import pytz
import discord
from croniter import croniter
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Game1337Bet, Game1337PlayerStats, BetType
from bot.config import Config
from utils.logger import setup_logger

logger = setup_logger('game_1337')


class Game1337Manager:
    """Manager for 1337 game with cron-based scheduling."""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.timezone = pytz.timezone(Config.GAME_1337_TIMEZONE)
        self.cron_expression = Config.GAME_1337_CRON
        self._daily_win_time_cache = {}  # Cache for win times by date
        self._running = False
        self._scheduler_task = None
        self._game_callbacks = []  # Callbacks to call when game triggers
        self._bot = None  # Will be set from the bot instance
    
    def set_bot(self, bot):
        """Set the bot instance for role management."""
        self._bot = bot
    
    def add_game_callback(self, callback: Callable[[datetime], None]):
        """Add a callback to be called when a game is triggered."""
        self._game_callbacks.append(callback)
    
    def get_current_date(self) -> str:
        """Get current date in bot timezone as YYYY-MM-DD string."""
        now = datetime.now(self.timezone)
        return now.strftime('%Y-%m-%d')
    
    def get_current_datetime(self) -> datetime:
        """Get current datetime in bot timezone."""
        return datetime.now(self.timezone)
    
    def get_next_game_time(self, after_time: Optional[datetime] = None) -> datetime:
        """
        Get the next scheduled game time based on cron expression.
        
        Args:
            after_time: Calculate next time after this datetime
            
        Returns:
            Next game datetime in timezone
        """
        if after_time is None:
            after_time = self.get_current_datetime()
        
        # Convert to UTC for croniter
        utc_time = after_time.astimezone(pytz.UTC)
        
        # Create croniter instance
        cron = croniter(self.cron_expression, utc_time)
        next_utc = cron.get_next(datetime)
        
        # Convert back to configured timezone
        return next_utc.astimezone(self.timezone)
    
    def get_previous_game_time(self, before_time: Optional[datetime] = None) -> datetime:
        """
        Get the previous scheduled game time based on cron expression.
        
        Args:
            before_time: Calculate previous time before this datetime
            
        Returns:
            Previous game datetime in timezone
        """
        if before_time is None:
            before_time = self.get_current_datetime()
        
        # Convert to UTC for croniter
        utc_time = before_time.astimezone(pytz.UTC)
        
        # Create croniter instance
        cron = croniter(self.cron_expression, utc_time)
        prev_utc = cron.get_prev(datetime)
        
        # Convert back to configured timezone
        return prev_utc.astimezone(self.timezone)
    
    def get_early_bird_cutoff_time(self, game_time: datetime) -> datetime:
        """
        Get early bird cutoff time (N hours before game).
        
        Args:
            game_time: Scheduled game time
            
        Returns:
            Early bird cutoff datetime
        """
        cutoff_hours = Config.GAME_1337_EARLY_BIRD_CUTOFF_HOURS
        return game_time - timedelta(hours=cutoff_hours)
    
    def is_early_bird_period(self, check_time: Optional[datetime] = None) -> Tuple[bool, Optional[datetime]]:
        """
        Check if current time is in early bird period.
        
        Args:
            check_time: Time to check, defaults to now
            
        Returns:
            Tuple of (is_early_bird, next_game_time)
        """
        if check_time is None:
            check_time = self.get_current_datetime()
        
        next_game = self.get_next_game_time(check_time)
        cutoff_time = self.get_early_bird_cutoff_time(next_game)
        
        # Early bird period is between now and cutoff time
        is_early_bird = check_time < cutoff_time
        
        return is_early_bird, next_game
    
    def generate_win_time(self, game_datetime: datetime) -> int:
        """
        Generate deterministic win time for a specific game.
        
        Args:
            game_datetime: Exact game start time
            
        Returns:
            Win time in milliseconds after game start (0-60000)
        """
        # Create unique seed from game datetime
        seed_string = f"1337_game_{game_datetime.isoformat()}"
        
        # Check cache first
        if seed_string in self._daily_win_time_cache:
            return self._daily_win_time_cache[seed_string]
        
        # Generate deterministic random number
        random.seed(seed_string)
        win_time = random.randint(0, 60000)
        
        # Cache the result
        self._daily_win_time_cache[seed_string] = win_time
        
        logger.info(f"Generated win time for {game_datetime}: {win_time}ms")
        return win_time
    
    def get_game_end_datetime(self, game_start: datetime) -> datetime:
        """Get the exact moment when the game ends (game_start + win_time)."""
        win_time_ms = self.generate_win_time(game_start)
        return game_start + timedelta(milliseconds=win_time_ms)
    
    def is_game_active(self, check_time: Optional[datetime] = None) -> Tuple[bool, Optional[datetime], Optional[datetime]]:
        """
        Check if a game is currently active.
        
        Args:
            check_time: Time to check, defaults to now
            
        Returns:
            Tuple of (is_active, game_start, game_end)
        """
        if check_time is None:
            check_time = self.get_current_datetime()
        
        # Get the most recent game start time
        prev_game = self.get_previous_game_time(check_time)
        game_end = self.get_game_end_datetime(prev_game)
        
        is_active = prev_game <= check_time <= game_end
        
        return is_active, prev_game if is_active else None, game_end if is_active else None
    
    def can_place_bet(self, check_time: Optional[datetime] = None) -> Tuple[bool, str, Optional[datetime]]:
        """
        Check if a bet can be placed right now.
        
        Args:
            check_time: Time to check, defaults to now
            
        Returns:
            Tuple of (can_place, reason, next_game_time)
        """
        if check_time is None:
            check_time = self.get_current_datetime()
        
        # Check if game is currently active
        is_active, game_start, game_end = self.is_game_active(check_time)
        
        if is_active:
            return True, "✅ Spiel ist aktiv - Wette kann platziert werden.", None
        
        # Check if in early bird period
        is_early_bird, next_game = self.is_early_bird_period(check_time)
        
        if is_early_bird:
            cutoff_time = self.get_early_bird_cutoff_time(next_game)
            return True, f"✅ Early-Bird Periode bis {cutoff_time.strftime('%H:%M:%S')} Uhr.", next_game
        
        # Neither active game nor early bird period
        next_game = self.get_next_game_time(check_time)
        return False, f"❌ Nächstes Spiel: {next_game.strftime('%d.%m.%Y um %H:%M:%S')} Uhr.", next_game
    
    async def has_user_bet_for_game(self, user_id: str, game_datetime: datetime) -> bool:
        """Check if user has already placed a bet for a specific game."""
        game_date_str = game_datetime.strftime('%Y-%m-%d')
        
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(Game1337Bet).filter(
                    and_(
                        Game1337Bet.user_id == user_id,
                        Game1337Bet.date == game_date_str
                    )
                )
            )
            return result.first() is not None
    
    async def place_normal_bet(self, user_id: str, username: str, guild_id: Optional[str] = None) -> Tuple[bool, str, Optional[int]]:
        """
        Place a normal bet at the current moment.
        
        Returns:
            Tuple of (success, message, play_time_ms)
        """
        current_time = self.get_current_datetime()
        
        # Check if bet can be placed
        can_place, reason, next_game = self.can_place_bet(current_time)
        if not can_place:
            return False, reason, None
        
        # Find the active game
        is_active, game_start, game_end = self.is_game_active(current_time)
        
        if not is_active:
            return False, "❌ Kein aktives Spiel für normale Wetten.", None
        
        # Check if user already bet for this game
        if await self.has_user_bet_for_game(user_id, game_start):
            return False, "❌ Du hast für dieses Spiel bereits eine Wette platziert!", None
        
        # Calculate play time
        play_time_ms = int((current_time - game_start).total_seconds() * 1000)
        
        # Ensure play_time is not negative
        if play_time_ms < 0:
            return False, "❌ Das Spiel hat noch nicht begonnen!", None
        
        # Save bet to database
        game_date_str = game_start.strftime('%Y-%m-%d')
        bet = Game1337Bet(
            user_id=user_id,
            username=username,
            play_time=play_time_ms,
            play_type=BetType.NORMAL,
            date=game_date_str,
            guild_id=guild_id
        )
        
        try:
            async with self.db_manager.get_session() as session:
                session.add(bet)
                await session.commit()
                
            logger.info(f"Normal bet placed by {username} ({user_id}): {play_time_ms}ms for game {game_start}")
            return True, f"✅ Wette platziert um **{current_time.strftime('%H:%M:%S.%f')[:-3]}** Uhr!", play_time_ms
            
        except Exception as e:
            logger.error(f"Error placing normal bet: {e}")
            return False, "❌ Fehler beim Speichern der Wette.", None
    
    async def place_early_bet(self, user_id: str, username: str, play_time_ms: int, guild_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        Place an early bet with predefined time.
        
        Args:
            user_id: Discord user ID
            username: Display name
            play_time_ms: Bet time in milliseconds after game start
            guild_id: Guild ID
            
        Returns:
            Tuple of (success, message)
        """
        current_time = self.get_current_datetime()
        
        # Check if we're in early bird period
        is_early_bird, next_game = self.is_early_bird_period(current_time)
        
        if not is_early_bird:
            can_place, reason, _ = self.can_place_bet(current_time)
            if not can_place:
                return False, reason
            return False, "❌ Early-Bird Periode ist vorbei!"
        
        # Check if user already bet for the next game
        if await self.has_user_bet_for_game(user_id, next_game):
            return False, "❌ Du hast für das nächste Spiel bereits eine Wette platziert!"
        
        # Save bet to database
        game_date_str = next_game.strftime('%Y-%m-%d')
        bet = Game1337Bet(
            user_id=user_id,
            username=username,
            play_time=play_time_ms,
            play_type=BetType.EARLY,
            date=game_date_str,
            guild_id=guild_id
        )
        
        try:
            async with self.db_manager.get_session() as session:
                session.add(bet)
                await session.commit()
                
            from utils.time_parser import format_milliseconds_to_time
            formatted_time = format_milliseconds_to_time(play_time_ms)
            
            # Assign early bird role if configured and bot is available
            if guild_id:
                await self.assign_early_bird_role(user_id, guild_id)
            
            logger.info(f"Early bet placed by {username} ({user_id}): {play_time_ms}ms for game {next_game}")
            return True, f"✅ Early-Bird Wette platziert für **{formatted_time}** nach Spielstart!\nNächstes Spiel: **{next_game.strftime('%d.%m.%Y um %H:%M:%S')}** Uhr"
            
        except Exception as e:
            logger.error(f"Error placing early bet: {e}")
            return False, "❌ Fehler beim Speichern der Wette."
    
    async def determine_winner(self, game_datetime: datetime) -> Optional[Dict]:
        """
        Determine the winner for a specific game.
        
        Args:
            game_datetime: The exact game start time
            
        Returns:
            Dict with winner info or None if no valid bets
        """
        game_date_str = game_datetime.strftime('%Y-%m-%d')
        win_time_ms = self.generate_win_time(game_datetime)
        
        async with self.db_manager.get_session() as session:
            # Get all bets for the game date
            result = await session.execute(
                select(Game1337Bet).filter(
                    Game1337Bet.date == game_date_str
                ).order_by(desc(Game1337Bet.play_time))
            )
            all_bets = result.scalars().all()
        
        if not all_bets:
            return None
        
        # Find normal bets within ±3 seconds of win time
        normal_bets_near_win = [
            bet for bet in all_bets 
            if bet.play_type == BetType.NORMAL and abs(bet.play_time - win_time_ms) <= 3000
        ]
        
        # Filter valid bets
        valid_bets = []
        
        # If there are normal bets near win time, early bets are invalid
        if normal_bets_near_win:
            valid_bets = [bet for bet in all_bets if bet.play_type == BetType.NORMAL]
        else:
            # All bets are valid
            valid_bets = all_bets
        
        # Find the latest bet that is <= win_time
        winner = None
        for bet in sorted(valid_bets, key=lambda x: x.play_time, reverse=True):
            if bet.play_time <= win_time_ms:
                winner = bet
                break
        
        if winner:
            return {
                'winner': winner,
                'win_time_ms': win_time_ms,
                'delta_ms': win_time_ms - winner.play_time,
                'total_bets': len(all_bets),
                'valid_bets': len(valid_bets),
                'game_datetime': game_datetime
            }
        
        return None
    
    async def get_game_leaderboard(self, game_datetime: datetime) -> List[Game1337Bet]:
        """Get all bets for a specific game, sorted by time."""
        game_date_str = game_datetime.strftime('%Y-%m-%d')
        
        async with self.db_manager.get_session() as session:
            result = await session.execute(
                select(Game1337Bet).filter(
                    Game1337Bet.date == game_date_str
                ).order_by(Game1337Bet.play_time)
            )
            return result.scalars().all()
    
    async def start_scheduler(self):
        """Start the cron-based game scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return
        
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Started 1337 game scheduler with cron: {self.cron_expression}")
    
    async def stop_scheduler(self):
        """Stop the game scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped 1337 game scheduler")
    
    async def _scheduler_loop(self):
        """Internal scheduler loop that waits for cron triggers."""
        try:
            while self._running:
                current_time = self.get_current_datetime()
                next_game = self.get_next_game_time(current_time)
                
                # Calculate seconds until next game
                time_until_game = (next_game - current_time).total_seconds()
                
                if time_until_game <= 0:
                    # Game should have started - trigger it
                    await self._trigger_game(next_game)
                    # Wait a bit to avoid immediate re-trigger
                    await asyncio.sleep(1)
                else:
                    # Wait until the next game
                    logger.info(f"Next 1337 game in {time_until_game:.1f} seconds at {next_game}")
                    await asyncio.sleep(min(time_until_game, 300))  # Check at least every 5 minutes
        
        except asyncio.CancelledError:
            logger.info("Scheduler loop cancelled")
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}")
    
    async def _trigger_game(self, game_datetime: datetime):
        """Trigger a game at the specified time."""
        logger.info(f"Game 1337 triggered at {game_datetime}")
        
        # Wait for the game to complete (win_time_ms after start)
        win_time_ms = self.generate_win_time(game_datetime)
        await asyncio.sleep(win_time_ms / 1000.0)  # Convert to seconds
        
        # Process game completion
        await self.process_game_completion(game_datetime)
        
        # Call all registered callbacks
        for callback in self._game_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(game_datetime)
                else:
                    callback(game_datetime)
            except Exception as e:
                logger.error(f"Error calling game callback: {e}")
    
    async def process_game_completion(self, game_datetime: datetime):
        """
        Process the completion of a game - determine winner and update stats.
        
        Args:
            game_datetime: The exact game start time
        """
        try:
            logger.info(f"Processing game completion for {game_datetime}")
            
            # Determine the winner
            winner_info = await self.determine_winner(game_datetime)
            if not winner_info:
                logger.info(f"No winner found for game {game_datetime}")
                return
            
            winner_bet = winner_info['winner']
            game_date_str = game_datetime.strftime('%Y-%m-%d')
            
            # Get all bets for this game
            all_bets = await self.get_game_leaderboard(game_datetime)
            
            # Update stats for all players who participated
            for bet in all_bets:
                is_winner = (bet.user_id == winner_bet.user_id)
                is_early_bird = (bet.play_type == BetType.EARLY)
                
                # Update player statistics
                await self.update_player_stats(
                    user_id=bet.user_id,
                    username=bet.username,
                    guild_id=bet.guild_id,
                    is_winner=is_winner,
                    play_time_ms=bet.play_time,
                    is_early_bird=is_early_bird,
                    game_date=game_date_str
                )
                
                # Assign appropriate roles
                if bet.guild_id:
                    if is_winner:
                        # Assign winner role
                        await self.assign_winner_role(bet.user_id, bet.guild_id)
                    
                    if is_early_bird:
                        # Assign early bird role
                        await self.assign_early_bird_role(bet.user_id, bet.guild_id)
                    
                    # Update rank-based roles (for all players)
                    await self.assign_rank_roles(bet.user_id, bet.guild_id)
            
            logger.info(f"Game completion processed: Winner {winner_bet.username} ({winner_bet.user_id})")
            
        except Exception as e:
            logger.error(f"Error processing game completion for {game_datetime}: {e}")
    
    def format_next_games(self, count: int = 5) -> str:
        """
        Format the next N game times as a string.
        
        Args:
            count: Number of next games to show
            
        Returns:
            Formatted string with next game times
        """
        current_time = self.get_current_datetime()
        next_games = []
        
        # Get next 'count' games
        check_time = current_time
        for _ in range(count):
            next_game = self.get_next_game_time(check_time)
            next_games.append(next_game)
            check_time = next_game + timedelta(seconds=1)
        
        # Format the list
        formatted_games = []
        for i, game_time in enumerate(next_games):
            day_name = game_time.strftime('%A')
            date_str = game_time.strftime('%d.%m.%Y')
            time_str = game_time.strftime('%H:%M:%S')
            
            if i == 0:
                formatted_games.append(f"🎯 **{day_name}, {date_str} um {time_str}** Uhr")
            else:
                formatted_games.append(f"📅 {day_name}, {date_str} um {time_str} Uhr")
        
        return "\n".join(formatted_games)
    
    async def update_player_stats(self, user_id: str, username: str, guild_id: str, is_winner: bool, play_time_ms: int, is_early_bird: bool, game_date: str):
        """
        Update player statistics using the database function.
        
        Args:
            user_id: Discord user ID
            username: Current username
            guild_id: Discord guild ID
            is_winner: Whether the player won this game
            play_time_ms: Play time in milliseconds
            is_early_bird: Whether this was an early bird bet
            game_date: Game date in YYYY-MM-DD format
        """
        try:
            async with self.db_manager.get_session() as session:
                # Call the database function to update player stats
                await session.execute(
                    func.update_1337_player_stats(
                        user_id, username, guild_id, is_winner, 
                        play_time_ms, is_early_bird, game_date
                    )
                )
                await session.commit()
                logger.info(f"Updated stats for {username} ({user_id}): win={is_winner}, time={play_time_ms}ms")
        except Exception as e:
            logger.error(f"Error updating player stats for {user_id}: {e}")
    
    async def get_player_stats(self, user_id: str) -> Optional[Game1337PlayerStats]:
        """Get player statistics for a specific user."""
        try:
            async with self.db_manager.get_session() as session:
                result = await session.execute(
                    select(Game1337PlayerStats).filter(
                        Game1337PlayerStats.user_id == user_id
                    )
                )
                return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting player stats for {user_id}: {e}")
            return None
    
    def get_role_id_for_rank(self, rank_title: str) -> Optional[str]:
        """Get the role ID for a specific rank title."""
        role_mapping = {
            "Leet General": Config.GAME_1337_LEET_GENERAL_ROLE_ID,
            "Leet Commander": Config.GAME_1337_LEET_COMMANDER_ROLE_ID,
            "Leet Sergeant": Config.GAME_1337_LEET_SERGEANT_ROLE_ID,
        }
        return role_mapping.get(rank_title)
    
    async def assign_rank_roles(self, user_id: str, guild_id: str):
        """
        Assign rank-based roles to a user based on their total wins.
        
        Args:
            user_id: Discord user ID
            guild_id: Discord guild ID
        """
        if not self._bot:
            logger.warning("Bot instance not set for role assignment")
            return
        
        # Get player stats
        player_stats = await self.get_player_stats(user_id)
        if not player_stats:
            logger.warning(f"No stats found for user {user_id} to assign role")
            return
        
        # Get the guild and member
        guild = self._bot.get_guild(int(guild_id))
        if not guild:
            logger.warning(f"Guild {guild_id} not found")
            return
            
        member = guild.get_member(int(user_id))
        if not member:
            logger.warning(f"Member {user_id} not found in guild {guild_id}")
            return
        
        # Get the current rank and required role
        current_rank = player_stats.rank_title
        target_role_id = self.get_role_id_for_rank(current_rank)
        
        if not target_role_id:
            logger.info(f"No role configured for rank '{current_rank}' for user {user_id}")
            return
        
        # Get the role object
        target_role = guild.get_role(int(target_role_id))
        if not target_role:
            logger.warning(f"Role with ID {target_role_id} not found in guild {guild_id}")
            return
        
        # Check if user already has this role
        if target_role in member.roles:
            logger.debug(f"User {user_id} already has role {target_role.name}")
            return
        
        # Remove all other rank roles first
        all_rank_role_ids = [
            Config.GAME_1337_LEET_SERGEANT_ROLE_ID,
            Config.GAME_1337_LEET_COMMANDER_ROLE_ID,
            Config.GAME_1337_LEET_GENERAL_ROLE_ID
        ]
        
        roles_to_remove = []
        for role_id in all_rank_role_ids:
            if role_id and role_id != target_role_id:
                role = guild.get_role(int(role_id))
                if role and role in member.roles:
                    roles_to_remove.append(role)
        
        try:
            # Remove old rank roles
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason="1337 Game rank update")
                logger.info(f"Removed old rank roles from {member.display_name}: {[r.name for r in roles_to_remove]}")
            
            # Add new rank role
            await member.add_roles(target_role, reason="1337 Game rank promotion")
            logger.info(f"Assigned rank role '{target_role.name}' to {member.display_name} ({user_id}) for {player_stats.total_wins} wins")
            
        except Exception as e:
            logger.error(f"Error updating rank roles for user {user_id}: {e}")
    
    async def assign_winner_role(self, user_id: str, guild_id: str):
        """Assign the winner role to a user."""
        if not self._bot or not Config.GAME_1337_WINNER_ROLE_ID:
            return
        
        guild = self._bot.get_guild(int(guild_id))
        if not guild:
            return
            
        member = guild.get_member(int(user_id))
        if not member:
            return
        
        role = guild.get_role(int(Config.GAME_1337_WINNER_ROLE_ID))
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="1337 Game winner")
                logger.info(f"Assigned winner role to {member.display_name}")
            except Exception as e:
                logger.error(f"Error assigning winner role to {user_id}: {e}")
    
    async def assign_early_bird_role(self, user_id: str, guild_id: str):
        """Assign the early bird role to a user."""
        if not self._bot or not Config.GAME_1337_EARLY_BIRD_ROLE_ID:
            return
        
        guild = self._bot.get_guild(int(guild_id))
        if not guild:
            return
            
        member = guild.get_member(int(user_id))
        if not member:
            return
        
        role = guild.get_role(int(Config.GAME_1337_EARLY_BIRD_ROLE_ID))
        if role and role not in member.roles:
            try:
                await member.add_roles(role, reason="1337 Game early bird")
                logger.info(f"Assigned early bird role to {member.display_name}")
            except Exception as e:
                logger.error(f"Error assigning early bird role to {user_id}: {e}")
