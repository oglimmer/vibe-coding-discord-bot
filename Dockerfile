FROM python:3.12-slim

# Build arguments for git information
ARG BUILD_TIME
ARG GIT_BRANCH
ARG GIT_REVISION

# Set working directory
WORKDIR /app

# procps: `pgrep` for the liveness probe. The psycopg[binary] wheel bundles
# libpq, so no PostgreSQL client libraries or a compiler are needed here.
RUN apt-get update && apt-get install -y \
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

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app /var/log
USER app

ENTRYPOINT ["/app/entrypoint.sh"]
