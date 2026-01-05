#!/usr/bin/env python3
"""
Interactive setup wizard for JournalTX.

Guides users through initial configuration with validation.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import print as rprint

app = typer.Typer(help="Interactive setup wizard")
console = Console()


def test_quicknode(http_url: str) -> bool:
    """Test QuickNode connection."""
    try:
        response = requests.post(
            http_url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getHealth",
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("result") == "ok":
            return True
        return False

    except Exception:
        return False


def test_telegram(bot_token: str, chat_id: str) -> bool:
    """Test Telegram bot connection."""
    try:
        # Test bot info
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            return False

        # Send test message
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "JournalTX\n\n✓ Setup test successful!",
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("ok", False)

    except Exception:
        return False


@app.command()
def main(
    quicknode_ws: str = typer.Option("", "--quicknode-ws", help="QuickNode WebSocket URL"),
    quicknode_http: str = typer.Option("", "--quicknode-http", help="QuickNode HTTP URL"),
    telegram_token: str = typer.Option("", "--telegram-token", help="Telegram bot token"),
    telegram_chat: str = typer.Option("", "--telegram-chat", help="Telegram chat ID"),
    profile: str = typer.Option("balanced", "--profile", help="Threshold profile"),
):
    """
    Run interactive setup wizard.

    Prompts for configuration if values not provided via CLI.
    """
    console.print(Panel.fit(
        "[bold cyan]JournalTX Setup Wizard[/bold cyan]\n\n"
        "This wizard will guide you through configuration.\n"
        "Press Ctrl+C at any time to cancel.",
        border_style="cyan"
    ))

    rprint("")

    # QuickNode setup
    console.print("[bold yellow]Step 1/3: QuickNode Configuration[/bold yellow]\n")

    if not quicknode_ws or not quicknode_http:
        console.print("QuickNode provides Solana RPC endpoints.")
        console.print("Get a free endpoint at: https://www.quicknode.com")
        console.print("")

        if not quicknode_http:
            quicknode_http = Prompt.ask(
                "QuickNode HTTP URL",
                default="https://your-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY/",
                console=console,
            )

        if not quicknode_ws:
            quicknode_ws = Prompt.ask(
                "QuickNode WebSocket URL",
                default="wss://your-endpoint.solana-mainnet.quiknode.pro/YOUR_KEY/",
                console=console,
            )

    # Test QuickNode
    console.print("\n[yellow]Testing QuickNode connection...[/yellow]")
    if test_quicknode(quicknode_http):
        console.print("[green]✓ QuickNode connection successful[/green]")
    else:
        if not Confirm.ask("\nQuickNode test failed. Continue anyway?", console=console):
            raise typer.Exit(1)

    # Telegram setup
    console.print("\n")
    console.print("[bold yellow]Step 2/3: Telegram Configuration[/bold yellow]\n")

    if not telegram_token:
        console.print("Create a Telegram bot:")
        console.print("1. Open Telegram and search @BotFather")
        console.print("2. Send: /newbot")
        console.print("3. Follow prompts and copy the bot token")
        console.print("")

        telegram_token = Prompt.ask(
            "Telegram Bot Token",
            default="123456:ABC-DEF...",
            console=console,
        )

    if not telegram_chat:
        console.print("\nGet your Chat ID:")
        console.print("1. Add bot to your Telegram group")
        console.print("2. Make bot admin")
        console.print("3. Send: /start in the group")
        console.print("4. Run: venv/bin/python scripts/get_chat_id.py")
        console.print("")

        telegram_chat = Prompt.ask(
            "Telegram Chat ID",
            default="-1001234567890",
            console=console,
        )

    # Test Telegram
    console.print("\n[yellow]Testing Telegram connection...[/yellow]")
    if test_telegram(telegram_token, telegram_chat):
        console.print("[green]✓ Telegram connection successful[/green]")
    else:
        if not Confirm.ask("\nTelegram test failed. Continue anyway?", console=console):
            raise typer.Exit(1)

    # Profile selection
    console.print("\n")
    console.print("[bold yellow]Step 3/3: Threshold Profile[/bold yellow]\n")

    from journaltx.core.profiles import ProfileManager, BUILT_IN_PROFILES

    manager = ProfileManager()

    console.print("Choose your trading style:\n")
    for name, prof in BUILT_IN_PROFILES.items():
        console.print(f"  [cyan]{name}[/cyan] - {prof.description}")

    console.print("")
    profile = Prompt.ask(
        "Select profile",
        default=profile,
        choices=list(BUILT_IN_PROFILES.keys()),
        console=console,
    )

    selected_profile = manager.get_profile(profile)

    console.print(f"\n[green]✓ Selected: {selected_profile.name}[/green]")
    console.print(f"  LP Add Min: {selected_profile.lp_add_min_sol:,.0f} SOL (~${selected_profile.lp_add_min_usd:,.0f})")
    console.print(f"  Max Trades/Day: {selected_profile.max_trades_per_day}")

    # Write to .env
    console.print("\n")
    if Confirm.ask("Save configuration to .env file?", console=console, default=True):
        env_path = Path(__file__).parent.parent / ".env"

        env_content = f"""# JournalTX Configuration
