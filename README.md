# Discord Greeting Bot

A professional Discord bot written in Python 3.12 that responds to greetings with wave emojis and tracks greeting statistics in a MariaDB database.

## Features

- **Automatic Greeting Response**: Responds with 👋 emoji to messages containing "morning", "good morning", or "gn"
- **Greeting Tracking**: Saves user greeting data to MariaDB database with timestamps
- **Daily Statistics**: `/greetings` slash command shows daily greeting statistics
- **AI-Powered Internet Troll**: Automatically analyzes longer messages (>100 chars) with configurable probability and acts as a humorous contrarian troll via ChatGPT API (requires user opt-in)
- **Reaction-Based Fact Checking**: Users can react with 🔍 emoji to any message to request a detailed fact-check with numerical scoring (0-9 scale)
- **TL;DR Summaries**: `/tldr` summarizes the recent messages of a channel via DeepSeek (optionally scoped to the last N messages or the last hour / 24 hours); users can exclude their own messages with `/tldr_optout` (and re-enable with `/tldr_optin`)
- **Vibecode (self-extending bot)**: `/vibecode` spawns a Kubernetes Job in which an agentic coding AI (Claude Code + DeepSeek) implements the requested feature in this repository, verifies it with the test suite and ruff, opens a pull request, and works through the AI reviewer's findings until it is approved
- **Postillon RSS archive**: Polls for new Postillon articles every 15 minutes, stores them in MariaDB, and publishes new entries as Discord embeds
- **Birthday greetings**: `/birthday-set` stores a birthday, and the bot congratulates the user at 08:00 (Europe/Berlin) with a randomly varied message
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
  --from-literal=OPENAI_API_KEY="XXX" \
  --from-literal=DEEPSEEK_API_KEY="XXX" \
  --from-literal=VIBECODE_GITHUB_TOKEN="XXX" \
  --namespace=default \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-secrets/discord-bot-sealedsecret.yaml
```

`DEEPSEEK_API_KEY` and `VIBECODE_GITHUB_TOKEN` are only needed for the `/vibecode` feature (set `vibecode.enabled: false` in `helm/values.yaml` to skip them). The GitHub token should be a fine-grained PAT limited to this repository with `contents: write` and `pull requests: write`.

for a test deployment, you can create a Kubernetes secret directly:

```bash
kubectl create secret generic discord-bot-vibe-secrets \
          --from-literal=DB_PASSWORD="XXX" \
          --from-literal=DISCORD_TOKEN="XXX" \
          --from-literal=OPENAI_API_KEY="XXX" \
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

# Klugscheißer Configuration (optional)
OPENAI_API_KEY=your_openai_api_key_here
KLUGSCHEISSER_ENABLED=true
KLUGSCHEISSER_PROBABILITY=10
KLUGSCHEISSER_MIN_LENGTH=100
KLUGSCHEISSER_MAX_TOKENS=200
KLUGSCHEISSER_MODEL=gpt-3.5-turbo
KLUGSCHEISSER_COOLDOWN_SECONDS=60
KLUGSCHEISSER_REQUIRE_OPTIN=true

