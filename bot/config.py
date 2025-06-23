import os
import logging
from dotenv import load_dotenv

# Load .env file, but don't override existing environment variables
load_dotenv(override=False)

class Config:
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', '/tmp/bot.log')
    
    # 1337 Game Configuration
    SERGEANT_ROLE_ID = int(os.getenv('SERGEANT_ROLE_ID', 0)) if os.getenv('SERGEANT_ROLE_ID') else None
    COMMANDER_ROLE_ID = int(os.getenv('COMMANDER_ROLE_ID', 0)) if os.getenv('COMMANDER_ROLE_ID') else None
    GENERAL_ROLE_ID = int(os.getenv('GENERAL_ROLE_ID', 0)) if os.getenv('GENERAL_ROLE_ID') else None
    ANNOUNCEMENT_CHANNEL_ID = int(os.getenv('ANNOUNCEMENT_CHANNEL_ID', 0)) if os.getenv('ANNOUNCEMENT_CHANNEL_ID') else None
    
    # Game Service Configuration
    GAME_SERVICE_PROTOCOL = os.getenv('GAME_SERVICE_PROTOCOL', 'http')
    GAME_SERVICE_DOMAIN = os.getenv('GAME_SERVICE_DOMAIN', 'localhost')
    GAME_SERVICE_PORT = os.getenv('GAME_SERVICE_PORT', '8001')
    GAME_SERVICE_URL = os.getenv('GAME_SERVICE_URL', f'{GAME_SERVICE_PROTOCOL}://{GAME_SERVICE_DOMAIN}:{GAME_SERVICE_PORT}')
    
    # Greeting Service Configuration
    GREETING_SERVICE_PROTOCOL = os.getenv('GREETING_SERVICE_PROTOCOL', 'http')
    GREETING_SERVICE_DOMAIN = os.getenv('GREETING_SERVICE_DOMAIN', 'localhost')
    GREETING_SERVICE_PORT = os.getenv('GREETING_SERVICE_PORT', '8080')
    GREETING_SERVICE_URL = os.getenv('GREETING_SERVICE_URL', f'{GREETING_SERVICE_PROTOCOL}://{GREETING_SERVICE_DOMAIN}:{GREETING_SERVICE_PORT}')
        
    # Webhook Configuration
    WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8080))
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')  # Should match game service secret

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