# Generated by setup wizard

# Database
JOURNALTX_DB_PATH=data/journaltx.db

# QuickNode
QUICKNODE_WS_URL={quicknode_ws}
QUICKNODE_HTTP_URL={quicknode_http}

# Telegram
TELEGRAM_BOT_TOKEN={telegram_token}
TELEGRAM_CHAT_ID={telegram_chat}

# Active Profile
JOURNALTX_PROFILE={profile}

# Alert Thresholds (from {selected_profile.name} profile)
LP_ADD_MIN_SOL={selected_profile.lp_add_min_sol}
LP_ADD_MIN_USD={selected_profile.lp_add_min_usd}
LP_REMOVE_MIN_PCT={selected_profile.lp_remove_min_pct}
VOLUME_SPIKE_MULTIPLIER={selected_profile.volume_spike_multiplier}
MAX_TRADES_PER_DAY={selected_profile.max_trades_per_day}
"""

        env_path.write_text(env_content)
        console.print(f"\n[green]✓ Configuration saved to {env_path}[/green]")

    console.print("\n")
    console.print(Panel.fit(
        "[bold green]Setup Complete![/bold green]\n\n"
        "Next steps:\n"
        "1. Initialize database:\n"
        "   [dim]python -c \"from journaltx.core.db import init_db; from journaltx.core.config import Config; init_db(Config.from_env())\"[/dim]\n\n"
        "2. Test alerts:\n"
        "   [dim]venv/bin/python scripts/test_telegram.py[/dim]\n\n"
        "3. Start listener:\n"
        "   [dim]venv/bin/python scripts/listen.py[/dim]",
        border_style="green"
    ))


@app.command()
def validate():
    """Validate existing configuration."""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    console.print("[bold]Validating Configuration...[/bold]\n")

    # Check QuickNode
    quicknode = os.getenv("QUICKNODE_HTTP_URL")
    if quicknode:
        console.print("QuickNode:", end=" ")
        if test_quicknode(quicknode):
            console.print("[green]✓ OK[/green]")
        else:
            console.print("[red]✗ Failed[/red]")
    else:
        console.print("QuickNode: [yellow]Not configured[/yellow]")

    # Check Telegram
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        console.print("Telegram:", end=" ")
        if test_telegram(token, chat):
            console.print("[green]✓ OK[/green]")
        else:
            console.print("[red]✗ Failed[/red]")
    else:
        console.print("Telegram: [yellow]Not configured[/yellow]")

    # Check profile
    from journaltx.core.profiles import ProfileManager

    manager = ProfileManager()
    active = manager.get_active_profile_name()

    try:
        profile = manager.get_profile(active)
        console.print(f"Profile: [green]✓ {profile.name}[/green]")
    except ValueError:
        console.print(f"Profile: [red]✗ Unknown: {active}[/red]")

    # Check database
    db_path = Path(os.getenv("JOURNALTX_DB_PATH", "data/journaltx.db"))
    if db_path.exists():
        console.print(f"Database: [green]✓ Exists[/green]")
    else:
        console.print("Database: [yellow]Not initialized[/yellow]")
        console.print("  Run: [dim]python -c \"from journaltx.core.db import init_db; from journaltx.core.config import Config; init_db(Config.from_env())\"[/dim]")


if __name__ == "__main__":
    app()
