# File: /discord-bot/discord-bot/src/bot/config.py

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    BOT_TOKEN = os.getenv("BOT_TOKEN")  # Alternative name for compatibility
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = os.getenv("DATABASE_PORT", "3306")
    DATABASE_USER = os.getenv("DATABASE_USER", "root")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "discord_bot_db")
    
    # Timezone configuration (used by greetings)
    TIMEZONE = os.getenv("TZ", "Europe/Berlin")
    
    # 1337 Game Configuration - Cron-based scheduling
    GAME_1337_CRON = os.getenv("GAME_1337_CRON", "37 13 * * *")  # Default: Daily at 13:37
    GAME_1337_EARLY_BIRD_CUTOFF_HOURS = int(os.getenv("GAME_1337_EARLY_BIRD_CUTOFF_HOURS", "2"))  # Early bird cutoff
    GAME_1337_TIMEZONE = os.getenv("GAME_1337_TIMEZONE", "Europe/Berlin")  # Timezone for cron scheduling
    
    # Role IDs for 1337 game (configurable via environment)
    GAME_1337_WINNER_ROLE_ID = os.getenv("GAME_1337_WINNER_ROLE_ID")
    GAME_1337_EARLY_BIRD_ROLE_ID = os.getenv("GAME_1337_EARLY_BIRD_ROLE_ID")
    
    # Three-tier role system for 1337 game ranking
    GAME_1337_LEET_SERGEANT_ROLE_ID = os.getenv("GAME_1337_LEET_SERGEANT_ROLE_ID")    # 1+ wins
    GAME_1337_LEET_COMMANDER_ROLE_ID = os.getenv("GAME_1337_LEET_COMMANDER_ROLE_ID")  # 5+ wins
    GAME_1337_LEET_GENERAL_ROLE_ID = os.getenv("GAME_1337_LEET_GENERAL_ROLE_ID")      # 10+ wins