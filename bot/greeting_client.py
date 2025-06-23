import aiohttp
import logging
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class GreetingClient:
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.session = None
        logger.info(f"GreetingClient initialized with base_url: {self.base_url}")

    async def _get_session(self):
        """Get or create an aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close the HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()

    async def detect_greeting(self, message: str) -> tuple[bool, Optional[str]]:
        """
        Detect if a message contains a greeting.
        Returns (is_greeting, matched_pattern).
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/greetings/detect"
            payload = {"message": message}
            logger.info(f"Making POST request to {url} with payload {payload}")
            
            async with session.post(url, json=payload) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successful detection response: {data}")
                    return data.get("is_greeting", False), data.get("matched_pattern")
                else:
                    response_text = await response.text()
                    logger.error(f"Greeting detection failed with status {response.status} for message: {message[:100]}...")
                    logger.info(f"Full URL was: {url}, Response: {response_text}")
                    return False, None
        except Exception as e:
            logger.error(f"Error detecting greeting via API: {e}")
            logger.info(f"Base URL: {self.base_url}, Message: {message[:50]}...")
            return False, None

    async def save_greeting(self, user_id: str, username: str, message_content: str,
                           guild_id: str, channel_id: str, message_id: str) -> Optional[int]:
        """
        Save a greeting to the database via the microservice.
        Returns the greeting ID if successful, None otherwise.
        """
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/greetings",
                json={
                    "user_id": user_id,
                    "username": username,
                    "message_content": message_content,
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "message_id": message_id,
                    "timestamp": datetime.now().isoformat()
                }
            ) as response:
                if response.status == 201:
                    data = await response.json()
                    return data.get("greeting_id")
                else:
                    logger.error(f"Save greeting failed with status {response.status} for user {username} ({user_id}) in guild {guild_id}")
                    return None
        except Exception as e:
            logger.error(f"Error saving greeting via API: {e}")
            return None

    async def get_todays_greetings(self, guild_id: str) -> Dict[str, Any]:
        """
        Get today's greeting statistics from the microservice.
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/greetings"
            params = {"guild_id": guild_id}
            logger.info(f"Making request to {url} with params {params}")
            
            async with session.get(url, params=params) as response:
                logger.info(f"Response status: {response.status}")
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Successful response data: {data}")
                    return data
                else:
                    response_text = await response.text()
                    logger.error(f"Get today's greetings failed with status {response.status} for guild {guild_id}. Response: {response_text}")
                    logger.info(f"Full URL was: {url}?guild_id={guild_id}")
                    return {
                        "total_reactions": 0,
                        "unique_greeters": 0,
                        "leaderboard": []
                    }
        except Exception as e:
            logger.error(f"Error getting today's greetings via API: {e}")
            logger.info(f"Base URL: {self.base_url}, Guild ID: {guild_id}")
            return {
                "total_reactions": 0,
                "unique_greeters": 0,
                "leaderboard": []
            }

    async def save_greeting_reaction(self, message_id: str, user_id: str, 
                                   username: str, emoji: str) -> bool:
        """
        Save a reaction to a greeting via the microservice.
        """
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/greetings/reactions",
                json={
                    "message_id": message_id,
                    "user_id": user_id,
                    "username": username,
                    "emoji": emoji
                }
            ) as response:
                return response.status == 201
        except Exception as e:
            logger.error(f"Error saving greeting reaction via API: {e}")
            return False

    async def remove_greeting_reaction(self, message_id: str, user_id: str, emoji: str) -> bool:
        """
        Remove a reaction from a greeting via the microservice.
        """
        try:
            session = await self._get_session()
            async with session.delete(
                f"{self.base_url}/greetings/reactions",
                json={
                    "message_id": message_id,
                    "user_id": user_id,
                    "emoji": emoji
                }
            ) as response:
                return response.status == 204
        except Exception as e:
            logger.error(f"Error removing greeting reaction via API: {e}")
            return False

    async def get_supported_languages(self) -> Dict[str, list]:
        """
        Get supported greeting languages from the microservice.
        """
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/greetings/languages") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("languages", {})
                else:
                    response_text = await response.text()
                    logger.error(f"Get supported languages failed with status {response.status}. Response: {response_text}")
                    return {}
        except Exception as e:
            logger.error(f"Error getting supported languages via API: {e}")
            return {}