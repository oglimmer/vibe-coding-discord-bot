-- post_migrate.sql — run ONCE against the target PostgreSQL database right
-- after pgloader finishes (psql -f post_migrate.sql).
--
-- pgloader copies tables, data, indexes and sequences, but two MariaDB-only
-- schema features do not survive the trip and the bot relies on them:
--
--   1. ON UPDATE CURRENT_TIMESTAMP — PostgreSQL has no such column clause, so
--      we recreate the auto-touch behavior with BEFORE UPDATE triggers. This
--      mirrors exactly what database.py builds on a fresh install.
--   2. The birthdays month/day lookup — on MariaDB it used VIRTUAL generated
--      columns + an index over them. get_birthdays_for_today now derives the
--      month/day with EXTRACT and needs a matching functional index. pgloader
--      materialized the old virtual columns as plain columns; we drop them and
--      add the functional index.
--
-- Idempotent: safe to run more than once.

BEGIN;

-- 1) updated_at / last_used / last_seen_at auto-touch triggers -------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_last_used() RETURNS trigger AS $$
BEGIN
    NEW.last_used = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_last_seen_at() RETURNS trigger AS $$
BEGIN
    NEW.last_seen_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_roles_updated_at ON game_1337_roles;
CREATE TRIGGER trg_roles_updated_at BEFORE UPDATE ON game_1337_roles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_klug_updated_at ON klugscheisser_user_preferences;
CREATE TRIGGER trg_klug_updated_at BEFORE UPDATE ON klugscheisser_user_preferences
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_feed_state_updated_at ON postillon_feed_state;
CREATE TRIGGER trg_feed_state_updated_at BEFORE UPDATE ON postillon_feed_state
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_deliveries_updated_at ON postillon_deliveries;
CREATE TRIGGER trg_deliveries_updated_at BEFORE UPDATE ON postillon_deliveries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_birthdays_updated_at ON birthdays;
CREATE TRIGGER trg_birthdays_updated_at BEFORE UPDATE ON birthdays
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_ai_cache_last_used ON ai_response_cache;
CREATE TRIGGER trg_ai_cache_last_used BEFORE UPDATE ON ai_response_cache
    FOR EACH ROW EXECUTE FUNCTION set_last_used();

DROP TRIGGER IF EXISTS trg_postillon_last_seen ON postillon_posts;
CREATE TRIGGER trg_postillon_last_seen BEFORE UPDATE ON postillon_posts
    FOR EACH ROW EXECUTE FUNCTION set_last_seen_at();

-- 2) birthdays month/day lookup -------------------------------------------
-- Dropping the columns also drops any index pgloader built over them.
ALTER TABLE birthdays DROP COLUMN IF EXISTS birthday_month;
ALTER TABLE birthdays DROP COLUMN IF EXISTS birthday_day;
CREATE INDEX IF NOT EXISTS idx_birthday_server_month_day
    ON birthdays (server_id, EXTRACT(MONTH FROM birthday), EXTRACT(DAY FROM birthday));

COMMIT;
