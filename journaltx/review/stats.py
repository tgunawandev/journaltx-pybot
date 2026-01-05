"""
Trade statistics module.

Provides various statistical views of trading performance.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, and_, or_

from journaltx.core.config import Config
from journaltx.core.models import Trade, Journal, Alert, ContinuationQuality, AlertType
from journaltx.core.db import session_scope

logger = logging.getLogger(__name__)


def get_trade_count(config: Config, days: int = 1) -> int:
    """
    Get number of trades in past N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with session_scope(config) as session:
        count = (
            session.query(func.count(Trade.id))
            .filter(Trade.timestamp >= cutoff)
            .scalar()
        )

        return count or 0


def get_recent_trades(config: Config, limit: int = 10) -> List[Trade]:
    """
    Get most recent trades.
    """
    with session_scope(config) as session:
        trades = (
            session.query(Trade)
            .order_by(Trade.timestamp.desc())
            .limit(limit)
            .all()
        )

        return trades


def get_alerts_screener(
    config: Config,
    hours: int = 24,
    alert_type: Optional[str] = None,
    min_sol: Optional[float] = None,
) -> List[Alert]:
    """
    Filter alerts for screener.

    Returns alerts matching criteria.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    with session_scope(config) as session:
        query = session.query(Alert).filter(Alert.triggered_at >= cutoff)

        if alert_type:
            # Normalize type
            type_map = {
                "lp_add": AlertType.LP_ADD,
                "lp_remove": AlertType.LP_REMOVE,
                "volume_spike": AlertType.VOLUME_SPIKE,
            }
            normalized_type = type_map.get(alert_type.lower())
            if normalized_type:
                query = query.filter(Alert.type == normalized_type)

        if min_sol:
            query = query.filter(Alert.value_sol >= min_sol)

        alerts = query.order_by(Alert.triggered_at.desc()).all()

        return alerts


def get_open_trades(config: Config) -> List[Trade]:
    """
    Get all trades without exit price.
    """
    with session_scope(config) as session:
        trades = (
            session.query(Trade)
            .filter(Trade.exit_price.is_(None))
            .order_by(Trade.timestamp.desc())
            .all()
        )

        return trades


def check_if_journal_missing(config: Config, trade_id: int) -> bool:
    """
    Check if a trade is missing journal entry.
    """
    with session_scope(config) as session:
        count = (
            session.query(func.count(Journal.id))
            .filter(Journal.trade_id == trade_id)
            .scalar()
        )

        return (count or 0) == 0
