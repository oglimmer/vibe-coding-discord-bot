# MariaDB → PostgreSQL migration runbook

One-time cutover of the shared bot database from MariaDB to PostgreSQL. The
application code already targets PostgreSQL (psycopg 3); this runbook moves the
existing data and flips the bot over.

## What changed in the code

- Driver: `mariadb` → `psycopg[binary]` (`requirements.txt`). The binary wheel
  bundles libpq, so no system client libraries or compiler are needed
  (`Dockerfile`, `worker/Dockerfile`, CI, and `oglimmer.sh` were trimmed
  accordingly).
- `config.py`: default `DB_PORT` 3306 → 5432.
- `database.py`: PostgreSQL DDL and dialect — `SERIAL`/`BIGSERIAL`, `%s`
  placeholders, `INSERT … ON CONFLICT`, `RETURNING id` (replacing
  `cursor.lastrowid`), `EXTRACT`-based birthday lookup, `CURRENT_DATE`/
  `make_interval` date math, and `BEFORE UPDATE` triggers replacing
  `ON UPDATE CURRENT_TIMESTAMP`.
- The 1337 winner race that MariaDB serialized with an InnoDB gap lock now uses
  a transaction-scoped `pg_advisory_xact_lock` keyed on the game date (PostgreSQL
  takes no gap lock on an absent row). See `_game_lock_key` in `database.py`.

## Strategy

Full migration with [pgloader](https://pgloader.io/) (schema + data + indexes +
sequences), then `post_migrate.sql` to restore the two MariaDB-only features
pgloader cannot carry across: the `ON UPDATE CURRENT_TIMESTAMP` triggers and the
birthdays month/day functional index.

Fresh installs (compose, a brand-new cluster) do **not** need pgloader — the bot
builds a clean PostgreSQL-native schema on first start via `create_tables()`.
This runbook is only for moving an existing MariaDB dataset.

## Prerequisites

- pgloader ≥ 3.6 on a host that can reach **both** databases
  (`apt-get install pgloader`, `brew install pgloader`, or the `dimitri/pgloader`
  Docker image).
- A PostgreSQL 14+ server for the shared DB, reachable from the cluster.
- Network access from the pgloader host to MariaDB:3306 and PostgreSQL:5432.
- A maintenance window: the bot must not write during the copy (see step 2).

## Steps

### 1. Provision the target database

```sql
-- as a postgres superuser
CREATE ROLE "vibe-bot" LOGIN PASSWORD 'CHANGE_ME';
CREATE DATABASE "vibe-bot" OWNER "vibe-bot";
```

Grant is implicit via ownership. Keep the empty DB empty — do **not** start the
new bot against it yet (that would create tables and make pgloader's
`include drop` do extra work).

### 2. Freeze writes

Stop the bot so the dataset is quiescent:

```bash
kubectl scale deployment/<release>-discord-bot-vibe --replicas=0
# confirm no pods remain
kubectl get pods -l app.kubernetes.io/name=discord-bot-vibe
```

### 3. Run pgloader

Edit `vibe-bot.load` and fill in the two connection strings (hosts +
passwords). Then:

```bash
pgloader vibe-bot.load
# or, containerized:
docker run --rm -v "$PWD:/w" -w /w dimitri/pgloader pgloader vibe-bot.load
```

pgloader prints a per-table summary (rows read/loaded, errors). Investigate any
non-zero error count before proceeding.

### 4. Restore triggers and the birthdays index

```bash
psql "postgresql://vibe-bot:CHANGE_ME@POSTGRES_HOST:5432/vibe-bot" -f post_migrate.sql
```

### 5. Verify

Compare row counts per table between source and target, e.g. on each side:

```sql
-- MariaDB
SELECT 'greetings', COUNT(*) FROM greetings
UNION ALL SELECT 'game_1337_bets', COUNT(*) FROM game_1337_bets
UNION ALL SELECT 'game_1337_winners', COUNT(*) FROM game_1337_winners
UNION ALL SELECT 'factcheck_requests', COUNT(*) FROM factcheck_requests
UNION ALL SELECT 'postillon_posts', COUNT(*) FROM postillon_posts
UNION ALL SELECT 'birthdays', COUNT(*) FROM birthdays;
```

Spot-check the sequences are ahead of the data (no collision on next insert):

```sql
-- PostgreSQL: should return the next id > current max(id)
SELECT nextval(pg_get_serial_sequence('greetings', 'id'));
```

Sanity-check the migrated app behavior without the bot running:

```bash
DB_HOST=POSTGRES_HOST DB_PORT=5432 DB_USER=vibe-bot DB_PASSWORD=CHANGE_ME \
DB_NAME=vibe-bot python3 inspect_bullshitboard.py
```

### 6. Cut over

Point the bot at PostgreSQL and bring it back up:

- Update the `DB_PASSWORD` in the sealed secret to the PostgreSQL role's
  password (see `sealed-secrets/`), if it differs.
- `helm/values.yaml` already defaults `DB_HOST: postgres` and `DB_PORT: "5432"`
  — set `DB_HOST` to the actual PostgreSQL service/hostname for your cluster.

```bash
helm upgrade <release> ./helm -f <your-values>
kubectl scale deployment/<release>-discord-bot-vibe --replicas=1
kubectl logs -f deployment/<release>-discord-bot-vibe
```

On boot the bot runs `create_tables()`, which is idempotent
(`CREATE TABLE/INDEX IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`) and no-ops
against the migrated schema. Watch for `Database tables created successfully`
and confirm `/about`, a `/1337` bet, and a factcheck all work.

### 7. Rollback

If something is wrong during the window, scale the bot back to 0, revert
`DB_HOST`/secret to MariaDB, and scale back up — the source MariaDB is untouched
by the migration. Keep MariaDB read-only but available until the PostgreSQL
deployment has run cleanly for a day or two, then decommission it.

## Notes / caveats

- **Benign index drift.** pgloader names its indexes differently from the bot's
  `create_tables()`. On first boot the bot may create a few extra indexes with
  its own names over columns pgloader already indexed. These are redundant but
  harmless; drop the pgloader-named duplicates later if you want a tidy schema.
- **Enums.** MariaDB `ENUM` columns become native PostgreSQL enum types under
  pgloader; a fresh install instead uses `VARCHAR + CHECK`. Both accept the same
  string values the bot writes, so this drift is cosmetic.
- **Credentials.** `vibe-bot.load` holds DB passwords once filled in — do not
  commit the filled copy.
