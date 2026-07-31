# Game 1337 Role Assignment and Distribution Logic

## Overview

Game 1337 implements a hierarchical role system with three tiers: Sergeant, Commander, and General. Roles are assigned based on game performance metrics and follow specific eligibility rules to prevent role stacking.

## Role Assignment Rules

### 1. General Role
- **Assignment**: Choose the player who has won the most games in the past 365 days
- **Eligibility**: Every player with at least one win in the window
- **Duration**: Updated daily based on 365-day rolling statistics
- **Priority**: Highest tier role

### 2. Commander Role
- **Assignment**: Choose the player who has won the most games in the past 14 days
- **Eligibility**: Must NOT be the General. The General is removed from the
  ranking before the winner is picked, so if the General also leads the 14-day
  stats the role simply goes to the best remaining player — and a player who is
  merely *level* with the General still gets it.
- **Duration**: Updated daily based on 14-day rolling statistics
- **Priority**: Mid-tier role

### 3. Sergeant Role
- **Assignment**: Pick the player who won a game today
- **Eligibility**: Must NOT be the General or the Commander
- **Duration**: Until the next daily winner is determined
- **Priority**: Lowest tier role

### Tie-Breaking

General and Commander are decided on win counts, which frequently tie. A tie
never leaves the role vacant:

1. If the **current holder** is among the tied players, they keep the role. You
   do not lose a rank because somebody drew level with you.
2. Otherwise the **most recent win** breaks the tie (`get_winner_stats()` orders
   by `wins DESC, last_win DESC`, so this is the first tied entry).

A role is only removed without a replacement when no eligible player has a win
in the window at all.

## Role Assignment Algorithm

The core assignment logic is handled by `determine_new_role_assignments()` in `game/game_1337_logic.py`:

```python
def determine_new_role_assignments(self, winner_today: Dict[str, Any],
                                  current_roles: Dict[str, Any],
                                  guild_id: int) -> Dict[str, int]:
    assignments = {}

    # Get top players for different time periods
    top_365_players = self.get_winner_stats(days=365)
    top_14_players = self.get_winner_stats(days=14)

    current_general_id = (current_roles.get('general') or {}).get('user_id')
    current_commander_id = (current_roles.get('commander') or {}).get('user_id')

    # 1. General: Player with the most wins in the past 365 days
    general = self._select_role_holder(top_365_players, current_general_id)
    if general:
        assignments['general'] = general['user_id']

    # 2. Commander: Player with the most wins in the past 14 days, General aside
    general_id = assignments.get('general') or current_general_id
    commander = self._select_role_holder(
        top_14_players,
        current_commander_id,
        excluded_user_ids={general_id} if general_id else None,
    )
    if commander:
        assignments['commander'] = commander['user_id']

    # 3. Sergeant: Today's winner who is not General or Commander
    new_general_id = assignments.get('general')
    new_commander_id = assignments.get('commander')

    if (winner_today['user_id'] != new_general_id
            and winner_today['user_id'] != new_commander_id):
        assignments['sergeant'] = winner_today['user_id']

    return assignments
```

Both ranked roles go through the same helper, `_select_role_holder()`, which
drops ineligible players, then applies the tie-breaking rules above:

```python
def _select_role_holder(self, ranked_players, current_holder_id=None,
                        excluded_user_ids=None):
    excluded_user_ids = excluded_user_ids or set()
    candidates = [p for p in ranked_players if p['user_id'] not in excluded_user_ids]
    if not candidates:
        return None

    top_wins = max(p['wins'] for p in candidates)
    tied = [p for p in candidates if p['wins'] == top_wins]

    if len(tied) > 1 and current_holder_id is not None:
        for player in tied:
            if player['user_id'] == current_holder_id:
                return player

    return tied[0]
```

## Assignment Rules

1. **No Role Stacking**: Players can only hold one role at a time
2. **Eligibility Checks**: Each role has specific eligibility requirements
3. **Incumbent Advantage**: On a tie, the current holder keeps the role
4. **Hierarchical Priority**: Higher roles take precedence in eligibility checks
5. **Statistical Merit**: Performance over different time periods determines role eligibility
6. **No Empty Ranks**: A role is only vacated when nobody is eligible for it

## Database Management

Role assignments are stored in the `game_1337_roles` table with the following schema:

```sql
CREATE TABLE IF NOT EXISTS game_1337_roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    role_type ENUM('sergeant', 'commander', 'general') NOT NULL,
    role_id BIGINT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY unique_guild_role (guild_id, role_type),
    INDEX idx_guild_user (guild_id, user_id),
    INDEX idx_user_id (user_id)
)
```

### Key Database Functions (database.py)
- `set_role_assignment(guild_id, user_id, role_type, role_id)` - Assign role to user
- `get_role_assignment(guild_id, role_type)` - Get current role holder
- `get_all_role_assignments(guild_id)` - Get all roles for a guild
- `remove_role_assignment(guild_id, role_type)` - Remove role assignment

## Discord Integration

Role updates happen automatically through the `_update_guild_roles()` method in `commands/game_1337_command.py`:

### Update Process
1. **Removal Phase**: Remove existing Discord roles from current holders
2. **Assignment Phase**: Assign new Discord roles based on game statistics
3. **Database Update**: Store new assignments in the database
4. **Error Handling**: Log and handle Discord API errors gracefully

### Configuration
Role IDs are configured through environment variables in `config.py`:
- `SERGEANT_ROLE_ID` - Discord role ID for Sergeant
- `COMMANDER_ROLE_ID` - Discord role ID for Commander
- `GENERAL_ROLE_ID` - Discord role ID for General

## Automatic Updates

Role assignments are updated automatically after each daily game through the `_update_roles()` method:

1. Determine today's winner from game results
2. Calculate 14-day top player statistics
3. Calculate 365-day top player statistics
4. Apply role assignment algorithm
5. Remove old Discord roles from previous holders
6. Assign new Discord roles to current winners
7. Update database records with new assignments

## Edge Cases

1. **Same Player Multiple Roles**: Algorithm ensures highest priority role is assigned
2. **No Winners**: Roles are maintained until new winners emerge
3. **Database Errors**: Graceful error handling with logging
4. **Discord API Failures**: Continue processing other roles if one fails
5. **Role Conflicts**: Database unique constraints prevent duplicate role assignments

## Files Involved

- `game/game_1337_logic.py` - Core role assignment logic
- `database.py` - Database role management functions
- `commands/game_1337_command.py` - Discord role application and command handling
- `config.py` - Role ID configuration and environment variables
