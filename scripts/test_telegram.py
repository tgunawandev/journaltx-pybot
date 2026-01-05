#!/usr/bin/env python3
"""
Test Telegram notifications.

Sends test alerts to verify Telegram is working.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from dotenv import load_dotenv
import os
import typer
from rich.console import Console

from journaltx.core.config import Config
from journaltx.core.models import Alert, AlertType
from journaltx.notify.telegram import TelegramNotifier

app = typer.Typer(help="Test Telegram notifications")
console = Console()


@app.command()
def main():
    """Send test Telegram notifications."""
    load_dotenv()

    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        console.print("[red]Telegram not configured.[/red]")
        console.print("\nRun: [bold]python scripts/setup_telegram.py[/bold]")
        raise typer.Exit(1)

    config = Config.from_env()
    telegram = TelegramNotifier(config)

    console.print("[yellow]Sending test alerts...[/yellow]\n")

    # Test 1: LP Added alert
    console.print("Sending LP Added test...")
    lp_alert = Alert(
        type=AlertType.LP_ADD,
        chain="solana",
        pair="BONK/SOL",
        value_sol=1250.0,
        value_usd=187500.0,
        triggered_at=datetime.utcnow(),
    )
    telegram.send_alert(lp_alert)

    # Test 2: Volume Spike alert
    console.print("Sending Volume Spike test...")
    volume_alert = Alert(
        type=AlertType.VOLUME_SPIKE,
        chain="solana",
        pair="WIF/SOL",
        value_sol=5000.0,
        value_usd=750000.0,
        triggered_at=datetime.utcnow(),
    )
    telegram.send_alert(volume_alert)

    # Test 3: LP Removed alert
    console.print("Sending LP Removed test...")
    remove_alert = Alert(
        type=AlertType.LP_REMOVE,
        chain="solana",
        pair="MYRO/SOL",
        value_sol=800.0,
        value_usd=120000.0,
        triggered_at=datetime.utcnow(),
    )
    telegram.send_alert(remove_alert)

    # Test 4: Weekly review
    console.print("Sending weekly review test...")
    from journaltx.review.weekly import format_weekly_review

    review = format_weekly_review(config, days=7)
    telegram.send_message(review)

    console.print("\n[green]✓ All test notifications sent![/green]")
    console.print("Check your Telegram app.")


@app.command()
def custom(
    pair: str = typer.Option("TOKEN/SOL", "--pair", "-p", help="Trading pair"),
    sol: float = typer.Option(1000.0, "--sol", "-s", help="SOL amount"),
    alert_type: str = typer.Option("lp_add", "--type", "-t", help="Alert type (lp_add, lp_remove, volume_spike)"),
):
    """Send a custom test alert."""
    load_dotenv()

    if not os.getenv("TELEGRAM_BOT_TOKEN") or not os.getenv("TELEGRAM_CHAT_ID"):
        console.print("[red]Telegram not configured.[/red]")
        console.print("\nRun: [bold]python scripts/setup_telegram.py[/bold]")
        raise typer.Exit(1)

    config = Config.from_env()
    telegram = TelegramNotifier(config)

    # Map type
    type_map = {
        "lp_add": AlertType.LP_ADD,
        "lp_remove": AlertType.LP_REMOVE,
        "volume_spike": AlertType.VOLUME_SPIKE,
    }
    alert_type_enum = type_map.get(alert_type, AlertType.LP_ADD)

    # Create alert
    alert = Alert(
        type=alert_type_enum,
        chain="solana",
        pair=pair.upper(),
        value_sol=sol,
        value_usd=sol * 150.0,  # Approximate
        triggered_at=datetime.utcnow(),
    )

    console.print(f"[yellow]Sending {alert_type} alert for {pair}...[/yellow]")
    telegram.send_alert(alert)
    console.print("[green]✓ Test alert sent![/green]")


if __name__ == "__main__":
    app()
