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
    
    def close(self):
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")