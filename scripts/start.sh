#!/bin/bash

# Docker startup script for VibeBot
set -e

echo "🚀 Starting VibeBot Discord Bot..."

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL database..."
while ! nc -z $DB_HOST $DB_PORT; do
  echo "Database not ready yet, waiting..."
  sleep 2
done

echo "✅ Database is ready!"

# Optional: Run database migrations here if needed
# python src/database/migrate.py

# Start the bot
echo "🤖 Starting Discord Bot..."
exec python src/main.py
