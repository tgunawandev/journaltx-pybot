"""
Manual alert logging.

Allows manual entry of alerts from CLI or other sources.
"""

import logging
from datetime import datetime
from typing import Optional

from journaltx.core.config import Config
from journaltx.core.models import Alert, AlertType
from journaltx.core.db import session_scope
from journaltx.filters.early_meme import check_early_stage_opportunity

logger = logging.getLogger(__name__)


def log_manual_alert(
    config: Config,
    alert_type: str,
    pair: str,
    value_sol: float,
    value_usd: Optional[float] = None,
    lp_sol_before: Optional[float] = None,
    pair_age_hours: Optional[float] = None,
) -> Alert:
    """
    Manually log an alert with early-stage filtering.

    Useful for testing or recording external observations.
    """
    # Normalize alert type
    type_map = {
        "lp_add": AlertType.LP_ADD,
        "lp_remove": AlertType.LP_REMOVE,
        "volume_spike": AlertType.VOLUME_SPIKE,
    }

    normalized_type = type_map.get(alert_type.lower())
    if not normalized_type:
        raise ValueError(f"Invalid alert type: {alert_type}")

    # Run refined early-stage filter check
    lp_before = lp_sol_before if lp_sol_before is not None else 0.0
    should_alert, should_log, filter_details = check_early_stage_opportunity(
        pair=pair,
        lp_added_sol=value_sol,
        lp_before_sol=lp_before,
        max_pair_age_hours=config.max_pair_age_hours,
        near_zero_baseline_sol=config.small_baseline_sol,
        min_lp_ignite_sol=config.min_lp_sol_threshold,
        max_market_cap_defensive=config.max_market_cap,
    )

    # Log the filtering result
    if filter_details.get("signal_counts"):
        counts = filter_details["signal_counts"]
        logger.info(
            f"Filter result: {pair} - Alert={should_alert}, "
            f"Signals={counts['total']} ({list(counts['types'].keys())})"
        )

    # Always log to database for analysis
    if not should_log:
        logger.info(f"Not logging to database: {pair}")
        # Return dummy alert for compatibility
        return Alert(
            id=0,
            type=normalized_type,
            chain="solana",
            pair=pair.upper(),
            value_sol=value_sol,
            value_usd=value_usd,
        )

    lp_sol_after = lp_before + value_sol

    # Create alert
    with session_scope(config) as session:
        alert = Alert(
            type=normalized_type,
            chain="solana",
            pair=pair.upper(),
            value_sol=value_sol,
            value_usd=value_usd,
            lp_sol_before=lp_sol_before,
            lp_sol_after=lp_sol_after,
            pair_age_hours=pair_age_hours,
            early_stage_passed=should_alert,  # True if should alert
            mode=config.mode,
            triggered_at=datetime.utcnow(),
        )
        session.add(alert)
        session.flush()

        # Load all attributes before session closes
        alert_id = alert.id
        alert_type_value = alert.type.value
        alert_pair = alert.pair
        alert_value_sol = alert.value_sol
        alert_value_usd = alert.value_usd
        alert_lp_before = alert.lp_sol_before
        alert_lp_after = alert.lp_sol_after
        alert_pair_age = alert.pair_age_hours
        alert_early_passed = alert.early_stage_passed
        alert_mode = alert.mode
        alert_triggered_at = alert.triggered_at

        logger.info(f"Manually logged alert: {alert}, early-stage: {should_alert}")

    # Create a new Alert object outside the session context
    return Alert(
        id=alert_id,
        type=normalized_type,
        chain="solana",
        pair=alert_pair,
        value_sol=alert_value_sol,
        value_usd=alert_value_usd,
        lp_sol_before=alert_lp_before,
        lp_sol_after=alert_lp_after,
        pair_age_hours=alert_pair_age,
        early_stage_passed=alert_early_passed,
        mode=alert_mode,
        triggered_at=alert_triggered_at,
    )

