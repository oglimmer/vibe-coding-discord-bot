"""
Database models for the Discord bot.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, Numeric
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

class UserGreeting(Base):
    """Model for storing user greetings."""
    
    __tablename__ = 'user_greetings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), nullable=False, index=True)  # Discord user ID
    username = Column(String(100), nullable=False)  # User display name
    guild_id = Column(String(20), nullable=True, index=True)  # Server ID
    channel_id = Column(String(20), nullable=True)  # Channel ID
    greeting_time = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return (f"<UserGreeting(id={self.id}, user_id='{self.user_id}', "
                f"username='{self.username}', greeting_time='{self.greeting_time}')>")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'guild_id': self.guild_id,
            'channel_id': self.channel_id,
            'greeting_time': self.greeting_time.isoformat() if self.greeting_time else None
        }


class BetType(enum.Enum):
    """Enum for bet types in 1337 game."""
    NORMAL = "normal"
    EARLY = "early"


class Game1337Bet(Base):
    """Model for storing 1337 game bets."""
    
    __tablename__ = 'game_1337_bets'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), nullable=False, index=True)  # Discord user ID
    username = Column(String(100), nullable=False)  # User display name at time of bet
    play_time = Column(Integer, nullable=False)  # Milliseconds after GAME_START_TIME
    play_type = Column(Enum(BetType), nullable=False)  # normal or early
    date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD (bot-local)
    guild_id = Column(String(20), nullable=True, index=True)  # Server ID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return (f"<Game1337Bet(id={self.id}, user_id='{self.user_id}', "
                f"username='{self.username}', play_time={self.play_time}, "
                f"play_type={self.play_type}, date='{self.date}')>")
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'play_time': self.play_time,
            'play_type': self.play_type.value if self.play_type else None,
            'date': self.date,
            'guild_id': self.guild_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Game1337PlayerStats(Base):
    """Model for storing 1337 game player statistics and rankings."""
    
    __tablename__ = 'game_1337_player_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(20), nullable=False, unique=True, index=True)  # Discord user ID
    username = Column(String(100), nullable=False)  # Current username
    guild_id = Column(String(20), nullable=True, index=True)  # Server ID
    total_wins = Column(Integer, default=0, nullable=False, index=True)
    total_games = Column(Integer, default=0, nullable=False)
    total_early_bird_bets = Column(Integer, default=0, nullable=False)
    best_time_ms = Column(Integer, nullable=True)  # Best time in milliseconds
    worst_time_ms = Column(Integer, nullable=True)  # Worst time in milliseconds
    avg_time_ms = Column(Numeric(10, 2), nullable=True)  # Average time
    current_streak = Column(Integer, default=0, nullable=False, index=True)  # Current winning streak
    max_streak = Column(Integer, default=0, nullable=False)  # Best streak ever
    last_game_date = Column(String(10), nullable=True)  # YYYY-MM-DD format
    last_win_date = Column(String(10), nullable=True)  # YYYY-MM-DD format
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return (f"<Game1337PlayerStats(id={self.id}, user_id='{self.user_id}', "
                f"username='{self.username}', total_wins={self.total_wins}, "
                f"total_games={self.total_games}, current_streak={self.current_streak})>")
    
    @property
    def win_percentage(self):
        """Calculate win percentage."""
        if self.total_games == 0:
            return 0.0
        return round((self.total_wins / self.total_games) * 100, 2)
    
    @property
    def rank_title(self):
        """Get rank title based on total wins."""
        if self.total_wins >= 10:
            return "Leet General"
        elif self.total_wins >= 5:
            return "Leet Commander"
        elif self.total_wins >= 1:
            return "Leet Sergeant"
        else:
            return "Recruit"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'guild_id': self.guild_id,
            'total_wins': self.total_wins,
            'total_games': self.total_games,
            'win_percentage': self.win_percentage,
            'total_early_bird_bets': self.total_early_bird_bets,
            'best_time_ms': self.best_time_ms,
            'worst_time_ms': self.worst_time_ms,
            'avg_time_ms': float(self.avg_time_ms) if self.avg_time_ms else None,
            'current_streak': self.current_streak,
            'max_streak': self.max_streak,
            'rank_title': self.rank_title,
            'last_game_date': self.last_game_date,
            'last_win_date': self.last_win_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