# Reaction-based Fact Checking
FACTCHECK_REACTION_EMOJI=🔍
FACTCHECK_DAILY_LIMIT_PER_USER=5
```

### Klugscheißer Feature Configuration

The bot includes an optional AI-powered "klugscheißer" feature that acts as an internet troll:
- Analyzes messages longer than a configurable threshold (default: 100 characters)
- Uses a configurable probability (default: 10%) to trigger responses
- Implements a 4-step troll system: opt-in check → probability check → AI troll-relevance check → troll response
- Always takes the opposite position with humorous contradictions and fake facts
- Uses internet troll phrases and pedantic corrections
- **Requires explicit user opt-in for privacy compliance**

**Configuration Options:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for klugscheißer feature)
- `KLUGSCHEISSER_ENABLED`: Enable/disable the feature (true/false)
- `KLUGSCHEISSER_PROBABILITY`: Percentage chance to trigger response (1-100)
- `KLUGSCHEISSER_MIN_LENGTH`: Minimum message length in characters
- `KLUGSCHEISSER_MAX_TOKENS`: Maximum tokens for ChatGPT response
- `KLUGSCHEISSER_MODEL`: OpenAI model to use (gpt-3.5-turbo, gpt-4, etc.)
- `KLUGSCHEISSER_COOLDOWN_SECONDS`: Cooldown time per user between responses
- `KLUGSCHEISSER_REQUIRE_OPTIN`: Require user opt-in (recommended: true)

**Available Commands:**
- `/ks_join`: Join the klugscheißer troll feature
- `/ks_leave`: Leave the klugscheißer troll feature
- `/ks_status`: Check your current troll status
- `/ks_stats`: Show klugscheißer troll statistics
- `/ks_help`: Get help about the klugscheißer feature

**Privacy Features:**
- Users must explicitly opt-in before their messages are processed
- Default behavior: no data processing without consent
- Easy opt-out process available at any time
- Transparent information about data usage

### Reaction-Based Fact Checking

The bot also features a reaction-based fact-checking system that allows users to request detailed fact-checks for any message:

**How it works:**
1. React with 🔍 emoji to any message
2. Bot checks if you haven't exceeded your daily limit
3. Verifies the message author has opted in to AI processing
4. Sends message to OpenAI for structured fact-checking
5. Returns a score (0-9) and detailed explanation
6. Adds score emoji reaction to the original message

**Configuration Options:**
- `FACTCHECK_REACTION_EMOJI`: Emoji used to trigger fact-checks (default: 🔍)
- `FACTCHECK_DAILY_LIMIT_PER_USER`: Daily limit per user (default: 5)

**Score Scale:**
- **0-2**: Definitiv falsch/irreführend
- **3-4**: Größtenteils falsch mit wenigen korrekten Elementen
- **5-6**: Gemischt, sowohl korrekte als auch falsche Elemente
- **7-8**: Größtenteils korrekt mit kleineren Ungenauigkeiten
- **9**: Vollständig korrekt und faktisch

**Additional Commands:**
- `/fact_stats`: View your personal fact-check statistics
- `/fact_left`: Check how many fact-checks you have left today
- `/bullshit [days] [page]`: View the bullshit board - ranking of users with worst fact-check scores

**Features:**
- Daily usage limits to prevent spam
- Comprehensive error handling and user feedback
- Statistical tracking for monitoring usage
- Same privacy protection as klugscheißer feature

### TL;DR Configuration

Enable the `/tldr` summary command (uses DeepSeek):

```bash
# TL;DR Configuration (optional)
TLDR_ENABLED=true
DEEPSEEK_API_KEY=your_deepseek_api_key_here   # shared with /vibecode
TLDR_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

**Available Commands:**
- `/tldr [anzahl] [zeit]`: Summarize recent channel messages (default: last 50; `zeit` optionally restricts to the last hour or 24 hours)
- `/tldr_optout`: Exclude your own messages from summaries (they are never sent to the AI)
- `/tldr_optin`: Re-include your messages

**Privacy:** Messages are sent to DeepSeek to generate the summary. Bot messages and messages from opted-out users are filtered out before anything leaves Discord.

## Usage

1. Start the bot:
```bash
python main.py
```

### Start with Docker Compose

1. Copy the environment template and configure at least the Discord token:

```bash
cp .env.example .env
```

2. To enable the Postillon feed, set these values in `.env`:

```dotenv
POSTILLON_ENABLED=true
POSTILLON_CHANNEL_ID=123456789012345678
POSTILLON_POLL_INTERVAL_MINUTES=15
POSTILLON_TIMEZONE=Europe/Berlin
POSTILLON_ANNOUNCE_FIRST_SYNC=false
```

`POSTILLON_CHANNEL_ID` is the numeric ID of the Discord channel. Enable
Developer Mode in Discord, right-click the channel, and select **Copy Channel
ID**. The bot needs the `View Channel`, `Send Messages`, and `Embed Links`
permissions in that channel.

3. Build and start MariaDB and the bot:

