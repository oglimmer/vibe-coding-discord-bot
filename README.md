# Discord Greeting Bot

A professional Discord bot written in Python 3.12 that responds to greetings with wave emojis and tracks greeting statistics in a MariaDB database.

## Features

- **Automatic Greeting Response**: Responds with 👋 emoji to messages containing "morning", "good morning", or "gn"
- **Greeting Tracking**: Saves user greeting data to MariaDB database with timestamps
- **Daily Statistics**: `/greetings` slash command shows daily greeting statistics
- **AI-Powered Internet Troll**: Automatically analyzes longer messages (>100 chars) with configurable probability and acts as a humorous contrarian troll via ChatGPT API (requires user opt-in)
- **Reaction-Based Fact Checking**: Users can react with 🔍 emoji to any message to request a detailed fact-check with numerical scoring (0-9 scale)
- **Professional Architecture**: Extensible command and message handler system
- **Comprehensive Logging**: Detailed logging for monitoring and debugging
- **Database Management**: Professional MariaDB integration with proper connection handling

## Requirements

- Python 3.12+
- MariaDB database server
- Discord bot token

or just go with

```bash
SERGEANT_ROLE_ID=??? COMMANDER_ROLE_ID=??? GENERAL_ROLE_ID=??? ANNOUNCEMENT_CHANNEL_ID=??? DISCORD_TOKEN=??? docker compose up --build
```

## Installation on k8s

For a production deployment, you can use Sealed Secrets to securely manage your secrets in Kubernetes. First, ensure you have `kubeseal` installed and the Sealed Secrets controller running in your cluster:

```bash
kubectl create secret generic discord-bot-secrets \
  --from-literal=DISCORD_TOKEN="XXX" \
  --from-literal=DB_PASSWORD="XXX" \
  --namespace=default \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secrets/discord-bot-sealedsecret.yaml
```

for a test deployment, you can create a Kubernetes secret directly:

```bash
kubectl create secret generic discord-bot-vibe-secrets \
          --from-literal=DB_PASSWORD="XXX" \
          --from-literal=DISCORD_TOKEN="XXX" \
          --namespace=default
```

On production use this ArgoCD:

```bash
helm install discord-bot ./helm

# or via ArgoCD

kubectl apply -f argocd/discord-bot-vibe-app.yaml
```

## Installation anywhere

1. Clone the repository:
```bash
git clone <repository-url>
cd discord-greeting-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your MariaDB database:
```sql
CREATE DATABASE discord_bot;
```

4. Configure environment variables:
```bash
cp .env.example .env
```
Edit `.env` and add your configuration:
```
DISCORD_TOKEN=your_discord_bot_token_here
DB_HOST=localhost
DB_PORT=3306
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_NAME=discord_bot

GAME_START_TIME=13:37:00.000
SERGEANT_ROLE_ID=
COMMANDER_ROLE_ID=
GENERAL_ROLE_ID=
ANNOUNCEMENT_CHANNEL_ID=

# Klugscheißer Configuration (optional)
OPENAI_API_KEY=your_openai_api_key_here
KLUGSCHEISSER_ENABLED=true
KLUGSCHEISSER_PROBABILITY=10
KLUGSCHEISSER_MIN_LENGTH=100
KLUGSCHEISSER_MAX_TOKENS=200
KLUGSCHEISSER_MODEL=gpt-3.5-turbo
KLUGSCHEISSER_COOLDOWN_SECONDS=60
KLUGSCHEISSER_REQUIRE_OPTIN=true

# Reaction-based Fact Checking
FACTCHECK_REACTION_EMOJI=🔍
FACTCHECK_DAILY_LIMIT_PER_USER=5
```

### Klugscheißer Feature Configuration

The bot includes an optional AI-powered "klugscheißer" feature that acts as an internet troll:
- Analyzes messages longer than a configurable threshold (default: 100 characters)
- Uses a configurable probability (default: 10%) to trigger responses
- Implements a 4-step troll system: opt-in check → probability check → AI troll-relevance check → troll response
- Always takes the opposite position with humorous contradictions and fake facts
- Uses internet troll phrases and pedantic corrections
- **Requires explicit user opt-in for privacy compliance**

**Configuration Options:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for klugscheißer feature)
- `KLUGSCHEISSER_ENABLED`: Enable/disable the feature (true/false)
- `KLUGSCHEISSER_PROBABILITY`: Percentage chance to trigger response (1-100)
- `KLUGSCHEISSER_MIN_LENGTH`: Minimum message length in characters
- `KLUGSCHEISSER_MAX_TOKENS`: Maximum tokens for ChatGPT response
- `KLUGSCHEISSER_MODEL`: OpenAI model to use (gpt-3.5-turbo, gpt-4, etc.)
- `KLUGSCHEISSER_COOLDOWN_SECONDS`: Cooldown time per user between responses
- `KLUGSCHEISSER_REQUIRE_OPTIN`: Require user opt-in (recommended: true)

**Available Commands:**
- `/ks_join`: Join the klugscheißer troll feature
- `/ks_leave`: Leave the klugscheißer troll feature
- `/ks_status`: Check your current troll status
- `/ks_stats`: Show klugscheißer troll statistics
- `/ks_help`: Get help about the klugscheißer feature

**Privacy Features:**
- Users must explicitly opt-in before their messages are processed
- Default behavior: no data processing without consent
- Easy opt-out process available at any time
- Transparent information about data usage

### Reaction-Based Fact Checking

The bot also features a reaction-based fact-checking system that allows users to request detailed fact-checks for any message:

**How it works:**
1. React with 🔍 emoji to any message
2. Bot checks if you haven't exceeded your daily limit
3. Verifies the message author has opted in to AI processing
4. Sends message to OpenAI for structured fact-checking
5. Returns a score (0-9) and detailed explanation
6. Adds score emoji reaction to the original message

**Configuration Options:**
- `FACTCHECK_REACTION_EMOJI`: Emoji used to trigger fact-checks (default: 🔍)
- `FACTCHECK_DAILY_LIMIT_PER_USER`: Daily limit per user (default: 5)

**Score Scale:**
- **0-2**: Definitiv falsch/irreführend
- **3-4**: Größtenteils falsch mit wenigen korrekten Elementen
- **5-6**: Gemischt, sowohl korrekte als auch falsche Elemente
- **7-8**: Größtenteils korrekt mit kleineren Ungenauigkeiten
- **9**: Vollständig korrekt und faktisch

**Additional Commands:**
- `/fact_stats`: View your personal fact-check statistics
- `/fact_left`: Check how many fact-checks you have left today
- `/bullshit [days] [page]`: View the bullshit board - ranking of users with worst fact-check scores

**Features:**
- Daily usage limits to prevent spam
- Comprehensive error handling and user feedback
- Statistical tracking for monitoring usage
- Same privacy protection as klugscheißer feature

## Usage

1. Start the bot:
```bash
python main.py
```

## Database Schema

Will be created automatically.

## Extensibility

The bot is designed for easy extension:

1. **Adding Commands**: Create new command files in the `commands/` directory
2. **Adding Message Handlers**: Extend the `MessageHandler` class or create new handlers
3. **Database Operations**: Add new methods to the `DatabaseManager` class

## Testing

Run the test suite:
```bash
python -m unittest discover tests
```

## Logging

The bot logs to both console and file (`bot.log` by default). Log levels can be configured via the `LOG_LEVEL` environment variable.

## License

This project is licensed under the MIT License.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request
