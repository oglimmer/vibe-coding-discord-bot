from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime

class GreetingDetectionRequest(BaseModel):
    message: str

class GreetingDetectionResponse(BaseModel):
    is_greeting: bool
    matched_pattern: Optional[str] = None

class SaveGreetingRequest(BaseModel):
    user_id: str
    username: str
    message_id: str
    channel_id: str
    guild_id: str
    message_content: str
    timestamp: Optional[datetime] = None

class SaveGreetingResponse(BaseModel):
    greeting_id: int

class LeaderboardEntry(BaseModel):
    username: str
    reaction_count: int
    reactions: List[str] = []

class TodaysGreetingsResponse(BaseModel):
    total_reactions: int
    unique_greeters: int
    first_greeting_time: Optional[datetime] = None
    latest_greeting_time: Optional[datetime] = None
    leaderboard: List[LeaderboardEntry]

class SaveReactionRequest(BaseModel):
    message_id: str
    user_id: str
    username: str
    emoji: str

class RemoveReactionRequest(BaseModel):
    message_id: str
    user_id: str
    emoji: str

class SupportedLanguagesResponse(BaseModel):
    languages: Dict[str, List[str]]

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None