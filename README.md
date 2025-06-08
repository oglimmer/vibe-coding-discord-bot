# VibeBot - Professional Discord Greeting Bot 👋

A professional Discord bot written in Python that tracks and responds to user greetings with comprehensive database integration and modern Discord features.

## 🚀 Features

- **Smart Greeting Detection**: Responds to "morning", "good morning", "gn", "good night", "gm" with wave emoji reactions
- **Slash Commands**: Modern Discord slash command integration
- **Database Integration**: Professional PostgreSQL integration with async support
- **Greeting Tracking**: Stores user greetings with timestamps and server information
- **1337 Game**: Interactive daily/scheduled game with cron-based timing
- **Statistics**: Detailed greeting and game statistics
- **Professional Logging**: Comprehensive logging with file and console output
- **Extensible Architecture**: Clean, modular design for easy feature additions
- **Error Handling**: Robust error handling and recovery
- **Unit Tests**: Comprehensive test suite for reliability
- **Docker Support**: Complete containerized deployment with PostgreSQL

## 🏗️ Architecture

```
discord-bot/
├── src/
│   ├── main.py                    # Bot entry point with VibeBot class
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── base.py               # Base command class
│   │   ├── greetings.py          # Greeting commands cog
│   │   └── game_1337.py          # 1337 Game commands with cron scheduling
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py         # Async database manager
│   │   ├── models.py             # SQLAlchemy models
│   │   └── migrations/
│   │       ├── init.sql          # Database initialization
│   │       ├── postgresql_init.sql # PostgreSQL specific init
│   │       └── game_1337_init.sql # 1337 Game tables
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── event_handler.py      # Discord event handlers
│   │   └── message_handler.py    # Message processing
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py             # Professional logging setup
│   │   ├── time_parser.py        # Time parsing utilities
│   │   └── game_1337.py          # 1337 Game logic with cron scheduling
│   └── bot/
│       ├── __init__.py
│       ├── client.py             # Legacy bot client
│       └── config.py             # Configuration management
├── tests/
│   ├── __init__.py
│   ├── test_commands.py          # Command tests
│   ├── test_handlers.py          # Handler tests
│   ├── test_cron_scheduling.py   # Cron scheduling tests
│   └── test_time_parser.py       # Time parser tests
├── logs/                         # Log files (auto-created)
├── compose.yml                   # Docker Compose configuration
├── Dockerfile                    # Docker build instructions
├── requirements.txt              # Python dependencies
├── .env                         # Environment variables
├── .env.example                 # Environment template
├── .gitignore                   # Git ignore rules
├── README.md                    # This file
├── DOCKER.md                    # Docker deployment guide
└── GAME_1337_README.md          # 1337 Game documentation
├── .gitignore                   # Git ignore rules
└── README.md                    # This file
```

## 📋 Commands

### Greetings Commands

#### `/greetings`
Shows all users who have greeted today with detailed information:
- List of users with greeting times
- Total greeting count for today
- First and last greeting of the day
- Optional weekly statistics

**Parameters:**
- `show_stats` (optional): Show additional weekly statistics

#### `/greeting-stats`
Displays detailed greeting statistics:
- Total greetings over specified period
- Unique users who greeted
- Average greetings per day
- Customizable timeframe (1-30 days)

**Parameters:**
- `days` (optional): Number of days to analyze (default: 7, max: 30)

### 1337 Game Commands

#### `/1337`
Place a real-time bet in the 1337 game during active game periods.

#### `/1337-early-bird <time>`
Place an early-bird bet with predefined time during early-bird periods.

**Parameters:**
- `time`: Time in format [hh:mm:]ss[.SSS] (max 60.000s)
- Examples: '13.5', '01:13', '1:02:03.999'

#### `/1337-next`
Show the next scheduled 1337 games and current status.

#### `/1337-info`
Show information about your current 1337 game bet.

#### `/1337-stats`
Display 1337 game statistics and leaderboards.

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- PostgreSQL database (or Docker)
- Discord Bot Token

### Quick Start with Docker (Recommended)

1. **Clone Repository**
```bash
git clone <repository-url>
cd discord-bot
```

2. **Setup Environment**
```bash
cp .env.example .env
# Edit .env and set your BOT_TOKEN
```

3. **Start with Docker**
```bash
docker compose up -d
```

4. **View Logs**
```bash
docker compose logs -f vibebot
```

See [DOCKER.md](DOCKER.md) for detailed Docker instructions.

### Manual Installation

#### 1. Clone Repository
```bash
git clone <repository-url>
cd discord-bot
```

#### 2. Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

#### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 4. Database Setup
Create a PostgreSQL database and run the initialization script:
```sql
CREATE DATABASE discord_bot;
-- Run the script in src/database/migrations/postgresql_init.sql
```

#### 5. Environment Configuration
Copy `.env.example` to `.env` and configure:
```env
BOT_TOKEN=your_discord_bot_token
DB_HOST=localhost
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=discord_bot
DB_PORT=5432

# 1337 Game Configuration (optional)
GAME_1337_CRON=37 13 * * *
GAME_1337_EARLY_BIRD_CUTOFF_HOURS=2
GAME_1337_TIMEZONE=Europe/Berlin
```

#### 6. Discord Bot Setup
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application and bot
3. Enable "Message Content Intent" in Bot settings
4. Copy the bot token to your `.env` file
5. Invite bot to your server with appropriate permissions

