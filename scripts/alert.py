#!/usr/bin/env python3
"""
Manual alert logging with Telegram notifications.

Allows creating alerts manually that will be sent to Telegram.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import typer
from rich.console import Console

from journaltx.core.config import Config
from journaltx.ingest.manual import log_manual_alert
from journaltx.notify.telegram import TelegramNotifier

app = typer.Typer(help="Log manual alert with Telegram notification")
console = Console()


@app.command()
def main(
    alert_type: str = typer.Option(..., "--type", "-t", help="Alert type (lp_add, lp_remove, volume_spike)"),
    pair: str = typer.Option(..., "--pair", "-p", help="Trading pair (e.g., BONK/SOL)"),
    sol: float = typer.Option(..., "--sol", "-s", help="SOL amount"),
    lp_before: float = typer.Option(0.0, "--lp-before", help="Liquidity before LP add (SOL)"),
    pair_age_hours: float = typer.Option(None, "--pair-age", help="Pair age in hours"),
):
    """
    Log a manual alert and send to Telegram.

    Example:
        python scripts/alert.py --type lp_add --pair NEWCOIN/SOL --sol 420 --lp-before 3 --pair-age 0.3
    """
    load_dotenv()
    config = Config.from_env()

    # Log alert with new fields
    alert = log_manual_alert(
        config,
        alert_type,
        pair,
        sol,
        sol * 150.0,
        lp_sol_before=lp_before,
        pair_age_hours=pair_age_hours
    )

    console.print(f"[green]✓ Alert logged: {alert.type.value} {pair} {sol} SOL[/green]")

    # Send to Telegram
    telegram = TelegramNotifier(config)
    if telegram.send_alert(alert):
        console.print("[green]✓ Telegram notification sent[/green]")
    else:
        console.print("[yellow]Telegram not configured or failed[/yellow]")


if __name__ == "__main__":
    app()
