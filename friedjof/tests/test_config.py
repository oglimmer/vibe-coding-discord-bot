"""
Test configuration and utilities for the 1337 Game role system tests.
"""
import os
import sys
from unittest.mock import MagicMock

# Test configuration constants
TEST_USER_IDS = [
    "test_user_1", "test_user_2", "test_user_3", "test_user_4", "test_user_5"
]

TEST_GUILD_ID = "test_guild_123"

TEST_ROLE_IDS = {
    "sergeant": "123456789",
    "commander": "123456790", 
    "general": "123456791",
    "winner": "123456792",
    "early_bird": "123456793"
}

# Test data templates
TEST_PLAYER_STATS_TEMPLATES = {
    "recruit": {
        "total_wins": 0,
        "total_games": 5,
        "best_time_ms": None,
        "worst_time_ms": None,
        "avg_time_ms": None,
        "current_streak": 0,
        "max_streak": 0
    },
    "sergeant": {
        "total_wins": 3,
        "total_games": 8,
        "best_time_ms": 25000,
        "worst_time_ms": 40000,
        "avg_time_ms": 32500,
        "current_streak": 1,
        "max_streak": 2
    },
    "commander": {
        "total_wins": 7,
        "total_games": 15,
        "best_time_ms": 20000,
        "worst_time_ms": 45000,
        "avg_time_ms": 32500,
        "current_streak": 2,
        "max_streak": 4
    },
    "general": {
        "total_wins": 15,
        "total_games": 25,
        "best_time_ms": 18000,
        "worst_time_ms": 50000,
        "avg_time_ms": 34000,
        "current_streak": 5,
        "max_streak": 8
    }
}

def setup_test_environment():
    """Set up the test environment with proper mocking."""
    # Mock all external dependencies
    sys.modules['database.connection'] = MagicMock()
    sys.modules['discord'] = MagicMock()
    sys.modules['discord.ext'] = MagicMock()
    sys.modules['discord.ext.commands'] = MagicMock()
    sys.modules['sqlalchemy'] = MagicMock()
    sys.modules['sqlalchemy.orm'] = MagicMock()
    sys.modules['sqlalchemy.ext'] = MagicMock()
    sys.modules['sqlalchemy.ext.declarative'] = MagicMock()
    
    # Add src to path if not already there
    src_path = os.path.join(os.path.dirname(__file__), '..', 'src')
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def create_mock_discord_environment():
    """Create a comprehensive mock Discord environment."""
    # Mock bot
    mock_bot = MagicMock()
    
    # Mock guild
    mock_guild = MagicMock()
    mock_guild.id = int(TEST_GUILD_ID)
    
    # Mock roles
    mock_roles = {}
    for role_name, role_id in TEST_ROLE_IDS.items():
        mock_role = MagicMock()
        mock_role.id = int(role_id)
        mock_role.name = role_name.title().replace('_', ' ')
        mock_roles[role_name] = mock_role
    
    # Mock members
    mock_members = {}
    for user_id in TEST_USER_IDS:
        mock_member = MagicMock()
        mock_member.id = int(user_id.split('_')[-1])  # Extract number from user_id
        mock_member.roles = []
        mock_members[user_id] = mock_member
    
    # Setup guild behavior
    mock_guild.get_role.side_effect = lambda role_id: next(
        (role for role in mock_roles.values() if role.id == role_id), None
    )
    mock_guild.get_member.side_effect = lambda user_id: mock_members.get(f"test_user_{user_id}")
    
    # Setup bot behavior
    mock_bot.get_guild.return_value = mock_guild
    
    return {
        'bot': mock_bot,
        'guild': mock_guild,
        'roles': mock_roles,
        'members': mock_members
    }


def create_mock_database_environment():
    """Create a comprehensive mock database environment."""
    mock_db_manager = MagicMock()
    
    # Mock session context manager
    mock_session = MagicMock()
    mock_context_manager = MagicMock()
    mock_context_manager.__aenter__.return_value = mock_session
    mock_context_manager.__aexit__.return_value = None
    
    mock_db_manager.get_session.return_value = mock_context_manager
    
    return {
        'db_manager': mock_db_manager,
        'session': mock_session,
        'context_manager': mock_context_manager
    }


def generate_test_player_stats(rank_type, user_id=None, username=None, guild_id=None):
    """Generate test player stats for a specific rank type."""
    from database.models import Game1337PlayerStats
    
    if rank_type not in TEST_PLAYER_STATS_TEMPLATES:
        raise ValueError(f"Invalid rank type: {rank_type}")
    
    template = TEST_PLAYER_STATS_TEMPLATES[rank_type]
    
    return Game1337PlayerStats(
        user_id=user_id or "test_user_123",
        username=username or "TestUser",
        guild_id=guild_id or TEST_GUILD_ID,
        **template
    )


