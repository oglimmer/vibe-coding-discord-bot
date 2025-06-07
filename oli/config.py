import os
import logging
from dotenv import load_dotenv

# Load .env file, but don't override existing environment variables
load_dotenv(override=False)

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'discord_bot')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'bot.log')
    
    # 1337 Game Configuration
    GAME_START_TIME = os.getenv('GAME_START_TIME', '13:37:00.000')
    SERGEANT_ROLE_ID = int(os.getenv('SERGEANT_ROLE_ID', 0)) if os.getenv('SERGEANT_ROLE_ID') else None
    COMMANDER_ROLE_ID = int(os.getenv('COMMANDER_ROLE_ID', 0)) if os.getenv('COMMANDER_ROLE_ID') else None
    GENERAL_ROLE_ID = int(os.getenv('GENERAL_ROLE_ID', 0)) if os.getenv('GENERAL_ROLE_ID') else None
    ANNOUNCEMENT_CHANNEL_ID = int(os.getenv('ANNOUNCEMENT_CHANNEL_ID', 0)) if os.getenv('ANNOUNCEMENT_CHANNEL_ID') else None

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)