from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional, List
from enum import Enum

class BetType(str, Enum):
    regular = "regular"
    early_bird = "early_bird"

class RoleType(str, Enum):
    sergeant = "sergeant"
    commander = "commander"
    general = "general"

# Request Models
class PlaceBetRequest(BaseModel):
    user_id: int
    username: str
    bet_type: BetType
    play_time: Optional[datetime] = None
    guild_id: int
    channel_id: int
    timestamp: Optional[str] = None

class BetValidationRequest(BaseModel):
    user_id: int

class TimestampValidationRequest(BaseModel):
    timestamp: str

# Response Models
class BetValidationResponse(BaseModel):
    valid: bool
    reason: Optional[str] = None
    message: Optional[str] = None
    existing_bet: Optional['BetInfo'] = None

class TimestampValidationResponse(BaseModel):
    valid: bool
    timestamp: Optional[datetime] = None
    reason: Optional[str] = None
    message: Optional[str] = None

class PlaceBetResponse(BaseModel):
    success: bool
    play_time: Optional[datetime] = None
    formatted_time: Optional[str] = None

class BetInfo(BaseModel):
    user_id: int
    username: str
    play_time: datetime
    bet_type: BetType
    game_date: date
    guild_id: int
    channel_id: int

class PlayerStats(BaseModel):
    user_id: int
    username: str
    wins: int

class WinnerResponse(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None
    win_time: Optional[datetime] = None
    play_time: Optional[datetime] = None
    bet_type: Optional[BetType] = None
    millisecond_diff: Optional[int] = None
    server_id: Optional[int] = None
    catastrophic_event: Optional[bool] = None
    identical_count: Optional[int] = None

class EmbedField(BaseModel):
    name: str
    value: str
    inline: bool

class EmbedData(BaseModel):
    title: str
    color: int
    fields: List[EmbedField]
    footer_text: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str
    message: str
    details: Optional[dict] = None

class HealthResponse(BaseModel):
    status: str
    timestamp: datetime

# Update forward references
BetValidationResponse.model_rebuild()