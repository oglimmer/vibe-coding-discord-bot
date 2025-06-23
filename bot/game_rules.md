# 1337 Game Rules & Mechanics

## Overview
The 1337 game is a daily precision timing competition where players attempt to place bets as close as possible to a randomly generated "win time" that occurs at 13:37 (1:37 PM) each day. The player whose bet time is closest to (but not after) the win time becomes the daily winner.

## Game Schedule
- **Daily Game Time**: 13:37:00.000 (1:37 PM)
- **Win Time Window**: The actual win time is randomly generated between 13:37:00.000 and 13:38:00.000 (within 1 minute after the base time)
- **Frequency**: One game per day
- **Winner Determination**: Automatic at the exact win time with millisecond precision

## Betting Mechanics

### Bet Types

#### 1. Regular Bet (`/1337`)
- **Description**: Place a bet at the current moment
- **Command**: `/1337`
- **Timing**: Must be placed before the game time (13:37:00) plus 1 minute buffer
- **Use Case**: Real-time betting during the game window

#### 2. Early Bird Bet (`/1337-early-bird`)
- **Description**: Schedule a bet for a specific timestamp
- **Command**: `/1337-early-bird <timestamp>`
- **Timing**: Can be scheduled for any time before the win time
- **Use Case**: Strategic pre-planning or when you can't be online during game time

### Timestamp Formats
Early bird bets accept multiple timestamp formats:
- `HH:MM:SS.SSS` (e.g., `13:36:45.123`)
- `HH:MM:SS` (e.g., `13:36:45`)
- `SS.SSS` (e.g., `45.123` - uses current game hour/minute)
- `SS` (e.g., `45` - uses current game hour/minute)

### Betting Rules
1. **One Bet Per Day**: Each player can only place one bet per day
2. **No Late Bets**: Bets placed after the win time are invalid
3. **No Future Bets**: Early bird timestamps cannot be in the future
4. **Precision Matters**: All times are tracked with millisecond precision

## Winner Determination

### Selection Process
1. **Find Closest Bets**: Find the closest regular bet and closest early_bird bet to the win time
2. **Regular Bet Priority**: If the regular bet is closer to the win time, it wins
3. **Early Bird Penalty**: If the early_bird bet is closer, it only wins if it's more than 3 seconds apart from the closest regular bet
4. **Tie Breaking**: If both bets are equally close, the regular bet wins

### 3-Second Penalty for Early Bird Bets
- **Purpose**: Prevents early bird bets from having an unfair advantage
- **Rule**: Early bird bets can only win if they are more than 3 seconds apart from the closest regular bet
- **Example**: 
  - Early bird at 13:37:25, Regular at 13:37:28, Win time at 13:37:30
  - Regular is closer (2s vs 5s from win time)
  - **Result**: Regular bet wins (closer to win time)

- **Example with Penalty**: 
  - Early bird at 13:37:28, Regular at 13:37:25, Win time at 13:37:30
  - Early bird is closer (2s vs 5s from win time), but only 3s apart from regular
  - **Result**: Regular bet wins (early bird closer but within 3s of regular)

### Winner Criteria
- **Primary**: Closest time to win time (before or equal to)
- **Secondary**: 3-second penalty rule for early bird bets
- **Measurement**: Millisecond precision difference
- **Example**: If win time is 13:37:15.500, a bet at 13:37:15.123 wins over 13:37:15.600

## Role System

### Discord Roles
The game includes a hierarchical role system based on winning performance:

#### 1. Sergeant Role
- **Assignment**: Daily winner
- **Duration**: Until next daily winner is determined
- **Privileges**: Recognition as daily champion

#### 2. Commander Role
- **Assignment**: Player with most wins in the last 14 days
- **Duration**: Until next 14-day period calculation
- **Privileges**: Recognition as short-term champion

#### 3. General Role
- **Assignment**: Player with most wins in the last 365 days
- **Duration**: Until next 365-day period calculation
- **Privileges**: 
  - Recognition as long-term champion
  - Special announcements when placing bets
  - Prestige status

### Role Management
- **Automatic Updates**: Roles are automatically assigned/removed after each game
- **Single Assignment**: Only one player can hold each role at a time
- **Priority**: General > Commander > Sergeant (higher roles take precedence)

## Game Commands

### Available Commands
1. **`/1337`** - Place a regular bet
2. **`/1337-early-bird <timestamp>`** - Place a scheduled bet
3. **`/1337-info`** - View today's game information
4. **`/1337-stats`** - View game statistics and leaderboards

### Command Features
- **Ephemeral Responses**: Bet confirmations are private to the user
- **Validation**: Commands validate timing and user eligibility
- **Error Handling**: Clear error messages for invalid actions

## Statistics & Tracking

### Tracked Data
- **Daily Bets**: All bets placed each day
- **Winners**: Daily winners with timing details
- **User Performance**: Win counts and timing accuracy
- **Role History**: Role assignments and durations

### Statistics Available
- **Daily Winners**: List of recent winners
- **User Rankings**: Top performers by win count
- **Timing Accuracy**: How close winners were to the target
- **Participation**: Daily bet counts and participation rates

## Technical Details

### Precision
- **Time Resolution**: Millisecond precision throughout
- **Synchronization**: High-precision timing for winner determination
- **Database Storage**: All times stored with full precision

### Randomization
- **Win Time Generation**: Cryptographically secure random generation
- **Daily Seed**: New random time generated each day
- **Consistency**: Same win time for all players on a given day

### Reliability
- **Automatic Scheduling**: Games run automatically without manual intervention
- **Error Recovery**: System handles failures and reschedules as needed
- **Logging**: Comprehensive logging for debugging and monitoring

## Strategy Tips

### Timing Strategies
1. **Early Bird Advantage**: Schedule bets in advance for consistent timing
2. **Real-time Precision**: Use regular bets for last-minute adjustments
3. **Risk Management**: Balance early timing with avoiding catastrophic events

### Role Strategy
1. **Daily Focus**: Aim for consistent daily wins for Sergeant role
2. **Streak Building**: Build winning streaks for Commander consideration
3. **Long-term Planning**: Maintain high win rates for General status

### Community Aspects
1. **Competition**: Compete with other players for timing supremacy
2. **Recognition**: Earn Discord roles for achievements
3. **Social**: Participate in daily gaming community

## Fair Play

### Rules Enforcement
- **Automatic Validation**: System prevents rule violations
- **No Manual Override**: All determinations are automated
- **Transparency**: All game logic is deterministic and verifiable

### Anti-Cheating
- **Server Time**: All times based on server clock
- **No Client Manipulation**: Client-side timing cannot affect results
- **Audit Trail**: Complete logging of all game events

---

*The 1337 game combines precision timing, strategic planning, and community competition in a daily challenge that rewards both skill and consistency.* 