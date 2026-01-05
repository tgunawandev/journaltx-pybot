"""
Behavioral guardrails.

Checks for trading patterns that indicate overtrading or lack of discipline.
Logs warnings but never blocks execution.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from journaltx.core.config import Config
from journaltx.core.models import Trade, Journal
from journaltx.review.stats import get_trade_count, check_if_journal_missing

logger = logging.getLogger(__name__)


class GuardrailWarning:
    """A guardrail warning message."""

    def __init__(self, category: str, message: str):
        self.category = category
        self.message = message

    def __str__(self) -> str:
        return f"[{self.category}] {self.message}"


def check_daily_trade_limit(config: Config) -> Optional[GuardrailWarning]:
    """
    Check if daily trade limit exceeded.

    Warns if trades >= max_trades_per_day.
    """
    trade_count = get_trade_count(config, days=1)

    if trade_count >= config.max_trades_per_day:
        return GuardrailWarning(
            "OVERTRADING",
            f"You have taken {trade_count} trade(s) today. "
            f"Consider stopping for the day."
        )

    return None


def check_journal_completion(config: Config, trade_id: int) -> Optional[GuardrailWarning]:
    """
    Check if trade has journal entry.

    Warns if journal is missing.
    """
    if check_if_journal_missing(config, trade_id):
        return GuardrailWarning(
            "JOURNAL_MISSING",
            f"Trade {trade_id} is missing journal entry. "
            f"Reflect before trading again."
        )

    return None


def check_scale_out_usage(config: Config, trade_id: int) -> Optional[GuardrailWarning]:
    """
    Check if scale-out was used.

    Warns if scale-out was not used.
    """
    from journaltx.core.db import session_scope

    with session_scope(config) as session:
        trade = session.query(Trade).filter(Trade.id == trade_id).first()

        if not trade:
            return None

        if not trade.scale_out_used:
            return GuardrailWarning(
                "SCALE_OUT",
                f"Trade {trade_id} did not use scale-out. "
                f"Consider taking partial profits."
            )

    return None


def check_open_trades(config: Config) -> Optional[GuardrailWarning]:
    """
    Check if too many trades are open.

    Warns if > 3 open trades.
    """
    from journaltx.review.stats import get_open_trades

    open_trades = get_open_trades(config)

    if len(open_trades) >= 3:
        return GuardrailWarning(
            "OPEN_POSITIONS",
            f"You have {len(open_trades)} open trade(s). "
            f"Consider closing existing positions before entering new ones."
        )

    return None


def run_all_guardrails(
    config: Config,
    trade_id: Optional[int] = None,
) -> List[GuardrailWarning]:
    """
    Run all guardrail checks.

    Returns list of warnings (empty if none).
    """
    warnings: List[GuardrailWarning] = []

    # Check daily limit
    daily_warning = check_daily_trade_limit(config)
    if daily_warning:
        warnings.append(daily_warning)

    # Check open trades
    open_warning = check_open_trades(config)
    if open_warning:
        warnings.append(open_warning)

    # Check specific trade if provided
    if trade_id:
        journal_warning = check_journal_completion(config, trade_id)
        if journal_warning:
            warnings.append(journal_warning)

        scale_warning = check_scale_out_usage(config, trade_id)
        if scale_warning:
            warnings.append(scale_warning)

    # Log all warnings
    for warning in warnings:
        logger.warning(f"Guardrail: {warning}")

    return warnings


def print_guardrails(
    config: Config,
    trade_id: Optional[int] = None,
) -> None:
    """
    Run guardrails and print warnings to stdout.
    """
    warnings = run_all_guardrails(config, trade_id)

    if not warnings:
        print("No guardrail warnings.")
        return

    print("\nGuardrail Warnings:")
    print("-" * 50)
    for warning in warnings:
        print(f"  {warning}")
    print()
