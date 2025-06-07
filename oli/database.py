import mariadb
import logging
from datetime import datetime
from config import Config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection = None
        self.connect()
        self.create_tables()
    
    def connect(self):
        try:
            self.connection = mariadb.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME
            )
            logger.info("Successfully connected to MariaDB")
        except mariadb.Error as e:
            logger.error(f"Error connecting to MariaDB: {e}")
            raise
    
    def create_tables(self):
        try:
            cursor = self.connection.cursor()
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
            
            self.connection.commit()
            logger.info("Database tables created successfully")
        except mariadb.Error as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def save_greeting(self, user_id, username, greeting_message, server_id=None, channel_id=None):
        try:
            cursor = self.connection.cursor()
            now = datetime.now()
            date = now.date()
            time = now.time()
            
            cursor.execute("""
                INSERT INTO greetings (user_id, username, greeting_message, greeting_date, greeting_time, server_id, channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, greeting_message, date, time, server_id, channel_id))
            
            self.connection.commit()
            logger.info(f"Saved greeting for user {username} ({user_id})")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving greeting: {e}")
            return False
    
    def get_daily_greetings(self, date=None):
        if date is None:
            date = datetime.now().date()
        
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT user_id, username, greeting_message, greeting_time, server_id, channel_id
                FROM greetings 
                WHERE greeting_date = ?
                ORDER BY greeting_time ASC
            """, (date,))
            
            results = cursor.fetchall()
            return [
                {
                    'user_id': row[0],
                    'username': row[1],
                    'greeting_message': row[2],
                    'greeting_time': row[3],
                    'server_id': row[4],
                    'channel_id': row[5]
                }
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Error fetching daily greetings: {e}")
            return []
    
    def save_1337_bet(self, user_id, username, play_time, game_date, bet_type='regular', server_id=None, channel_id=None):
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                INSERT INTO game_1337_bets (user_id, username, play_time, game_date, bet_type, server_id, channel_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                play_time = VALUES(play_time),
                bet_type = VALUES(bet_type),
                username = VALUES(username)
            """, (user_id, username, play_time, game_date, bet_type, server_id, channel_id))
            
            self.connection.commit()
            logger.info(f"Saved 1337 bet for user {username} ({user_id}) on {game_date}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving 1337 bet: {e}")
            return False
    
    def get_user_bet(self, user_id, game_date):
        try:
            cursor = self.connection.cursor()
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
    
    def get_daily_bets(self, game_date):
        try:
            cursor = self.connection.cursor()
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
    
    def save_1337_winner(self, user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id=None):
        try:
            cursor = self.connection.cursor()
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
            
            self.connection.commit()
            logger.info(f"Saved 1337 winner for user {username} ({user_id}) on {game_date}")
            return True
        except mariadb.Error as e:
            logger.error(f"Error saving 1337 winner: {e}")
            return False
    
    def get_winner_stats(self, user_id=None, days=None):
        try:
            cursor = self.connection.cursor()
            
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
    
    def get_daily_winner(self, game_date):
        try:
            cursor = self.connection.cursor()
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

    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")