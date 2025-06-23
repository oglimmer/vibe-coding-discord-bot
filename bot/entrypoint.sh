#!/bin/sh
set -e

# Start the bot, merging stdout+stderr into /var/log/app.log
exec python main.py 2>&1 | tee /var/log/app.log