#### 7. Run the Bot
```bash
python src/main.py
```

## 🔧 Configuration

### Environment Variables

#### Core Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Discord bot token | Required |
| `DB_HOST` | Database host | `localhost` |
| `DB_USER` | Database username | `admin` |
| `DB_PASSWORD` | Database password | `geheim` |
| `DB_NAME` | Database name | `discord_bot` |
| `DB_PORT` | Database port | `5432` |
| `TZ` | Timezone | `Europe/Berlin` |

#### 1337 Game Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `GAME_1337_CRON` | Cron expression for game schedule | `37 13 * * *` |
| `GAME_1337_EARLY_BIRD_CUTOFF_HOURS` | Hours before game for early-bird period | `2` |
| `GAME_1337_TIMEZONE` | Timezone for game scheduling | `Europe/Berlin` |
| `GAME_1337_WINNER_ROLE_ID` | Role ID for winners (optional) | None |
| `GAME_1337_EARLY_BIRD_ROLE_ID` | Role ID for early-bird players (optional) | None |

#### 1337 Game Three-Tier Role System
| Variable | Description | Default |
|----------|-------------|---------|
| `GAME_1337_LEET_SERGEANT_ROLE_ID` | Role ID for players with 1+ wins | None |
| `GAME_1337_LEET_COMMANDER_ROLE_ID` | Role ID for players with 5+ wins | None |
| `GAME_1337_LEET_GENERAL_ROLE_ID` | Role ID for players with 10+ wins | None |

**Note:** The three-tier role system automatically tracks player statistics and assigns hierarchical rank roles based on total wins. Higher ranks replace lower ones when players achieve new milestones.

### Discord Permissions
The bot requires the following permissions:
- Read Messages
- Send Messages
- Use Slash Commands
- Add Reactions
- View Channels
- Manage Roles (for 1337 Game role assignments)

## 🧪 Testing

Run the test suite:
```bash
# Run all tests
python -m unittest discover tests

# Run specific test file
python -m unittest tests.test_commands

# Run with verbose output
python -m unittest tests.test_commands -v
```

## 📊 Database Schema

### user_greetings Table
| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `user_id` | VARCHAR(20) | Discord user ID |
| `username` | VARCHAR(100) | User display name |
| `guild_id` | VARCHAR(20) | Server ID (nullable) |
| `channel_id` | VARCHAR(20) | Channel ID (nullable) |
| `greeting_time` | TIMESTAMP | Timestamp of greeting |

### game_1337_bets Table
| Column | Type | Description |
|--------|------|-------------|
| `id` | SERIAL | Primary key |
| `user_id` | VARCHAR(20) | Discord user ID |
| `username` | VARCHAR(100) | User display name |
| `play_time` | INTEGER | Milliseconds after game start |
| `play_type` | ENUM('normal', 'early') | Type of bet |
| `date` | VARCHAR(10) | Game date (YYYY-MM-DD) |
| `guild_id` | VARCHAR(20) | Server ID (nullable) |
| `created_at` | TIMESTAMP | Bet creation time |

## 🔍 Logging

The bot includes comprehensive logging:
- **Console Output**: Real-time status and errors
- **File Logging**: Detailed logs stored in `logs/` directory
- **Structured Logging**: Consistent format with timestamps
- **Log Levels**: Debug, Info, Warning, Error, Critical

Log files:
- `logs/main.log` - Main bot operations
- `logs/database.log` - Database operations
- `logs/greetings.log` - Greeting command activities

## 🚀 Extending the Bot

### Adding New Commands
1. Create a new cog in `src/commands/`
2. Use the base structure from `greetings.py`
3. Load the cog in `main.py`

### Adding New Database Models
1. Define models in `src/database/models.py`
2. Create migration scripts in `src/database/migrations/`
3. Update the database manager as needed

### Adding New Event Handlers
1. Create handlers in `src/handlers/`
2. Register events in the main bot class

## 🐛 Troubleshooting

### Common Issues

**Bot doesn't respond to messages:**
- Ensure "Message Content Intent" is enabled in Discord Developer Portal
- Check bot permissions in your server
- Verify the bot token is correct

**Database connection errors:**
- Verify database credentials in `.env`
- Ensure database server is running
- Check network connectivity

**Commands not appearing:**
- Restart the bot to sync slash commands
- Check bot permissions for slash commands
- Wait a few minutes for Discord to update

### Debug Mode
Enable SQL debugging by setting `echo=True` in database connection setup.

## 📈 Performance

- **Async Architecture**: Non-blocking database operations
- **Connection Pooling**: Efficient database connection management
- **Error Recovery**: Automatic reconnection and error handling
- **Memory Efficient**: Proper resource cleanup and session management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 coding standards
- Add tests for new features
- Update documentation
- Use type hints where appropriate
- Include proper error handling

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [discord.py](https://discordpy.readthedocs.io/) - Python Discord API wrapper
- [SQLAlchemy](https://sqlalchemy.org/) - SQL toolkit and ORM
- [aiomysql](https://aiomysql.readthedocs.io/) - Async MySQL driver

## 📞 Support

If you encounter issues or have questions:
1. Check the troubleshooting section
2. Review the logs for error details
3. Open an issue on GitHub
4. Join our Discord server for community support

---

Made with ❤️ for Discord communities