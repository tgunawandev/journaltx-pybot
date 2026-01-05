#!/usr/bin/env python3
"""
Profile management CLI.

Manage threshold profiles for different trading styles.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer
from rich.console import Console
from rich.table import Table

from journaltx.core.config import Config
from journaltx.core.profiles import ProfileManager, BUILT_IN_PROFILES

app = typer.Typer(help="Manage threshold profiles")
console = Console()


@app.command()
def list():
    """List all available profiles."""
    manager = ProfileManager()
    profiles = manager.list_profiles()

    console.print("\n[bold]Available Profiles:[/bold]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("LP Min (SOL)", justify="right")
    table.add_column("LP Min ($)", justify="right")
    table.add_column("Max Trades/Day", justify="right")

    for p in profiles:
        # Mark built-in profiles
        name_mark = f"{p.name} *" if p.name in BUILT_IN_PROFILES else p.name
        table.add_row(
            name_mark,
            p.description,
            f"{p.lp_add_min_sol:,.0f}",
            f"${p.lp_add_min_usd:,.0f}",
            str(p.max_trades_per_day),
        )

    console.print(table)
    console.print("\n[dim]* Built-in profile[/dim]")


@app.command()
def switch(
    profile_name: str = typer.Argument(..., help="Profile name to switch to"),
):
    """
    Switch active profile.

    Updates JOURNALTX_PROFILE in .env file.
    """
    manager = ProfileManager()

    try:
        profile = manager.get_profile(profile_name)

        # Update .env file
        env_path = Path(__file__).parent.parent / ".env"
        env_lines = env_path.read_text().splitlines()

        # Update or add JOURNALTX_PROFILE
        updated = []
        profile_updated = False

        for line in env_lines:
            if line.startswith("JOURNALTX_PROFILE="):
                updated.append(f'JOURNALTX_PROFILE={profile_name}')
                profile_updated = True
            else:
                updated.append(line)

        if not profile_updated:
            updated.append(f'JOURNALTX_PROFILE={profile_name}')

        env_path.write_text("\n".join(updated))

        console.print(f"\n[green]✓ Switched to profile: {profile_name}[/green]\n")
        console.print(f"[bold]{profile.description}[/bold]\n")
        console.print("Thresholds:")
        console.print(f"  • LP Add Min: {profile.lp_add_min_sol:,.0f} SOL (~${profile.lp_add_min_usd:,.0f})")
        console.print(f"  • LP Remove Min: {profile.lp_remove_min_pct:.0f}%")
        console.print(f"  • Volume Spike: {profile.volume_spike_multiplier}x baseline")
        console.print(f"  • Max Trades/Day: {profile.max_trades_per_day}\n")
        console.print("Restart the listener to apply changes.")

    except ValueError as e:
        console.print(f"\n[red]✗ {e}[/red]")
        console.print("\nRun: [bold]journaltx-profile list[/bold] to see available profiles")


@app.command()
def current():
    """Show currently active profile."""
    manager = ProfileManager()
    active_name = manager.get_active_profile_name()

    try:
        profile = manager.get_profile(active_name)

        console.print(f"\n[bold]Active Profile:[/bold] {profile.name}\n")
        console.print(f"{profile.description}\n")
        console.print("Thresholds:")
        console.print(f"  • LP Add Min: {profile.lp_add_min_sol:,.0f} SOL (~${profile.lp_add_min_usd:,.0f})")
        console.print(f"  • LP Remove Min: {profile.lp_remove_min_pct:.0f}%")
        console.print(f"  • Volume Spike: {profile.volume_spike_multiplier}x baseline")
        console.print(f"  • Max Trades/Day: {profile.max_trades_per_day}\n")

    except ValueError as e:
        console.print(f"\n[red]✗ {e}[/red]")


@app.command()
def create(
    name: str = typer.Option(..., "--name", "-n", help="Profile name"),
    description: str = typer.Option(..., "--description", "-d", help="Profile description"),
    min_sol: float = typer.Option(500.0, "--min-sol", help="Min SOL for LP add"),
    min_usd: float = typer.Option(10000.0, "--min-usd", help="Min USD for LP add"),
    remove_pct: float = typer.Option(50.0, "--remove-pct", help="Min % for LP remove"),
    volume_mult: float = typer.Option(3.0, "--volume-mult", help="Volume spike multiplier"),
    max_trades: int = typer.Option(2, "--max-trades", help="Max trades per day"),
):
    """
    Create a custom profile.
    """
    manager = ProfileManager()

    try:
        profile = manager.create_profile(
            name=name,
            description=description,
            lp_add_min_sol=min_sol,
            lp_add_min_usd=min_usd,
            lp_remove_min_pct=remove_pct,
            volume_spike_multiplier=volume_mult,
            max_trades_per_day=max_trades,
        )

        console.print(f"\n[green]✓ Created profile: {name}[/green]\n")
        console.print(f"{description}\n")
        console.print("To use this profile:")
        console.print(f"  [bold]journaltx-profile switch {name}[/bold]")

    except Exception as e:
        console.print(f"\n[red]✗ Failed to create profile: {e}[/red]")


if __name__ == "__main__":
    app()
