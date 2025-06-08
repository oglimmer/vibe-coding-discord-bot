"""
Time parsing utilities for the 1337 game.
"""

import re
from typing import Optional


def parse_time_to_milliseconds(time_string: str) -> Optional[int]:
    """
    Parse time string to milliseconds.
    
    Format: [hh:mm:]ss[.SSS]
    Examples:
        - "13.5" -> 13500ms
        - "01:13" -> 73000ms  
        - "1:02:03.999" -> 3723999ms
        - "60.000" -> 60000ms (max allowed)
    
    Args:
        time_string: Time string to parse
        
    Returns:
        Milliseconds as integer, or None if invalid
    """
    if not time_string or not isinstance(time_string, str):
        return None
    
    # Clean input
    time_string = time_string.strip()
    
    # Validation regex: ^(?:(\d{1,2}):)?(?:(\d{1,2}):)?(\d{1,2})(?:\.(\d{1,3}))?$
    pattern = r'^(?:(\d{1,2}):)?(?:(\d{1,2}):)?(\d{1,2})(?:\.(\d{1,3}))?$'
    match = re.match(pattern, time_string)
    
    if not match:
        return None
    
    groups = match.groups()
    
    # Parse components
    hours = int(groups[0]) if groups[0] else 0
    minutes = int(groups[1]) if groups[1] else 0
    seconds = int(groups[2]) if groups[2] else 0
    milliseconds = 0
    
    # Handle decimal part
    if groups[3]:
        # Pad to 3 digits and convert
        decimal_str = groups[3].ljust(3, '0')[:3]
        milliseconds = int(decimal_str)
    
    # Validate ranges
    if hours > 23 or minutes > 59 or seconds > 59:
        return None
    
    # Convert to total milliseconds
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    
    # Check if within allowed range (0 to 60000ms = 60 seconds)
    if total_ms < 0 or total_ms > 60000:
        return None
    
    return total_ms


def format_milliseconds_to_time(milliseconds: int) -> str:
    """
    Format milliseconds back to readable time string.
    
    Args:
        milliseconds: Time in milliseconds
        
    Returns:
        Formatted time string
    """
    if milliseconds < 0:
        return "0.000s"
    
    total_seconds = milliseconds / 1000
    ms_part = milliseconds % 1000
    
    if total_seconds >= 60:
        minutes = int(total_seconds // 60)
        seconds = total_seconds % 60
        return f"{minutes}:{seconds:06.3f}"
    else:
        return f"{total_seconds:.3f}s"


def validate_time_input(time_string: str) -> tuple[bool, str, Optional[int]]:
    """
    Validate time input and return result.
    
    Args:
        time_string: Time string to validate
        
    Returns:
        Tuple of (is_valid, error_message, milliseconds)
    """
    if not time_string:
        return False, "❌ Zeit darf nicht leer sein.", None
    
    # Check for common mistakes
    if ',' in time_string:
        return False, "❌ Verwende einen Punkt (.) für Dezimalstellen, nicht ein Komma.", None
    
    # Parse the time
    ms = parse_time_to_milliseconds(time_string)
    
    if ms is None:
        return False, (
            "❌ Ungültiges Zeitformat. Verwende das Format `[hh:mm:]ss[.SSS]`\n"
            "**Beispiele:** `13.5`, `01:13`, `1:02:03.999`, `60.000`"
        ), None
    
    if ms > 60000:
        return False, "❌ Maximum erlaubte Zeit ist 60.000 Sekunden.", None
    
    return True, "✅ Gültige Zeit!", ms
