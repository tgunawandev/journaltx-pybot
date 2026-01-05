#!/usr/bin/env python3
"""
Log a trade manually.

This is the ONLY way trades should be entered into the system.
Forces reflection and journaling.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm

from journaltx.core.config import Config
from journaltx.core.models import Trade, Journal, ContinuationQuality
from journaltx.core.db import session_scope
from journaltx.guardrails.rules import print_guardrails

app = typer.Typer(help="Log a trade manually")
console = Console()


@app.command()
def main(
    pair_base: str = typer.Option(..., "--pair", "-p", help="Base token (e.g., TOKEN)"),
    entry_price: float = typer.Option(..., "--entry", "-e", help="Entry price"),
    notes: str = typer.Option("", "--notes", "-n", help="Trade notes"),
):
    """
    Log a new trade with mandatory journaling.

    Prompts for all required information.
    """
    config = Config.from_env()

    # Print guardrails first
    console.print("\n[bold]Checking guardrails...[/bold]\n")
    print_guardrails(config)

    # Collect trade information
    console.print("\n[bold]Log Trade[/bold]\n")

    pair_quote = "SOL"  # Fixed to SOL

    # Ask journaling questions
    console.print("[yellow]Journaling Questions[/yellow]\n")

    why_enter = Prompt.ask("Why did I enter?", console=console)
    risk_defined = Confirm.ask("Was risk defined before entry?", console=console)
    scale_out = Confirm.ask("Was scale-out used?", console=console)
    invalidation = Prompt.ask("Where was invalidation?", console=console)

    rule_followed = Confirm.ask(
        "Did I follow my rules?", console=console, default=True
    )

    console.print("\n[bold]Continuation Quality:[/bold]")
    console.print("  ❌ Not justified")
    console.print("  ⚠️  Mixed")
    console.print("  ✅ Strong")

    continuation_choice = Prompt.ask(
        "Select continuation quality",
        choices=["❌", "⚠️", "✅"],
        default="⚠️",
        console=console,
    )
    continuation = ContinuationQuality(continuation_choice)

    lesson = Prompt.ask(
        "One sentence lesson:", console=console
    )

    # Build notes
    full_notes = notes or ""
    full_notes += f"\n\nWhy entered: {why_enter}"
    full_notes += f"\nRisk defined: {'Yes' if risk_defined else 'No'}"
    full_notes += f"\nScale-out: {'Yes' if scale_out else 'No'}"
    full_notes += f"\nInvalidation: {invalidation}"

    # Save trade and journal
    with session_scope(config) as session:
        trade = Trade(
            pair_base=pair_base.upper(),
            pair_quote=pair_quote,
            entry_price=entry_price,
            risk_followed=rule_followed,
            scale_out_used=scale_out,
            notes=full_notes.strip(),
            timestamp=datetime.utcnow(),
        )
        session.add(trade)
        session.flush()

        # Add journal
        journal = Journal(
            trade_id=trade.id,
            rule_followed=rule_followed,
            continuation_quality=continuation,
            lesson=lesson,
        )
        session.add(journal)

        console.print(f"\n[green]Trade #{trade.id} logged successfully.[/green]\n")


@app.command()
def exit_trade(
    trade_id: int = typer.Argument(..., help="Trade ID"),
    exit_price: float = typer.Option(..., "--price", "-p", help="Exit price"),
):
    """
    Mark a trade as closed with exit price.
    """
    config = Config.from_env()

    with session_scope(config) as session:
        trade = session.query(Trade).filter(Trade.id == trade_id).first()

        if not trade:
            console.print(f"[red]Trade #{trade_id} not found.[/red]")
            raise typer.Exit(1)

        if trade.exit_price:
            console.print(f"[yellow]Trade #{trade_id} already closed at {trade.exit_price}[/yellow]")
            raise typer.Exit(1)

        # Update trade
        trade.exit_price = exit_price

        # Calculate PnL %
        if trade.entry_price > 0:
            trade.pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * 100
        else:
            trade.pnl_pct = 0

        session.add(trade)

        pnl_str = f"+{trade.pnl_pct:.2f}%" if trade.pnl_pct >= 0 else f"{trade.pnl_pct:.2f}%"
        console.print(f"\n[green]Trade #{trade_id} closed at {exit_price} ({pnl_str})[/green]\n")


if __name__ == "__main__":
    app()
