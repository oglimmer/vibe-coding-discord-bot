# Discord Greeting Bot

A professional Discord bot written in Python 3.12 that responds to greetings with wave emojis and tracks greeting statistics in a MariaDB database.

## Features

- **Automatic Greeting Response**: Responds with 👋 emoji to messages containing "morning", "good morning", or "gn"
- **Greeting Tracking**: Saves user greeting data to MariaDB database with timestamps
- **Daily Statistics**: `/greetings` slash command shows daily greeting statistics
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
```

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