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

logger = logging.getLogger(__name__)


def log_manual_alert(
    config: Config,
    alert_type: str,
    pair: str,
    value_sol: float,
    value_usd: Optional[float] = None,
) -> Alert:
    """
    Manually log an alert.

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

    # Create alert
    with session_scope(config) as session:
        alert = Alert(
            type=normalized_type,
            chain="solana",
            pair=pair.upper(),
            value_sol=value_sol,
            value_usd=value_usd,
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
        alert_triggered_at = alert.triggered_at

        logger.info(f"Manually logged alert: {alert}")

    # Create a new Alert object outside the session context
    return Alert(
        id=alert_id,
        type=normalized_type,
        chain="solana",
        pair=alert_pair,
        value_sol=alert_value_sol,
        value_usd=alert_value_usd,
        triggered_at=alert_triggered_at,
    )
