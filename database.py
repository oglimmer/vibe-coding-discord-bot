import hashlib
import psycopg
import logging
from config import Config
import dataclasses
import datetime as dt
import json
from datetime import datetime
from typing import List, Optional
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

GERMANY_TZ = ZoneInfo("Europe/Berlin")


def _game_lock_key(game_date) -> int:
    """Stable signed 64-bit key for a game_date, used with pg_advisory_xact_lock.

    On MariaDB the 1337 flow serialized bet inserts against winner
    determination with a SELECT ... FOR UPDATE gap lock on the (absent)
    winner row. PostgreSQL takes no gap lock when the row is missing, so
    save_1337_bet and decide_winner_atomically instead take a
    transaction-scoped advisory lock on this key. Both derive the key from
    game_date alone, so they contend on exactly the same lock; it releases
    automatically at COMMIT/ROLLBACK.
    """
    digest = hashlib.blake2b(str(game_date).encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big", signed=True)


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
            connection = psycopg.connect(
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                dbname=Config.DB_NAME,
            )
            return connection
        except psycopg.Error as e:
            logger.error(f"Error connecting to PostgreSQL: {e}")
            raise

    def create_tables(self):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS greetings (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    greeting_message TEXT,
                    greeting_date DATE NOT NULL,
                    greeting_time TIME NOT NULL,
                    server_id BIGINT,
                    channel_id BIGINT,
                    message_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Kept for databases migrated from MariaDB, where message_id was
            # added by an ALTER rather than being part of the base schema.
            cursor.execute(
                "ALTER TABLE greetings ADD COLUMN IF NOT EXISTS message_id BIGINT"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS greeting_reactions (
                    id SERIAL PRIMARY KEY,
                    greeting_id INT NOT NULL,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    reaction_emoji VARCHAR(50) NOT NULL,
                    reaction_date DATE NOT NULL,
                    reaction_time TIME NOT NULL,
                    server_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_reaction
                        UNIQUE (greeting_id, user_id, reaction_emoji),
                    FOREIGN KEY (greeting_id) REFERENCES greetings(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_1337_bets (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    play_time TIMESTAMP(3) NOT NULL,
                    game_date DATE NOT NULL,
                    bet_type VARCHAR(20) NOT NULL DEFAULT 'regular'
                        CHECK (bet_type IN ('regular', 'early_bird')),
                    server_id BIGINT,
                    channel_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_user_per_day UNIQUE (user_id, game_date)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_1337_winners (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    game_date DATE NOT NULL,
                    win_time TIMESTAMP(3) NOT NULL,
                    play_time TIMESTAMP(3) NOT NULL,
                    bet_type VARCHAR(20) NOT NULL
                        CHECK (bet_type IN ('regular', 'early_bird')),
                    millisecond_diff INT NOT NULL,
                    server_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_date UNIQUE (game_date)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS game_1337_roles (
                    id SERIAL PRIMARY KEY,
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    role_type VARCHAR(20) NOT NULL
                        CHECK (role_type IN ('sergeant', 'commander', 'general')),
                    role_id BIGINT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_guild_role UNIQUE (guild_id, role_type)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS klugscheisser_user_preferences (
                    user_id BIGINT PRIMARY KEY,
                    opted_in BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tldr_optins (
                    guild_id BIGINT NOT NULL,
                    user_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, user_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS factcheck_requests (
                    id SERIAL PRIMARY KEY,
                    requester_user_id BIGINT NOT NULL,
                    requester_username VARCHAR(255) NOT NULL,
                    target_message_id BIGINT NOT NULL,
                    target_user_id BIGINT NOT NULL,
                    target_username VARCHAR(255) NOT NULL,
                    message_content TEXT NOT NULL,
                    request_date DATE NOT NULL,
                    score SMALLINT CHECK (score >= 0 AND score <= 100),
                    factcheck_response TEXT,
                    is_factcheckable BOOLEAN DEFAULT TRUE,
                    server_id BIGINT,
                    channel_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Kept for databases migrated from MariaDB, where is_factcheckable
            # was added by an ALTER rather than the base schema.
            cursor.execute(
                "ALTER TABLE factcheck_requests "
                "ADD COLUMN IF NOT EXISTS is_factcheckable BOOLEAN DEFAULT TRUE"
            )

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_response_cache (
                    id SERIAL PRIMARY KEY,
                    message_content_hash VARCHAR(64) NOT NULL,
                    message_content TEXT NOT NULL,
                    response_type VARCHAR(20) NOT NULL
                        CHECK (response_type IN ('klugscheiss', 'factcheck')),
                    ai_response TEXT NOT NULL,
                    score SMALLINT NULL,
                    hit_count INT DEFAULT 1,
                    first_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_hash_type
                        UNIQUE (message_content_hash, response_type)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS postillon_posts (
                    id BIGSERIAL PRIMARY KEY,
                    identity_hash CHAR(64) NOT NULL,
                    url_hash CHAR(64) NOT NULL,
                    external_id VARCHAR(512),
                    title TEXT NOT NULL,
                    url VARCHAR(2048) NOT NULL,
                    author VARCHAR(255),
                    summary_text TEXT,
                    image_url VARCHAR(2048),
                    categories_json TEXT,
                    published_at TIMESTAMP,
                    source_updated_at TIMESTAMP,
                    content_hash CHAR(64) NOT NULL,
                    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_postillon_identity UNIQUE (identity_hash),
                    CONSTRAINT unique_postillon_url UNIQUE (url_hash)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS postillon_deliveries (
                    id BIGSERIAL PRIMARY KEY,
                    post_id BIGINT NOT NULL,
                    channel_id BIGINT NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sending', 'sent')),
                    attempt_count INT NOT NULL DEFAULT 0,
                    claimed_at TIMESTAMP,
                    discord_message_id BIGINT,
                    delivered_at TIMESTAMP,
                    last_error TEXT,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT unique_postillon_post_channel
                        UNIQUE (post_id, channel_id),
                    FOREIGN KEY (post_id) REFERENCES postillon_posts(id)
                        ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS postillon_feed_state (
                    feed_key VARCHAR(191) PRIMARY KEY,
                    etag VARCHAR(512),
                    last_modified VARCHAR(512),
                    last_attempt_at TIMESTAMP,
                    last_success_at TIMESTAMP,
                    last_error TEXT,
                    initial_sync_completed BOOLEAN NOT NULL DEFAULT FALSE,
                    lease_owner VARCHAR(255),
                    lease_until TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS birthdays (
                    user_id BIGINT NOT NULL,
                    username VARCHAR(255) NOT NULL,
                    birthday DATE NOT NULL,
                    server_id BIGINT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, server_id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS birthday_announcements (
                    server_id BIGINT NOT NULL,
                    announce_date DATE NOT NULL,
                    announced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (server_id, announce_date)
                )
            """)

            self._create_indexes(cursor)
            self._create_updated_at_triggers(cursor)

            connection.commit()
            logger.info("Database tables created successfully")
        except psycopg.Error as e:
            logger.error(f"Error creating tables: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def _create_indexes(self, cursor):
        """Create the non-constraint secondary indexes.

        On PostgreSQL index names are unique per schema (not per table as on
        MariaDB), so each name is prefixed with its table. The birthday
        lookup index is functional — it replaces the MariaDB
        birthday_month / birthday_day VIRTUAL generated columns, which
        get_birthdays_for_today now derives with EXTRACT.
        """
        index_statements = [
            "CREATE INDEX IF NOT EXISTS idx_greetings_user_date "
            "ON greetings (user_id, greeting_date)",
            "CREATE INDEX IF NOT EXISTS idx_greetings_date "
            "ON greetings (greeting_date)",
            "CREATE INDEX IF NOT EXISTS idx_greetings_message_id "
            "ON greetings (message_id)",
            "CREATE INDEX IF NOT EXISTS idx_greeting_reactions_greeting_id "
            "ON greeting_reactions (greeting_id)",
            "CREATE INDEX IF NOT EXISTS idx_greeting_reactions_user_id "
            "ON greeting_reactions (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_greeting_reactions_reaction_date "
            "ON greeting_reactions (reaction_date)",
            "CREATE INDEX IF NOT EXISTS idx_bets_game_date "
            "ON game_1337_bets (game_date)",
            "CREATE INDEX IF NOT EXISTS idx_bets_user_id "
            "ON game_1337_bets (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_bets_play_time "
            "ON game_1337_bets (play_time)",
            "CREATE INDEX IF NOT EXISTS idx_winners_user_id "
            "ON game_1337_winners (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_winners_game_date "
            "ON game_1337_winners (game_date)",
            "CREATE INDEX IF NOT EXISTS idx_roles_guild_user "
            "ON game_1337_roles (guild_id, user_id)",
            "CREATE INDEX IF NOT EXISTS idx_roles_user_id "
            "ON game_1337_roles (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_klug_opted_in "
            "ON klugscheisser_user_preferences (opted_in)",
            "CREATE INDEX IF NOT EXISTS idx_factcheck_requester_date "
            "ON factcheck_requests (requester_user_id, request_date)",
            "CREATE INDEX IF NOT EXISTS idx_factcheck_target_message "
            "ON factcheck_requests (target_message_id)",
            "CREATE INDEX IF NOT EXISTS idx_factcheck_request_date "
            "ON factcheck_requests (request_date)",
            "CREATE INDEX IF NOT EXISTS idx_factcheck_factcheckable "
            "ON factcheck_requests (is_factcheckable)",
            "CREATE INDEX IF NOT EXISTS idx_ai_cache_hash "
            "ON ai_response_cache (message_content_hash)",
            "CREATE INDEX IF NOT EXISTS idx_ai_cache_type "
            "ON ai_response_cache (response_type)",
            "CREATE INDEX IF NOT EXISTS idx_ai_cache_last_used "
            "ON ai_response_cache (last_used)",
            "CREATE INDEX IF NOT EXISTS idx_postillon_published "
            "ON postillon_posts (published_at)",
            "CREATE INDEX IF NOT EXISTS idx_postillon_first_seen "
            "ON postillon_posts (first_seen_at)",
            "CREATE INDEX IF NOT EXISTS idx_postillon_delivery_work "
            "ON postillon_deliveries (status, claimed_at)",
            "CREATE INDEX IF NOT EXISTS idx_birthday_server_month_day "
            "ON birthdays (server_id, EXTRACT(MONTH FROM birthday), "
            "EXTRACT(DAY FROM birthday))",
        ]
        for statement in index_statements:
            cursor.execute(statement)

    def _create_updated_at_triggers(self, cursor):
        """Recreate the auto-touch behavior of MariaDB's ON UPDATE CURRENT_TIMESTAMP.

        PostgreSQL has no ON UPDATE clause, so a BEFORE UPDATE trigger bumps
        the relevant timestamp column on every row change. Triggers are
        dropped and recreated so this stays idempotent across startups.
        """
        cursor.execute("""
            CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        cursor.execute("""
            CREATE OR REPLACE FUNCTION set_last_used() RETURNS trigger AS $$
            BEGIN
                NEW.last_used = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        cursor.execute("""
            CREATE OR REPLACE FUNCTION set_last_seen_at() RETURNS trigger AS $$
            BEGIN
                NEW.last_seen_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)

        triggers = [
            ("trg_roles_updated_at", "game_1337_roles", "set_updated_at"),
            (
                "trg_klug_updated_at",
                "klugscheisser_user_preferences",
                "set_updated_at",
            ),
            ("trg_feed_state_updated_at", "postillon_feed_state", "set_updated_at"),
            ("trg_deliveries_updated_at", "postillon_deliveries", "set_updated_at"),
            ("trg_birthdays_updated_at", "birthdays", "set_updated_at"),
            ("trg_ai_cache_last_used", "ai_response_cache", "set_last_used"),
            ("trg_postillon_last_seen", "postillon_posts", "set_last_seen_at"),
        ]
        for trigger_name, table, function in triggers:
            cursor.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}")
            cursor.execute(
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {function}()"
            )

    def get_todays_greetings(
        self, guild_id: Optional[int] = None
    ) -> List[GreetingRecord]:
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
                cursor.execute(
                    """
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    INNER JOIN (
                        SELECT user_id, MAX(greeting_time) as max_time
                        FROM greetings
                        WHERE server_id = %s AND greeting_date = %s
                        GROUP BY user_id
                    ) latest ON g.user_id = latest.user_id AND g.greeting_time = latest.max_time
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                                                    AND gr.reaction_date = %s
                                                    AND gr.user_id != g.user_id
                    WHERE g.server_id = %s AND g.greeting_date = %s
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """,
                    (guild_id, today, today, guild_id, today),
                )
            else:
                cursor.execute(
                    """
                    SELECT g.username, g.greeting_time, COUNT(gr.id) as reaction_count
                    FROM greetings g
                    INNER JOIN (
                        SELECT user_id, MAX(greeting_time) as max_time
                        FROM greetings
                        WHERE greeting_date = %s
                        GROUP BY user_id
                    ) latest ON g.user_id = latest.user_id AND g.greeting_time = latest.max_time
                    LEFT JOIN greeting_reactions gr ON g.id = gr.greeting_id
                                                    AND gr.reaction_date = %s
                                                    AND gr.user_id != g.user_id
                    WHERE g.greeting_date = %s
                    GROUP BY g.id, g.username, g.greeting_time
                    ORDER BY g.greeting_time ASC
                """,
                    (today, today, today),
                )

            results = cursor.fetchall()
            return [
                GreetingRecord(
                    username=row[0], greeting_time=row[1], reaction_count=row[2]
                )
                for row in results
            ]
        except psycopg.Error as e:
            logger.error(f"Error fetching today's greetings: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def save_greeting(
        self,
        user_id,
        username,
        greeting_message,
        server_id=None,
        channel_id=None,
        message_id=None,
    ):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            date = now.date()
            time = now.time()

            cursor.execute(
                """
                INSERT INTO greetings (user_id, username, greeting_message, greeting_date, greeting_time, server_id, channel_id, message_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    user_id,
                    username,
                    greeting_message,
                    date,
                    time,
                    server_id,
                    channel_id,
                    message_id,
                ),
            )

            greeting_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(
                f"Saved greeting for user {username} ({user_id}) with ID {greeting_id}"
            )
            return greeting_id
        except psycopg.Error as e:
            logger.error(f"Error saving greeting: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def save_greeting_reaction(
        self, greeting_id, user_id, username, reaction_emoji, server_id=None
    ):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            now = datetime.now()
            date = now.date()
            time = now.time()

            cursor.execute(
                """
                INSERT INTO greeting_reactions (greeting_id, user_id, username, reaction_emoji, reaction_date, reaction_time, server_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (greeting_id, user_id, reaction_emoji) DO UPDATE SET
                reaction_time = EXCLUDED.reaction_time
            """,
                (greeting_id, user_id, username, reaction_emoji, date, time, server_id),
            )

            connection.commit()
            logger.info(
                f"Saved reaction {reaction_emoji} from {username} ({user_id}) to greeting {greeting_id}"
            )
            return True
        except psycopg.Error as e:
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
            cursor.execute(
                """
                DELETE FROM greeting_reactions
                WHERE greeting_id = %s AND user_id = %s AND reaction_emoji = %s
            """,
                (greeting_id, user_id, reaction_emoji),
            )

            connection.commit()
            logger.info(
                f"Removed reaction {reaction_emoji} from user {user_id} to greeting {greeting_id}"
            )
            return True
        except psycopg.Error as e:
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
                cursor.execute(
                    """
                    SELECT id FROM greetings
                    WHERE message_id = %s AND server_id = %s
                    ORDER BY created_at DESC LIMIT 1
                """,
                    (message_id, server_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT id FROM greetings
                    WHERE message_id = %s
                    ORDER BY created_at DESC LIMIT 1
                """,
                    (message_id,),
                )

            result = cursor.fetchone()
            return result[0] if result else None
        except psycopg.Error as e:
            logger.error(f"Error getting greeting ID: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def save_1337_bet(
        self,
        user_id,
        username,
        play_time,
        game_date,
        bet_type="regular",
        server_id=None,
        channel_id=None,
    ):
        """Save a bet, refusing if a winner has already been determined for game_date.

        Returns: 'saved' | 'game_closed' | 'error'.

        The SELECT ... FOR UPDATE on game_1337_winners(game_date) acquires a
        next-key gap lock when the row is absent, which serializes against the
        winner-determination transaction in decide_winner_atomically. Either
        the winner row is already visible (we reject), or our bet INSERT
        commits first and the winner-determination path observes our row.
        """
        connection = None
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()

            # Serialize against decide_winner_atomically on the same game_date
            # (replaces the MariaDB winner-row gap lock — see _game_lock_key).
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_game_lock_key(game_date),)
            )

            cursor.execute(
                "SELECT 1 FROM game_1337_winners WHERE game_date = %s",
                (game_date,),
            )
            if cursor.fetchone() is not None:
                connection.rollback()
                logger.info(
                    f"Bet rejected for {username} ({user_id}) on {game_date}: "
                    f"winner already determined"
                )
                return "game_closed"

            cursor.execute(
                """
                INSERT INTO game_1337_bets (user_id, username, play_time, game_date, bet_type, server_id, channel_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, game_date) DO UPDATE SET
                play_time = EXCLUDED.play_time,
                bet_type = EXCLUDED.bet_type,
                username = EXCLUDED.username
            """,
                (
                    user_id,
                    username,
                    play_time,
                    game_date,
                    bet_type,
                    server_id,
                    channel_id,
                ),
            )

            connection.commit()
            logger.info(
                f"Saved 1337 bet for user {username} ({user_id}) on {game_date}"
            )
            return "saved"
        except psycopg.Error as e:
            if connection:
                try:
                    connection.rollback()
                except psycopg.Error:
                    pass
            logger.error(f"Error saving 1337 bet: {e}")
            return "error"
        finally:
            if connection:
                connection.close()

    def get_user_bet(self, user_id, game_date):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT user_id, username, play_time, bet_type
                FROM game_1337_bets
                WHERE user_id = %s AND game_date = %s
            """,
                (user_id, game_date),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "username": result[1],
                    "play_time": result[2],
                    "bet_type": result[3],
                }
            return None
        except psycopg.Error as e:
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
            cursor.execute(
                """
                SELECT user_id, username, play_time, bet_type, server_id, channel_id
                FROM game_1337_bets
                WHERE game_date = %s
                ORDER BY play_time ASC
            """,
                (game_date,),
            )

            results = cursor.fetchall()
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "play_time": row[2],
                    "bet_type": row[3],
                    "server_id": row[4],
                    "channel_id": row[5],
                }
                for row in results
            ]
        except psycopg.Error as e:
            logger.error(f"Error fetching daily bets: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def save_1337_winner(
        self,
        user_id,
        username,
        game_date,
        win_time,
        play_time,
        bet_type,
        millisecond_diff,
        server_id=None,
    ):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO game_1337_winners (user_id, username, game_date, win_time, play_time, bet_type, millisecond_diff, server_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_date) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                username = EXCLUDED.username,
                win_time = EXCLUDED.win_time,
                play_time = EXCLUDED.play_time,
                bet_type = EXCLUDED.bet_type,
                millisecond_diff = EXCLUDED.millisecond_diff
            """,
                (
                    user_id,
                    username,
                    game_date,
                    win_time,
                    play_time,
                    bet_type,
                    millisecond_diff,
                    server_id,
                ),
            )

            connection.commit()
            logger.info(
                f"Saved 1337 winner for user {username} ({user_id}) on {game_date}"
            )
            return True
        except psycopg.Error as e:
            logger.error(f"Error saving 1337 winner: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def decide_winner_atomically(self, game_date, win_time, pick_winner):
        """Atomically lock today's winner row, read bets, pick a winner, and persist.

        Holds a SELECT ... FOR UPDATE gap lock on game_1337_winners(game_date)
        across reading bets and inserting the winner. Bet inserts in
        save_1337_bet take the same lock, so no bet can land between the read
        and the winner insert: either the bet commits first and we observe it,
        or it blocks until we commit and then rejects with 'game_closed'.

        pick_winner(bets, win_time) -> Optional[dict]
            Returns one of:
              - None for "no eligible winner today"
              - {'catastrophic_event': True, 'identical_count': N}
              - winner dict with keys: user_id, username, play_time, bet_type,
                millisecond_diff, server_id (server_id may be None)

        Returns the picker's result, or None if a winner was already recorded
        (idempotent re-entry).
        """
        connection = None
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()

            # Hold the per-game_date advisory lock across reading bets and
            # inserting the winner, so no bet can land in between (save_1337_bet
            # takes the same lock). Replaces the MariaDB gap lock.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s)", (_game_lock_key(game_date),)
            )

            cursor.execute(
                "SELECT 1 FROM game_1337_winners WHERE game_date = %s",
                (game_date,),
            )
            if cursor.fetchone() is not None:
                connection.rollback()
                logger.info(
                    f"Winner already recorded for {game_date}; skipping re-decision"
                )
                # Distinct from "no eligible bets" — the caller must not
                # announce "no winner today" in this case.
                return {"already_decided": True}

            cursor.execute(
                """
                SELECT user_id, username, play_time, bet_type, server_id, channel_id
                FROM game_1337_bets
                WHERE game_date = %s
                ORDER BY play_time ASC
            """,
                (game_date,),
            )
            bets = [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "play_time": row[2],
                    "bet_type": row[3],
                    "server_id": row[4],
                    "channel_id": row[5],
                }
                for row in cursor.fetchall()
            ]

            picked = pick_winner(bets, win_time)

            if picked is None or picked.get("catastrophic_event"):
                connection.rollback()
                return picked

            cursor.execute(
                """
                INSERT INTO game_1337_winners
                    (user_id, username, game_date, win_time, play_time,
                     bet_type, millisecond_diff, server_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    picked["user_id"],
                    picked["username"],
                    game_date,
                    win_time,
                    picked["play_time"],
                    picked["bet_type"],
                    picked["millisecond_diff"],
                    picked.get("server_id"),
                ),
            )
            connection.commit()
            logger.info(
                f"Atomically decided 1337 winner for {game_date}: "
                f"{picked['username']} ({picked['user_id']})"
            )
            return picked

        except psycopg.Error as e:
            if connection:
                try:
                    connection.rollback()
                except psycopg.Error:
                    pass
            logger.error(f"Error in decide_winner_atomically: {e}")
            raise
        finally:
            if connection:
                connection.close()

    def get_winner_stats(self, user_id=None, days=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            if user_id and days:
                cursor.execute(
                    """
                    SELECT COUNT(*) as wins
                    FROM game_1337_winners
                    WHERE user_id = %s AND game_date >= CURRENT_DATE - make_interval(days => %s)
                """,
                    (user_id, days),
                )
            elif user_id:
                cursor.execute(
                    """
                    SELECT COUNT(*) as wins
                    FROM game_1337_winners
                    WHERE user_id = %s
                """,
                    (user_id,),
                )
            elif days:
                cursor.execute(
                    """
                    SELECT w.user_id,
                           (SELECT username FROM game_1337_winners
                            WHERE user_id = w.user_id
                            ORDER BY game_date DESC LIMIT 1) as latest_username,
                           COUNT(*) as wins,
                           MAX(w.game_date) as last_win
                    FROM game_1337_winners w
                    WHERE w.game_date >= CURRENT_DATE - make_interval(days => %s)
                    GROUP BY w.user_id
                    ORDER BY wins DESC, last_win DESC
                """,
                    (days,),
                )
            else:
                cursor.execute("""
                    SELECT w.user_id,
                           (SELECT username FROM game_1337_winners
                            WHERE user_id = w.user_id
                            ORDER BY game_date DESC LIMIT 1) as latest_username,
                           COUNT(*) as wins,
                           MAX(w.game_date) as last_win
                    FROM game_1337_winners w
                    GROUP BY w.user_id
                    ORDER BY wins DESC, last_win DESC
                """)

            if user_id:
                result = cursor.fetchone()
                return result[0] if result else 0
            else:
                results = cursor.fetchall()
                return [
                    {
                        "user_id": row[0],
                        "username": row[1],
                        "wins": row[2],
                        "last_win": row[3],
                    }
                    for row in results
                ]
        except psycopg.Error as e:
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
            cursor.execute(
                """
                SELECT user_id, username, win_time, play_time, bet_type, millisecond_diff
                FROM game_1337_winners
                WHERE game_date = %s
            """,
                (game_date,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "user_id": result[0],
                    "username": result[1],
                    "win_time": result[2],
                    "play_time": result[3],
                    "bet_type": result[4],
                    "millisecond_diff": result[5],
                }
            return None
        except psycopg.Error as e:
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
            cursor.execute(
                """
                INSERT INTO game_1337_roles (guild_id, user_id, role_type, role_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (guild_id, role_type) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                role_id = EXCLUDED.role_id,
                updated_at = CURRENT_TIMESTAMP
            """,
                (guild_id, user_id, role_type, role_id),
            )

            connection.commit()
            logger.info(
                f"Set {role_type} role assignment for user {user_id} in guild {guild_id}"
            )
            return True
        except psycopg.Error as e:
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
            cursor.execute(
                """
                SELECT user_id, role_id
                FROM game_1337_roles
                WHERE guild_id = %s AND role_type = %s
            """,
                (guild_id, role_type),
            )

            result = cursor.fetchone()
            if result:
                return {"user_id": result[0], "role_id": result[1]}
            return None
        except psycopg.Error as e:
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
            cursor.execute(
                """
                SELECT user_id, role_type, role_id
                FROM game_1337_roles
                WHERE guild_id = %s
            """,
                (guild_id,),
            )

            results = cursor.fetchall()
            return [
                {"user_id": row[0], "role_type": row[1], "role_id": row[2]}
                for row in results
            ]
        except psycopg.Error as e:
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
            cursor.execute(
                """
                DELETE FROM game_1337_roles
                WHERE guild_id = %s AND role_type = %s
            """,
                (guild_id, role_type),
            )

            connection.commit()
            logger.info(f"Removed {role_type} role assignment in guild {guild_id}")
            return True
        except psycopg.Error as e:
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
            cursor.execute(
                """
                INSERT INTO klugscheisser_user_preferences (user_id, opted_in)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                opted_in = EXCLUDED.opted_in,
                updated_at = CURRENT_TIMESTAMP
            """,
                (user_id, opted_in),
            )

            connection.commit()
            status = "opted in" if opted_in else "opted out"
            logger.info(f"User {user_id} {status} of klugscheißer feature")
            return True
        except psycopg.Error as e:
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
            cursor.execute(
                """
                SELECT opted_in, created_at
                FROM klugscheisser_user_preferences
                WHERE user_id = %s
            """,
                (user_id,),
            )

            result = cursor.fetchone()
            if result:
                return {"opted_in": bool(result[0]), "created_at": result[1]}
            return {"opted_in": False, "created_at": None}
        except psycopg.Error as e:
            logger.error(f"Error fetching klugscheißer preference: {e}")
            return {"opted_in": False, "created_at": None}
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
        except psycopg.Error as e:
            logger.error(f"Error fetching opted in users count: {e}")
            return 0
        finally:
            if connection:
                connection.close()

    def set_tldr_optin(self, guild_id, user_id, opted_in):
        """Opt a user in to (or back out of) having their messages summarized by /tldr.

        /tldr is opt-in only: a user's messages are excluded from summaries
        unless they have an explicit opt-in row here. Consent is per guild, so
        opting in on one server never exposes the user's messages on another.
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            if opted_in:
                cursor.execute(
                    """
                    INSERT INTO tldr_optins (guild_id, user_id)
                    VALUES (%s, %s)
                    ON CONFLICT (guild_id, user_id) DO NOTHING
                """,
                    (guild_id, user_id),
                )
            else:
                cursor.execute(
                    "DELETE FROM tldr_optins WHERE guild_id = %s AND user_id = %s",
                    (guild_id, user_id),
                )

            connection.commit()
            status = "opted in to" if opted_in else "opted back out of"
            logger.info(
                f"User {user_id} {status} /tldr summarization in guild {guild_id}"
            )
            return True
        except psycopg.Error as e:
            logger.error(f"Error setting tldr opt-in: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_tldr_opted_in_users(self, guild_id):
        """Return the set of user_ids opted in to /tldr summarization in this guild."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "SELECT user_id FROM tldr_optins WHERE guild_id = %s",
                (guild_id,),
            )
            return {row[0] for row in cursor.fetchall()}
        except psycopg.Error as e:
            logger.error(f"Error fetching tldr opt-in list: {e}")
            return set()
        finally:
            if connection:
                connection.close()

    def save_factcheck_request(
        self,
        requester_user_id,
        requester_username,
        target_message_id,
        target_user_id,
        target_username,
        message_content,
        score=None,
        factcheck_response=None,
        is_factcheckable=True,
        server_id=None,
        channel_id=None,
    ):
        """Save a fact-check request to the database"""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            today = datetime.now().date()

            cursor.execute(
                """
                INSERT INTO factcheck_requests (
                    requester_user_id, requester_username, target_message_id,
                    target_user_id, target_username, message_content, request_date,
                    score, factcheck_response, is_factcheckable, server_id, channel_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    requester_user_id,
                    requester_username,
                    target_message_id,
                    target_user_id,
                    target_username,
                    message_content,
                    today,
                    score,
                    factcheck_response,
                    is_factcheckable,
                    server_id,
                    channel_id,
                ),
            )

            factcheck_id = cursor.fetchone()[0]
            connection.commit()
            logger.info(
                f"Saved factcheck request from {requester_username} ({requester_user_id}) with ID {factcheck_id}, factcheckable: {is_factcheckable}"
            )
            return factcheck_id
        except psycopg.Error as e:
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

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM factcheck_requests
                WHERE requester_user_id = %s AND request_date = %s
            """,
                (user_id, date),
            )

            result = cursor.fetchone()
            return result[0] if result else 0
        except psycopg.Error as e:
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
            cursor.execute(
                """
                UPDATE factcheck_requests
                SET score = %s, factcheck_response = %s
                WHERE id = %s
            """,
                (score, factcheck_response, factcheck_id),
            )

            connection.commit()
            logger.info(f"Updated factcheck request {factcheck_id} with score {score}")
            return True
        except psycopg.Error as e:
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
                cursor.execute(
                    """
                    SELECT COUNT(*) as total_requests,
                           AVG(score) as avg_score,
                           MIN(score) as min_score,
                           MAX(score) as max_score
                    FROM factcheck_requests
                    WHERE requester_user_id = %s
                      AND request_date >= CURRENT_DATE - make_interval(days => %s)
                      AND score IS NOT NULL
                """,
                    (user_id, days),
                )

                result = cursor.fetchone()
                if result:
                    return {
                        "total_requests": result[0],
                        "avg_score": float(result[1]) if result[1] else 0,
                        "min_score": result[2],
                        "max_score": result[3],
                    }
            else:
                cursor.execute(
                    """
                    SELECT f.requester_user_id,
                           (SELECT requester_username FROM factcheck_requests
                            WHERE requester_user_id = f.requester_user_id
                            ORDER BY created_at DESC LIMIT 1) as latest_username,
                           COUNT(*) as total_requests,
                           AVG(f.score) as avg_score
                    FROM factcheck_requests f
                    WHERE f.request_date >= CURRENT_DATE - make_interval(days => %s)
                      AND f.score IS NOT NULL
                    GROUP BY f.requester_user_id
                    ORDER BY total_requests DESC
                """,
                    (days,),
                )

                results = cursor.fetchall()
                return [
                    {
                        "user_id": row[0],
                        "username": row[1],
                        "total_requests": row[2],
                        "avg_score": float(row[3]) if row[3] else 0,
                    }
                    for row in results
                ]

            return {} if user_id else []
        except psycopg.Error as e:
            logger.error(f"Error fetching factcheck statistics: {e}")
            return {} if user_id else []
        finally:
            if connection:
                connection.close()

    def get_bullshit_board_data(
        self, page=0, per_page=10, days=30, sort_by="score_asc"
    ):
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
                "requests_desc": "total_requests DESC, avg_score ASC",
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
                            COALESCE(AVG(target_checks.score), 0) * LN(COUNT(target_checks.id) + 1)
                        ELSE 0
                    END as weighted_score
                FROM klugscheisser_user_preferences u
                LEFT JOIN (
                    -- Latest username per user: DISTINCT ON keeps the row with
                    -- the most recent created_at for each target_user_id.
                    SELECT DISTINCT ON (target_user_id)
                        target_user_id,
                        target_username as username
                    FROM factcheck_requests
                    WHERE request_date >= CURRENT_DATE - make_interval(days => {days})
                    ORDER BY target_user_id, created_at DESC
                ) latest_username ON u.user_id = latest_username.target_user_id
                LEFT JOIN factcheck_requests target_checks
                    ON u.user_id = target_checks.target_user_id
                    AND target_checks.requester_user_id != target_checks.target_user_id  -- EXCLUDE self-checks!
                    AND target_checks.score IS NOT NULL
                    AND target_checks.is_factcheckable = TRUE  -- ONLY factcheckable messages count toward score!
                    AND target_checks.request_date >= CURRENT_DATE - make_interval(days => {days})
                LEFT JOIN (
                    -- Self-checks separately
                    SELECT
                        target_user_id,
                        COUNT(*) as self_check_count
                    FROM factcheck_requests
                    WHERE requester_user_id = target_user_id  -- Self-check
                        AND request_date >= CURRENT_DATE - make_interval(days => {days})
                    GROUP BY target_user_id
                ) self_checks ON u.user_id = self_checks.target_user_id
                LEFT JOIN (
                    -- All requests
                    SELECT
                        requester_user_id,
                        COUNT(*) as total_requests
                    FROM factcheck_requests
                    WHERE request_date >= CURRENT_DATE - make_interval(days => {days})
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
                    "user_id": row[0],
                    "username": row[1],
                    "avg_score": float(row[2]) if row[2] else 0.0,
                    "times_checked_by_others": row[3],
                    "self_checks": row[4],
                    "total_requests": row[5],
                    "total_activity": row[6],
                    "worst_score": row[7],
                    "weighted_score": float(row[8]) if row[8] else 0.0,
                }
                for row in results
            ]
        except psycopg.Error as e:
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

            cursor.execute(
                """
                SELECT COUNT(DISTINCT u.user_id)
                FROM klugscheisser_user_preferences u
                JOIN factcheck_requests target_checks
                    ON u.user_id = target_checks.target_user_id
                    AND target_checks.requester_user_id != target_checks.target_user_id  -- EXCLUDE self-checks!
                    AND target_checks.score IS NOT NULL
                    AND target_checks.request_date >= CURRENT_DATE - make_interval(days => %s)
                WHERE u.opted_in = TRUE
                GROUP BY u.user_id
                HAVING COUNT(target_checks.id) >= 1  -- Min. 1x checked by OTHERS
            """,
                (days,),
            )

            result = cursor.fetchone()
            return result[0] if result else 0
        except psycopg.Error as e:
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

            cursor.execute(
                """
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
                     WHERE requester_user_id = %s
                       AND request_date >= CURRENT_DATE - make_interval(days => %s)) as total_requests,
                    -- Unique checkers
                    COUNT(DISTINCT CASE WHEN fcr.requester_user_id != fcr.target_user_id
                                       THEN fcr.requester_user_id END) as unique_checkers
                FROM factcheck_requests fcr
                WHERE fcr.target_user_id = %s
                  AND fcr.score IS NOT NULL
                  AND fcr.request_date >= CURRENT_DATE - make_interval(days => %s)
            """,
                (user_id, days, user_id, days),
            )

            result = cursor.fetchone()
            if result:
                checked_by_others = result[0] or 0
                self_checks = result[4] or 0
                total_checks = checked_by_others + self_checks

                return {
                    "checked_by_others": checked_by_others,
                    "score_from_others": float(result[1]) if result[1] else 0.0,
                    "worst_from_others": result[2],
                    "self_checks": self_checks,
                    "score_from_self": float(result[4]) if result[4] else 0.0,
                    "total_requests": result[5] or 0,
                    "unique_checkers": result[6] or 0,
                    "self_check_ratio": (self_checks / total_checks)
                    if total_checks > 0
                    else 0.0,
                    "legitimacy_flag": "SUSPICIOUS"
                    if (self_checks / total_checks) > 0.3 and total_checks >= 5
                    else "CLEAN",
                }
            return {}
        except psycopg.Error as e:
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
            content_hash = hashlib.sha256(
                message_content.strip().encode("utf-8")
            ).hexdigest()
            cursor.execute(
                """
                SELECT ai_response, score, hit_count FROM ai_response_cache
                WHERE message_content_hash = %s AND response_type = %s
                LIMIT 1
            """,
                (content_hash, response_type),
            )
            row = cursor.fetchone()
            if row:
                # Update hit_count and last_used
                cursor.execute(
                    """
                    UPDATE ai_response_cache
                    SET hit_count = hit_count + 1, last_used = CURRENT_TIMESTAMP
                    WHERE message_content_hash = %s AND response_type = %s
                """,
                    (content_hash, response_type),
                )
                connection.commit()
                return {"ai_response": row[0], "score": row[1], "hit_count": row[2] + 1}
            return None
        except Exception as e:
            logger.error(f"Error fetching ai_response_cache: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def save_ai_response_cache(
        self, message_content, response_type, ai_response, score=None
    ):
        """
        Saves or updates the AI response cache for a given message_content and response_type.
        """
        import hashlib

        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            content_hash = hashlib.sha256(
                message_content.strip().encode("utf-8")
            ).hexdigest()
            cursor.execute(
                """
                INSERT INTO ai_response_cache (message_content_hash, message_content, response_type, ai_response, score, hit_count)
                VALUES (%s, %s, %s, %s, %s, 1)
                ON CONFLICT (message_content_hash, response_type) DO UPDATE SET
                    ai_response = EXCLUDED.ai_response,
                    score = EXCLUDED.score,
                    hit_count = ai_response_cache.hit_count + 1,
                    last_used = CURRENT_TIMESTAMP
            """,
                (content_hash, message_content, response_type, ai_response, score),
            )
            connection.commit()
            logger.info(
                f"Saved AI response cache for type={response_type}, hash={content_hash[:8]}"
            )
            return True
        except Exception as e:
            logger.error(f"Error saving ai_response_cache: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_postillon_feed_state(self, feed_key):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT feed_key, etag, last_modified, last_attempt_at,
                       last_success_at, last_error, initial_sync_completed,
                       lease_owner, lease_until
                FROM postillon_feed_state
                WHERE feed_key = %s
                """,
                (feed_key,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            keys = (
                "feed_key",
                "etag",
                "last_modified",
                "last_attempt_at",
                "last_success_at",
                "last_error",
                "initial_sync_completed",
                "lease_owner",
                "lease_until",
            )
            return dict(zip(keys, row))
        finally:
            if connection:
                connection.close()

    def try_acquire_postillon_lease(self, feed_key, owner, lease_seconds):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO postillon_feed_state (feed_key) VALUES (%s) "
                "ON CONFLICT (feed_key) DO NOTHING",
                (feed_key,),
            )
            cursor.execute(
                """
                UPDATE postillon_feed_state
                SET lease_owner = %s,
                    lease_until = ((now() AT TIME ZONE 'utc') + make_interval(secs => %s))
                WHERE feed_key = %s
                  AND (lease_until IS NULL OR lease_until < (now() AT TIME ZONE 'utc')
                       OR lease_owner = %s)
                """,
                (owner, lease_seconds, feed_key, owner),
            )
            cursor.execute(
                "SELECT lease_owner FROM postillon_feed_state WHERE feed_key = %s",
                (feed_key,),
            )
            row = cursor.fetchone()
            acquired = bool(row and row[0] == owner)
            connection.commit()
            return acquired
        except psycopg.Error:
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()

    def release_postillon_lease(self, feed_key, owner):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE postillon_feed_state
                SET lease_owner = NULL, lease_until = NULL
                WHERE feed_key = %s AND lease_owner = %s
                """,
                (feed_key, owner),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            if connection:
                connection.close()

    def record_postillon_attempt(self, feed_key, error=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO postillon_feed_state
                    (feed_key, last_attempt_at, last_error)
                VALUES (%s, (now() AT TIME ZONE 'utc'), %s)
                ON CONFLICT (feed_key) DO UPDATE SET
                    last_attempt_at = (now() AT TIME ZONE 'utc'),
                    last_error = EXCLUDED.last_error
                """,
                (feed_key, error),
            )
            connection.commit()
            return True
        finally:
            if connection:
                connection.close()

    def record_postillon_not_modified(self, feed_key, etag=None, last_modified=None):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE postillon_feed_state
                SET etag = COALESCE(%s, etag),
                    last_modified = COALESCE(%s, last_modified),
                    last_attempt_at = (now() AT TIME ZONE 'utc'),
                    last_success_at = (now() AT TIME ZONE 'utc'),
                    last_error = NULL
                WHERE feed_key = %s
                """,
                (etag, last_modified, feed_key),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            if connection:
                connection.close()

    def import_postillon_posts(
        self,
        feed_key,
        posts,
        channel_id,
        announce_first_sync,
        etag=None,
        last_modified=None,
    ):
        connection = None
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()
            cursor.execute(
                "SELECT initial_sync_completed FROM postillon_feed_state "
                "WHERE feed_key = %s FOR UPDATE",
                (feed_key,),
            )
            state = cursor.fetchone()
            initial_sync_completed = bool(state and state[0])
            inserted = 0
            updated = 0
            queued = 0

            for post in posts:
                cursor.execute(
                    """
                    SELECT id, content_hash
                    FROM postillon_posts
                    WHERE identity_hash = %s
                    LIMIT 1 FOR UPDATE
                    """,
                    (post.identity_hash,),
                )
                identity_match = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT id, content_hash
                    FROM postillon_posts
                    WHERE url_hash = %s
                    LIMIT 1 FOR UPDATE
                    """,
                    (post.url_hash,),
                )
                url_match = cursor.fetchone()
                if identity_match and url_match and identity_match[0] != url_match[0]:
                    logger.error(
                        "Skipping ambiguous Postillon identity/URL collision for %s",
                        post.url,
                    )
                    continue
                existing = identity_match or url_match
                values = (
                    post.identity_hash,
                    post.url_hash,
                    post.external_id,
                    post.title,
                    post.url,
                    post.author,
                    post.summary_text,
                    post.image_url,
                    json.dumps(post.categories, ensure_ascii=False),
                    post.published_at,
                    post.updated_at,
                    post.content_hash,
                )
                if existing:
                    post_id, old_content_hash = existing
                    cursor.execute(
                        """
                        UPDATE postillon_posts
                        SET identity_hash = %s, url_hash = %s, external_id = %s,
                            title = %s, url = %s, author = %s, summary_text = %s,
                            image_url = %s, categories_json = %s, published_at = %s,
                            source_updated_at = %s, content_hash = %s
                        WHERE id = %s
                        """,
                        (*values, post_id),
                    )
                    if old_content_hash != post.content_hash:
                        updated += 1
                    continue

                cursor.execute(
                    """
                    INSERT INTO postillon_posts
                        (identity_hash, url_hash, external_id, title, url, author,
                         summary_text, image_url, categories_json, published_at,
                         source_updated_at, content_hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    values,
                )
                post_id = cursor.fetchone()[0]
                inserted += 1
                if initial_sync_completed or announce_first_sync:
                    cursor.execute(
                        """
                        INSERT INTO postillon_deliveries (post_id, channel_id)
                        VALUES (%s, %s)
                        ON CONFLICT (post_id, channel_id) DO NOTHING
                        """,
                        (post_id, channel_id),
                    )
                    if cursor.rowcount == 1:
                        queued += 1

            cursor.execute(
                """
                UPDATE postillon_feed_state
                SET etag = %s, last_modified = %s,
                    last_attempt_at = (now() AT TIME ZONE 'utc'),
                    last_success_at = (now() AT TIME ZONE 'utc'), last_error = NULL,
                    initial_sync_completed = TRUE
                WHERE feed_key = %s
                """,
                (etag, last_modified, feed_key),
            )
            connection.commit()
            return {"inserted": inserted, "updated": updated, "queued": queued}
        except Exception:
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()

    def claim_postillon_deliveries(self, channel_id, stale_after_seconds, limit=50):
        connection = None
        try:
            connection = self._get_connection()
            connection.autocommit = False
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT d.id, p.id, p.external_id, p.title, p.url, p.author,
                       p.summary_text, p.image_url, p.categories_json,
                       p.published_at, p.source_updated_at
                FROM postillon_deliveries d
                JOIN postillon_posts p ON p.id = d.post_id
                WHERE d.channel_id = %s
                  AND (d.status = 'pending'
                       OR (d.status = 'sending' AND d.claimed_at <
                           ((now() AT TIME ZONE 'utc') - make_interval(secs => %s))))
                ORDER BY COALESCE(p.published_at, p.first_seen_at) ASC, p.id ASC
                LIMIT %s FOR UPDATE OF d
                """,
                (channel_id, stale_after_seconds, limit),
            )
            rows = cursor.fetchall()
            if rows:
                placeholders = ",".join("%s" for _ in rows)
                cursor.execute(
                    f"""
                    UPDATE postillon_deliveries
                    SET status = 'sending', claimed_at = (now() AT TIME ZONE 'utc'),
                        attempt_count = attempt_count + 1
                    WHERE id IN ({placeholders})
                    """,
                    tuple(row[0] for row in rows),
                )
            connection.commit()
            keys = (
                "delivery_id",
                "post_id",
                "external_id",
                "title",
                "url",
                "author",
                "summary_text",
                "image_url",
                "categories_json",
                "published_at",
                "updated_at",
            )
            return [dict(zip(keys, row)) for row in rows]
        except Exception:
            if connection:
                connection.rollback()
            raise
        finally:
            if connection:
                connection.close()

    def mark_postillon_delivery_sent(self, delivery_id, discord_message_id):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE postillon_deliveries
                SET status = 'sent', discord_message_id = %s,
                    delivered_at = (now() AT TIME ZONE 'utc'), last_error = NULL
                WHERE id = %s AND status = 'sending'
                """,
                (discord_message_id, delivery_id),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            if connection:
                connection.close()

    def mark_postillon_delivery_pending(self, delivery_id, error):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                UPDATE postillon_deliveries
                SET status = 'pending', claimed_at = NULL, last_error = %s
                WHERE id = %s AND status = 'sending'
                """,
                (error[:65535], delivery_id),
            )
            connection.commit()
            return cursor.rowcount == 1
        finally:
            if connection:
                connection.close()

    def get_recent_postillon_posts(self, amount=10):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT id, external_id, title, url, author, summary_text,
                       image_url, categories_json, published_at, source_updated_at
                FROM postillon_posts
                ORDER BY COALESCE(published_at, first_seen_at) DESC, id DESC
                LIMIT %s
                """,
                (amount,),
            )
            keys = (
                "post_id",
                "external_id",
                "title",
                "url",
                "author",
                "summary_text",
                "image_url",
                "categories_json",
                "published_at",
                "updated_at",
            )
            return [dict(zip(keys, row)) for row in cursor.fetchall()]
        finally:
            if connection:
                connection.close()

    def get_postillon_stats(self, channel_id):
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM postillon_posts")
            posts = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT status, COUNT(*) FROM postillon_deliveries
                WHERE channel_id = %s GROUP BY status
                """,
                (channel_id,),
            )
            deliveries = {row[0]: row[1] for row in cursor.fetchall()}
            return {"posts": posts, "deliveries": deliveries}
        finally:
            if connection:
                connection.close()

    def set_birthday(self, user_id, username, birthday, server_id):
        """Insert or update a user's birthday on one server."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO birthdays (user_id, username, birthday, server_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, server_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    birthday = EXCLUDED.birthday
                """,
                (user_id, username, birthday, server_id),
            )
            connection.commit()
            logger.info(f"Set birthday for user {username} ({user_id}): {birthday}")
            return True
        except psycopg.Error as e:
            logger.error(f"Error setting birthday: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def get_birthdays_for_today(self, server_id, today=None):
        """Return the users on *server_id* whose birthday matches today.

        Parameters
        ----------
        server_id : int
            Only birthdays set on this server are returned, so a user in two
            servers is greeted in each rather than wherever they last typed
            the command.
        today : datetime.date or None
            Override for "today" (optional — defaults to the current date in
            Germany).  Useful in tests to avoid patching the clock.
        """
        if today is None:
            today = dt.datetime.now(GERMANY_TZ).date()
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT user_id, username, birthday, server_id
                FROM birthdays
                WHERE server_id = %s
                  AND EXTRACT(MONTH FROM birthday) = %s
                  AND EXTRACT(DAY FROM birthday) = %s
                """,
                (server_id, today.month, today.day),
            )
            results = cursor.fetchall()
            return [
                {
                    "user_id": row[0],
                    "username": row[1],
                    "birthday": row[2],
                    "server_id": row[3],
                }
                for row in results
            ]
        except psycopg.Error as e:
            logger.error(f"Error fetching today's birthdays: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def try_claim_birthday_announcement(self, server_id, announce_date):
        """Claim the birthday announcement for *server_id* on *announce_date*.

        Returns True for exactly one caller per server and date, across
        restarts and replicas — the PRIMARY KEY makes the INSERT the arbiter.
        A DB error returns False so that an unverifiable claim never leads to
        a duplicate announcement.
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO birthday_announcements (server_id, announce_date)
                VALUES (%s, %s)
                ON CONFLICT (server_id, announce_date) DO NOTHING
                """,
                (server_id, announce_date),
            )
            connection.commit()
            return cursor.rowcount > 0
        except psycopg.Error as e:
            logger.error(f"Error claiming birthday announcement: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def release_birthday_announcement(self, server_id, announce_date):
        """Give up a claim so a later attempt on the same day can retry."""
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                """
                DELETE FROM birthday_announcements
                WHERE server_id = %s AND announce_date = %s
                """,
                (server_id, announce_date),
            )
            connection.commit()
            return True
        except psycopg.Error as e:
            logger.error(f"Error releasing birthday announcement claim: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def remove_birthday(self, user_id, server_id):
        """Remove a user's stored birthday on one server.

        Returns True if a row was deleted, False if the user had none stored,
        and None if the delete failed — the caller needs to tell "nothing to
        do" apart from "we could not do it".
        """
        connection = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()
            cursor.execute(
                "DELETE FROM birthdays WHERE user_id = %s AND server_id = %s",
                (user_id, server_id),
            )
            connection.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(
                    f"Removed birthday for user {user_id} on server {server_id}"
                )
            return deleted
        except psycopg.Error as e:
            logger.error(f"Error removing birthday: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def close(self):
        # No persistent connection to close
        logger.info("DatabaseManager closed")
