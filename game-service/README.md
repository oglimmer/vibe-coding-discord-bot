# 1337 Game Service

A FastAPI microservice that handles the core logic for the 1337 betting game.

## Overview

This service manages:
- Bet validation and placement
- Game logic and winner determination
- Statistics and leaderboards
- Game state management

## API Documentation

The service provides a comprehensive REST API documented in OpenAPI format. When running, visit:
- `/docs` - Interactive Swagger UI
- `/redoc` - ReDoc documentation
- `/openapi.json` - OpenAPI specification

## Setup

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
DB_HOST=localhost
DB_PORT=3306
DB_USER=vibe-bot
DB_PASSWORD=foobar
DB_NAME=vibe-bot
GAME_START_TIME=13:37:00.000
PORT=8001
```

### Database

The service uses MariaDB (shared with the Discord bot) and automatically creates required tables on startup.

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python main.py
```

### Running with Docker

```bash
# Build the image
docker build -t game-service .

# Run the container
docker run -p 8001:8001 --env-file .env game-service
```

## API Endpoints

### Health Check
- `GET /health` - Service health status

### Game Operations
- `POST /game/validate-bet` - Validate bet placement
- `POST /game/validate-early-bird` - Validate early bird timestamp
- `POST /game/place-bet` - Place a bet
- `GET /game/user-bet/{user_id}` - Get user's bet info
- `GET /game/daily-winner` - Get daily winner
- `POST /game/determine-winner` - Determine daily winner (internal)

### Statistics
- `GET /game/stats` - Get game statistics
- `GET /game/daily-bets` - Get daily bets
- `GET /game/stats-page/{page}` - Get formatted stats for Discord

### Discord Integration
- `GET /game/user-info-embed/{user_id}` - Get Discord embed data

## Integration

The bot communicates with this service via HTTP using the `GameServiceClient` class. The service maintains the same interface as the original game logic for seamless integration.

## Architecture

```
Bot (Discord) <--HTTP--> Game Service <--MariaDB--> Database (Shared)
```

The service is stateless and scales horizontally. All game state is persisted in the shared MariaDB database.