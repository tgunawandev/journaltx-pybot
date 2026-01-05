"""
LP event listener for QuickNode streams.

Monitors liquidity pool additions and removals on Solana.
"""

import logging
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from journaltx.core.config import Config
from journaltx.core.models import Alert, AlertType
from journaltx.core.db import session_scope
from journaltx.ingest.quicknode.schemas import LPEvent
from journaltx.ingest.quicknode.transaction_parser import ParsedLPEvent
from journaltx.ingest.token_resolver import get_price_service
from journaltx.filters.early_meme import check_early_stage_opportunity

logger = logging.getLogger(__name__)


class LPEventListener:
    """
    Listens for LP events from QuickNode WebSocket.

    Filters by threshold and logs alerts.
    """

    def __init__(self, config: Config):
        self.config = config
        self.price_service = get_price_service()

    def _get_sol_price_usd(self) -> float:
        """Get SOL price in USD from price service."""
        return self.price_service.get_sol_price_usd()

    def _convert_to_usd(self, amount_sol: float) -> float:
        """Convert SOL amount to USD."""
        return amount_sol * self._get_sol_price_usd()

    def process_parsed_lp_event(
        self,
        parsed_event: ParsedLPEvent,
        on_alert: Optional[Callable[[Alert], None]] = None,
    ) -> Optional[Alert]:
        """
        Process a fully parsed LP event with all metadata.

        This is the main entry point for real LP events.

        Args:
            parsed_event: Fully parsed LP event from transaction parser
            on_alert: Callback when alert is generated

        Returns:
            Alert if created, None otherwise
        """
        # Check SOL threshold
        if parsed_event.sol_amount < self.config.lp_add_min_sol:
            logger.debug(
                f"LP add below SOL threshold: {parsed_event.sol_amount:.1f} SOL < {self.config.lp_add_min_sol} SOL"
            )
            return None

        # Check USD threshold
        if parsed_event.sol_amount_usd < self.config.lp_add_min_usd:
            logger.debug(
                f"LP add below USD threshold: ${parsed_event.sol_amount_usd:.0f} < ${self.config.lp_add_min_usd}"
            )
            return None

        logger.info(
            f"Processing LP event: {parsed_event.pair_string} "
            f"+{parsed_event.sol_amount:.1f} SOL (~${parsed_event.sol_amount_usd:.0f})"
        )

        # Run early-stage checks
        # Calculate baseline liquidity (liquidity before this LP add)
        lp_before_sol = max(0, parsed_event.liquidity_sol - parsed_event.sol_amount)

        should_alert, should_log, details = check_early_stage_opportunity(
            pair=parsed_event.pair_string,
            lp_added_sol=parsed_event.sol_amount,
            lp_before_sol=lp_before_sol,
            max_pair_age_hours=self.config.max_pair_age_hours,
            preferred_pair_age_hours=self.config.preferred_pair_age_hours,
            near_zero_baseline_sol=self.config.near_zero_baseline_sol,
            hard_reject_baseline_liquidity=self.config.hard_reject_baseline_liquidity_sol,
            hard_reject_pair_age_hours=self.config.hard_reject_pair_age_hours,
            hard_reject_market_cap=self.config.hard_reject_market_cap_usd,
            min_lp_ignite_sol=self.config.min_lp_sol_threshold,
            max_market_cap_defensive=self.config.max_market_cap,
            signal_window_minutes=self.config.signal_window_minutes,
            legacy_memes=self.config.legacy_memes,
            is_new_pool=parsed_event.is_new_pool,
            require_multi_signal=self.config.require_multi_signal,
        )

        # Override pair age with actual data if we have it
        if parsed_event.pair_age_hours > 0:
            details["pair_age_hours"] = parsed_event.pair_age_hours

        # Override market cap with actual data if we have it
        if parsed_event.market_cap > 0:
            details["market_cap"] = parsed_event.market_cap

        # Log the checks
        for check in details.get("checks", []):
            logger.info(f"  {check['rule']}: {check['status']} - {check['reason']}")

        # Create alert
        with session_scope(self.config) as session:
            alert = Alert(
                type=AlertType.LP_ADD,
                chain="solana",
                pair=parsed_event.pair_string,
                token_mint=parsed_event.token_mint,
                pool_address=parsed_event.pool_address,
                tx_signature=parsed_event.signature,
                value_sol=parsed_event.sol_amount,
                value_usd=parsed_event.sol_amount_usd,
                lp_sol_before=lp_before_sol,
                lp_sol_after=parsed_event.liquidity_sol,
                market_cap=parsed_event.market_cap,
                pair_age_hours=parsed_event.pair_age_hours,
                is_new_pool=parsed_event.is_new_pool,
                early_stage_passed=should_alert,
                mode=self.config.mode,
                triggered_at=parsed_event.timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(
                f"Logged alert: {alert.pair} | "
                f"early_stage={should_alert} | "
                f"new_pool={parsed_event.is_new_pool} | "
                f"age={parsed_event.pair_age_hours:.1f}h | "
                f"mcap=${parsed_event.market_cap/1e6:.2f}M"
            )

            if on_alert and should_alert:
                on_alert(alert)

            return alert

    def process_lp_add(
        self,
        token_a: str,
        token_b: str,
        amount_a: float,
        amount_b: float,
        raw_data: Dict[str, Any],
        on_alert: Optional[Callable[[Alert], None]] = None,
        # New optional parameters for full data
        token_mint: Optional[str] = None,
        pool_address: Optional[str] = None,
        is_new_pool: bool = False,
        liquidity_sol: float = 0,
        market_cap: float = 0,
        pair_age_hours: float = 0,
    ) -> Optional[LPEvent]:
        """
        Process LP addition event.

        This method supports both legacy and new data formats.
        """
        pair = self._format_pair(token_a, token_b)

        # Only monitor TOKEN/SOL pairs
        if not pair.endswith("/SOL"):
            logger.debug(f"Ignoring non-SOL pair: {pair}")
            return None

        # Extract SOL amount
        amount_sol = amount_b if token_b.upper() == "SOL" else amount_a

        # Check thresholds
        amount_usd = self._convert_to_usd(amount_sol)

        if amount_sol < self.config.lp_add_min_sol:
            logger.debug(
                f"LP add below threshold: {amount_sol:.1f} SOL"
            )
            return None

        # Calculate baseline
        lp_before_sol = max(0, liquidity_sol - amount_sol) if liquidity_sol > 0 else 0

        # Run early-stage checks
        should_alert, should_log, details = check_early_stage_opportunity(
            pair=pair,
            lp_added_sol=amount_sol,
            lp_before_sol=lp_before_sol,
            max_pair_age_hours=self.config.max_pair_age_hours,
            preferred_pair_age_hours=self.config.preferred_pair_age_hours,
            near_zero_baseline_sol=self.config.near_zero_baseline_sol,
            hard_reject_baseline_liquidity=self.config.hard_reject_baseline_liquidity_sol,
            hard_reject_pair_age_hours=self.config.hard_reject_pair_age_hours,
            hard_reject_market_cap=self.config.hard_reject_market_cap_usd,
            min_lp_ignite_sol=self.config.min_lp_sol_threshold,
            max_market_cap_defensive=self.config.max_market_cap,
            signal_window_minutes=self.config.signal_window_minutes,
            legacy_memes=self.config.legacy_memes,
            is_new_pool=is_new_pool,
            require_multi_signal=self.config.require_multi_signal,
        )

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
                token_mint=token_mint,
                pool_address=pool_address,
                tx_signature=raw_data.get("signature"),
                value_sol=amount_sol,
                value_usd=amount_usd,
                lp_sol_before=lp_before_sol,
                lp_sol_after=liquidity_sol if liquidity_sol > 0 else amount_sol,
                market_cap=market_cap,
                pair_age_hours=pair_age_hours,
                is_new_pool=is_new_pool,
                early_stage_passed=should_alert,
                mode=self.config.mode,
                triggered_at=event.timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(f"Logged LP add alert: {event}")

            if on_alert and should_alert:
                on_alert(alert)

        return event

    def _format_pair(self, token_a: str, token_b: str) -> str:
        """Format trading pair. Ensures TOKEN/SOL format."""
        tokens = [token_a.upper(), token_b.upper()]

        if "SOL" in tokens[1]:
            return f"{tokens[0]}/{tokens[1]}"
        if "SOL" in tokens[0]:
            return f"{tokens[1]}/{tokens[0]}"

        return f"{tokens[0]}/{tokens[1]}"

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

        if not pair.endswith("/SOL"):
            logger.debug(f"Ignoring non-SOL pair: {pair}")
            return None

        # Calculate removal percentage
        remove_pct = (amount_b / lp_total) * 100 if lp_total > 0 else 0

        if remove_pct < self.config.lp_remove_min_pct:
            logger.debug(f"LP remove below threshold: {remove_pct:.1f}%")
            return None

        amount_sol = amount_b if token_b.upper() == "SOL" else amount_a
        amount_usd = self._convert_to_usd(amount_sol)

        event = LPEvent(
            pair=pair,
            event_type="remove",
            amount_sol=amount_sol,
            amount_usd=amount_usd,
            timestamp=datetime.utcnow(),
            raw_data=raw_data,
        )

        with session_scope(self.config) as session:
            alert = Alert(
                type=AlertType.LP_REMOVE,
                chain="solana",
                pair=pair,
                value_sol=amount_sol,
                value_usd=amount_usd,
                mode=self.config.mode,
                triggered_at=event.timestamp,
            )
            session.add(alert)
            session.flush()

            logger.info(f"Logged LP remove alert: {event}")

            if on_alert:
                on_alert(alert)

        return event
