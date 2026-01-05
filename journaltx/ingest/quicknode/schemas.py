"""
Schemas for QuickNode event data.

Defines the structure of incoming WebSocket messages.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


class LPEvent:
    """
    Liquidity pool event (add or remove).

    Normalized structure from QuickNode streams.
    """

    def __init__(
        self,
        pair: str,
        event_type: str,  # "add" or "remove"
        amount_sol: float,
        amount_usd: Optional[float],
        timestamp: datetime,
        raw_data: Dict[str, Any],
    ):
        self.pair = pair
        self.event_type = event_type
        self.amount_sol = amount_sol
        self.amount_usd = amount_usd
        self.timestamp = timestamp
        self.raw_data = raw_data

    def __repr__(self) -> str:
        usd_str = f"~${self.amount_usd:,.0f}" if self.amount_usd else "N/A"
        return f"<LPEvent {self.event_type} {self.pair}: {self.amount_sol:.2f} SOL ({usd_str})>"


class VolumeEvent:
    """
    Volume spike event.

    Detected when volume exceeds rolling baseline.
    """

    def __init__(
        self,
        pair: str,
        volume_sol: float,
        volume_usd: Optional[float],
        spike_multiplier: float,
        baseline_sol: float,
        timestamp: datetime,
        raw_data: Dict[str, Any],
    ):
        self.pair = pair
        self.volume_sol = volume_sol
        self.volume_usd = volume_usd
        self.spike_multiplier = spike_multiplier
        self.baseline_sol = baseline_sol
        self.timestamp = timestamp
        self.raw_data = raw_data

    def __repr__(self) -> str:
        usd_str = f"~${self.volume_usd:,.0f}" if self.volume_usd else "N/A"
        return (
            f"<VolumeEvent {self.pair}: {self.volume_sol:.2f} SOL ({usd_str}) "
            f"- {self.spike_multiplier}x baseline>"
        )
