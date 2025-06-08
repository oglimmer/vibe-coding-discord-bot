#!/usr/bin/env python3
"""
Test script for 1337 game time parser functionality.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.time_parser import validate_time_input, parse_time_to_milliseconds, format_milliseconds_to_time

def test_time_parser():
    """Test the time parser with various inputs."""
    test_cases = [
        # Valid cases
        ("13.5", True, 13500),
        ("01:13", True, 73000),
        ("1:02:03.999", True, 3723999),
        ("60.000", True, 60000),
        ("0", True, 0),
        ("30", True, 30000),
        ("1:30", True, 90000),
        
        # Invalid cases
        ("61", False, None),
        ("-1", False, None),
        ("1:60:00", False, None),
        ("13,500", False, None),
        ("60.001", False, None),
        ("", False, None),
        ("abc", False, None),
    ]
    
    print("🧪 Testing Time Parser Functions")
    print("=" * 50)
    
    for test_input, expected_valid, expected_ms in test_cases:
        is_valid, message, ms = validate_time_input(test_input)
        
        status = "✅" if is_valid == expected_valid else "❌"
        print(f"{status} Input: '{test_input}' -> Valid: {is_valid}, MS: {ms}")
        
        if expected_valid and ms:
            formatted = format_milliseconds_to_time(ms)
            print(f"   Formatted back: {formatted}")
        
        if is_valid != expected_valid:
            print(f"   ❌ Expected valid={expected_valid}, got {is_valid}")
        
        if expected_valid and ms != expected_ms:
            print(f"   ❌ Expected {expected_ms}ms, got {ms}ms")
        
        print()

if __name__ == "__main__":
    test_time_parser()
