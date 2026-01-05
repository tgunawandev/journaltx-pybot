"""
Volume spike listener for QuickNode streams.

Monitors trading volume and detects spikes above baseline.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from journaltx.core.config import Config
from journaltx.core.models import Alert, AlertType
from journaltx.core.db import session_scope
from journaltx.ingest.quicknode.schemas import VolumeEvent

logger = logging.getLogger(__name__)


class VolumeTracker:
    """
    Tracks rolling volume baseline for pairs.

    Uses simple moving average over configurable window.
    """

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self._volume_history: Dict[str, List[tuple[datetime, float]]] = defaultdict(list)

    def add_volume(self, pair: str, volume_sol: float, timestamp: datetime) -> float:
        """
        Add volume data point and return current baseline.

        Maintains rolling window of volume data.
        """
        cutoff = timestamp - timedelta(minutes=self.window_minutes)

        # Add new point
        self._volume_history[pair].append((timestamp, volume_sol))

        # Remove old points
        self._volume_history[pair] = [
            (ts, vol) for ts, vol in self._volume_history[pair] if ts > cutoff
        ]

        # Calculate baseline (average)
        if self._volume_history[pair]:
            baseline = sum(vol for _, vol in self._volume_history[pair]) / len(
                self._volume_history[pair]
            )
        else:
            baseline = volume_sol

        return baseline

    def get_baseline(self, pair: str) -> Optional[float]:
        """Get current baseline for a pair."""
        if not self._volume_history[pair]:
            return None

        if self._volume_history[pair]:
            return sum(vol for _, vol in self._volume_history[pair]) / len(
                self._volume_history[pair]
            )
        return None


class VolumeEventListener:
    """
    Listens for volume events from QuickNode WebSocket.

    Detects spikes above rolling baseline.
    """

    def __init__(self, config: Config):
        self.config = config
        self.tracker = VolumeTracker(window_minutes=60)
        self.sol_price_usd: Optional[float] = None

    def _get_sol_price_usd(self) -> Optional[float]:
        """Get SOL price in USD."""
        if self.sol_price_usd is None:
            # TODO: Implement actual price fetching
            self.sol_price_usd = 150.0
        return self.sol_price_usd

    def _convert_to_usd(self, amount_sol: float) -> Optional[float]:
        """Convert SOL amount to USD."""
        sol_price = self._get_sol_price_usd()
        if sol_price:
            return amount_sol * sol_price
        return None

    def process_trade(
        self,
        pair: str,
        volume_sol: float,
        raw_data: Dict[str, Any],
        on_alert: Optional[Callable[[Alert], None]] = None,
    ) -> Optional[VolumeEvent]:
        """
        Process trade event.

        Logs alert if volume spike detected.
        """
        # Only monitor TOKEN/SOL pairs
        if not pair.upper().endswith("/SOL"):
            logger.debug(f"Ignoring non-SOL pair: {pair}")
            return None

        timestamp = datetime.utcnow()

        # Update baseline
        baseline = self.tracker.add_volume(pair, volume_sol, timestamp)

        # Check spike multiplier
        if baseline > 0:
            spike_multiplier = volume_sol / baseline
        else:
            spike_multiplier = 1.0

        if spike_multiplier < self.config.volume_spike_multiplier:
            logger.debug(
                f"Volume below spike threshold: {volume_sol:.2f} SOL "
                f"({spike_multiplier:.1f}x baseline)"
            )
            return None

        # Create event
        volume_usd = self._convert_to_usd(volume_sol)

        event = VolumeEvent(
            pair=pair,
            volume_sol=volume_sol,
            volume_usd=volume_usd,
            spike_multiplier=spike_multiplier,
            baseline_sol=baseline,
            timestamp=timestamp,
            raw_data=raw_data,
        )

        # Log alert
        with session_scope(self.config) as session:
            alert = Alert(
                type=AlertType.VOLUME_SPIKE,
                chain="solana",
                pair=pair,
                value_sol=volume_sol,
                value_usd=volume_usd,
                triggered_at=timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(f"Logged volume spike alert: {event}")

            if on_alert:
                on_alert(alert)

        return event
