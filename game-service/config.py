import os
import logging
from dotenv import load_dotenv

# Load .env file, but don't override existing environment variables
load_dotenv(override=False)

class Config:
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'vibe-bot')
    
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # 1337 Game Configuration
    GAME_START_TIME = os.getenv('GAME_START_TIME', '13:37:00.000')
    PORT = int(os.getenv('PORT', 8001))
    
    # Scheduler Configuration
    ENABLE_SCHEDULER = os.getenv('ENABLE_SCHEDULER', 'true').lower() == 'true'
    
    # Webhook Configuration  
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'http://localhost:8080/webhook/winner')  # Discord bot webhook
    WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')  # Optional secret for webhook auth

def setup_logging():
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)