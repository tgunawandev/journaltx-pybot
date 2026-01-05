"""
LP event listener for QuickNode streams.

Monitors liquidity pool additions and removals on Solana.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

from journaltx.core.config import Config
from journaltx.core.models import Alert, AlertType
from journaltx.core.db import session_scope
from journaltx.ingest.quicknode.schemas import LPEvent

logger = logging.getLogger(__name__)


class LPEventListener:
    """
    Listens for LP events from QuickNode WebSocket.

    Filters by threshold and logs alerts.
    """

    def __init__(self, config: Config):
        self.config = config
        self.sol_price_usd: Optional[float] = None
        self._price_updated_at: Optional[datetime] = None

    def _get_sol_price_usd(self) -> Optional[float]:
        """
        Get SOL price in USD.

        In production, this would query a price API.
        For now, returns a cached value or None.
        """
        # Update price every 5 minutes
        if self._price_updated_at and datetime.utcnow() - self._price_updated_at < timedelta(minutes=5):
            return self.sol_price_usd

        # TODO: Implement actual price fetching
        # For now, use a reasonable default
        self.sol_price_usd = 150.0
        self._price_updated_at = datetime.utcnow()
        return self.sol_price_usd

    def _format_pair(self, token_a: str, token_b: str) -> str:
        """
        Format trading pair.

        Ensures TOKEN/SOL format.
        """
        # Normalize to standard format
        tokens = [token_a.upper(), token_b.upper()]

        # Sort so SOL is always quote
        if "SOL" in tokens[1]:
            return f"{tokens[0]}/{tokens[1]}"
        if "SOL" in tokens[0]:
            return f"{tokens[1]}/{tokens[0]}"

        # If no SOL, return as-is
        return f"{tokens[0]}/{tokens[1]}"

    def _convert_to_usd(self, amount_sol: float) -> Optional[float]:
        """Convert SOL amount to USD."""
        sol_price = self._get_sol_price_usd()
        if sol_price:
            return amount_sol * sol_price
        return None

    def process_lp_add(
        self,
        token_a: str,
        token_b: str,
        amount_a: float,
        amount_b: float,
        raw_data: Dict[str, Any],
        on_alert: Optional[Callable[[Alert], None]] = None,
    ) -> Optional[LPEvent]:
        """
        Process LP addition event.

        Logs alert if threshold met.
        """
        pair = self._format_pair(token_a, token_b)

        # Only monitor TOKEN/SOL pairs
        if not pair.endswith("/SOL"):
            logger.debug(f"Ignoring non-SOL pair: {pair}")
            return None

        # Extract SOL amount (simplified - assumes amount_b is SOL)
        amount_sol = amount_b if token_b.upper() == "SOL" else amount_a

        # Check thresholds
        amount_usd = self._convert_to_usd(amount_sol)

        meets_sol_threshold = amount_sol >= self.config.lp_add_min_sol
        meets_usd_threshold = amount_usd and amount_usd >= self.config.lp_add_min_usd

        if not (meets_sol_threshold or meets_usd_threshold):
            logger.debug(
                f"LP add below threshold: {amount_sol} SOL (~${amount_usd:.0f})"
            )
            return None

        # Create event
        event = LPEvent(
            pair=pair,
            event_type="add",
            amount_sol=amount_sol,
            amount_usd=amount_usd,
            timestamp=datetime.utcnow(),
            raw_data=raw_data,
        )

        # Log alert
        with session_scope(self.config) as session:
            alert = Alert(
                type=AlertType.LP_ADD,
                chain="solana",
                pair=pair,
                value_sol=amount_sol,
                value_usd=amount_usd,
                triggered_at=event.timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(f"Logged LP add alert: {event}")

            if on_alert:
                on_alert(alert)

        return event

    def process_lp_remove(
        self,
        token_a: str,
        token_b: str,
        amount_a: float,
        amount_b: float,
        lp_total: float,
        raw_data: Dict[str, Any],
        on_alert: Optional[Callable[[Alert], None]] = None,
    ) -> Optional[LPEvent]:
        """
        Process LP removal event.

        Logs alert if removal % threshold met.
        """
        pair = self._format_pair(token_a, token_b)

        # Only monitor TOKEN/SOL pairs
        if not pair.endswith("/SOL"):
            logger.debug(f"Ignoring non-SOL pair: {pair}")
            return None

        # Calculate removal percentage
        remove_pct = (amount_b / lp_total) * 100 if lp_total > 0 else 0

        if remove_pct < self.config.lp_remove_min_pct:
            logger.debug(f"LP remove below threshold: {remove_pct:.1f}%")
            return None

        # Extract SOL amount
        amount_sol = amount_b if token_b.upper() == "SOL" else amount_a
        amount_usd = self._convert_to_usd(amount_sol)

        # Create event
        event = LPEvent(
            pair=pair,
            event_type="remove",
            amount_sol=amount_sol,
            amount_usd=amount_usd,
            timestamp=datetime.utcnow(),
            raw_data=raw_data,
        )

        # Log alert
        with session_scope(self.config) as session:
            alert = Alert(
                type=AlertType.LP_REMOVE,
                chain="solana",
                pair=pair,
                value_sol=amount_sol,
                value_usd=amount_usd,
                triggered_at=event.timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(f"Logged LP remove alert: {event}")

            if on_alert:
                on_alert(alert)

        return event
