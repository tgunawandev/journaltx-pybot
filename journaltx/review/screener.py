"""
Screener module for reviewing historical alerts.

Shows what happened, never suggests trades.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

from journaltx.core.config import Config
from journaltx.core.models import Alert, Trade
from journaltx.review.stats import get_alerts_screener

logger = logging.getLogger(__name__)


def format_screener_output(
    config: Config,
    hours: int = 24,
    alert_type: Optional[str] = None,
    min_sol: Optional[float] = None,
) -> str:
    """
    Format screener output as plain text.
    """
    alerts = get_alerts_screener(config, hours, alert_type, min_sol)

    # Group by pair
    by_pair = defaultdict(list)
    for alert in alerts:
        by_pair[alert.pair].append(alert)

    # Header
    lines = [
        f"JournalTX Screener - Last {hours}h",
        "",
    ]

    if not by_pair:
        lines.append("No alerts match criteria.")
        return "\n".join(lines)

    # Output by pair
    for pair, pair_alerts in sorted(by_pair.items()):
        lines.append(f"{pair}")

        # Check if trade was taken
        with config.database_path:
            from journaltx.core.db import get_session
            session = get_session(config)

            trade_taken = (
                session.query(Trade)
                .filter(
                    Trade.pair_base == pair.split("/")[0],
                    Trade.pair_quote == "SOL",
                )
                .first()
            )

            session.close()

        # Summarize alerts
        lp_adds = sum(1 for a in pair_alerts if a.type.value == "lp_add")
        lp_removes = sum(1 for a in pair_alerts if a.type.value == "lp_remove")
        volume_spikes = sum(1 for a in pair_alerts if a.type.value == "volume_spike")

        max_lp = max(
            (a.value_sol for a in pair_alerts if a.type.value == "lp_add"),
            default=0,
        )

        # Output
        if lp_adds:
            lines.append(f"- LP Added: {max_lp:,.2f} SOL")
        if volume_spikes:
            lines.append(f"- Volume Spike: {'Yes' if volume_spikes > 0 else 'No'}")
        if lp_removes:
            lines.append(f"- LP Removed: Yes")

        lines.append(f"- Trade Taken: {'Yes' if trade_taken else 'No'}")
        lines.append("")

    return "\n".join(lines)


def print_screener(
    config: Config,
    hours: int = 24,
    alert_type: Optional[str] = None,
    min_sol: Optional[float] = None,
) -> None:
    """
    Print screener output to stdout.
    """
    output = format_screener_output(config, hours, alert_type, min_sol)
    print(output)
