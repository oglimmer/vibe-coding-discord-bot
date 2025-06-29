# Game 1337 Role Assignment and Distribution Logic

## Overview

Game 1337 implements a hierarchical role system with three tiers: Sergeant, Commander, and General. Roles are assigned based on game performance metrics and follow specific eligibility rules to prevent role stacking.

## Role Assignment Rules

### 1. General Role
- **Assignment**: Choose the player who has won more games in the past 365 days than any other player
- **Eligibility**: Must NOT already be the General
- **Duration**: Updated daily based on 365-day rolling statistics
- **Priority**: Highest tier role

### 2. Commander Role
- **Assignment**: Choose the player who has won the most games in the past 14 days
- **Eligibility**: Must NOT be the General or already the Commander
- **Special Case**: If the General also has the most wins in the past 14 days, then pick the second-most winning player in the last 14 days as Commander (as long as they have more wins than everyone else besides the General and are not already the Commander)
- **Duration**: Updated daily based on 14-day rolling statistics
- **Priority**: Mid-tier role

### 3. Sergeant Role
- **Assignment**: Pick the player who won a game today
- **Eligibility**: Must NOT be the General or the Commander
- **Duration**: Until the next daily winner is determined
- **Priority**: Lowest tier role

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
    
    # 1. General: Top 365-day player who is not already General
    if top_365_players:
        current_general_id = current_roles.get('general', {}).get('user_id')
        for player in top_365_players:
            if player['user_id'] != current_general_id:
                assignments['general'] = player['user_id']
                break
    
    # 2. Commander: Top 14-day player who is not General or already Commander
    if top_14_players:
        general_id = assignments.get('general') or current_roles.get('general', {}).get('user_id')
        current_commander_id = current_roles.get('commander', {}).get('user_id')
        
        # Find the best candidate for Commander
        commander_candidate = None
        for player in top_14_players:
            if player['user_id'] != general_id and player['user_id'] != current_commander_id:
                commander_candidate = player
                break
        
        # Special case: If General also has most 14-day wins, pick second place
        if (top_14_players and general_id and 
            top_14_players[0]['user_id'] == general_id and 
            len(top_14_players) > 1):
            # Pick second place as Commander if they're not already Commander
            second_place = top_14_players[1]
            if second_place['user_id'] != current_commander_id:
                commander_candidate = second_place
        
        if commander_candidate:
            assignments['commander'] = commander_candidate['user_id']
    
    # 3. Sergeant: Today's winner who is not General or Commander
    general_id = assignments.get('general') or current_roles.get('general', {}).get('user_id')
    commander_id = assignments.get('commander') or current_roles.get('commander', {}).get('user_id')
    
    if (winner_today['user_id'] != general_id and 
        winner_today['user_id'] != commander_id):
        assignments['sergeant'] = winner_today['user_id']
    
    return assignments
```

## Assignment Rules

1. **No Role Stacking**: Players can only hold one role at a time
2. **Eligibility Checks**: Each role has specific eligibility requirements
3. **Current Role Protection**: Players cannot be assigned the same role they already hold
4. **Hierarchical Priority**: Higher roles take precedence in eligibility checks
5. **Statistical Merit**: Performance over different time periods determines role eligibility

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