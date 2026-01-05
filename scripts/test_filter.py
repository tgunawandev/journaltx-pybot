#!/usr/bin/env python3
"""
Test market cap filter.

Demonstrates how the early meme coin filter works.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from journaltx.core.config import Config
from journaltx.filters.market_cap import is_early_meme_coin, check_dexscreener

load_dotenv()
console = Console()


def test_filter():
    """Test market cap filter on example coins."""
    config = Config.from_env()

    # Test coins
    test_pairs = [
        ("BONK/SOL", "Established coin - $1B+ market cap"),
        ("PEPE/SOL", "Established coin - $3B+ market cap"),
        ("WIF/SOL", "Established coin - $2B+ market cap"),
        ("NEWCOIN/SOL", "Hypothetical new coin"),
    ]

    console.print("\n[bold cyan]Early Meme Coin Filter Test[/bold cyan]\n")
    console.print(f"Max Market Cap: ${config.max_market_cap:,.0f}")
    console.print(f"Max Pair Age: {config.max_pair_age_hours} hours\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Pair", style="cyan")
    table.add_column("Expected", style="yellow")
    table.add_column("Market Cap", justify="right", style="green")
    table.add_column("Pair Age", justify="right")
    table.add_column("Result", style="bold")

    for pair, description in test_pairs:
        console.print(f"\n[bold]Testing: {pair}[/bold]")
        console.print(f"Description: {description}")

        is_early, data = is_early_meme_coin(
            pair,
            max_market_cap=config.max_market_cap,
            max_pair_age_hours=config.max_pair_age_hours
        )

        if data:
            market_cap = data.get("market_cap", 0)
            pair_created = data.get("pair_created_at")

            if pair_created:
                from datetime import datetime, timedelta
                pair_age = datetime.now() - datetime.fromtimestamp(pair_created / 1000)
                age_str = str(pair_age).split(".")[0]
            else:
                age_str = "Unknown"

            result = "[green]✓ PASS[/green]" if is_early else "[red]✗ REJECT[/red]"
            expected = "PASS" if "NEWCOIN" in pair else "REJECT"

            table.add_row(
                pair,
                expected,
                f"${market_cap:,.0f}",
                age_str,
                result
            )
        else:
            table.add_row(
                pair,
                "?",
                "N/A",
                "N/A",
                "[yellow]? UNKNOWN[/yellow]"
            )

    console.print("\n")
    console.print(table)
    console.print("\n[dim]Filter ensures only early meme coins trigger alerts[/dim]\n")


if __name__ == "__main__":
    test_filter()
