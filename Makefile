# VibeBot Docker Makefile

.PHONY: help build up down restart logs clean backup

# Default target
help:
	@echo "🤖 VibeBot Docker Commands:"
	@echo ""
	@echo "  make up         - Start all services"
	@echo "  make up-admin   - Start with pgAdmin"
	@echo "  make down       - Stop all services"
	@echo "  make restart    - Restart bot service"
	@echo "  make build      - Build bot image"
	@echo "  make logs       - Show all logs"
	@echo "  make logs-bot   - Show bot logs only"
	@echo "  make logs-db    - Show database logs only"
	@echo "  make clean      - Remove containers and images"
	@echo "  make backup     - Backup database"
	@echo "  make status     - Show service status"
	@echo ""

# Build the bot image
build:
	@echo "🏗️ Building VibeBot image..."
	docker compose build vibebot

# Start services
up:
	@echo "🚀 Starting VibeBot..."
	docker compose up -d

# Start with admin tools
up-admin:
	@echo "🚀 Starting VibeBot with pgAdmin..."
	docker compose --profile admin up -d

# Stop services
down:
	@echo "🛑 Stopping VibeBot..."
	docker compose down

# Restart bot
restart:
	@echo "🔄 Restarting bot..."
	docker compose restart vibebot

# Show logs
logs:
	docker compose logs -f

logs-bot:
	docker compose logs -f vibebot

logs-db:
	docker compose logs -f postgres

# Service status
status:
	docker compose ps

# Clean up
clean:
	@echo "🧹 Cleaning up containers and images..."
	docker compose down -v
	docker compose rm -f
	docker image rm discord-bot_vibebot 2>/dev/null || true

# Backup database
backup:
	@echo "💾 Creating database backup..."
	@mkdir -p backups
	docker compose exec postgres pg_dump -U admin meine_datenbank > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/ directory"

# Development: rebuild and restart
dev:
	@echo "🔧 Development restart..."
	docker compose build vibebot
	docker compose up -d vibebot
