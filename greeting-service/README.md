# Greeting Microservice

A REST API microservice that handles greeting functionality for the Discord bot, including multilingual greeting detection, database operations, and statistics.

## Features

- **Multilingual Greeting Detection**: Supports English, German, Regional (Austria/Switzerland), and International greetings
- **Database Operations**: Save greetings, manage reactions, and retrieve statistics
- **REST API**: FastAPI-based service with OpenAPI documentation
- **Containerized**: Docker support for easy deployment

## API Endpoints

### Greeting Detection
- `POST /greetings/detect` - Detect if a message contains a greeting
- `GET /greetings/languages` - Get all supported greeting languages

### Greeting Management
- `POST /greetings` - Save a greeting to the database
- `GET /greetings?guild_id=<id>` - Get today's greeting statistics

### Reaction Management
- `POST /greetings/reactions` - Save a reaction to a greeting
- `DELETE /greetings/reactions` - Remove a reaction from a greeting

### Health Check
- `GET /health` - Service health status

## Setup

1. **Install Dependencies**:
   ```bash
   cd greeting-service
   pip install -r requirements.txt
   ```

2. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

3. **Run the Service**:
   ```bash
   python main.py
   ```
   Or with uvicorn:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8080
   ```

## Docker Deployment

```bash
cd greeting-service
docker build -t greeting-service .
docker run -p 8080:8080 --env-file .env greeting-service
```

## API Documentation

Once the service is running, visit:
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI Spec: `http://localhost:8080/openapi.json`

## Database Schema

The service expects the following tables:
- `greetings` - Stores greeting messages
- `greeting_reactions` - Tracks reactions to greetings

## Supported Languages

- **English**: morning, good morning, gm, hello, hi, hey, etc.
- **German**: guten morgen, moin, hallo, servus, etc.
- **Regional**: grüezi, grüß gott, hoi, salü, etc.
- **International**: bonjour, hola, namaste, konnichiwa, etc.

## Integration

The main Discord bot communicates with this service via the `GreetingClient` class, which handles HTTP requests to all endpoints.