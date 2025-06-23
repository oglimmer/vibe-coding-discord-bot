"""
FastAPI application for the 1337 Game Service
"""

import logging
import asyncio
import aiohttp
from datetime import datetime, date, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, Path
from contextlib import asynccontextmanager

from config import Config, setup_logging
from database import DatabaseManager
from game_logic import Game1337Logic
from models import (
    BetValidationRequest, BetValidationResponse, PlaceBetRequest, PlaceBetResponse,
    TimestampValidationRequest, TimestampValidationResponse, BetInfo, PlayerStats,
    WinnerResponse, EmbedData, ErrorResponse, HealthResponse
)

# Setup logging
logger = setup_logging()

# Global instances
db_manager = None
game_logic = None
scheduler_task = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan"""
    global db_manager, game_logic, scheduler_task
    
    # Startup
    logger.info("Starting 1337 Game Service")
    
    db_manager = DatabaseManager()
    await db_manager.connect()
    
    game_logic = Game1337Logic(db_manager)
    
    # Start the game scheduler if enabled
    if Config.ENABLE_SCHEDULER:
        scheduler_task = asyncio.create_task(game_scheduler())
        logger.info("Game scheduler started")
    else:
        logger.info("Game scheduler disabled by configuration")
    
    logger.info("1337 Game Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down 1337 Game Service")
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("Game scheduler stopped")
    
    if db_manager:
        await db_manager.disconnect()
    logger.info("1337 Game Service stopped")

async def game_scheduler():
    """Background task that handles game scheduling and winner determination"""
    logger.info("🎯 [SCHEDULER] Game scheduler started")
    
    while True:
        try:
            await _schedule_next_winner_determination()
        except asyncio.CancelledError:
            logger.info("🎯 [SCHEDULER] Game scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"🎯 [SCHEDULER] Error in game scheduler: {e}")
            # Wait a bit before retrying on error
            await asyncio.sleep(60)

async def _schedule_next_winner_determination():
    """Calculate and schedule the exact time for winner determination"""
    try:
        current_time = datetime.now()
        game_start_time = game_logic.parse_game_start_time()
        
        # Calculate next game time (today or tomorrow)
        next_game_time = datetime.combine(current_time.date(), game_start_time)
        if current_time >= next_game_time:
            # Game time has passed today, schedule for tomorrow
            next_game_time = next_game_time + timedelta(days=1)
        
        # Add a small buffer (1 minute) after game start time to ensure all bets are in
        next_game_time += timedelta(minutes=1)
        
        # Calculate delay until winner determination time
        delay_seconds = (next_game_time - current_time).total_seconds()
        
        logger.info(
            f"🎯 [SCHEDULER] Next winner determination scheduled for {next_game_time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"(in {delay_seconds:.1f} seconds)"
        )
        
        # Wait until it's time
        await asyncio.sleep(delay_seconds)
        
        # Determine the winner
        await _auto_determine_winner()
        
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"🎯 [SCHEDULER] Error scheduling winner determination: {e}")

async def _auto_determine_winner():
    """Automatically determine the daily winner"""
    try:
        logger.info("🎯 [SCHEDULER] Starting automatic winner determination")
        
        current_time = datetime.now()
        game_date = current_time.date()
        
        # Check if we already have a winner for today
        existing_winner = await game_logic.get_daily_winner(game_date)
        if existing_winner:
            logger.info(f"🎯 [SCHEDULER] Winner already exists for {game_date}: {existing_winner['username']}")
            return
        
        # Get the win time for today
        win_time = game_logic.get_daily_win_time(game_date)
        logger.info(f"🎯 [SCHEDULER] Win time for {game_date}: {game_logic.format_time_with_ms(win_time)}")
        
        # Determine winner
        winner_result = await game_logic.determine_winner(game_date, win_time)
        
        if not winner_result:
            logger.info(f"🎯 [SCHEDULER] No winner determined for {game_date} - no valid bets")
            return
        
        if winner_result.get('catastrophic_event'):
            logger.warning(f"💥 [SCHEDULER] Catastrophic event on {game_date}! {winner_result['identical_count']} identical times")
            # Notify about catastrophic event
            await _notify_webhook_catastrophic(winner_result)
            return
        
        # Save winner
        success = await game_logic.save_winner(winner_result)
        if success:
            logger.info(f"🎯 [SCHEDULER] Winner saved successfully: {winner_result['username']} on {game_date}")
            
            # Notify external services (like the Discord bot)
            await _notify_webhook(winner_result)
            
        else:
            logger.error(f"🎯 [SCHEDULER] Failed to save winner for {game_date}")
        
    except Exception as e:
        logger.error(f"🎯 [SCHEDULER] Error in automatic winner determination: {e}")

async def _notify_webhook(winner_result):
    """Send webhook notification about winner determination"""
    if not Config.WEBHOOK_URL:
        return
    
    try:
        # Convert datetime objects to ISO strings for JSON serialization
        serializable_winner = _serialize_winner_data(winner_result)
        
        payload = {
            "event": "winner_determined",
            "winner": serializable_winner,
            "timestamp": datetime.now().isoformat()
        }
        
        headers = {"Content-Type": "application/json"}
        if Config.WEBHOOK_SECRET:
            headers["Authorization"] = f"Bearer {Config.WEBHOOK_SECRET}"
        
        logger.info(f"🔔 [WEBHOOK] Sending winner notification to {Config.WEBHOOK_URL}")
        logger.debug(f"🔔 [WEBHOOK] Payload: {payload}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(Config.WEBHOOK_URL, json=payload, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"🔔 [WEBHOOK] Successfully notified webhook about winner: {winner_result['username']}")
                else:
                    response_text = await response.text()
                    logger.warning(f"🔔 [WEBHOOK] Webhook notification failed with status {response.status}: {response_text}")
                    
    except Exception as e:
        logger.error(f"🔔 [WEBHOOK] Error sending webhook notification: {e}")

def _serialize_winner_data(winner_data):
    """Convert datetime objects in winner data to ISO strings for JSON serialization"""
    serialized = {}
    
    for key, value in winner_data.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, date):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    
    return serialized

async def _notify_webhook_catastrophic(catastrophic_result):
    """Send webhook notification about catastrophic event"""
    if not Config.WEBHOOK_URL:
        return
    
    try:
        payload = {
            "event": "catastrophic_event",
            "catastrophic_data": catastrophic_result,
            "timestamp": datetime.now().isoformat()
        }
        
        headers = {"Content-Type": "application/json"}
        if Config.WEBHOOK_SECRET:
            headers["Authorization"] = f"Bearer {Config.WEBHOOK_SECRET}"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(Config.WEBHOOK_URL.replace('/winner', '/catastrophic'), json=payload, headers=headers) as response:
                if response.status == 200:
                    logger.info(f"🔔 [WEBHOOK] Successfully notified webhook about catastrophic event")
                else:
                    logger.warning(f"🔔 [WEBHOOK] Catastrophic webhook notification failed with status {response.status}")
                    
    except Exception as e:
        logger.error(f"🔔 [WEBHOOK] Error sending catastrophic webhook notification: {e}")

# Create FastAPI app
app = FastAPI(
    title="1337 Game Service API",
    description="Microservice for managing the 1337 betting game logic and operations",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now()
    )

@app.get("/game/start-time")
async def get_game_start_time():
    """Get the configured game start time"""
    try:
        return {
            "start_time": Config.GAME_START_TIME,
            "formatted_time": Config.GAME_START_TIME[:5]  # HH:MM format
        }
    except Exception as e:
        logger.error(f"Error getting game start time: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/game/validate-bet", response_model=BetValidationResponse)
async def validate_bet(request: BetValidationRequest):
    """Validate if a user can place a bet"""
    try:
        validation = await game_logic.validate_bet_placement(request.user_id)
        
        response = BetValidationResponse(
            valid=validation['valid'],
            reason=validation.get('reason'),
            message=validation.get('message')
        )
        
        if 'existing_bet' in validation:
            existing = validation['existing_bet']
            response.existing_bet = BetInfo(
                user_id=existing['user_id'],
                username=existing['username'],
                play_time=existing['play_time'],
                bet_type=existing['bet_type'],
                game_date=existing.get('game_date', game_logic.get_game_date()),
                guild_id=existing.get('guild_id', 0),
                channel_id=existing.get('channel_id', 0)
            )
        
        return response
    except Exception as e:
        logger.error(f"Error validating bet: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/game/validate-early-bird", response_model=TimestampValidationResponse)
async def validate_early_bird_timestamp(request: TimestampValidationRequest):
    """Validate an early bird timestamp"""
    try:
        validation = game_logic.validate_early_bird_timestamp(request.timestamp)
        
        return TimestampValidationResponse(
            valid=validation['valid'],
            timestamp=validation.get('timestamp'),
            reason=validation.get('reason'),
            message=validation.get('message')
        )
    except Exception as e:
        logger.error(f"Error validating early bird timestamp: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/game/place-bet", response_model=PlaceBetResponse)
async def place_bet(request: PlaceBetRequest):
    """Place a bet (regular or early bird)"""
    try:
        # For regular bets, use current time
        if request.bet_type == "regular":
            play_time = datetime.now()
        else:
            # For early bird bets, validate and use provided timestamp
            if not request.timestamp:
                raise HTTPException(status_code=400, detail="Timestamp required for early bird bets")
            
            validation = game_logic.validate_early_bird_timestamp(request.timestamp)
            if not validation['valid']:
                raise HTTPException(status_code=400, detail=validation['message'])
            
            play_time = validation['timestamp']
        
        # Save the bet
        success = await game_logic.save_bet(
            request.user_id,
            request.username,
            play_time,
            request.bet_type,
            request.guild_id,
            request.channel_id
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save bet")
        
        return PlaceBetResponse(
            success=True,
            play_time=play_time,
            formatted_time=game_logic.format_time_with_ms(play_time)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error placing bet: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/user-bet/{user_id}", response_model=BetInfo)
async def get_user_bet(user_id: int = Path(..., description="Discord user ID")):
    """Get user's bet information for today"""
    try:
        bet_info = await game_logic.get_user_bet_info(user_id)
        
        if not bet_info:
            raise HTTPException(status_code=404, detail="No bet found for today")
        
        return BetInfo(
            user_id=bet_info['user_id'],
            username=bet_info['username'],
            play_time=bet_info['play_time'],
            bet_type=bet_info['bet_type'],
            game_date=bet_info.get('game_date', game_logic.get_game_date()),
            guild_id=bet_info.get('guild_id', 0),
            channel_id=bet_info.get('channel_id', 0)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user bet: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/daily-winner", response_model=WinnerResponse)
async def get_daily_winner(game_date: Optional[date] = Query(None, description="Game date (defaults to today)")):
    """Get the daily winner"""
    try:
        winner = await game_logic.get_daily_winner(game_date)
        
        if not winner:
            raise HTTPException(status_code=404, detail="No winner determined yet")
        
        return WinnerResponse(
            user_id=winner['user_id'],
            username=winner['username'],
            win_time=winner['win_time'],
            play_time=winner['play_time'],
            bet_type=winner['bet_type'],
            millisecond_diff=winner['millisecond_diff']
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting daily winner: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/stats", response_model=List[PlayerStats])
async def get_game_stats(
    days: Optional[int] = Query(None, description="Number of days to include", ge=1, le=365),
    user_id: Optional[int] = Query(None, description="Get stats for specific user")
):
    """Get game statistics"""
    try:
        stats = await game_logic.get_winner_stats(days=days, user_id=user_id)
        
        return [
            PlayerStats(
                user_id=stat['user_id'],
                username=stat['username'],
                wins=stat['wins']
            )
            for stat in stats
        ]
    except Exception as e:
        logger.error(f"Error getting game stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/daily-bets", response_model=List[BetInfo])
async def get_daily_bets(game_date: Optional[date] = Query(None, description="Game date (defaults to today)")):
    """Get all bets for a specific date"""
    try:
        bets = await game_logic.get_daily_bets(game_date)
        
        return [
            BetInfo(
                user_id=bet['user_id'],
                username=bet['username'],
                play_time=bet['play_time'],
                bet_type=bet['bet_type'],
                game_date=game_date or game_logic.get_game_date(),
                guild_id=bet.get('server_id', 0),
                channel_id=bet.get('channel_id', 0)
            )
            for bet in bets
        ]
    except Exception as e:
        logger.error(f"Error getting daily bets: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/user-info-embed/{user_id}", response_model=EmbedData)
async def get_user_info_embed(user_id: int = Path(..., description="Discord user ID")):
    """Get user info embed data for Discord"""
    try:
        bet_info = await game_logic.get_user_bet_info(user_id)
        
        if not bet_info:
            raise HTTPException(status_code=404, detail="No bet found for today")
        
        embed_data = game_logic.create_user_info_embed_data(bet_info)
        
        return EmbedData(
            title=embed_data['title'],
            color=embed_data['color'],
            fields=[
                {
                    'name': field['name'],
                    'value': field['value'],
                    'inline': field['inline']
                }
                for field in embed_data['fields']
            ],
            footer_text=embed_data.get('footer_text')
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user info embed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/game/stats-page/{page}", response_model=EmbedData)
async def get_stats_page(page: int = Path(..., description="Page number", ge=0, le=2)):
    """Get statistics page data for Discord embed"""
    try:
        embed_data = await game_logic.get_stats_page_data(page)
        
        return EmbedData(
            title=embed_data['title'],
            color=embed_data['color'],
            fields=[
                {
                    'name': field['name'],
                    'value': field['value'],
                    'inline': field['inline']
                }
                for field in embed_data['fields']
            ],
            footer_text=embed_data.get('footer_text')
        )
    except Exception as e:
        logger.error(f"Error getting stats page: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/roles/set")
async def set_role_assignment(
    guild_id: int = Query(..., description="Discord guild ID"),
    user_id: int = Query(..., description="Discord user ID"),  
    role_type: str = Query(..., description="Role type"),
    role_id: int = Query(..., description="Discord role ID")
):
    """Set role assignment for a user in a guild"""
    try:
        success = await db_manager.set_role_assignment(guild_id, user_id, role_type, role_id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to set role assignment")
        
        return {"success": True, "message": f"Role {role_type} assigned to user {user_id}"}
    except Exception as e:
        logger.error(f"Error setting role assignment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/roles/{guild_id}/{role_type}")
async def get_role_assignment(
    guild_id: int = Path(..., description="Discord guild ID"),
    role_type: str = Path(..., description="Role type")
):
    """Get role assignment for a specific role type in a guild"""
    try:
        assignment = await db_manager.get_role_assignment(guild_id, role_type)
        
        if not assignment:
            raise HTTPException(status_code=404, detail="Role assignment not found")
        
        return assignment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting role assignment: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/roles/{guild_id}")
async def get_all_role_assignments(guild_id: int = Path(..., description="Discord guild ID")):
    """Get all role assignments for a guild"""
    try:
        assignments = await db_manager.get_all_role_assignments(guild_id)
        return {"assignments": assignments}
    except Exception as e:
        logger.error(f"Error getting all role assignments: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/game/winner-message")
async def create_winner_message(
    winner_user_id: int = Query(..., description="Winner user ID"),
    guild_id: Optional[int] = Query(None, description="Guild ID for role assignments")
):
    """Create winner announcement message with role assignments"""
    try:
        # Get today's winner
        winner = await game_logic.get_daily_winner()
        if not winner or winner['user_id'] != winner_user_id:
            raise HTTPException(status_code=404, detail="Winner not found")
        
        # Get top players for role calculations
        top_14_day_stats = await game_logic.get_winner_stats(days=14)
        top_365_day_stats = await game_logic.get_winner_stats(days=365)
        
        top_14_day = top_14_day_stats[0] if top_14_day_stats else None
        top_365_day = top_365_day_stats[0] if top_365_day_stats else None
        
        # Get current role holders if guild_id provided
        current_role_holders = None
        if guild_id:
            assignments = await db_manager.get_all_role_assignments(guild_id)
            current_role_holders = {
                assignment['role_type']: {
                    'user_id': assignment['user_id'],
                    'role_id': assignment['role_id']
                }
                for assignment in assignments
            }
        
        # Create winner message
        message = await game_logic.create_winner_message(
            winner, top_14_day, top_365_day, guild_id, current_role_holders
        )
        
        # Calculate new role assignments
        new_assignments = game_logic.determine_new_role_assignments(winner, top_14_day, top_365_day)
        
        return {
            "message": message,
            "new_role_assignments": new_assignments,
            "winner": winner,
            "top_14_day": top_14_day,
            "top_365_day": top_365_day
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating winner message: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/game/schedule-check")
async def schedule_check():
    """Check if it's time to determine a winner and do so if needed"""
    try:
        # Check if game time has passed and winner determination is needed
        current_time = datetime.now()
        game_passed = game_logic.is_game_time_passed(current_time)
        win_time_passed = game_logic.is_win_time_passed(current_time)
        
        # Get today's winner to see if we already have one
        today_winner = await game_logic.get_daily_winner()
        
        if win_time_passed and not today_winner:
            logger.info("Win time has passed and no winner determined yet - determining winner now")
            
            game_date = game_logic.get_game_date()
            win_time = game_logic.get_daily_win_time(game_date)
            
            winner_result = await game_logic.determine_winner(game_date, win_time)
            
            if winner_result and not winner_result.get('catastrophic_event'):
                success = await game_logic.save_winner(winner_result)
                if success:
                    return {
                        "winner_determined": True,
                        "winner": winner_result,
                        "message": f"Winner determined: {winner_result['username']}"
                    }
                else:
                    raise HTTPException(status_code=500, detail="Failed to save winner")
            elif winner_result and winner_result.get('catastrophic_event'):
                return {
                    "winner_determined": True,
                    "catastrophic_event": True,
                    "message": "Catastrophic event occurred"
                }
            else:
                return {
                    "winner_determined": False,
                    "message": "No valid bets found"
                }
        elif today_winner:
            return {
                "winner_determined": True,
                "winner": today_winner,
                "message": f"Winner already determined: {today_winner['username']}"
            }
        else:
            return {
                "winner_determined": False,
                "message": f"Not time yet - game_passed: {game_passed}, win_time_passed: {win_time_passed}"
            }
            
    except Exception as e:
        logger.error(f"Error in schedule check: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT)