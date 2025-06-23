"""
HTTP client for communicating with the 1337 Game Service
"""

import logging
import aiohttp
import asyncio
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from config import Config

logger = logging.getLogger(__name__)


class GameServiceClient:
    """HTTP client for the 1337 Game Service"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip('/')
        self.session = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _ensure_session(self):
        """Ensure we have an active session"""
        if not self.session:
            self.session = aiohttp.ClientSession()
    
    async def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the game service"""
        await self._ensure_session()
        
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.status == 404:
                    return None
                
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {method} {url} - {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in HTTP request: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        return await self._make_request("GET", "/health")
    
    async def get_game_start_time(self) -> Dict[str, Any]:
        """Get the game start time configuration"""
        return await self._make_request("GET", "/game/start-time")
    
    async def validate_bet_placement(self, user_id: int) -> Dict[str, Any]:
        """Validate if a user can place a bet"""
        data = {"user_id": user_id}
        return await self._make_request("POST", "/game/validate-bet", json=data)
    
    async def validate_early_bird_timestamp(self, timestamp: str) -> Dict[str, Any]:
        """Validate an early bird timestamp"""
        data = {"timestamp": timestamp}
        return await self._make_request("POST", "/game/validate-early-bird", json=data)
    
    async def place_bet(self, user_id: int, username: str, bet_type: str, 
                       guild_id: int, channel_id: int, timestamp: Optional[str] = None) -> Dict[str, Any]:
        """Place a bet (regular or early bird)"""
        data = {
            "user_id": user_id,
            "username": username,
            "bet_type": bet_type,
            "guild_id": guild_id,
            "channel_id": channel_id
        }
        
        if timestamp:
            data["timestamp"] = timestamp
        
        return await self._make_request("POST", "/game/place-bet", json=data)
    
    async def get_user_bet(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's bet information for today"""
        return await self._make_request("GET", f"/game/user-bet/{user_id}")
    
    async def get_daily_winner(self, game_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Get the daily winner"""
        params = {}
        if game_date:
            params["date"] = game_date.isoformat()
        
        return await self._make_request("GET", "/game/daily-winner", params=params)
    
    async def get_game_stats(self, days: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get game statistics"""
        params = {}
        if days:
            params["days"] = days
        if user_id:
            params["user_id"] = user_id
        
        return await self._make_request("GET", "/game/stats", params=params)
    
    async def get_daily_bets(self, game_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get all bets for a specific date"""
        params = {}
        if game_date:
            params["date"] = game_date.isoformat()
        
        return await self._make_request("GET", "/game/daily-bets", params=params)
    
    async def get_user_info_embed(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user info embed data for Discord"""
        return await self._make_request("GET", f"/game/user-info-embed/{user_id}")
    
    async def get_stats_page(self, page: int) -> Dict[str, Any]:
        """Get statistics page data for Discord embed"""
        return await self._make_request("GET", f"/game/stats-page/{page}")
    
    
    async def set_role_assignment(self, guild_id: int, user_id: int, role_type: str, role_id: int) -> Dict[str, Any]:
        """Set role assignment for a user in a guild"""
        params = {
            "guild_id": guild_id,
            "user_id": user_id,
            "role_type": role_type,
            "role_id": role_id
        }
        return await self._make_request("POST", "/roles/set", params=params)
    
    async def get_role_assignment(self, guild_id: int, role_type: str) -> Optional[Dict[str, Any]]:
        """Get role assignment for a specific role type in a guild"""
        return await self._make_request("GET", f"/roles/{guild_id}/{role_type}")
    
    async def get_all_role_assignments(self, guild_id: int) -> Dict[str, Any]:
        """Get all role assignments for a guild"""
        return await self._make_request("GET", f"/roles/{guild_id}")
    
    async def create_winner_message(self, winner_user_id: int, guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Create winner announcement message with role assignments"""
        params = {"winner_user_id": winner_user_id}
        if guild_id:
            params["guild_id"] = guild_id
        
        return await self._make_request("POST", "/game/winner-message", params=params)
    
    async def close(self):
        """Close the HTTP session"""
        if self.session:
            await self.session.close()
            self.session = None


# Compatibility functions to maintain the same interface as the original game logic
class GameServiceAdapter:
    """Adapter to maintain compatibility with existing bot code"""
    
    def __init__(self, game_service_url: str = "http://localhost:8001"):
        self.client = GameServiceClient(game_service_url)
    
    async def get_game_start_time(self) -> str:
        """Get the game start time from the service"""
        try:
            response = await self.client.get_game_start_time()
            return response.get('formatted_time', '13:37')
        except Exception as e:
            logger.error(f"Error getting game start time from service: {e}")
            # Fallback to default
            return '13:37'
    
    def parse_game_start_time(self):
        """Parse the game start time from configuration - deprecated, use get_game_start_time instead"""
        # Fallback implementation - should be replaced with service calls
        time_str = '13:37:00.000'  # Default fallback
        parts = time_str.split(':')
        hour = int(parts[0])
        minute = int(parts[1])
        second_parts = parts[2].split('.')
        second = int(second_parts[0])
        microsecond = int(second_parts[1]) * 1000 if len(second_parts) > 1 else 0
        return datetime.now().replace(hour=hour, minute=minute, second=second, microsecond=microsecond).time()
    
    def get_game_date(self):
        """Get the current game date"""
        return datetime.now().date()
    
    def format_time_with_ms(self, dt) -> str:
        """Format datetime with milliseconds"""
        if isinstance(dt, str):
            # If it's already a string, return as-is
            return dt
        elif isinstance(dt, datetime):
            return dt.strftime('%H:%M:%S.%f')[:-3]
        else:
            # Handle other types by converting to string
            return str(dt)
    
    def calculate_millisecond_difference(self, time1, time2):
        """Calculate millisecond difference between two times"""
        # Handle both datetime objects and time strings
        if isinstance(time1, str) and isinstance(time2, str):
            # Parse time strings back to datetime for calculation
            try:
                from datetime import datetime
                t1 = datetime.strptime(time1, '%H:%M:%S.%f').time()
                t2 = datetime.strptime(time2, '%H:%M:%S.%f').time()
                
                # Convert to total microseconds for comparison
                t1_microseconds = (t1.hour * 3600 + t1.minute * 60 + t1.second) * 1000000 + t1.microsecond
                t2_microseconds = (t2.hour * 3600 + t2.minute * 60 + t2.second) * 1000000 + t2.microsecond
                
                return (t1_microseconds - t2_microseconds) // 1000  # Return milliseconds
            except:
                return 0
        elif isinstance(time1, datetime) and isinstance(time2, datetime):
            # Handle datetime objects
            diff = time1 - time2
            return int(diff.total_seconds() * 1000)
        else:
            # Fallback
            return 0
    
    async def validate_bet_placement(self, user_id: int) -> Dict[str, Any]:
        """Validate if a user can place a bet"""
        return await self.client.validate_bet_placement(user_id)
    
    async def validate_early_bird_timestamp(self, timestamp: str) -> Dict[str, Any]:
        """Validate an early bird timestamp"""
        return await self.client.validate_early_bird_timestamp(timestamp)
    
    async def save_bet(self, user_id: int, username: str, play_time: datetime, bet_type: str, 
                      guild_id: int, channel_id: int) -> bool:
        """Save a bet - for compatibility with existing code"""
        try:
            # For regular bets, let the service determine the time
            if bet_type == "regular":
                result = await self.client.place_bet(user_id, username, bet_type, guild_id, channel_id)
            else:
                # For early bird bets, pass the timestamp
                timestamp_str = play_time.strftime('%H:%M:%S.%f')[:-3]
                result = await self.client.place_bet(user_id, username, bet_type, guild_id, channel_id, timestamp_str)
            
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Error saving bet via service: {e}")
            return False
    
    async def get_user_bet_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user's bet information for today"""
        return await self.client.get_user_bet(user_id)
    
    async def get_daily_winner(self, game_date: Optional[date] = None) -> Optional[Dict[str, Any]]:
        """Get the daily winner for a specific date"""
        return await self.client.get_daily_winner(game_date)
    
    async def get_winner_stats(self, days: Optional[int] = None, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get winner statistics"""
        return await self.client.get_game_stats(days=days, user_id=user_id)
    
    async def get_daily_bets(self, game_date: Optional[date] = None) -> List[Dict[str, Any]]:
        """Get all bets for a specific date"""
        return await self.client.get_daily_bets(game_date)
    
    async def create_user_info_embed_data(self, user_bet: Dict[str, Any]) -> Dict[str, Any]:
        """Create data for user bet info embed - use service if available, fallback to local"""
        try:
            embed_data = await self.client.get_user_info_embed(user_bet['user_id'])
            if embed_data:
                return embed_data
        except Exception as e:
            logger.warning(f"Failed to get embed data from service, using fallback: {e}")
        
        # Fallback implementation
        return self._create_user_info_embed_fallback(user_bet)
    
    async def get_stats_page_data(self, page: int) -> Dict[str, Any]:
        """Get statistics page data"""
        return await self.client.get_stats_page(page)
    
    
    async def set_role_assignment(self, guild_id: int, user_id: int, role_type: str, role_id: int) -> bool:
        """Set role assignment for a user in a guild"""
        try:
            result = await self.client.set_role_assignment(guild_id, user_id, role_type, role_id)
            return result.get('success', False)
        except Exception as e:
            logger.error(f"Error setting role assignment: {e}")
            return False
    
    async def get_role_assignment(self, guild_id: int, role_type: str) -> Optional[Dict[str, Any]]:
        """Get role assignment for a specific role type in a guild"""
        return await self.client.get_role_assignment(guild_id, role_type)
    
    async def get_all_role_assignments(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all role assignments for a guild"""
        try:
            result = await self.client.get_all_role_assignments(guild_id)
            return result.get('assignments', [])
        except Exception as e:
            logger.error(f"Error getting role assignments: {e}")
            return []
    
    async def create_winner_message(self, winner_data: Dict[str, Any], 
                                   top_14_day: Optional[Dict[str, Any]], 
                                   top_365_day: Optional[Dict[str, Any]],
                                   guild_id: Optional[int] = None,
                                   current_role_holders: Optional[Dict[str, Any]] = None) -> str:
        """Create plain text winner announcement message"""
        try:
            result = await self.client.create_winner_message(winner_data['user_id'], guild_id)
            return result.get('message', f"**{winner_data['username']}** won today's 1337 game!")
        except Exception as e:
            logger.error(f"Error creating winner message via service: {e}")
            # Fallback to simple message
            bet_type = "early bird" if winner_data['bet_type'] == 'early_bird' else "regular"
            return f"**{winner_data['username']}** won with a {bet_type} bet"
    
    def _create_user_info_embed_fallback(self, user_bet: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback embed creation if service is unavailable"""
        embed_data = {
            'title': '🎯 Your 1337 Bet Info',
            'color': 0x1337FF,
            'fields': []
        }

        bet_type_emoji = "🐦" if user_bet['bet_type'] == 'early_bird' else "⚡"
        embed_data['fields'].append({
            'name': 'Bet Type',
            'value': f"{bet_type_emoji} {user_bet['bet_type'].replace('_', ' ').title()}",
            'inline': True
        })

        embed_data['fields'].append({
            'name': 'Your Time',
            'value': f"`{self.format_time_with_ms(user_bet['play_time'])}`",
            'inline': True
        })

        embed_data['fields'].append({
            'name': 'Status',
            'value': f'⏳ Waiting for 13:37...',
            'inline': False
        })

        return embed_data
    
    async def close(self):
        """Close the service client"""
        await self.client.close()