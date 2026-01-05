#!/usr/bin/env python3
"""
Profile management CLI.

View and switch between trading profiles.
"""

import sys
import re
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import typer

app = typer.Typer(help="JournalTX Profile Management")


@app.command()
def current():
    """Show current profile settings."""
    from dotenv import load_dotenv
    from journaltx.core.config import Config

    load_dotenv()
    config = Config.from_env()

    typer.echo(config.get_filter_summary())


@app.command()
def list():
    """List all available profiles."""
    from journaltx.core.config import Config

    profiles_dir = Path("config/profiles")
    filters_dir = Path("config/filters")

    typer.secho("\n📊 Available Profiles:", bold=True)
    typer.echo("─" * 50)

    for profile_file in sorted(profiles_dir.glob("*.json")):
        profile_name = profile_file.stem
        try:
            profile_data = Config._load_json(profile_file)
            name = profile_data.get("name", profile_name)
            desc = profile_data.get("description", "")
            filters = profile_data.get("filters", {})

            typer.echo(f"\n{profile_name}")
            typer.echo(f"  Name: {name}")
            typer.echo(f"  Description: {desc}")
            typer.echo(f"  LP Min: {filters.get('lp_add_min_sol', 0):,.0f} SOL (~${filters.get('lp_add_min_usd', 0):,.0f})")
            typer.echo(f"  Max Trades/Day: {filters.get('max_trades_per_day', 0)}")
        except Exception as e:
            typer.echo(f"\n{profile_name} (error loading: {e})")

    typer.secho("\n\n🔍 Available Filters:", bold=True)
    typer.echo("─" * 50)

    for filter_file in sorted(filters_dir.glob("*.json")):
        filter_name = filter_file.stem
        try:
            filter_data = Config._load_json(filter_file)
            name = filter_data.get("name", filter_name)
            desc = filter_data.get("description", "")
            max_mc = filter_data.get("max_market_cap", 0)
            legacy = filter_data.get("legacy_memes", [])

            typer.echo(f"\n{filter_name}")
            typer.echo(f"  Name: {name}")
            typer.echo(f"  Description: {desc}")
            typer.echo(f"  Max Market Cap: ${max_mc/1_000_000:,.0f}M")
            typer.echo(f"  Legacy Memes Excluded: {len(legacy)}")
        except Exception as e:
            typer.echo(f"\n{filter_name} (error loading: {e})")

    typer.echo("\n")


@app.command()
def switch(
    profile: str = typer.Argument(..., help="Profile name (conservative, balanced, aggressive, degens_only)"),
    filter: str = typer.Option(None, help="Filter name (default, or custom)"),
):
    """Switch to a different profile (updates .env file)."""
    from dotenv import load_dotenv

    load_dotenv()
    env_path = Path(".env")

    if not env_path.exists():
        typer.secho("Error: .env file not found!", fg=typer.colors.RED)
        raise typer.Exit(1)

    # Validate profile exists
    profile_path = Path(f"config/profiles/{profile}.json")
    if not profile_path.exists():
        typer.secho(f"Error: Profile '{profile}' not found!", fg=typer.colors.RED)
        typer.echo("Run: python scripts/profile.py list")
        raise typer.Exit(1)

    # Read .env
    content = env_path.read_text()

    # Update PROFILE_TEMPLATE
    if "PROFILE_TEMPLATE=" in content:
        content = re.sub(r"PROFILE_TEMPLATE=.*", f"PROFILE_TEMPLATE={profile}", content)
    else:
        content += f"\nPROFILE_TEMPLATE={profile}\n"

    # Update FILTER_TEMPLATE if provided
    if filter:
        filter_path = Path(f"config/filters/{filter}.json")
        if not filter_path.exists():
            typer.secho(f"Error: Filter '{filter}' not found!", fg=typer.colors.RED)
            typer.echo("Run: python scripts/profile.py list")
            raise typer.Exit(1)

        if "FILTER_TEMPLATE=" in content:
            content = re.sub(r"FILTER_TEMPLATE=.*", f"FILTER_TEMPLATE={filter}", content)
        else:
            content += f"FILTER_TEMPLATE={filter}\n"

    # Write back
    env_path.write_text(content)

    # Update environment variables so Config.from_env() sees the new values
    import os
    os.environ["PROFILE_TEMPLATE"] = profile
    if filter:
        os.environ["FILTER_TEMPLATE"] = filter

    typer.secho(f"✓ Switched to profile: {profile}", fg=typer.colors.GREEN)
    if filter:
        typer.secho(f"✓ Switched to filter: {filter}", fg=typer.colors.GREEN)

    typer.echo("\nNew settings:")
    # Reload config to show new settings
    from journaltx.core.config import Config
    config = Config.from_env()
    typer.echo(config.get_filter_summary())


if __name__ == "__main__":
    app()
