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

## Installation

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
```

## Usage

1. Start the bot:
```bash
python main.py
```

2. Invite the bot to your Discord server with the following permissions:
   - Send Messages
   - Use Slash Commands
   - Read Message History

## Commands

- `/greetings` - Shows all users who have greeted today with statistics

## Architecture

The bot follows a professional modular architecture:

```
├── main.py                 # Main bot entry point
├── config.py              # Configuration and logging setup
├── database.py            # Database connection and operations
├── handlers/              # Message handlers
│   └── message_handler.py # Greeting message processing
├── commands/              # Slash commands
│   └── greetings_command.py # Daily greetings statistics
└── tests/                 # Unit tests
    └── test_message_handler.py
```

### Key Components

- **DiscordBot**: Main bot class extending discord.ext.commands.Bot
- **DatabaseManager**: Handles MariaDB connections and operations
- **MessageHandler**: Processes incoming messages for greetings
- **GreetingsCommand**: Implements the /greetings slash command

## Database Schema

The bot creates a `greetings` table with the following structure:

```sql
CREATE TABLE greetings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    username VARCHAR(255) NOT NULL,
    greeting_message TEXT,
    greeting_date DATE NOT NULL,
    greeting_time TIME NOT NULL,
    server_id BIGINT,
    channel_id BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

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