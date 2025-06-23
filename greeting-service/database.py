import os
import logging
import mariadb
from datetime import datetime, date, time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class GreetingRecord:
    username: str
    greeting_time: time
    reaction_count: int

class DatabaseManager:
    def __init__(self):
        self.host = os.getenv('DB_HOST', 'localhost')
        self.port = int(os.getenv('DB_PORT', 3306))
        self.user = os.getenv('DB_USER')
        self.password = os.getenv('DB_PASSWORD')
        self.database = os.getenv('DB_NAME', 'discord_bot')
        self.create_tables()

    def _get_connection(self):
        """Create a new database connection."""
        return mariadb.connect(
            user=self.user,
            password=self.password,
            host=self.host,
            port=self.port,
            database=self.database,
            autocommit=False
        )

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
            
            connection.commit()
            logger.info("Greeting database tables created successfully")
        except mariadb.Error as e:
            logger.error(f"Error creating greeting tables: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def save_greeting(self, user_id: str, username: str, greeting_message: str, 
                     server_id: Optional[str] = None, channel_id: Optional[str] = None, 
                     message_id: Optional[str] = None) -> Optional[int]:
        """Save a greeting to the database."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            greeting_date = now.date()
            greeting_time = now.time()
            
            cursor.execute("""
                INSERT INTO greetings (user_id, username, greeting_message, greeting_date, greeting_time, server_id, channel_id, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, username, greeting_message, greeting_date, greeting_time, server_id, channel_id, message_id))
            
            greeting_id = cursor.lastrowid
            connection.commit()
            logger.info(f"Saved greeting for user {username} ({user_id}) with ID {greeting_id}")
            return greeting_id
        except mariadb.Error as e:
            logger.error(f"Database error saving greeting for user {username} ({user_id}): {e}", exc_info=True)
            if connection:
                connection.rollback()
            return None
        except Exception as e:
            logger.error(f"Unexpected error saving greeting for user {username} ({user_id}): {e}", exc_info=True)
            if connection:
                connection.rollback()
            return None
        finally:
            if connection:
                connection.close()

    def get_todays_greetings(self, guild_id: Optional[str] = None) -> List[GreetingRecord]:
        """Fetch all greetings for the given guild from today with reaction counts."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            today = datetime.now().date()
            
            if guild_id:
                cursor.execute("""
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id AND gr.reaction_date = g.greeting_date
                    WHERE g.server_id = ? AND g.greeting_date = ?
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """, (guild_id, today))
            else:
                cursor.execute("""
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id AND gr.reaction_date = g.greeting_date
                    WHERE g.greeting_date = ?
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """, (today,))
            
            results = cursor.fetchall()
            return [
                GreetingRecord(username=row[0], greeting_time=row[1], reaction_count=row[2])
                for row in results
            ]
        except mariadb.Error as e:
            logger.error(f"Database error fetching today's greetings for guild {guild_id}: {e}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching today's greetings for guild {guild_id}: {e}", exc_info=True)
            return []
        finally:
            if connection:
                connection.close()

    def save_greeting_reaction(self, greeting_id: int, user_id: str, username: str, 
                             reaction_emoji: str, server_id: Optional[str] = None) -> bool:
        """Save a reaction to a greeting."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            reaction_date = now.date()
            reaction_time = now.time()
            
            cursor.execute("""
                INSERT INTO greeting_reactions (greeting_id, user_id, username, reaction_emoji, reaction_date, reaction_time, server_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE
                reaction_time = VALUES(reaction_time)
            """, (greeting_id, user_id, username, reaction_emoji, reaction_date, reaction_time, server_id))
            
            connection.commit()
            logger.info(f"Saved reaction {reaction_emoji} from {username} ({user_id}) to greeting {greeting_id}")
            return True
        except mariadb.Error as e:
            logger.error(f"Database error saving reaction {reaction_emoji} from {username} ({user_id}) to greeting {greeting_id}: {e}", exc_info=True)
            if connection:
                connection.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving reaction {reaction_emoji} from {username} ({user_id}) to greeting {greeting_id}: {e}", exc_info=True)
            if connection:
                connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

    def remove_greeting_reaction(self, greeting_id: int, user_id: str, reaction_emoji: str) -> bool:
        """Remove a reaction from a greeting."""
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
            logger.error(f"Database error removing reaction {reaction_emoji} from user {user_id} to greeting {greeting_id}: {e}", exc_info=True)
            if connection:
                connection.rollback()
            return False
        except Exception as e:
            logger.error(f"Unexpected error removing reaction {reaction_emoji} from user {user_id} to greeting {greeting_id}: {e}", exc_info=True)
            if connection:
                connection.rollback()
            return False
        finally:
            if connection:
                connection.close()

    def get_greeting_id_by_message(self, message_id: str, server_id: Optional[str] = None) -> Optional[int]:
        """Get greeting ID by message ID."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            if server_id:
                cursor.execute("""
                    SELECT id FROM greetings 
                    WHERE message_id = ? AND server_id = ?
                    ORDER BY greeting_date DESC, greeting_time DESC LIMIT 1
                """, (message_id, server_id))
            else:
                cursor.execute("""
                    SELECT id FROM greetings 
                    WHERE message_id = ?
                    ORDER BY greeting_date DESC, greeting_time DESC LIMIT 1
                """, (message_id,))
            
            result = cursor.fetchone()
            return result[0] if result else None
        except mariadb.Error as e:
            logger.error(f"Database error getting greeting ID for message {message_id} in server {server_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting greeting ID for message {message_id} in server {server_id}: {e}", exc_info=True)
            return None
        finally:
            if connection:
                connection.close()

    def get_greeting_statistics(self, guild_id: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive greeting statistics for today."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            today = datetime.now().date()
            
            # Get basic stats
            if guild_id:
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT g.username) as unique_greeters,
                        COUNT(gr.id) as total_reactions,
                        MIN(g.greeting_time) as first_greeting,
                        MAX(g.greeting_time) as latest_greeting
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                    WHERE g.server_id = ? AND g.greeting_date = ?
                """, (guild_id, today))
            else:
                cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT g.username) as unique_greeters,
                        COUNT(gr.id) as total_reactions,
                        MIN(g.greeting_time) as first_greeting,
                        MAX(g.greeting_time) as latest_greeting
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                    WHERE g.greeting_date = ?
                """, (today,))
            
            stats = cursor.fetchone()
            
            # Get leaderboard
            if guild_id:
                cursor.execute("""
                    SELECT 
                        g.username,
                        COUNT(gr.id) as reaction_count,
                        GROUP_CONCAT(gr.reaction_emoji) as reactions
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                    WHERE g.server_id = ? AND g.greeting_date = ?
                    GROUP BY g.username
                    ORDER BY reaction_count DESC, g.greeting_time ASC
                """, (guild_id, today))
            else:
                cursor.execute("""
                    SELECT 
                        g.username,
                        COUNT(gr.id) as reaction_count,
                        GROUP_CONCAT(gr.reaction_emoji) as reactions
                    FROM greetings g
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                    WHERE g.greeting_date = ?
                    GROUP BY g.username
                    ORDER BY reaction_count DESC, g.greeting_time ASC
                """, (today,))
            
            leaderboard_results = cursor.fetchall()
            
            return {
                'unique_greeters': stats[0] or 0,
                'total_reactions': stats[1] or 0,
                'first_greeting_time': stats[2],
                'latest_greeting_time': stats[3],
                'leaderboard': [
                    {
                        'username': row[0],
                        'reaction_count': row[1] or 0,
                        'reactions': row[2].split(',') if row[2] else []
                    }
                    for row in leaderboard_results
                ]
            }
        except mariadb.Error as e:
            logger.error(f"Database error getting greeting statistics for guild {guild_id}: {e}", exc_info=True)
            return {
                'unique_greeters': 0,
                'total_reactions': 0,
                'first_greeting_time': None,
                'latest_greeting_time': None,
                'leaderboard': []
            }
        except Exception as e:
            logger.error(f"Unexpected error getting greeting statistics for guild {guild_id}: {e}", exc_info=True)
            return {
                'unique_greeters': 0,
                'total_reactions': 0,
                'first_greeting_time': None,
                'latest_greeting_time': None,
                'leaderboard': []
            }
        finally:
            if connection:
                connection.close()