```bash
docker compose up --build
```

The database tables are created automatically. On the first successful sync,
the current feed entries are stored but not posted when
`POSTILLON_ANNOUNCE_FIRST_SYNC=false`. Use `/postillon_sync` as a server
administrator to trigger the first sync immediately.

4. Run in the background or inspect logs:

```bash
docker compose up --build -d
docker compose logs -f bot
```

Stop the deployment with:

```bash
docker compose down
```

### Start directly with Python

Python 3.12, MariaDB development libraries, and a running MariaDB server are
required. Configure `.env`, then run:

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Available Postillon commands after Discord has synchronized the command tree:

- `/postillon amount:10`: browse recent stored articles
- `/postillon_status`: show import and delivery status
- `/postillon_sync`: manually import now; requires `Manage Server`

### Birthday Greetings

```env
# Channel for the greetings; falls back to ANNOUNCEMENT_CHANNEL_ID when unset
BIRTHDAY_CHANNEL_ID=
```

The bot posts a greeting at 08:00 Europe/Berlin, picking one of several
messages so the same person is not congratulated identically every year. If
neither `BIRTHDAY_CHANNEL_ID` nor `ANNOUNCEMENT_CHANNEL_ID` is set, greetings
are skipped and a warning is logged at startup.

Available birthday commands:

- `/birthday-set datum:15-07-1990`: store your birthday, format `dd-mm-yyyy`
- `/birthday-remove`: delete your stored birthday

Birthdays are stored per server, so a user in several servers is greeted in
each one and can remove the entry per server. Both commands only work inside a
server, not in DMs.

## Database Schema

Will be created automatically.

## Extensibility

The bot is designed for easy extension:

1. **Adding Commands**: Create new command files in the `commands/` directory
2. **Adding Message Handlers**: Extend the `MessageHandler` class or create new handlers
3. **Database Operations**: Add new methods to the `DatabaseManager` class

## Vibecode: the bot builds its own features

`/vibecode <feature description>` lets anyone on the server extend the bot:

1. The bot creates a **Kubernetes Job** in its own namespace (RBAC for this ships with the Helm chart; the worker image is built by `.github/workflows/worker-build-push.yml` from `worker/`).
2. The worker clones this repository, creates a `vibecode/...` branch, and runs **Claude Code** against a **DeepSeek** backend on the request. The bot wraps the raw request in an enhanced prompt that pins the repo conventions (cog structure, config, DB access, embeds) and quality gates.
3. A **self-review** gate then has a judge model read the resulting diff and answer one question: does this actually implement what was asked, with a test that exercises it? A "no" goes back to the agent as a corrective round. This catches the worst failure mode — plausible-looking work on the wrong thing — before a PR is ever opened.
4. A **verification** gate runs the repo's real checks locally: the pre-commit hooks plus `ruff check` / `ruff format --check` and the test suite. Failures go back to the agent for up to two fix rounds. If it still can't go green, no PR is opened — the branch is pushed for a human to finish.
5. Only then does it push and open a **pull request**. The [AI review action](.github/workflows/ai-review.yml) reviews it, and the worker feeds every finding (plus any failing CI check, with job logs) back to the agent and pushes fixes, until the reviewer approves or the round budget runs out.
6. The result is posted back to the Discord channel. **Auto-merge is off**: `/vibecode` is open to everyone and `main` auto-deploys, so an approved PR waits for a human to press merge. (`VIBECODE_AUTO_MERGE=true` on the worker would change that.)
7. The Job cleans itself up (`ttlSecondsAfterFinished`), is capped by `VIBECODE_JOB_TIMEOUT_SECONDS`, and abuse is limited via a per-user cooldown (`VIBECODE_COOLDOWN_SECONDS`) and a global concurrency cap (`VIBECODE_MAX_CONCURRENT_JOBS`).

Local development: the service falls back to your local kubeconfig when it is not running in-cluster; the target namespace then needs the secret from `VIBECODE_SECRET_NAME` containing `DEEPSEEK_API_KEY` and `VIBECODE_GITHUB_TOKEN`.

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
