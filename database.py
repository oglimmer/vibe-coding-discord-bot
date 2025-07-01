import mariadb
import logging
from config import Config
import dataclasses
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class GreetingRecord:
    username: str
    greeting_time: datetime
    reaction_count: int = 0

class DatabaseManager:
    def __init__(self):
        self.create_tables()
    
    def _get_connection(self):
        """Get a fresh database connection for each operation"""
        try:
            connection = mariadb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME
            )
            return connection
        except mariadb.Error as e:
            logger.error(f"Error connecting to MariaDB: {e}")
            raise
    
    def create_tables(self):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS greetings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    greeting_message TEXT,
                    greeting_date DATE NOT NULL,
                    greeting_time TIME NOT NULL,
                    server_id BIGINT,
                    channel_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_user_date (user_id, greeting_date),
                    INDEX idx_date (greeting_date)
                )
            """)
            
            # Migration: Add message_id column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE greetings ADD COLUMN message_id BIGINT")
                cursor.execute("ALTER TABLE greetings ADD INDEX idx_message_id (message_id)")
                logger.info("Added message_id column to greetings table")
            except mariadb.Error as e:
                if "Duplicate column name" in str(e):
                    logger.info("message_id column already exists in greetings table")
                else:
                    logger.warning(f"Could not add message_id column: {e}")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS greeting_reactions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    greeting_id INT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    reaction_emoji VARCHAR(50) NOT NULL,
                    reaction_date DATE NOT NULL,
                    reaction_time TIME NOT NULL,
                    server_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (greeting_id) REFERENCES greetings(id) ON DELETE CASCADE,
                    UNIQUE KEY unique_reaction (greeting_id, user_id, reaction_emoji),
                    INDEX idx_greeting_id (greeting_id),
                    INDEX idx_user_id (user_id),
                    INDEX idx_reaction_date (reaction_date)
                )
            """)
            
            cursor.execute("""
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
            
            cursor.execute("""
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
            
            cursor.execute("""
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
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS klugscheisser_user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    opted_in BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_opted_in (opted_in)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS factcheck_requests (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    requester_user_id BIGINT NOT NULL,
                    requester_username VARCHAR(255) NOT NULL,
                    target_message_id BIGINT NOT NULL,
                    target_user_id BIGINT NOT NULL,
                    target_username VARCHAR(255) NOT NULL,
                    message_content TEXT NOT NULL,
                    request_date DATE NOT NULL,
                    score TINYINT UNSIGNED CHECK (score >= 0 AND score <= 100),
                    factcheck_response TEXT,
                    is_factcheckable BOOLEAN DEFAULT TRUE,
                    server_id BIGINT,
                    channel_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_requester_date (requester_user_id, request_date),
                    INDEX idx_target_message (target_message_id),
                    INDEX idx_request_date (request_date),
                    INDEX idx_factcheckable (is_factcheckable)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_response_cache (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    message_content_hash VARCHAR(64) NOT NULL,
                    message_content TEXT NOT NULL,
                    response_type ENUM('klugscheiss', 'factcheck') NOT NULL,
                    ai_response TEXT NOT NULL,
                    score TINYINT NULL,
                    hit_count INT DEFAULT 1,
                    first_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_hash_type (message_content_hash, response_type),
                    INDEX idx_hash (message_content_hash),
                    INDEX idx_type (response_type),
                    INDEX idx_last_used (last_used)
                )
            """)
            
            # Migration: Add is_factcheckable column if it doesn't exist
            try:
                cursor.execute("ALTER TABLE factcheck_requests ADD COLUMN is_factcheckable BOOLEAN DEFAULT TRUE")
                cursor.execute("ALTER TABLE factcheck_requests ADD INDEX idx_factcheckable (is_factcheckable)")
                logger.info("Added is_factcheckable column to factcheck_requests table")
            except mariadb.Error as e:
                if "Duplicate column name" in str(e):
                    logger.info("is_factcheckable column already exists in factcheck_requests table")
                else:
                    logger.warning(f"Could not add is_factcheckable column: {e}")
            
            connection.commit()
            logger.info("Database tables created successfully")
        except mariadb.Error as e:
            logger.error(f"Error creating tables: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def get_todays_greetings(self, guild_id: Optional[int] = None) -> List[GreetingRecord]:
        """
        Fetch the latest greeting per user for the given guild from today,
        ordered by greeting_time ascending, with reaction counts (excluding poster's own reactions).
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            today = datetime.now().date()
            
            if guild_id:
                cursor.execute("""
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    INNER JOIN (
                        SELECT user_id, MAX(greeting_time) as max_time
                        FROM greetings
                        WHERE server_id = ? AND greeting_date = ?
                        GROUP BY user_id
                    ) latest ON g.user_id = latest.user_id AND g.greeting_time = latest.max_time
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id 
                                                    AND gr.reaction_date = ?
                                                    AND gr.user_id != g.user_id
                    WHERE g.server_id = ? AND g.greeting_date = ?
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """, (guild_id, today, today, guild_id, today))
            else:
                cursor.execute("""
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    INNER JOIN (
                        SELECT user_id, MAX(greeting_time) as max_time
                        FROM greetings
                        WHERE greeting_date = ?
                        GROUP BY user_id
                    ) latest ON g.user_id = latest.user_id AND g.greeting_time = latest.max_time
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id 
                                                    AND gr.reaction_date = ?
                                                    AND gr.user_id != g.user_id
                    WHERE g.greeting_date = ?
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """, (today, today, today))
            
            results = cursor.fetchall()
            return [
                GreetingRecord(username=row[0], greeting_time=row[1], reaction_count=row[2])
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Error fetching today's greetings: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def save_greeting(self, user_id, username, greeting_message, server_id=None, channel_id=None, message_id=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            date = now.date()
            time = now.time()
            
            cursor.execute("""
                INSERT INTO greetings (user_id, username, greeting_message, greeting_date, greeting_time, server_id, channel_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, greeting_message, date, time, server_id, channel_id, message_id))
            
            greeting_id = cursor.lastrowid
            connection.commit()
            logger.info(f"Saved greeting for user {username} ({user_id}) with ID {greeting_id}")
            return greeting_id
        except mariadb.Error as e:
            logger.error(f"Error saving greeting: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def save_greeting_reaction(self, greeting_id, user_id, username, reaction_emoji, server_id=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            date = now.date()
            time = now.time()
            
            cursor.execute("""
                INSERT INTO greeting_reactions (greeting_id, user_id, username, reaction_emoji, reaction_date, reaction_time, server_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                reaction_time = VALUES(reaction_time)
            """, (greeting_id, user_id, username, reaction_emoji, date, time, server_id))
            
            connection.commit()
            logger.info(f"Saved reaction {reaction_emoji} from {username} ({user_id}) to greeting {greeting_id}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving greeting reaction: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def remove_greeting_reaction(self, greeting_id, user_id, reaction_emoji):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                DELETE FROM greeting_reactions 
                WHERE greeting_id = ? AND user_id = ? AND reaction_emoji = ?
            """, (greeting_id, user_id, reaction_emoji))
            
            connection.commit()
            logger.info(f"Removed reaction {reaction_emoji} from user {user_id} to greeting {greeting_id}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error removing greeting reaction: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_greeting_id_by_message(self, message_id, server_id=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            if server_id:
                cursor.execute("""
                    SELECT id FROM greetings 
                    WHERE message_id = ? AND server_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (message_id, server_id))
            else:
                cursor.execute("""
                    SELECT id FROM greetings 
                    WHERE message_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (message_id,))
            
            result = cursor.fetchone()
            return result[0] if result else None
        except mariadb.Error as e:
            logger.error(f"Error getting greeting ID: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def save_1337_bet(self, user_id, username, play_time, game_date, bet_type='regular', server_id=None, channel_id=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO game_1337_bets (user_id, username, play_time, game_date, bet_type, server_id, channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                play_time = VALUES(play_time),
                bet_type = VALUES(bet_type),
                username = VALUES(username)
            """, (user_id, username, play_time, game_date, bet_type, server_id, channel_id))
            
            connection.commit()
            logger.info(f"Saved 1337 bet for user {username} ({user_id}) on {game_date}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving 1337 bet: {e}")
            return False
        finally:
            if connection:
                connection.close()
    
    def get_user_bet(self, user_id, game_date):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, username, play_time, bet_type
                FROM game_1337_bets 
                WHERE user_id = ? AND game_date = ?
            """, (user_id, game_date))
            
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'username': result[1],
                    'play_time': result[2],
                    'bet_type': result[3]
                }
            return None
        except mariadb.Error as e:
            logger.error(f"Error fetching user bet: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def get_daily_bets(self, game_date):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, username, play_time, bet_type, server_id, channel_id
                FROM game_1337_bets 
                WHERE game_date = ?
                ORDER BY play_time ASC
            """, (game_date,))
            
            results = cursor.fetchall()
            return [
                {
                    'user_id': row[0],
                    'username': row[1],
                    'play_time': row[2],
                    'bet_type': row[3],
                    'server_id': row[4],
                    'channel_id': row[5]
                }
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Error fetching daily bets: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def save_1337_winner(self, user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO game_1337_winners (user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                user_id = VALUES(user_id),
                username = VALUES(username),
                win_time = VALUES(win_time),
                play_time = VALUES(play_time),
                bet_type = VALUES(bet_type),
                millisecond_diff = VALUES(millisecond_diff)
            """, (user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id))
            
            connection.commit()
            logger.info(f"Saved 1337 winner for user {username} ({user_id}) on {game_date}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving 1337 winner: {e}")
            return False
        finally:
            if connection:
                connection.close()
    
    def get_winner_stats(self, user_id=None, days=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            if user_id and days:
                cursor.execute("""
                    SELECT COUNT(*) as wins
                    FROM game_1337_winners 
                    WHERE user_id = ? AND game_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
                """, (user_id, days))
            elif user_id:
                cursor.execute("""
                    SELECT COUNT(*) as wins
                    FROM game_1337_winners 
                    WHERE user_id = ?
                """, (user_id,))
            elif days:
                cursor.execute("""
                    SELECT user_id, username, COUNT(*) as wins, MAX(game_date) as last_win
                    FROM game_1337_winners 
                    WHERE game_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
                    GROUP BY user_id, username
                    ORDER BY wins DESC, last_win DESC
                """, (days,))
            else:
                cursor.execute("""
                    SELECT user_id, username, COUNT(*) as wins, MAX(game_date) as last_win
                    FROM game_1337_winners 
                    GROUP BY user_id, username
                    ORDER BY wins DESC, last_win DESC
                """)
            
            if user_id:
                result = cursor.fetchone()
                return result[0] if result else 0
            else:
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1],
                        'wins': row[2],
                        'last_win': row[3]
                    }
                    for row in results
                ]
        except mariadb.Error as e:
            logger.error(f"Error fetching winner stats: {e}")
            return 0 if user_id else []
        finally:
            if connection:
                connection.close()
    
    def get_daily_winner(self, game_date):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, username, win_time, play_time, bet_type, millisecond_diff
                FROM game_1337_winners 
                WHERE game_date = ?
            """, (game_date,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'username': result[1],
                    'win_time': result[2],
                    'play_time': result[3],
                    'bet_type': result[4],
                    'millisecond_diff': result[5]
                }
            return None
        except mariadb.Error as e:
            logger.error(f"Error fetching daily winner: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def set_role_assignment(self, guild_id, user_id, role_type, role_id):
        """Set or update role assignment for a user in a specific guild"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO game_1337_roles (guild_id, user_id, role_type, role_id)
                VALUES (?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                user_id = VALUES(user_id),
                role_id = VALUES(role_id),
                updated_at = CURRENT_TIMESTAMP
            """, (guild_id, user_id, role_type, role_id))
            
            connection.commit()
            logger.info(f"Set {role_type} role assignment for user {user_id} in guild {guild_id}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error setting role assignment: {e}")
            return False
        finally:
            if connection:
                connection.close()
    
    def get_role_assignment(self, guild_id, role_type):
        """Get current role assignment for a specific role type in a guild"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, role_id
                FROM game_1337_roles 
                WHERE guild_id = ? AND role_type = ?
            """, (guild_id, role_type))
            
            result = cursor.fetchone()
            if result:
                return {
                    'user_id': result[0],
                    'role_id': result[1]
                }
            return None
        except mariadb.Error as e:
            logger.error(f"Error fetching role assignment: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def get_all_role_assignments(self, guild_id):
        """Get all current role assignments for a guild"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT user_id, role_type, role_id
                FROM game_1337_roles 
                WHERE guild_id = ?
            """, (guild_id,))
            
            results = cursor.fetchall()
            return [
                {
                    'user_id': row[0],
                    'role_type': row[1],
                    'role_id': row[2]
                }
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Error fetching all role assignments: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def remove_role_assignment(self, guild_id, role_type):
        """Remove role assignment for a specific role type in a guild"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                DELETE FROM game_1337_roles 
                WHERE guild_id = ? AND role_type = ?
            """, (guild_id, role_type))
            
            connection.commit()
            logger.info(f"Removed {role_type} role assignment in guild {guild_id}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error removing role assignment: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def set_klugscheisser_preference(self, user_id, opted_in):
        """Set or update user's klugscheißer opt-in preference"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                INSERT INTO klugscheisser_user_preferences (user_id, opted_in)
                VALUES (?, ?)
                ON DUPLICATE KEY UPDATE
                opted_in = VALUES(opted_in),
                updated_at = CURRENT_TIMESTAMP
            """, (user_id, opted_in))
            
            connection.commit()
            status = "opted in" if opted_in else "opted out"
            logger.info(f"User {user_id} {status} of klugscheißer feature")
            return True
        except mariadb.Error as e:
            logger.error(f"Error setting klugscheißer preference: {e}")
            return False
        finally:
            if connection:
                connection.close()
    
    def get_klugscheisser_preference(self, user_id):
        """Get user's klugscheißer opt-in preference (default: False)"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT opted_in, created_at
                FROM klugscheisser_user_preferences 
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            if result:
                return {
                    'opted_in': bool(result[0]),
                    'created_at': result[1]
                }
            return {'opted_in': False, 'created_at': None}
        except mariadb.Error as e:
            logger.error(f"Error fetching klugscheißer preference: {e}")
            return {'opted_in': False, 'created_at': None}
        finally:
            if connection:
                connection.close()
    
    def get_opted_in_users_count(self):
        """Get count of users who have opted in to klugscheißer"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM klugscheisser_user_preferences 
                WHERE opted_in = TRUE
            """)
            
            result = cursor.fetchone()
            return result[0] if result else 0
        except mariadb.Error as e:
            logger.error(f"Error fetching opted in users count: {e}")
            return 0
        finally:
            if connection:
                connection.close()

    def save_factcheck_request(self, requester_user_id, requester_username, target_message_id, 
                              target_user_id, target_username, message_content, score=None, 
                              factcheck_response=None, is_factcheckable=True, server_id=None, channel_id=None):
        """Save a fact-check request to the database"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            today = datetime.now().date()
            
            cursor.execute("""
                INSERT INTO factcheck_requests (
                    requester_user_id, requester_username, target_message_id, 
                    target_user_id, target_username, message_content, request_date,
                    score, factcheck_response, is_factcheckable, server_id, channel_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (requester_user_id, requester_username, target_message_id, 
                  target_user_id, target_username, message_content, today,
                  score, factcheck_response, is_factcheckable, server_id, channel_id))
            
            factcheck_id = cursor.lastrowid
            connection.commit()
            logger.info(f"Saved factcheck request from {requester_username} ({requester_user_id}) with ID {factcheck_id}, factcheckable: {is_factcheckable}")
            return factcheck_id
        except mariadb.Error as e:
            logger.error(f"Error saving factcheck request: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def get_daily_factcheck_count(self, user_id, date=None):
        """Get the number of fact-check requests made by a user on a specific date"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            if date is None:
                date = datetime.now().date()
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM factcheck_requests 
                WHERE requester_user_id = ? AND request_date = ?
            """, (user_id, date))
            
            result = cursor.fetchone()
            return result[0] if result else 0
        except mariadb.Error as e:
            logger.error(f"Error fetching daily factcheck count: {e}")
            return 0
        finally:
            if connection:
                connection.close()
    
    def update_factcheck_result(self, factcheck_id, score, factcheck_response):
        """Update a fact-check request with the result and score"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE factcheck_requests 
                SET score = ?, factcheck_response = ?
                WHERE id = ?
            """, (score, factcheck_response, factcheck_id))
            
            connection.commit()
            logger.info(f"Updated factcheck request {factcheck_id} with score {score}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error updating factcheck result: {e}")
            return False
        finally:
            if connection:
                connection.close()
    
    def get_factcheck_statistics(self, user_id=None, days=30):
        """Get fact-check statistics for a user or all users"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            if user_id:
                cursor.execute("""
                    SELECT COUNT(*) as total_requests,
                           AVG(score) as avg_score,
                           MIN(score) as min_score,
                           MAX(score) as max_score
                    FROM factcheck_requests 
                    WHERE requester_user_id = ? 
                      AND request_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
                      AND score IS NOT NULL
                """, (user_id, days))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total_requests': result[0],
                        'avg_score': float(result[1]) if result[1] else 0,
                        'min_score': result[2],
                        'max_score': result[3]
                    }
            else:
                cursor.execute("""
                    SELECT requester_user_id, requester_username,
                           COUNT(*) as total_requests,
                           AVG(score) as avg_score
                    FROM factcheck_requests 
                    WHERE request_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
                      AND score IS NOT NULL
                    GROUP BY requester_user_id, requester_username
                    ORDER BY total_requests DESC
                """, (days,))
                
                results = cursor.fetchall()
                return [
                    {
                        'user_id': row[0],
                        'username': row[1],
                        'total_requests': row[2],
                        'avg_score': float(row[3]) if row[3] else 0
                    }
                    for row in results
                ]
            
            return {} if user_id else []
        except mariadb.Error as e:
            logger.error(f"Error fetching factcheck statistics: {e}")
            return {} if user_id else []
        finally:
            if connection:
                connection.close()

    def get_bullshit_board_data(self, page=0, per_page=10, days=30, sort_by="score_asc"):
        """Get comprehensive bullshit board data with anti-cheat (excludes self-checks from score)"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            # Sort options
            sort_options = {
                "score_asc": "avg_score ASC, times_checked_by_others DESC",  # Lowest accuracy first (most bullshit)
                "score_desc": "avg_score DESC, times_checked_by_others DESC",  # Highest accuracy first
                "checked_desc": "times_checked_by_others DESC, avg_score ASC",
                "activity_desc": "total_activity DESC, avg_score ASC",
                "requests_desc": "total_requests DESC, avg_score ASC"
            }
            order_clause = sort_options.get(sort_by, sort_options["score_asc"])
            
            offset = page * per_page
            
            query = f"""
                SELECT 
                    u.user_id,
                    COALESCE(latest_username.username, 'Unknown') as username,
                    -- Score only from OTHER users (prevents self-manipulation)
                    COALESCE(AVG(target_checks.score), 0) as avg_score,
                    COUNT(target_checks.id) as times_checked_by_others,
                    -- Self-checks separately (don't count toward score)
                    COALESCE(self_checks.self_check_count, 0) as self_checks,
                    -- All requests (including self-checks)
                    COALESCE(requester_stats.total_requests, 0) as total_requests,
                    -- Total activity
                    (COUNT(target_checks.id) + COALESCE(self_checks.self_check_count, 0) + COALESCE(requester_stats.total_requests, 0)) as total_activity,
                    -- Worst single score (from others only)
                    COALESCE(MIN(target_checks.score), 0) as worst_score,
                    -- Weighted Score: avg_score * log(check_count) for better weighting
                    -- Lower accuracy percentage = higher on bullshit board
                    CASE 
                        WHEN COUNT(target_checks.id) > 0 THEN 
                            COALESCE(AVG(target_checks.score), 0) * LOG(COUNT(target_checks.id) + 1)
                        ELSE 0 
                    END as weighted_score
                FROM klugscheisser_user_preferences u
                LEFT JOIN (
                    -- Get latest username for each user
                    SELECT 
                        target_user_id, 
                        target_username as username
                    FROM factcheck_requests
                    WHERE request_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                    GROUP BY target_user_id
                    ORDER BY MAX(created_at) DESC
                ) latest_username ON u.user_id = latest_username.target_user_id
                LEFT JOIN factcheck_requests target_checks 
                    ON u.user_id = target_checks.target_user_id 
                    AND target_checks.requester_user_id != target_checks.target_user_id  -- EXCLUDE self-checks!
                    AND target_checks.score IS NOT NULL
                    AND target_checks.is_factcheckable = TRUE  -- ONLY factcheckable messages count toward score!
                    AND target_checks.request_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                LEFT JOIN (
                    -- Self-checks separately
                    SELECT 
                        target_user_id,
                        COUNT(*) as self_check_count
                    FROM factcheck_requests 
                    WHERE requester_user_id = target_user_id  -- Self-check
                        AND request_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                    GROUP BY target_user_id
                ) self_checks ON u.user_id = self_checks.target_user_id
                LEFT JOIN (
                    -- All requests
                    SELECT 
                        requester_user_id,
                        COUNT(*) as total_requests
                    FROM factcheck_requests 
                    WHERE request_date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
                    GROUP BY requester_user_id
                ) requester_stats ON u.user_id = requester_stats.requester_user_id
                WHERE u.opted_in = TRUE
                GROUP BY u.user_id, latest_username.username, self_checks.self_check_count, requester_stats.total_requests
                HAVING COUNT(target_checks.id) >= 1  -- Min. 1x checked by OTHERS
                ORDER BY {order_clause}
                LIMIT {per_page} OFFSET {offset}
            """
            
            cursor.execute(query)
            
            results = cursor.fetchall()
            return [
                {
                    'user_id': row[0],
                    'username': row[1],
                    'avg_score': float(row[2]) if row[2] else 0.0,
                    'times_checked_by_others': row[3],
                    'self_checks': row[4],
                    'total_requests': row[5],
                    'total_activity': row[6],
                    'worst_score': row[7],
                    'weighted_score': float(row[8]) if row[8] else 0.0
                }
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Error fetching bullshit board data: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def get_bullshit_board_count(self, days=30):
        """Get total count of users eligible for bullshit board"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT COUNT(DISTINCT u.user_id)
                FROM klugscheisser_user_preferences u
                JOIN factcheck_requests target_checks 
                    ON u.user_id = target_checks.target_user_id 
                    AND target_checks.requester_user_id != target_checks.target_user_id  -- EXCLUDE self-checks!
                    AND target_checks.score IS NOT NULL
                    AND target_checks.request_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
                WHERE u.opted_in = TRUE
                GROUP BY u.user_id
                HAVING COUNT(target_checks.id) >= 1  -- Min. 1x checked by OTHERS
            """, (days,))
            
            result = cursor.fetchone()
            return result[0] if result else 0
        except mariadb.Error as e:
            logger.error(f"Error fetching bullshit board count: {e}")
            return 0
        finally:
            if connection:
                connection.close()
    
    def get_user_factcheck_breakdown(self, user_id, days=30):
        """Get detailed breakdown of user's factcheck activity"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            
            cursor.execute("""
                SELECT 
                    -- Checks by others (counts toward score)
                    COUNT(CASE WHEN fcr.requester_user_id != fcr.target_user_id THEN 1 END) as checked_by_others,
                    AVG(CASE WHEN fcr.requester_user_id != fcr.target_user_id THEN fcr.score END) as score_from_others,
                    MIN(CASE WHEN fcr.requester_user_id != fcr.target_user_id THEN fcr.score END) as worst_from_others,
                    -- Self-checks (don't count toward score)
                    COUNT(CASE WHEN fcr.requester_user_id = fcr.target_user_id THEN 1 END) as self_checks,
                    AVG(CASE WHEN fcr.requester_user_id = fcr.target_user_id THEN fcr.score END) as score_from_self,
                    -- Requests made
                    (SELECT COUNT(*) FROM factcheck_requests 
                     WHERE requester_user_id = ? 
                       AND request_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)) as total_requests,
                    -- Unique checkers
                    COUNT(DISTINCT CASE WHEN fcr.requester_user_id != fcr.target_user_id 
                                       THEN fcr.requester_user_id END) as unique_checkers
                FROM factcheck_requests fcr
                WHERE fcr.target_user_id = ? 
                  AND fcr.score IS NOT NULL
                  AND fcr.request_date >= DATE_SUB(CURDATE(), INTERVAL ? DAY)
            """, (user_id, days, user_id, days))
            
            result = cursor.fetchone()
            if result:
                checked_by_others = result[0] or 0
                self_checks = result[4] or 0
                total_checks = checked_by_others + self_checks
                
                return {
                    'checked_by_others': checked_by_others,
                    'score_from_others': float(result[1]) if result[1] else 0.0,
                    'worst_from_others': result[2],
                    'self_checks': self_checks,
                    'score_from_self': float(result[4]) if result[4] else 0.0,
                    'total_requests': result[5] or 0,
                    'unique_checkers': result[6] or 0,
                    'self_check_ratio': (self_checks / total_checks) if total_checks > 0 else 0.0,
                    'legitimacy_flag': 'SUSPICIOUS' if (self_checks / total_checks) > 0.3 and total_checks >= 5 else 'CLEAN'
                }
            return {}
        except mariadb.Error as e:
            logger.error(f"Error fetching user factcheck breakdown: {e}")
            return {}
        finally:
            if connection:
                connection.close()

    def get_ai_response_cache(self, message_content, response_type):
        """
        Returns cached AI response for exact message_content and response_type ('klugscheiss' or 'factcheck'), or None.
        """
        import hashlib
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            content_hash = hashlib.sha256(message_content.strip().encode("utf-8")).hexdigest()
            cursor.execute("""
                SELECT ai_response, score, hit_count FROM ai_response_cache
                WHERE message_content_hash = ? AND response_type = ?
                LIMIT 1
            """, (content_hash, response_type))
            row = cursor.fetchone()
            if row:
                # Update hit_count and last_used
                cursor.execute("""
                    UPDATE ai_response_cache
                    SET hit_count = hit_count + 1, last_used = CURRENT_TIMESTAMP
                    WHERE message_content_hash = ? AND response_type = ?
                """, (content_hash, response_type))
                connection.commit()
                return {
                    "ai_response": row[0],
                    "score": row[1],
                    "hit_count": row[2] + 1
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching ai_response_cache: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def save_ai_response_cache(self, message_content, response_type, ai_response, score=None):
        """
        Saves or updates the AI response cache for a given message_content and response_type.
        """
        import hashlib
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            content_hash = hashlib.sha256(message_content.strip().encode("utf-8")).hexdigest()
            cursor.execute("""
                INSERT INTO ai_response_cache (message_content_hash, message_content, response_type, ai_response, score, hit_count)
                VALUES (?, ?, ?, ?, ?, 1)
                ON DUPLICATE KEY UPDATE
                    ai_response = VALUES(ai_response),
                    score = VALUES(score),
                    hit_count = hit_count + 1,
                    last_used = CURRENT_TIMESTAMP
            """, (content_hash, message_content, response_type, ai_response, score))
            connection.commit()
            logger.info(f"Saved AI response cache for type={response_type}, hash={content_hash[:8]}")
            return True
        except Exception as e:
            logger.error(f"Error saving ai_response_cache: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def close(self):
        # No persistent connection to close
        logger.info("DatabaseManager closed")
