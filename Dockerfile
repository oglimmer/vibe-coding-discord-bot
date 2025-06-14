FROM python:3.12-slim

# Build arguments for git information
ARG BUILD_TIME
ARG GIT_BRANCH
ARG GIT_REVISION

# Set working directory
WORKDIR /app

# Install system dependencies for MariaDB connector
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create build-info.json with build arguments
RUN echo "{\"build_time\":\"${BUILD_TIME}\",\"git_branch\":\"${GIT_BRANCH}\",\"git_revision\":\"${GIT_REVISION}\"}" > build-info.json

RUN python -m unittest discover tests

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Command to run the bot
CMD ["python", "main.py"]