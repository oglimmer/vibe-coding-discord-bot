-- PostgreSQL initialization script for VibeBot
-- Creates all necessary tables for the bot functionality
-- Run this script to initialize your PostgreSQL database

-- Enable UUID extension (optional, but useful for future features)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create user_greetings table
CREATE TABLE IF NOT EXISTS user_greetings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    username VARCHAR(100) NOT NULL,
    guild_id VARCHAR(20),
    channel_id VARCHAR(20),
    greeting_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Create indexes for better performance
    CONSTRAINT idx_user_greetings_user_id_date UNIQUE (user_id, DATE(greeting_time))
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_greetings_user_id ON user_greetings(user_id);
CREATE INDEX IF NOT EXISTS idx_user_greetings_guild_id ON user_greetings(guild_id);
CREATE INDEX IF NOT EXISTS idx_user_greetings_greeting_time ON user_greetings(greeting_time);
CREATE INDEX IF NOT EXISTS idx_user_greetings_date ON user_greetings(DATE(greeting_time));

-- Create a view for today's greetings
CREATE OR REPLACE VIEW todays_greetings AS
SELECT 
    user_id,
    username,
    guild_id,
    channel_id,
    greeting_time
FROM user_greetings 
WHERE DATE(greeting_time) = CURRENT_DATE
ORDER BY greeting_time;

