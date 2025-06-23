

-- Update game_1337_bets table
UPDATE game_1337_bets
SET play_time  = DATE_SUB(play_time, INTERVAL 1 DAY),
    game_date  = DATE_SUB(game_date, INTERVAL 1 DAY),
    created_at = DATE_SUB(created_at, INTERVAL 1 DAY);

-- Update game_1337_winners table
UPDATE game_1337_winners
SET game_date  = DATE_SUB(game_date, INTERVAL 1 DAY),
    win_time   = DATE_SUB(win_time, INTERVAL 1 DAY),
    play_time  = DATE_SUB(play_time, INTERVAL 1 DAY),
    created_at = DATE_SUB(created_at, INTERVAL 1 DAY);

-- Update game_1337_roles table
UPDATE game_1337_roles
SET assigned_at = DATE_SUB(assigned_at, INTERVAL 1 DAY),
    updated_at  = DATE_SUB(updated_at, INTERVAL 1 DAY);
