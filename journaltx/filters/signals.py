"""
Multi-signal tracker for early-stage meme detection.

Tracks momentum signals in rolling time windows.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """A momentum signal for a token."""
    signal_type: str  # "lp_add", "volume_spike", "buy_pressure"
    timestamp: datetime
    pair: str
    details: dict


class SignalTracker:
    """
    Tracks momentum signals in rolling windows.

    Requires at least 2 signals within 30 minutes to trigger alert.
    """

    def __init__(self, window_minutes: int = 30):
        self.window_minutes = window_minutes
        self.signals: Dict[str, List[Signal]] = {}  # pair -> list of signals

    def add_signal(self, signal: Signal) -> bool:
        """
        Add a signal and check if we have enough to alert.

        Returns True if should alert (2+ signals in window).
        """
        pair = signal.pair
        now = datetime.now()

        # Initialize list for this pair
        if pair not in self.signals:
            self.signals[pair] = []

        # Remove old signals outside window
        cutoff = now - timedelta(minutes=self.window_minutes)
        self.signals[pair] = [
            s for s in self.signals[pair]
            if s.timestamp > cutoff
        ]

        # Add new signal
        self.signals[pair].append(signal)

        # Count unique signal types in window
        recent_signals = self.signals[pair]
        unique_types = set(s.signal_type for s in recent_signals)

        logger.info(
            f"{pair}: {len(recent_signals)} signals in window, "
            f"{len(unique_types)} unique types: {unique_types}"
        )

        # Need at least 2 different signal types
        return len(unique_types) >= 2

    def get_signal_count(self, pair: str) -> dict:
        """
        Get signal counts for a pair.

        Returns dict with total count and breakdown by type.
        """
        if pair not in self.signals:
            return {"total": 0, "types": {}}

        now = datetime.now()
        cutoff = now - timedelta(minutes=self.window_minutes)

        recent = [s for s in self.signals[pair] if s.timestamp > cutoff]

        type_counts = {}
        for s in recent:
            type_counts[s.signal_type] = type_counts.get(s.signal_type, 0) + 1

        return {
            "total": len(recent),
            "types": type_counts,
        }


# Global signal tracker instance
_signal_tracker = SignalTracker()


def get_signal_tracker() -> SignalTracker:
    """Get the global signal tracker instance."""
    return _signal_tracker
