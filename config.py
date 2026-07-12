import os
import logging
from dotenv import load_dotenv

# Load .env file, but don't override existing environment variables
load_dotenv(override=False)


class Config:
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME", "discord_bot")

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "/tmp/bot.log")

    # 1337 Game Configuration
    GAME_START_TIME = os.getenv("GAME_START_TIME", "13:37:00.000")
    SERGEANT_ROLE_ID = (
        int(os.getenv("SERGEANT_ROLE_ID", 0)) if os.getenv("SERGEANT_ROLE_ID") else None
    )
    COMMANDER_ROLE_ID = (
        int(os.getenv("COMMANDER_ROLE_ID", 0))
        if os.getenv("COMMANDER_ROLE_ID")
        else None
    )
    GENERAL_ROLE_ID = (
        int(os.getenv("GENERAL_ROLE_ID", 0)) if os.getenv("GENERAL_ROLE_ID") else None
    )
    ANNOUNCEMENT_CHANNEL_ID = (
        int(os.getenv("ANNOUNCEMENT_CHANNEL_ID", 0))
        if os.getenv("ANNOUNCEMENT_CHANNEL_ID")
        else None
    )

    # Klugscheißer Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    KLUGSCHEISSER_ENABLED = (
        os.getenv("KLUGSCHEISSER_ENABLED", "false").lower() == "true"
    )
    KLUGSCHEISSER_PROBABILITY = int(os.getenv("KLUGSCHEISSER_PROBABILITY", 10))
    KLUGSCHEISSER_MIN_LENGTH = int(os.getenv("KLUGSCHEISSER_MIN_LENGTH", 100))
    KLUGSCHEISSER_MAX_TOKENS = int(os.getenv("KLUGSCHEISSER_MAX_TOKENS", 200))
    KLUGSCHEISSER_MODEL = os.getenv("KLUGSCHEISSER_MODEL", "gpt-3.5-turbo")
    KLUGSCHEISSER_COOLDOWN_SECONDS = int(
        os.getenv("KLUGSCHEISSER_COOLDOWN_SECONDS", 60)
    )
    KLUGSCHEISSER_REQUIRE_OPTIN = (
        os.getenv("KLUGSCHEISSER_REQUIRE_OPTIN", "true").lower() == "true"
    )

    # Reaction-based Fact Checking Configuration
    FACTCHECK_REACTION_EMOJI = os.getenv("FACTCHECK_REACTION_EMOJI", "🔍")
    FACTCHECK_DAILY_LIMIT_PER_USER = int(os.getenv("FACTCHECK_DAILY_LIMIT_PER_USER", 5))

    # Vibecode (self-extending bot) Configuration
    VIBECODE_ENABLED = os.getenv("VIBECODE_ENABLED", "false").lower() == "true"
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    VIBECODE_GITHUB_TOKEN = os.getenv("VIBECODE_GITHUB_TOKEN")
    VIBECODE_REPO = os.getenv("VIBECODE_REPO", "oglimmer/vibe-coding-discord-bot")
    VIBECODE_BASE_BRANCH = os.getenv("VIBECODE_BASE_BRANCH", "main")
    VIBECODE_WORKER_IMAGE = os.getenv(
        "VIBECODE_WORKER_IMAGE",
        "ghcr.io/oglimmer/vibe-coding-discord-bot-worker:latest",
    )
    VIBECODE_MODEL = os.getenv("VIBECODE_MODEL", "deepseek/deepseek-v4-pro")
    VIBECODE_NAMESPACE = os.getenv("VIBECODE_NAMESPACE")
    VIBECODE_SECRET_NAME = os.getenv("VIBECODE_SECRET_NAME", "discord-bot-secrets")
    VIBECODE_IMAGE_PULL_SECRET = os.getenv("VIBECODE_IMAGE_PULL_SECRET")
    VIBECODE_JOB_TIMEOUT_SECONDS = int(os.getenv("VIBECODE_JOB_TIMEOUT_SECONDS", 2700))
    VIBECODE_COOLDOWN_SECONDS = int(os.getenv("VIBECODE_COOLDOWN_SECONDS", 900))
    VIBECODE_MAX_CONCURRENT_JOBS = int(os.getenv("VIBECODE_MAX_CONCURRENT_JOBS", 1))

    # Postillon RSS feed configuration
    POSTILLON_ENABLED = os.getenv("POSTILLON_ENABLED", "false").lower() == "true"
    POSTILLON_FEED_URL = os.getenv(
        "POSTILLON_FEED_URL",
        "https://www.der-postillon.com/feeds/posts/default"
        "?alt=rss&max-results=50&start-index=1",
    )
    POSTILLON_CHANNEL_ID = (
        int(os.getenv("POSTILLON_CHANNEL_ID"))
        if os.getenv("POSTILLON_CHANNEL_ID")
        else None
    )
    POSTILLON_POLL_INTERVAL_MINUTES = int(
        os.getenv("POSTILLON_POLL_INTERVAL_MINUTES", "15")
    )
    POSTILLON_TIMEZONE = os.getenv("POSTILLON_TIMEZONE", "Europe/Berlin")
    POSTILLON_ANNOUNCE_FIRST_SYNC = (
        os.getenv("POSTILLON_ANNOUNCE_FIRST_SYNC", "false").lower() == "true"
    )
    POSTILLON_REQUEST_TIMEOUT_SECONDS = int(
        os.getenv("POSTILLON_REQUEST_TIMEOUT_SECONDS", "20")
    )
    POSTILLON_DELIVERY_DELAY_SECONDS = float(
        os.getenv("POSTILLON_DELIVERY_DELAY_SECONDS", "1")
    )
    POSTILLON_LEASE_SECONDS = int(os.getenv("POSTILLON_LEASE_SECONDS", "1800"))


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(Config.LOG_FILE), logging.StreamHandler()],
    )
    return logging.getLogger(__name__)
