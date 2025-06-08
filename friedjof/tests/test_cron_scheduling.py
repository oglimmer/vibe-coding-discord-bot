#!/usr/bin/env python3
"""
Test script for 1337 Game Cron Scheduling
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime
import pytz
from croniter import croniter

def test_cron_expressions():
    """Test different cron expressions for the 1337 game."""
    
    timezone = pytz.timezone("Europe/Berlin")
    current_time = datetime.now(timezone)
    
    print(f"🕐 Current time: {current_time.strftime('%d.%m.%Y %H:%M:%S %Z')}")
    print("=" * 60)
    
    test_expressions = [
        ("Daily at 13:37", "37 13 * * *"),
        ("Twice daily (13:37 and 21:37)", "37 13,21 * * *"),
        ("Weekdays only at 13:37", "37 13 * * 1-5"),
        ("Every hour at :37", "0 37 * * * *"),
        ("Every 30 minutes", "0 */30 * * * *"),
        ("Every 5 minutes (testing)", "0 */5 * * * *"),
        ("Weekends at 15:00", "0 0 15 * * 6,7"),
    ]
    
    for description, cron_expr in test_expressions:
        print(f"\n📅 {description}")
        print(f"   Cron: {cron_expr}")
        
        try:
            # Convert to UTC for croniter
            utc_time = current_time.astimezone(pytz.UTC)
            cron = croniter(cron_expr, utc_time)
            
            # Get next 3 occurrences
            print("   Next times:")
            for i in range(3):
                next_utc = cron.get_next(datetime)
                next_local = next_utc.astimezone(timezone)
                relative_time = (next_local - current_time).total_seconds()
                
                if relative_time < 3600:
                    time_desc = f"in {relative_time/60:.1f} minutes"
                elif relative_time < 86400:
                    time_desc = f"in {relative_time/3600:.1f} hours"
                else:
                    time_desc = f"in {relative_time/86400:.1f} days"
                
                print(f"   {i+1}. {next_local.strftime('%d.%m.%Y %H:%M:%S')} ({time_desc})")
        
        except Exception as e:
            print(f"   ❌ Error: {e}")

def test_early_bird_calculation():
    """Test early bird period calculation."""
    
    timezone = pytz.timezone("Europe/Berlin")
    
    # Test with a known game time
    game_time = timezone.localize(datetime(2025, 6, 7, 13, 37, 0))
    cutoff_hours = 2
    
    cutoff_time = game_time - pytz.timezone("UTC").localize(datetime(1970, 1, 1, cutoff_hours, 0, 0)).replace(tzinfo=None)
    
    print(f"\n🐦 Early Bird Test:")
    print(f"   Game time: {game_time.strftime('%d.%m.%Y %H:%M:%S')}")
    print(f"   Cutoff: {cutoff_hours} hours before")
    print(f"   Early bird starts: {(game_time - pytz.timedelta(hours=cutoff_hours)).strftime('%d.%m.%Y %H:%M:%S')}")

if __name__ == "__main__":
    print("🎮 1337 Game Cron Testing")
    print("=" * 60)
    
    try:
        test_cron_expressions()
        test_early_bird_calculation()
        print("\n✅ All tests completed successfully!")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Install dependencies: pip install croniter pytz")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
