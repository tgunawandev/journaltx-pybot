#!/usr/bin/env python3
"""
Weekly review script.

Shows behavioral metrics and suggests ONE change for next week.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console

from journaltx.core.config import Config
from journaltx.review.weekly import print_weekly_review, export_weekly_review

app = typer.Typer(help="Weekly review")
console = Console()


@app.command()
def main(
    days: int = typer.Option(7, "--days", "-d", help="Number of days to review"),
    export: bool = typer.Option(False, "--export", "-e", help="Export to file"),
    telegram: bool = typer.Option(False, "--telegram", "-t", help="Send to Telegram"),
):
    """
    Generate weekly review.

    Shows trades, win rate, discipline metrics, and suggests ONE change.
    """
    config = Config.from_env()

    review_text = format_weekly_review(config, days)

    if export:
        filepath = export_weekly_review(config, days)
        console.print(f"[green]Review exported to {filepath}[/green]")
    elif telegram:
        from journaltx.notify.telegram import TelegramNotifier
        telegram_notifier = TelegramNotifier(config)
        if telegram_notifier.send_message(review_text):
            console.print("[green]Review sent to Telegram[/green]")
        else:
            console.print("[yellow]Telegram send failed, printing to console[/yellow]\n")
            print(review_text)
    else:
        print(review_text)


if __name__ == "__main__":
    app()
