#!/usr/bin/env python3
"""
Get Telegram Chat ID (Personal or Group).

Run this after adding your bot to a group or messaging it.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv
import os

console = Console()
load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

console.print(Panel.fit(
    "[bold cyan]Get Telegram Chat ID[/bold cyan]\n\n"
    "Choose one option:\n"
    "1. [bold]Personal Chat[/bold] - Message bot directly\n"
    "2. [bold]Group Chat[/bold] - Add bot to a group",
    border_style="cyan"
))

console.print("\n[yellow]Which type of chat ID do you want?[/yellow]")
choice = console.input("Enter [bold]1[/bold] for personal or [bold]2[/bold] for group: ").strip()

if choice == "1":
    # Personal chat
    console.print("\n[bold]Personal Chat Setup:[/bold]")
    console.print("1. Open Telegram")
    console.print(f"2. Search for your bot (token: {token[:10]}...)")
    console.print("3. Send: /start")
    console.print("\n[dim]Press Enter after sending message...[/dim]")
    input()

elif choice == "2":
    # Group chat
    console.print("\n[bold]Group Chat Setup:[/bold]")
    console.print("1. Open Telegram")
    console.print("2. Create a new group or open existing group")
    console.print("3. Add your bot to the group:")
    console.print("   - Group name → Add members → Search bot")
    console.print("   - Or: https://t.me/<bot_username>")
    console.print("4. Send a message in the group (any message)")
    console.print("   - Mention the bot: @your_bot hello")
    console.print("   - Or just send: /start")
    console.print("\n[dim]Press Enter after sending message...[/dim]")
    input()
else:
    console.print("[red]Invalid choice. Exiting.[/red]")
    sys.exit(1)

try:
    console.print("\n[yellow]Fetching Chat ID...[/yellow]")

    response = requests.get(f"https://api.telegram.org/bot{token}/getUpdates")
    data = response.json()

    if data.get("ok") and data.get("result"):
        # Show all recent chats
        console.print("\n[bold]Recent chats found:[/bold]\n")

        chats = {}
        for update in data["result"]:
            if "message" in update:
                chat = update["message"]["chat"]
                chat_id = chat["id"]
                chat_type = chat.get("type", "unknown")

                if chat_type == "private":
                    name = chat.get("first_name", "Unknown")
                    identifier = f"Personal: {name}"
                elif chat_type == "group":
                    name = chat.get("title", "Unknown Group")
                    identifier = f"Group: {name}"
                elif chat_type == "supergroup":
                    name = chat.get("title", "Unknown SuperGroup")
                    identifier = f"SuperGroup: {name}"
                else:
                    identifier = f"Chat ID {chat_id}"

                chats[chat_id] = identifier

        # Display unique chats
        seen = set()
        for chat_id, identifier in chats.items():
            if identifier not in seen:
                console.print(f"  [cyan]{chat_id}[/cyan] - {identifier}")
                seen.add(identifier)

        # Get the most recent one
        latest = data["result"][-1]
        chat_id = latest["message"]["chat"]["id"]
        chat_type = latest["message"]["chat"].get("type", "unknown")

        if chat_type == "private":
            name = latest["message"]["chat"].get("first_name", "Unknown")
            console.print(f"\n[green]Selected: Personal chat - {name}[/green]")
        else:
            name = latest["message"]["chat"].get("title", "Unknown")
            console.print(f"\n[green]Selected: Group - {name}[/green]")

        console.print(f"[green]Chat ID: {chat_id}[/green]")

        # Confirm
        confirm = console.input("\n[bold]Use this Chat ID?[/bold] [Y/n]: ").strip().lower()
        if confirm and confirm[0] == 'n':
            console.print("[yellow]Cancelled. You can manually set TELEGRAM_CHAT_ID in .env[/yellow]")
            sys.exit(0)

        # Update .env
        env_path = Path(__file__).parent.parent / ".env"
        lines = env_path.read_text().splitlines()
        updated = []
        updated_chat = False

        for line in lines:
            if line.startswith("TELEGRAM_CHAT_ID="):
                updated.append(f"TELEGRAM_CHAT_ID={chat_id}")
                updated_chat = True
            else:
                updated.append(line)

        if not updated_chat:
            updated.append(f"TELEGRAM_CHAT_ID={chat_id}")

        env_path.write_text("\n".join(updated))
        console.print(f"\n[green]✓ Saved to .env[/green]")

        # Test message
        console.print("\n[yellow]Sending test message...[/yellow]")
        test_response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": "JournalTX\n\n✓ Telegram is now configured!\n\nYou will receive alerts here.",
            },
        )
        if test_response.json().get("ok"):
            console.print("[green]✓ Test message sent![/green]")
            console.print("\nCheck your Telegram (personal chat or group).")
        else:
            error = test_response.json().get("description", "Unknown error")
            console.print(f"[red]✗ Test failed: {error}[/red]")
    else:
        console.print("[red]No messages found.[/red]")
        console.print("\nDid you:")
        if choice == "1":
            console.print("- Message the bot directly with /start?")
        else:
            console.print("- Add the bot to the group?")
            console.print("- Send a message in the group mentioning the bot?")

except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
