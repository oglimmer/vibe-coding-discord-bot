# Vibecode worker: clones this repo, runs Claude Code (pointed at a DeepSeek
# backend) on a feature request, self-reviews, verifies build/lint/test locally,
# opens a PR, drives the ai-review GitHub Action's review->fix loop, and reports
# back to the bot.
#
# Adapted from the coding-agent platform's worker-claude image. That one is
# polyglot (Go + JDK + Node) because it targets arbitrary repos; this worker only
# ever builds THIS Python repo, so only Python (base image) and Node (the Claude
# Code CLI runtime) are installed.
FROM python:3.12-slim

ARG CLAUDE_CODE_VERSION=latest

# git: clone/push; curl+jq: GitHub REST API and log-marker JSON.
# nodejs (NodeSource LTS): the Claude Code CLI runtime.
# gcc/libmariadb/pkg-config: build this repo's mariadb driver when installing
# its requirements at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    ca-certificates \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (the coding engine). Installed globally; pointed at DeepSeek at
# runtime purely via ANTHROPIC_BASE_URL / ANTHROPIC_AUTH_TOKEN (see run_agent.sh).
RUN npm install -g "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm cache clean --force

# pre-commit in its own venv so the pre-PR verify gate can run this repo's
# .pre-commit-config.yaml hooks locally, without colliding with the repo's deps.
RUN python -m venv /opt/precommit && \
    /opt/precommit/bin/pip install --no-cache-dir pre-commit && \
    ln -s /opt/precommit/bin/pre-commit /usr/local/bin/pre-commit

RUN useradd --uid 1000 --create-home worker && \
    mkdir -p /work && chown worker:worker /work

COPY run_agent.sh /usr/local/bin/run_agent.sh
RUN chmod +x /usr/local/bin/run_agent.sh

USER worker
WORKDIR /work
# HOME=/work keeps npm's cache, pre-commit's hook envs and Claude Code's config
# on the writable volume.
ENV HOME=/work

# Build provenance, baked in last so it never busts the toolchain layer cache.
ARG GIT_COMMIT=none
ARG VERSION=dev
ARG BUILD_TIME=unknown
ENV WORKER_GIT_COMMIT=$GIT_COMMIT \
    WORKER_VERSION=$VERSION \
    WORKER_BUILD_TIME=$BUILD_TIME

ENTRYPOINT ["/usr/local/bin/run_agent.sh"]