def assert_rank_progression(test_case, win_counts, expected_ranks):
    """Helper to assert rank progression for different win counts."""
    from database.models import Game1337PlayerStats
    
    for wins, expected_rank in zip(win_counts, expected_ranks):
        stats = Game1337PlayerStats(
            user_id="test_user",
            username="TestUser",
            guild_id=TEST_GUILD_ID,
            total_wins=wins,
            total_games=max(wins + 3, 1),
            best_time_ms=20000 if wins > 0 else None,
            worst_time_ms=40000 if wins > 0 else None,
            avg_time_ms=30000 if wins > 0 else None,
            current_streak=1 if wins > 0 else 0,
            max_streak=wins
        )
        
        test_case.assertEqual(
            stats.rank_title, 
            expected_rank,
            f"Expected rank {expected_rank} for {wins} wins, got {stats.rank_title}"
        )


def create_test_game_scenario(players_data):
    """Create a test game scenario with multiple players."""
    from unittest.mock import MagicMock
    
    mock_bets = []
    for player in players_data:
        mock_bet = MagicMock()
        mock_bet.user_id = player.get('user_id', 'test_user')
        mock_bet.username = player.get('username', 'TestUser')
        mock_bet.guild_id = player.get('guild_id', TEST_GUILD_ID)
        mock_bet.play_time = player.get('play_time', 30000)
        
        mock_play_type = MagicMock()
        mock_play_type.value = player.get('play_type', 'normal')
        mock_bet.play_type = mock_play_type
        
        mock_bets.append(mock_bet)
    
    return mock_bets


# Test data generators
def generate_performance_test_data(count=1000):
    """Generate test data for performance testing."""
    test_data = []
    
    for i in range(count):
        data = {
            'user_id': f"perf_user_{i}",
            'username': f"PerfUser{i}",
            'guild_id': TEST_GUILD_ID,
            'total_wins': i % 50,  # 0-49 wins
            'total_games': max((i % 50) + 10, 1),
            'best_time_ms': 15000 + (i % 5000),
            'worst_time_ms': 45000 + (i % 10000),
            'avg_time_ms': 30000 + (i % 7500),
            'current_streak': i % 10,
            'max_streak': i % 20
        }
        test_data.append(data)
    
    return test_data


def validate_test_environment():
    """Validate that the test environment is properly set up."""
    required_modules = [
        'database.models',
        'utils.game_1337',
        'bot.config'
    ]
    
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
        except ImportError as e:
            missing_modules.append(f"{module}: {e}")
    
    if missing_modules:
        raise ImportError(f"Missing required modules: {missing_modules}")
    
    return True


# Test utilities
class TestTimer:
    """Context manager for timing test operations."""
    
    def __init__(self, description="Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        import time
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        import time
        self.end_time = time.time()
    
    @property
    def elapsed_time(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None
    
    def print_result(self):
        if self.elapsed_time:
            print(f"{self.description}: {self.elapsed_time:.3f} seconds")


class TestDataCollector:
    """Collect and analyze test data."""
    
    def __init__(self):
        self.data = []
    
    def add_measurement(self, test_name, elapsed_time, additional_data=None):
        """Add a test measurement."""
        entry = {
            'test_name': test_name,
            'elapsed_time': elapsed_time,
            'additional_data': additional_data or {}
        }
        self.data.append(entry)
    
    def get_summary(self):
        """Get summary statistics."""
        if not self.data:
            return {}
        
        times = [entry['elapsed_time'] for entry in self.data]
        return {
            'total_tests': len(self.data),
            'total_time': sum(times),
            'average_time': sum(times) / len(times),
            'min_time': min(times),
            'max_time': max(times)
        }
    
    def print_summary(self):
        """Print summary statistics."""
        summary = self.get_summary()
        if summary:
            print("Test Performance Summary:")
            print(f"  Total tests: {summary['total_tests']}")
            print(f"  Total time: {summary['total_time']:.3f}s")
            print(f"  Average time: {summary['average_time']:.3f}s")
            print(f"  Min time: {summary['min_time']:.3f}s")
            print(f"  Max time: {summary['max_time']:.3f}s")


# Export commonly used items
__all__ = [
    'TEST_USER_IDS',
    'TEST_GUILD_ID', 
    'TEST_ROLE_IDS',
    'TEST_PLAYER_STATS_TEMPLATES',
    'setup_test_environment',
    'create_mock_discord_environment',
    'create_mock_database_environment',
    'generate_test_player_stats',
    'assert_rank_progression',
    'create_test_game_scenario',
    'generate_performance_test_data',
    'validate_test_environment',
    'TestTimer',
    'TestDataCollector'
]
