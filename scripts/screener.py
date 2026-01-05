#!/usr/bin/env python3
"""
Screener script.

Shows historical alerts for review.
Never suggests trades.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console

from journaltx.core.config import Config
from journaltx.review.screener import print_screener

app = typer.Typer(help="Screener for historical alerts")
console = Console()


@app.command()
def main(
    hours: int = typer.Option(24, "--hours", "-h", help="Hours to look back"),
    type: str = typer.Option(None, "--type", "-t", help="Filter by type (lp_add, lp_remove, volume_spike)"),
    min_sol: float = typer.Option(None, "--min-sol", "-m", help="Minimum SOL amount"),
):
    """
    Screen alerts from the past N hours.

    Example:
        python scripts/screener.py --last 24h --type lp_add --min-sol 500
    """
    config = Config.from_env()

    print_screener(config, hours, type, min_sol)


if __name__ == "__main__":
    app()