-- Create a function to get greeting statistics
CREATE OR REPLACE FUNCTION get_greeting_stats(days_back INTEGER DEFAULT 7)
RETURNS TABLE(
    total_greetings BIGINT,
    unique_users BIGINT,
    avg_per_day NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_greetings,
        COUNT(DISTINCT user_id)::BIGINT as unique_users,
        (COUNT(*)::NUMERIC / days_back) as avg_per_day
    FROM user_greetings 
    WHERE greeting_time >= CURRENT_DATE - INTERVAL '%s days' % days_back;
END;
$$ LANGUAGE plpgsql;

-- Create a function to clean old greetings (optional maintenance)
CREATE OR REPLACE FUNCTION cleanup_old_greetings(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_greetings 
    WHERE greeting_time < CURRENT_DATE - INTERVAL '%s days' % days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Grant permissions (adjust as needed for your user)
-- GRANT ALL PRIVILEGES ON TABLE user_greetings TO your_bot_user;
-- GRANT USAGE, SELECT ON SEQUENCE user_greetings_id_seq TO your_bot_user;

-- ================================================================
-- 1337 GAME TABLES
-- ================================================================

-- Create 1337 game bets table
CREATE TABLE IF NOT EXISTS game_1337_bets (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL,
    username VARCHAR(100) NOT NULL,
    play_time INTEGER NOT NULL,           -- Milliseconds after game start
    play_type VARCHAR(10) NOT NULL CHECK (play_type IN ('normal', 'early')),
    date VARCHAR(10) NOT NULL,            -- YYYY-MM-DD format
    guild_id VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for 1337 game table
CREATE INDEX IF NOT EXISTS idx_game_1337_user_date ON game_1337_bets(user_id, date);
CREATE INDEX IF NOT EXISTS idx_game_1337_date ON game_1337_bets(date);
CREATE INDEX IF NOT EXISTS idx_game_1337_guild ON game_1337_bets(guild_id);
CREATE INDEX IF NOT EXISTS idx_game_1337_play_time ON game_1337_bets(play_time);

-- Create a view for today's 1337 game bets
CREATE OR REPLACE VIEW todays_1337_bets AS
SELECT 
    user_id,
    username,
    play_time,
    play_type,
    guild_id,
    created_at
FROM game_1337_bets 
WHERE date = TO_CHAR(CURRENT_DATE, 'YYYY-MM-DD')
ORDER BY play_time;

-- Create function to get 1337 game statistics
CREATE OR REPLACE FUNCTION get_1337_game_stats(days_back INTEGER DEFAULT 7)
RETURNS TABLE(
    total_bets BIGINT,
    unique_players BIGINT,
    avg_bets_per_day NUMERIC,
    best_time INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::BIGINT as total_bets,
        COUNT(DISTINCT user_id)::BIGINT as unique_players,
        (COUNT(*)::NUMERIC / days_back) as avg_bets_per_day,
        MIN(play_time)::INTEGER as best_time
    FROM game_1337_bets 
    WHERE created_at >= CURRENT_DATE - INTERVAL '%s days' % days_back;
END;
$$ LANGUAGE plpgsql;

-- Create function to clean old 1337 game data (optional maintenance)
CREATE OR REPLACE FUNCTION cleanup_old_1337_bets(days_to_keep INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM game_1337_bets 
    WHERE created_at < CURRENT_DATE - INTERVAL '%s days' % days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- 1337 GAME PLAYER STATISTICS TABLE
-- ================================================================

-- Create player statistics table for ranking system
CREATE TABLE IF NOT EXISTS game_1337_player_stats (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(20) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL,
    guild_id VARCHAR(20),
    total_wins INTEGER DEFAULT 0,
    total_games INTEGER DEFAULT 0,
    total_early_bird_bets INTEGER DEFAULT 0,
    best_time_ms INTEGER,
    worst_time_ms INTEGER,
    avg_time_ms NUMERIC(10,2),
    current_streak INTEGER DEFAULT 0,
    max_streak INTEGER DEFAULT 0,
    last_game_date VARCHAR(10),           -- YYYY-MM-DD format
    last_win_date VARCHAR(10),            -- YYYY-MM-DD format
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for player stats
CREATE INDEX IF NOT EXISTS idx_game_1337_stats_user ON game_1337_player_stats(user_id);
CREATE INDEX IF NOT EXISTS idx_game_1337_stats_guild ON game_1337_player_stats(guild_id);
CREATE INDEX IF NOT EXISTS idx_game_1337_stats_wins ON game_1337_player_stats(total_wins);
CREATE INDEX IF NOT EXISTS idx_game_1337_stats_streak ON game_1337_player_stats(current_streak);

-- Function to update player statistics after a game
CREATE OR REPLACE FUNCTION update_1337_player_stats(
    p_user_id VARCHAR(20),
    p_username VARCHAR(100),
    p_guild_id VARCHAR(20),
    p_is_winner BOOLEAN,
    p_play_time_ms INTEGER,
    p_is_early_bird BOOLEAN,
    p_game_date VARCHAR(10)
)
RETURNS VOID AS $$
BEGIN
    -- Insert or update player stats
    INSERT INTO game_1337_player_stats (
        user_id, username, guild_id, total_wins, total_games, 
        total_early_bird_bets, best_time_ms, worst_time_ms, 
        current_streak, max_streak, last_game_date, last_win_date
    )
    VALUES (
        p_user_id, p_username, p_guild_id,
        CASE WHEN p_is_winner THEN 1 ELSE 0 END,
        1,
        CASE WHEN p_is_early_bird THEN 1 ELSE 0 END,
        p_play_time_ms,
        p_play_time_ms,
        CASE WHEN p_is_winner THEN 1 ELSE 0 END,
        CASE WHEN p_is_winner THEN 1 ELSE 0 END,
        p_game_date,
        CASE WHEN p_is_winner THEN p_game_date ELSE NULL END
    )
    ON CONFLICT (user_id) DO UPDATE SET
        username = p_username,
        guild_id = p_guild_id,
        total_wins = game_1337_player_stats.total_wins + CASE WHEN p_is_winner THEN 1 ELSE 0 END,
        total_games = game_1337_player_stats.total_games + 1,
        total_early_bird_bets = game_1337_player_stats.total_early_bird_bets + CASE WHEN p_is_early_bird THEN 1 ELSE 0 END,
        best_time_ms = CASE 
            WHEN game_1337_player_stats.best_time_ms IS NULL OR p_play_time_ms < game_1337_player_stats.best_time_ms 
            THEN p_play_time_ms 
            ELSE game_1337_player_stats.best_time_ms 
        END,
        worst_time_ms = CASE 
            WHEN game_1337_player_stats.worst_time_ms IS NULL OR p_play_time_ms > game_1337_player_stats.worst_time_ms 
            THEN p_play_time_ms 
            ELSE game_1337_player_stats.worst_time_ms 
        END,
        current_streak = CASE 
            WHEN p_is_winner THEN game_1337_player_stats.current_streak + 1 
            ELSE 0 
        END,
        max_streak = CASE 
            WHEN p_is_winner AND (game_1337_player_stats.current_streak + 1) > game_1337_player_stats.max_streak 
            THEN game_1337_player_stats.current_streak + 1 
            ELSE game_1337_player_stats.max_streak 
        END,
        last_game_date = p_game_date,
        last_win_date = CASE WHEN p_is_winner THEN p_game_date ELSE game_1337_player_stats.last_win_date END,
        updated_at = CURRENT_TIMESTAMP,
        -- Update average time
        avg_time_ms = (
            (COALESCE(game_1337_player_stats.avg_time_ms, 0) * game_1337_player_stats.total_games + p_play_time_ms) 
            / (game_1337_player_stats.total_games + 1)
        );
END;
$$ LANGUAGE plpgsql;

-- Create a view for 1337 game leaderboard
CREATE OR REPLACE VIEW game_1337_leaderboard AS
SELECT 
    user_id,
    username,
    guild_id,
    total_wins,
    total_games,
    ROUND((total_wins::NUMERIC / NULLIF(total_games, 0) * 100), 2) as win_percentage,
    total_early_bird_bets,
    best_time_ms,
    current_streak,
    max_streak,
    last_win_date,
    CASE 
        WHEN total_wins >= 10 THEN 'Leet General'
        WHEN total_wins >= 5 THEN 'Leet Commander'
        WHEN total_wins >= 1 THEN 'Leet Sergeant'
        ELSE 'Recruit'
    END as rank_title
FROM game_1337_player_stats 
ORDER BY total_wins DESC, win_percentage DESC, best_time_ms ASC;

-- Grant permissions for 1337 game tables (adjust as needed for your user)
-- GRANT ALL PRIVILEGES ON TABLE game_1337_bets TO your_bot_user;
-- GRANT USAGE, SELECT ON SEQUENCE game_1337_bets_id_seq TO your_bot_user;
-- GRANT ALL PRIVILEGES ON TABLE game_1337_player_stats TO your_bot_user;
-- GRANT USAGE, SELECT ON SEQUENCE game_1337_player_stats_id_seq TO your_bot_user;
