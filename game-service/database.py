import aiomysql
import logging
from config import Config
from datetime import datetime, date
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.pool = None
    
    async def connect(self):
        """Initialize the connection pool"""
        try:
            self.pool = await aiomysql.create_pool(
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                db=Config.DB_NAME,
                autocommit=True,
                minsize=1,
                maxsize=10
            )
            await self.create_tables()
            logger.info("Database connection pool created successfully")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    async def disconnect(self):
        """Close the connection pool"""
        if self.pool:
            self.pool.close()
            await self.pool.wait_closed()
            logger.info("Database connection pool closed")
    
    async def create_tables(self):
        """Create necessary tables if they don't exist"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    # Create game_1337_bets table
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS game_1337_bets (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            username VARCHAR(255) NOT NULL,
                            play_time DATETIME(3) NOT NULL,
                            game_date DATE NOT NULL,
                            bet_type ENUM('regular', 'early_bird') NOT NULL DEFAULT 'regular',
                            server_id BIGINT,
                            channel_id BIGINT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_user_per_day (user_id, game_date),
                            INDEX idx_game_date (game_date),
                            INDEX idx_user_id (user_id),
                            INDEX idx_play_time (play_time)
                        )
                    """)
                    
                    # Create game_1337_winners table
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS game_1337_winners (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            username VARCHAR(255) NOT NULL,
                            game_date DATE NOT NULL,
                            win_time DATETIME(3) NOT NULL,
                            play_time DATETIME(3) NOT NULL,
                            bet_type ENUM('regular', 'early_bird') NOT NULL,
                            millisecond_diff INT NOT NULL,
                            server_id BIGINT,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_date (game_date),
                            INDEX idx_user_id (user_id),
                            INDEX idx_game_date (game_date)
                        )
                    """)
                    
                    # Create game_1337_roles table
                    await cursor.execute("""
                        CREATE TABLE IF NOT EXISTS game_1337_roles (
                            id INT AUTO_INCREMENT PRIMARY KEY,
                            guild_id BIGINT NOT NULL,
                            user_id BIGINT NOT NULL,
                            role_type ENUM('sergeant', 'commander', 'general') NOT NULL,
                            role_id BIGINT NOT NULL,
                            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                            UNIQUE KEY unique_guild_role (guild_id, role_type),
                            INDEX idx_guild_user (guild_id, user_id),
                            INDEX idx_user_id (user_id)
                        )
                    """)
                    
                    logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    async def save_1337_bet(self, user_id: int, username: str, play_time: datetime, 
                           game_date: date, bet_type: str = 'regular', 
                           server_id: Optional[int] = None, channel_id: Optional[int] = None) -> bool:
        """Save a 1337 bet to the database"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO game_1337_bets (user_id, username, play_time, game_date, bet_type, server_id, channel_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        play_time = VALUES(play_time),
                        bet_type = VALUES(bet_type),
                        username = VALUES(username)
                    """, (user_id, username, play_time, game_date, bet_type, server_id, channel_id))
                    
                    logger.info(f"Saved 1337 bet for user {username} ({user_id}) on {game_date}")
                    return True
        except Exception as e:
            logger.error(f"Error saving 1337 bet: {e}")
            return False
    
    async def get_user_bet(self, user_id: int, game_date: date) -> Optional[Dict[str, Any]]:
        """Get user's bet for a specific date"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT user_id, username, play_time, bet_type, game_date, server_id, channel_id
                        FROM game_1337_bets 
                        WHERE user_id = %s AND game_date = %s
                    """, (user_id, game_date))
                    
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'user_id': row['user_id'],
                            'username': row['username'],
                            'play_time': row['play_time'],
                            'bet_type': row['bet_type'],
                            'game_date': row['game_date'],
                            'guild_id': row['server_id'],
                            'channel_id': row['channel_id']
                        }
                    return None
        except Exception as e:
            logger.error(f"Error fetching user bet: {e}")
            return None
    
    async def get_daily_bets(self, game_date: date) -> List[Dict[str, Any]]:
        """Get all bets for a specific date"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT user_id, username, play_time, bet_type, server_id, channel_id
                        FROM game_1337_bets 
                        WHERE game_date = %s
                        ORDER BY play_time ASC
                    """, (game_date,))
                    
                    rows = await cursor.fetchall()
                    return [
                        {
                            'user_id': row['user_id'],
                            'username': row['username'],
                            'play_time': row['play_time'],
                            'bet_type': row['bet_type'],
                            'server_id': row['server_id'],
                            'channel_id': row['channel_id']
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error fetching daily bets: {e}")
            return []
    
    async def save_1337_winner(self, user_id: int, username: str, game_date: date, 
                              win_time: datetime, play_time: datetime, bet_type: str, 
                              millisecond_diff: int, server_id: Optional[int] = None) -> bool:
        """Save a 1337 winner to the database"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO game_1337_winners (user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id),
                        username = VALUES(username),
                        win_time = VALUES(win_time),
                        play_time = VALUES(play_time),
                        bet_type = VALUES(bet_type),
                        millisecond_diff = VALUES(millisecond_diff)
                    """, (user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id))
                    
                    logger.info(f"Saved 1337 winner for user {username} ({user_id}) on {game_date}")
                    return True
        except Exception as e:
            logger.error(f"Error saving 1337 winner: {e}")
            return False
    
    async def get_daily_winner(self, game_date: date) -> Optional[Dict[str, Any]]:
        """Get the winner for a specific date"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT user_id, username, win_time, play_time, bet_type, millisecond_diff
                        FROM game_1337_winners 
                        WHERE game_date = %s
                    """, (game_date,))
                    
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'user_id': row['user_id'],
                            'username': row['username'],
                            'win_time': row['win_time'],
                            'play_time': row['play_time'],
                            'bet_type': row['bet_type'],
                            'millisecond_diff': row['millisecond_diff']
                        }
                    return None
        except Exception as e:
            logger.error(f"Error fetching daily winner: {e}")
            return None
    
    async def get_winner_stats(self, user_id: Optional[int] = None, days: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get winner statistics"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    if user_id and days:
                        await cursor.execute("""
                            SELECT COUNT(*) as wins
                            FROM game_1337_winners 
                            WHERE user_id = %s AND game_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                        """, (user_id, days))
                        row = await cursor.fetchone()
                        return [{'wins': row['wins']}] if row else [{'wins': 0}]
                    elif user_id:
                        await cursor.execute("""
                            SELECT COUNT(*) as wins
                            FROM game_1337_winners 
                            WHERE user_id = %s
                        """, (user_id,))
                        row = await cursor.fetchone()
                        return [{'wins': row['wins']}] if row else [{'wins': 0}]
                    elif days:
                        await cursor.execute("""
                            SELECT user_id, username, COUNT(*) as wins, MAX(game_date) as last_win
                            FROM game_1337_winners 
                            WHERE game_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
                            GROUP BY user_id, username
                            ORDER BY wins DESC, last_win DESC
                        """, (days,))
                    else:
                        await cursor.execute("""
                            SELECT user_id, username, COUNT(*) as wins, MAX(game_date) as last_win
                            FROM game_1337_winners 
                            GROUP BY user_id, username
                            ORDER BY wins DESC, last_win DESC
                        """)
                    
                    rows = await cursor.fetchall()
                    return [
                        {
                            'user_id': row['user_id'],
                            'username': row['username'],
                            'wins': row['wins'],
                            'last_win': row['last_win']
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error fetching winner stats: {e}")
            return []
    
    async def set_role_assignment(self, guild_id: int, user_id: int, role_type: str, role_id: int) -> bool:
        """Set or update role assignment for a user in a specific guild"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute("""
                        INSERT INTO game_1337_roles (guild_id, user_id, role_type, role_id)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                        user_id = VALUES(user_id),
                        role_id = VALUES(role_id),
                        updated_at = CURRENT_TIMESTAMP
                    """, (guild_id, user_id, role_type, role_id))
                    
                    logger.info(f"Set {role_type} role assignment for user {user_id} in guild {guild_id}")
                    return True
        except Exception as e:
            logger.error(f"Error setting role assignment: {e}")
            return False
    
    async def get_role_assignment(self, guild_id: int, role_type: str) -> Optional[Dict[str, Any]]:
        """Get current role assignment for a specific role type in a guild"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT user_id, role_id
                        FROM game_1337_roles 
                        WHERE guild_id = %s AND role_type = %s
                    """, (guild_id, role_type))
                    
                    row = await cursor.fetchone()
                    if row:
                        return {
                            'user_id': row['user_id'],
                            'role_id': row['role_id']
                        }
                    return None
        except Exception as e:
            logger.error(f"Error fetching role assignment: {e}")
            return None
    
    async def get_all_role_assignments(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all current role assignments for a guild"""
        try:
            async with self.pool.acquire() as connection:
                async with connection.cursor(aiomysql.DictCursor) as cursor:
                    await cursor.execute("""
                        SELECT user_id, role_type, role_id
                        FROM game_1337_roles 
                        WHERE guild_id = %s
                    """, (guild_id,))
                    
                    rows = await cursor.fetchall()
                    return [
                        {
                            'user_id': row['user_id'],
                            'role_type': row['role_type'],
                            'role_id': row['role_id']
                        }
                        for row in rows
                    ]
        except Exception as e:
            logger.error(f"Error fetching all role assignments: {e}")
            return []