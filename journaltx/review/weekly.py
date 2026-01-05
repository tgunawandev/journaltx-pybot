"""
Weekly review module.

Generates behavioral summaries for weekly reflection.
"""

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func, and_

from journaltx.core.config import Config
from journaltx.core.models import Trade, Journal, Alert, ContinuationQuality
from journaltx.core.db import session_scope

logger = logging.getLogger(__name__)


def get_weekly_stats(config: Config, days: int = 7) -> dict:
    """
    Calculate trading statistics for the past N days.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    with session_scope(config) as session:
        # Get trades in period
        trades = (
            session.query(Trade)
            .filter(Trade.timestamp >= cutoff)
            .order_by(Trade.timestamp)
            .all()
        )

        # Count total
        total_trades = len(trades)

        if total_trades == 0:
            return {
                "total_trades": 0,
                "closed_trades": 0,
                "win_rate": None,
                "avg_win": None,
                "avg_loss": None,
                "rules_followed_pct": None,
                "scale_out_used_pct": None,
                "continuation_breakdown": None,
                "trades": [],
            }

        # Separate closed and open
        closed_trades = [t for t in trades if t.exit_price is not None]
        open_trades = [t for t in trades if t.exit_price is None]

        closed_count = len(closed_trades)

        # Calculate win rate
        wins = [t for t in closed_trades if t.pnl_pct and t.pnl_pct > 0]
        losses = [t for t in closed_trades if t.pnl_pct and t.pnl_pct < 0]

        win_rate = (len(wins) / closed_count * 100) if closed_count > 0 else 0

        # Average win/loss
        avg_win = (
            sum(t.pnl_pct for t in wins if t.pnl_pct) / len(wins) if wins else None
        )
        avg_loss = (
            sum(t.pnl_pct for t in losses if t.pnl_pct) / len(losses) if losses else None
        )

        # Rules followed
        rules_followed = sum(1 for t in trades if t.risk_followed)
        rules_followed_pct = (rules_followed / total_trades * 100) if total_trades > 0 else 0

        # Scale out used
        scale_out_used = sum(1 for t in trades if t.scale_out_used)
        scale_out_used_pct = (scale_out_used / total_trades * 100) if total_trades > 0 else 0

        # Get journal entries
        trade_ids = [t.id for t in trades]
        journals = (
            session.query(Journal)
            .filter(Journal.trade_id.in_(trade_ids))
            .all()
        )

        # Continuation quality breakdown
        continuation_counter = Counter(j.continuation_quality for j in journals)
        continuation_breakdown = {
            ContinuationQuality.POOR.value: continuation_counter.get(ContinuationQuality.POOR, 0),
            ContinuationQuality.MIXED.value: continuation_counter.get(ContinuationQuality.MIXED, 0),
            ContinuationQuality.STRONG.value: continuation_counter.get(ContinuationQuality.STRONG, 0),
        }

        return {
            "total_trades": total_trades,
            "closed_trades": closed_count,
            "open_trades": len(open_trades),
            "win_rate": win_rate,
            "avg_win": avg_win,
            "avg_loss": avg_loss,
            "rules_followed_pct": rules_followed_pct,
            "scale_out_used_pct": scale_out_used_pct,
            "continuation_breakdown": continuation_breakdown,
            "trades": trades,
        }


def format_weekly_review(config: Config, days: int = 7) -> str:
    """
    Format weekly review as plain text.
    """
    stats = get_weekly_stats(config, days)

    # Header
    lines = [
        f"JournalTX - Weekly Review (Last {days} days)",
        "",
    ]

    if stats["total_trades"] == 0:
        lines.extend([
            "No trades logged in this period.",
            "",
            "Review focus:",
            "- Why were no trades taken?",
            "- Was the market environment unfavorable?",
            "- Were rules too restrictive?",
        ])
        return "\n".join(lines)

    # Trade stats
    lines.extend([
        f"Trades: {stats['total_trades']}",
        f"Closed: {stats['closed_trades']}",
        f"Open: {stats['open_trades']}",
        "",
    ])

    # Performance
    if stats["closed_trades"] > 0:
        lines.extend([
            "Performance:",
            f"Win rate: {stats['win_rate']:.0f}%",
        ])

        if stats["avg_win"]:
            lines.append(f"Avg win: +{stats['avg_win']:.0f}%")
        if stats["avg_loss"]:
            lines.append(f"Avg loss: {stats['avg_loss']:.0f}%")

        lines.append("")

    # Behavioral metrics
    lines.extend([
        "Discipline:",
        f"Rules followed: {stats['rules_followed_pct']:.0f}%",
        f"Scale-out used: {stats['scale_out_used_pct']:.0f}%",
        "",
    ])

    # Continuation quality
    if stats["continuation_breakdown"]:
        cont = stats["continuation_breakdown"]
        lines.extend([
            "Continuation:",
            f"Not justified: {cont[ContinuationQuality.POOR.value]}",
            f"Mixed: {cont[ContinuationQuality.MIXED.value]}",
            f"Strong: {cont[ContinuationQuality.STRONG.value]}",
            "",
        ])

        # Suggest ONE change
        if cont[ContinuationQuality.POOR.value] > cont[ContinuationQuality.STRONG.value]:
            lines.append("ONE CHANGE NEXT WEEK:")
            lines.append("-> Stop trading on weak continuation signals")
            lines.append("")
        elif stats["scale_out_used_pct"] < 50:
            lines.append("ONE CHANGE NEXT WEEK:")
            lines.append("-> Take partial profits earlier on first impulse")
            lines.append("")
        elif stats["rules_followed_pct"] < 80:
            lines.append("ONE CHANGE NEXT WEEK:")
            lines.append("-> Write down rules before every trade entry")
            lines.append("")

    return "\n".join(lines)


def print_weekly_review(config: Config, days: int = 7) -> None:
    """
    Print weekly review to stdout.
    """
    review = format_weekly_review(config, days)
    print(review)


def export_weekly_review(config: Config, days: int = 7, filepath: str = None) -> str:
    """
    Export weekly review to file.

    Returns file path.
    """
    if not filepath:
        filepath = f"data/weekly_review_{datetime.utcnow().strftime('%Y%m%d')}.txt"

    review = format_weekly_review(config, days)

    with open(filepath, "w") as f:
        f.write(review)

    logger.info(f"Weekly review exported to {filepath}")
    return filepath
