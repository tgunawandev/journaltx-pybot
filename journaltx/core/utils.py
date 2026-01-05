"""
Utility functions for JournalTX.
"""


def format_age_human(hours: float) -> str:
    """
    Convert hours to human-readable age format.

    Examples:
        0.5 -> "30m"
        2.5 -> "2h 30m"
        25 -> "1d 1h"
        750 -> "1mo 1d"
        13341.28 -> "1y 6mo 7d"

    Args:
        hours: Age in hours

    Returns:
        Human-readable string like "1y 6mo 7d" or "2h 30m"
    """
    if hours <= 0:
        return "just now"

    # Convert to minutes
    total_minutes = int(hours * 60)

    # Define time units
    MINUTES_PER_HOUR = 60
    MINUTES_PER_DAY = 60 * 24
    MINUTES_PER_MONTH = MINUTES_PER_DAY * 30  # Approximate
    MINUTES_PER_YEAR = MINUTES_PER_DAY * 365

    years = total_minutes // MINUTES_PER_YEAR
    remaining = total_minutes % MINUTES_PER_YEAR

    months = remaining // MINUTES_PER_MONTH
    remaining = remaining % MINUTES_PER_MONTH

    days = remaining // MINUTES_PER_DAY
    remaining = remaining % MINUTES_PER_DAY

    hours_part = remaining // MINUTES_PER_HOUR
    minutes_part = remaining % MINUTES_PER_HOUR

    # Build the string based on the largest unit
    parts = []

    if years > 0:
        parts.append(f"{years}y")
        if months > 0:
            parts.append(f"{months}mo")
        if days > 0:
            parts.append(f"{days}d")
    elif months > 0:
        parts.append(f"{months}mo")
        if days > 0:
            parts.append(f"{days}d")
    elif days > 0:
        parts.append(f"{days}d")
        if hours_part > 0:
            parts.append(f"{hours_part}h")
    elif hours_part > 0:
        parts.append(f"{hours_part}h")
        if minutes_part > 0:
            parts.append(f"{minutes_part}m")
    else:
        parts.append(f"{minutes_part}m")

    return " ".join(parts)


def format_pair_age(hours: float, short: bool = False) -> str:
    """
    Format pair age with both numeric and human-readable format.

    Args:
        hours: Age in hours
        short: If True, return only human-readable format

    Returns:
        Formatted string like "13341.28h (1y 6mo 7d)" or just "1y 6mo 7d"
    """
    human = format_age_human(hours)

    if short:
        return human

    if hours < 1:
        return f"{hours*60:.0f}m ({human})"
    elif hours < 24:
        return f"{hours:.1f}h ({human})"
    else:
        return f"{hours:.0f}h ({human})"
