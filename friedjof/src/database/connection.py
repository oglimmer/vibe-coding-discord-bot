"""
Professional database connection manager with async support.
"""

import os
from datetime import datetime, date
from typing import List, Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_, func
from contextlib import asynccontextmanager

from .models import Base, UserGreeting
from utils.logger import setup_logger

logger = setup_logger('database')

class DatabaseManager:
    """Async database manager for the Discord bot."""
    
    def __init__(self):
        # Build database URL from environment variables
        self.database_url = self._build_database_url()
        self.engine = None
        self.session_factory = None
        
    def _build_database_url(self) -> str:
        """Build database URL from environment variables."""
        host = os.getenv('DB_HOST', 'localhost')
        user = os.getenv('DB_USER', 'postgres')
        password = os.getenv('DB_PASSWORD', '')
        database = os.getenv('DB_NAME', 'discord_bot')
        port = os.getenv('DB_PORT', '5432')
        
        # Use asyncpg for async PostgreSQL support
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    async def initialize(self):
        """Initialize database connection and create tables."""
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,
                pool_recycle=3600
            )
            
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
                
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """Get an async database session."""
        async with self.session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def save_greeting(self, user_id: int, username: str, 
                          guild_id: Optional[int] = None, 
                          channel_id: Optional[int] = None) -> bool:
        """
        Save a user greeting to the database.
        Multiple greetings per day per user are allowed.
        
        Args:
            user_id: Discord user ID
            username: User's display name
            guild_id: Guild (server) ID
            channel_id: Channel ID
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            async with self.get_session() as session:
                # Create new greeting record (no check for existing greetings)
                # Users can greet multiple times per day
                greeting = UserGreeting(
                    user_id=str(user_id),
                    username=username,
                    guild_id=str(guild_id) if guild_id else None,
                    channel_id=str(channel_id) if channel_id else None,
                    greeting_time=datetime.utcnow()
                )
                
                session.add(greeting)
                await session.commit()
                
                logger.info(f"Saved greeting for {username} (ID: {user_id})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save greeting for {username}: {e}")
            return False
    
    async def get_todays_greetings(self, guild_id: Optional[int] = None) -> List[UserGreeting]:
        """
        Get all greetings for today.
        
        Args:
            guild_id: Optional guild ID to filter by
            
        Returns:
            List of UserGreeting objects
        """
        try:
            async with self.get_session() as session:
                today = date.today()
                query = select(UserGreeting).where(
                    func.date(UserGreeting.greeting_time) == today
                )
                
                if guild_id:
                    query = query.where(UserGreeting.guild_id == str(guild_id))
                
                query = query.order_by(UserGreeting.greeting_time)
                
                result = await session.execute(query)
                return result.scalars().all()
                
        except Exception as e:
            logger.error(f"Failed to get today's greetings: {e}")
            return []
    
    async def get_greeting_stats(self, days: int = 7) -> dict:
        """
        Get greeting statistics for the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with statistics
        """
        try:
            async with self.get_session() as session:
                # Get total greetings in the last N days
                cutoff_date = date.today() - datetime.timedelta(days=days)
                
                result = await session.execute(
                    select(func.count(UserGreeting.id)).where(
                        func.date(UserGreeting.greeting_time) >= cutoff_date
                    )
                )
                total_greetings = result.scalar()
                
                # Get unique users in the last N days
                result = await session.execute(
                    select(func.count(func.distinct(UserGreeting.user_id))).where(
                        func.date(UserGreeting.greeting_time) >= cutoff_date
                    )
                )
                unique_users = result.scalar()
                
                return {
                    'total_greetings': total_greetings or 0,
                    'unique_users': unique_users or 0,
                    'days': days
                }
                
        except Exception as e:
            logger.error(f"Failed to get greeting stats: {e}")
            return {'total_greetings': 0, 'unique_users': 0, 'days': days}
    
    async def close(self):
        """Close database connection."""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connection closed")