# Handlers

This directory contains message and reaction handlers for the Discord bot.

## Available Handlers

### MessageHandler (`message_handler.py`)
Handles incoming Discord messages and processes them for various features like greetings and automatic klugscheißer responses.

**Features:**
- Greeting detection and storage
- Automatic klugscheißer responses based on probability
- Message filtering and validation

### KlugscheisserHandler (`klugscheisser_handler.py`)
Manages the automatic klugscheißer feature that provides smart-alecky responses to messages.

**Features:**
- Probability-based message analysis
- User opt-in requirement checking
- Cooldown management
- OpenAI integration for intelligent responses

### FactCheckHandler (`factcheck_handler.py`)
Handles reaction-based fact-checking requests from users.

**Features:**
- Reaction-based triggering (🔍 emoji)
- Daily limit enforcement per user
- User opt-in verification for message authors
- Structured fact-checking with numerical scores (0-9)
- Automatic score emoji reactions
- Comprehensive error handling

## Fact-Check Feature

### How it works
1. **User reacts** with 🔍 emoji to any message
2. **System checks** if user hasn't exceeded daily limit (configurable via `.env`)
3. **Verification** that message author has opted in to OpenAI processing
4. **AI Analysis** sends message to OpenAI for structured fact-checking
5. **Scoring** receives score (0-9) and explanation from AI
6. **Response** adds score emoji to original message and sends detailed response
7. **Database** logs the fact-check request for statistics

### Configuration
Set these variables in your `.env` file:

```env
# Reaction-based Fact Checking
FACTCHECK_REACTION_EMOJI=🔍
FACTCHECK_DAILY_LIMIT_PER_USER=5
```

### Database Schema
The fact-check feature uses the `factcheck_requests` table:

```sql
CREATE TABLE factcheck_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    requester_user_id BIGINT NOT NULL,
    requester_username VARCHAR(255) NOT NULL,
    target_message_id BIGINT NOT NULL,
    target_user_id BIGINT NOT NULL,
    target_username VARCHAR(255) NOT NULL,
    message_content TEXT NOT NULL,
    request_date DATE NOT NULL,
    score TINYINT CHECK (score >= 0 AND score <= 9),
    factcheck_response TEXT,
    server_id BIGINT,
    channel_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Privacy & Opt-in
- Only messages from users who have opted in via `/klugscheisser_optin` can be fact-checked
- Users who haven't opted in will see a message explaining the requirement
- The same privacy settings apply to both automatic klugscheißer and reaction-based fact-checking

### Error Handling
The handler gracefully handles:
- Rate limiting from OpenAI API
- Daily limit exceeded
- User not opted in
- Messages too short for analysis
- API timeouts and errors
- Discord API errors

### Commands
Users can interact with the fact-check feature via these commands:
- `/factcheck_test` - Test the fact-checking with a specific message
- `/factcheck_stats` - View personal fact-check statistics
- `/klugscheisser_status` - Shows opt-in status and daily fact-check usage
- `/klugscheisser_stats` - Global statistics including fact-check info

### Score Scale
The AI provides scores on a 0-9 scale:
- **0-2**: Definitiv falsch/irreführend
- **3-4**: Größtenteils falsch mit wenigen korrekten Elementen  
- **5-6**: Gemischt, sowohl korrekte als auch falsche Elemente
- **7-8**: Größtenteils korrekt mit kleineren Ungenauigkeiten
- **9**: Vollständig korrekt und faktisch

### Technical Implementation
The fact-check handler:
1. Uses structured JSON prompts for consistent AI responses
2. Implements fallback score extraction for non-JSON responses
3. Includes comprehensive logging for debugging
4. Manages database transactions safely
5. Provides user-friendly error messages
6. Tracks statistics for monitoring usage

### Integration
The FactCheckHandler is integrated into the main bot via:
- `main.py` - Reaction event handling
- `commands/klugscheisser_command.py` - User commands and statistics
- `database.py` - Data persistence and retrieval
- `services/openai_service.py` - AI integration
