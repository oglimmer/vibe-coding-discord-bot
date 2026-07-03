# Vibecode worker: clones the bot repo, runs aider (DeepSeek) on a feature
# request, verifies tests + lint, pushes a branch and opens a PR.
FROM python:3.12-slim

# git: clone/push; jq+curl: GitHub API; gcc/libmariadb: build the repo's
# mariadb driver when installing its requirements at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    jq \
    ca-certificates \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Aider lives in its own venv so it never conflicts with the repo's deps.
RUN python -m venv /opt/aider && \
    /opt/aider/bin/pip install --no-cache-dir aider-chat && \
    ln -s /opt/aider/bin/aider /usr/local/bin/aider

RUN useradd --uid 1000 --create-home worker && \
    mkdir -p /work && chown worker:worker /work

COPY run_agent.sh /usr/local/bin/run_agent.sh
RUN chmod +x /usr/local/bin/run_agent.sh

USER worker
WORKDIR /work
ENV HOME=/work

ENTRYPOINT ["/usr/local/bin/run_agent.sh"]
