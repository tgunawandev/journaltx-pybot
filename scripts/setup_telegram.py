#!/usr/bin/env python3
"""
Telegram Bot Setup Helper

Guides you through creating and configuring a Telegram bot for JournalTX.
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

app = typer.Typer(help="Setup Telegram bot for JournalTX")
console = Console()


def print_step(step: int, title: str):
    """Print a step header."""
    rprint(f"\n[bold cyan]Step {step}: {title}[/bold cyan]")


def check_token(token: str) -> bool:
    """Verify if bot token is valid."""
    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=10)
        data = response.json()

        if data.get("ok"):
            bot_info = data["result"]
            console.print(f"[green]✓ Bot connected: @{bot_info.get('username')}[/green]")
            console.print(f"  Bot name: {bot_info.get('first_name')}")
            return True
        else:
            console.print(f"[red]✗ Invalid token: {data.get('description')}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error checking token: {e}[/red]")
        return False


def get_chat_id(token: str) -> str:
    """Get chat ID by checking bot updates."""
    console.print("\n[yellow]Getting your Chat ID...[/yellow]")
    console.print("1. [bold]Open Telegram and message your bot[/bold]")
    console.print("   Send any message: /start")
    console.print("\n2. [bold]Wait 10 seconds, then press Enter[/bold]")

    input("\n   Press Enter after sending message...")

    try:
        response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=10)
        data = response.json()

        if data.get("ok") and data.get("result"):
            # Get the most recent message
            latest = data["result"][-1]
            chat_id = latest["message"]["chat"]["id"]
            chat_username = latest["message"]["chat"].get("username", "N/A")

            console.print(f"[green]✓ Chat ID found: {chat_id}[/green]")
            console.print(f"  Username: @{chat_username}")
            return str(chat_id)
        else:
            console.print("[red]✗ No messages found. Did you message your bot?[/red]")
            return None
    except Exception as e:
        console.print(f"[red]✗ Error getting updates: {e}[/red]")
        return None


def send_test_message(token: str, chat_id: str) -> bool:
    """Send a test message to verify setup."""
    console.print("\n[yellow]Sending test message...[/yellow]")

    message = """JournalTX Setup Test

This is a test message from your JournalTX bot.

If you see this, Telegram is configured correctly!"""

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "None",
            },
            timeout=10,
        )
        data = response.json()

        if data.get("ok"):
            console.print("[green]✓ Test message sent![/green]")
            console.print("  Check your Telegram app.")
            return True
        else:
            console.print(f"[red]✗ Failed: {data.get('description')}[/red]")
            return False
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False


def update_env_file(token: str, chat_id: str):
    """Update .env file with Telegram credentials."""
    env_path = Path(__file__).parent.parent / ".env"

    try:
        # Read existing file
        lines = env_path.read_text().splitlines()

        # Update or add Telegram credentials
        updated = []
        token_added = False
        chat_added = False

        for line in lines:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                updated.append(f"TELEGRAM_BOT_TOKEN={token}")
                token_added = True
            elif line.startswith("TELEGRAM_CHAT_ID="):
                updated.append(f"TELEGRAM_CHAT_ID={chat_id}")
                chat_added = True
            else:
                updated.append(line)

        # Add if not present
        if not token_added:
            updated.append(f"TELEGRAM_BOT_TOKEN={token}")
        if not chat_added:
            updated.append(f"TELEGRAM_CHAT_ID={chat_id}")

        # Write back
        env_path.write_text("\n".join(updated))

        console.print(f"[green]✓ Updated {env_path}[/green]")
        return True

    except Exception as e:
        console.print(f"[red]✗ Error updating .env: {e}[/red]")
        return False


@app.command()
def main():
    """Interactive Telegram bot setup."""
    console.print(Panel.fit(
        "[bold cyan]JournalTX Telegram Bot Setup[/bold cyan]\n\n"
        "This helper will guide you through creating and\n"
        "configuring a Telegram bot for alerts.",
        border_style="cyan"
    ))

    # Step 1: Create bot
    print_step(1, "Create Your Telegram Bot")
    console.print("\n1. Open Telegram and search for [bold]@BotFather[/bold]")
    console.print("2. Start a chat and send: [bold]/newbot[/bold]")
    console.print("3. Follow the prompts:")
    console.print("   - Choose a name (e.g., JournalTX Bot)")
    console.print("   - Choose a username (e.g., journaltx_mybot)")
    console.print("4. Copy the [bold]Bot Token[/bold] provided")

    console.print(Panel(
        "Example token:\n"
        "[dim]1234567890:ABCdefGHIjklMNOpqrsTUVwxyz[/dim]\n\n"
        "It looks like: numbers:letters",
        title="[bold]Bot Token Format[/bold]",
        border_style="dim"
    ))

    # Step 2: Enter token
    print_step(2, "Enter Your Bot Token")
    bot_token = Prompt.ask("Paste your bot token here", console=console)

    # Validate token
    console.print("\n[yellow]Validating token...[/yellow]")
    if not check_token(bot_token):
        if not Confirm.ask("\nWould you like to try again?", console=console):
            raise typer.Exit(1)
        bot_token = Prompt.ask("Paste your bot token again", console=console)
        if not check_token(bot_token):
            console.print("[red]Token validation failed. Exiting.[/red]")
            raise typer.Exit(1)

    # Step 3: Get chat ID
    print_step(3, "Get Your Chat ID")
    chat_id = get_chat_id(bot_token)

    if not chat_id:
        if not Confirm.ask("\nWould you like to try again?", console=console):
            raise typer.Exit(1)
        chat_id = get_chat_id(bot_token)

    # Step 4: Test message
    print_step(4, "Test Configuration")
    if not send_test_message(bot_token, chat_id):
        console.print("[red]Test failed. Please check your settings.[/red]")
        raise typer.Exit(1)

    # Step 5: Save to .env
    print_step(5, "Save Configuration")
    if Confirm.ask("Save to .env file?", console=console, default=True):
        update_env_file(bot_token, chat_id)
    else:
        console.print("\n[yellow]Skipped saving.[/yellow]")
        console.print("\nAdd these to your .env file manually:")
        console.print(f"  TELEGRAM_BOT_TOKEN={bot_token}")
        console.print(f"  TELEGRAM_CHAT_ID={chat_id}")

    # Done
    console.print("\n")
    console.print(Panel.fit(
        "[bold green]Telegram Setup Complete![/bold green]\n\n"
        "You will now receive alerts for:\n"
        "• LP Additions (≥ threshold)\n"
        "• LP Removals (≥ threshold)\n"
        "• Volume Spikes (≥ baseline)\n\n"
        "Run: [dim]python scripts/test_telegram.py[/dim] to verify",
        border_style="green"
    ))


@app.command()
def verify():
    """Verify existing Telegram configuration."""
    from dotenv import load_dotenv
    import os

    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        console.print("[red]Telegram not configured in .env[/red]")
        console.print("\nRun: [bold]python scripts/setup_telegram.py[/bold]")
        raise typer.Exit(1)

    console.print("[yellow]Verifying Telegram configuration...[/yellow]\n")

    if not check_token(token):
        raise typer.Exit(1)

    if not send_test_message(token, chat_id):
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
