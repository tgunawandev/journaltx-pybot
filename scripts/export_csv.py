#!/usr/bin/env python3
"""
Export data to CSV.

Exports trades or alerts to CSV format for external analysis.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import csv
import typer
from datetime import datetime
from rich.console import Console

from journaltx.core.config import Config
from journaltx.core.models import Trade, Alert
from journaltx.core.db import session_scope

app = typer.Typer(help="Export data to CSV")
console = Console()


@app.command()
def trades(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Export all trades to CSV.
    """
    config = Config.from_env()

    if not output:
        output = f"data/trades_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    with session_scope(config) as session:
        trade_query = session.query(Trade).order_by(Trade.timestamp)
        trades = trade_query.all()

        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "timestamp",
                "chain",
                "pair_base",
                "pair_quote",
                "entry_price",
                "exit_price",
                "pnl_pct",
                "risk_followed",
                "scale_out_used",
                "notes",
            ])

            for trade in trades:
                writer.writerow([
                    trade.id,
                    trade.timestamp.isoformat(),
                    trade.chain,
                    trade.pair_base,
                    trade.pair_quote,
                    trade.entry_price,
                    trade.exit_price or "",
                    trade.pnl_pct or "",
                    "Yes" if trade.risk_followed else "No",
                    "Yes" if trade.scale_out_used else "No",
                    trade.notes or "",
                ])

    console.print(f"[green]Exported {len(trades)} trades to {output}[/green]")


@app.command()
def alerts(
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """
    Export all alerts to CSV.
    """
    config = Config.from_env()

    if not output:
        output = f"data/alerts_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

    with session_scope(config) as session:
        alert_query = session.query(Alert).order_by(Alert.triggered_at.desc())
        alerts = alert_query.all()

        with open(output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id",
                "type",
                "chain",
                "pair",
                "value_sol",
                "value_usd",
                "triggered_at",
                "trade_id",
            ])

            for alert in alerts:
                writer.writerow([
                    alert.id,
                    alert.type.value,
                    alert.chain,
                    alert.pair,
                    alert.value_sol,
                    alert.value_usd or "",
                    alert.triggered_at.isoformat(),
                    alert.trade_id or "",
                ])

    console.print(f"[green]Exported {len(alerts)} alerts to {output}[/green]")


if __name__ == "__main__":
    app()
