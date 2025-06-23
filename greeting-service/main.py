import logging
import os
from datetime import datetime, time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from models import *
from greeting_detector import GreetingDetector
from database import DatabaseManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Greeting Microservice API",
    description="REST API for Discord bot greeting functionality",
    version="1.0.0"
)

# Initialize components
greeting_detector = GreetingDetector()
db_manager = DatabaseManager()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now()
    )

@app.post("/greetings/detect", response_model=GreetingDetectionResponse)
async def detect_greeting(request: GreetingDetectionRequest):
    """Detect if a message contains a greeting."""
    try:
        is_greeting, matched_pattern = greeting_detector.is_greeting(request.message)
        return GreetingDetectionResponse(
            is_greeting=is_greeting,
            matched_pattern=matched_pattern
        )
    except Exception as e:
        logger.error(f"Error detecting greeting for message '{request.message}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/greetings", response_model=SaveGreetingResponse)
async def save_greeting(request: SaveGreetingRequest):
    """Save a greeting to the database."""
    try:
        greeting_id = db_manager.save_greeting(
            user_id=request.user_id,
            username=request.username,
            greeting_message=request.message_content,
            server_id=request.guild_id,
            channel_id=request.channel_id,
            message_id=request.message_id
        )
        
        if greeting_id is None:
            raise HTTPException(status_code=500, detail="Failed to save greeting")
        
        return JSONResponse(
            content=SaveGreetingResponse(greeting_id=greeting_id).model_dump(),
            status_code=201
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving greeting for user {request.username} ({request.user_id}) in guild {request.guild_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/greetings", response_model=TodaysGreetingsResponse)
async def get_todays_greetings(guild_id: str):
    """Get today's greeting statistics."""
    try:
        stats = db_manager.get_greeting_statistics(guild_id)
        
        # Convert time objects to datetime for JSON serialization
        first_greeting_time = None
        latest_greeting_time = None
        
        if stats['first_greeting_time']:
            first_time = stats['first_greeting_time']
            if hasattr(first_time, 'total_seconds'):  # It's a timedelta
                total_seconds = int(first_time.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                first_time = time(hours, minutes)
            first_greeting_time = datetime.combine(datetime.now().date(), first_time)
        if stats['latest_greeting_time']:
            latest_time = stats['latest_greeting_time']
            if hasattr(latest_time, 'total_seconds'):  # It's a timedelta
                total_seconds = int(latest_time.total_seconds())
                hours, remainder = divmod(total_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                latest_time = time(hours, minutes)
            latest_greeting_time = datetime.combine(datetime.now().date(), latest_time)
        
        leaderboard = [
            LeaderboardEntry(
                username=entry['username'],
                reaction_count=entry['reaction_count'],
                reactions=entry['reactions']
            )
            for entry in stats['leaderboard']
        ]
        
        return TodaysGreetingsResponse(
            total_reactions=stats['total_reactions'],
            unique_greeters=stats['unique_greeters'],
            first_greeting_time=first_greeting_time,
            latest_greeting_time=latest_greeting_time,
            leaderboard=leaderboard
        )
    except Exception as e:
        logger.error(f"Error getting today's greetings for guild {guild_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/greetings/reactions")
async def save_greeting_reaction(request: SaveReactionRequest):
    """Save a reaction to a greeting."""
    try:
        # First, get the greeting ID from the message ID
        greeting_id = db_manager.get_greeting_id_by_message(request.message_id)
        
        if greeting_id is None:
            raise HTTPException(status_code=404, detail="Greeting not found for this message")
        
        success = db_manager.save_greeting_reaction(
            greeting_id=greeting_id,
            user_id=request.user_id,
            username=request.username,
            reaction_emoji=request.emoji
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save reaction")
        
        return JSONResponse(status_code=201, content={"message": "Reaction saved"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving greeting reaction {request.emoji} from {request.username} ({request.user_id}) to message {request.message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/greetings/reactions")
async def remove_greeting_reaction(request: RemoveReactionRequest):
    """Remove a reaction from a greeting."""
    try:
        # First, get the greeting ID from the message ID
        greeting_id = db_manager.get_greeting_id_by_message(request.message_id)
        
        if greeting_id is None:
            raise HTTPException(status_code=404, detail="Greeting not found for this message")
        
        success = db_manager.remove_greeting_reaction(
            greeting_id=greeting_id,
            user_id=request.user_id,
            reaction_emoji=request.emoji
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to remove reaction")
        
        return JSONResponse(status_code=204, content=None)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing greeting reaction {request.emoji} from user {request.user_id} to message {request.message_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/greetings/languages", response_model=SupportedLanguagesResponse)
async def get_supported_languages():
    """Get all supported greeting languages and patterns."""
    try:
        languages = greeting_detector.get_supported_languages()
        return SupportedLanguagesResponse(languages=languages)
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)