#!/usr/bin/env python3
"""
QuickNode WebSocket listener.

Connects to QuickNode and monitors for LP and volume events.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
from datetime import datetime

import websockets
from typer import Typer, Option
from rich.console import Console

from journaltx.core.config import Config
from journaltx.ingest.quicknode.lp_events import LPEventListener
from journaltx.ingest.quicknode.volume_events import VolumeEventListener
from journaltx.notify.telegram import TelegramNotifier

app = Typer(help="QuickNode WebSocket listener")
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@app.command()
def main(
    test: bool = Option(False, "--test", "-t", help="Test mode (single message)"),
):
    """
    Connect to QuickNode WebSocket and listen for events.

    Requires QUICKNODE_WS_URL in .env or environment.
    """
    config = Config.from_env()

    if not config.quicknode_ws_url:
        console.print("[red]QUICKNODE_WS_URL not configured.[/red]")
        console.print("\nSet it in .env file:")
        console.print("QUICKNODE_WS_URL=wss://your-quicknode-url")
        raise typer.Exit(1)

    # Initialize listeners
    lp_listener = LPEventListener(config)
    volume_listener = VolumeEventListener(config)

    # Initialize Telegram if configured
    telegram = None
    if config.telegram_bot_token and config.telegram_chat_id:
        telegram = TelegramNotifier(config)
        console.print("[green]Telegram notifications enabled[/green]\n")

    async def on_message(ws_message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(ws_message)

            # Parse based on QuickNode subscription format
            # This is a simplified example - adjust based on actual QuickNode schema
            if "params" in data and "result" in data["params"]:
                result = data["params"]["result"]

                # Detect LP events
                if "liquidity" in str(result).lower():
                    # Extract LP event data
                    # Format varies by subscription type
                    pass

                # Detect volume events
                if "volume" in str(result).lower() or "swaps" in str(result).lower():
                    # Extract volume event data
                    pass

        except Exception as e:
            logging.error(f"Error processing message: {e}")

    async def connect_and_listen():
        """Connect to WebSocket and listen."""
        console.print(f"[bold]Connecting to QuickNode...[/bold]\n")
        console.print(f"URL: {config.quicknode_ws_url}\n")

        try:
            async with websockets.connect(config.quicknode_ws_url) as ws:
                console.print("[green]Connected. Listening for events...[/green]\n")
                console.print("[dim]Press Ctrl+C to stop[/dim]\n")

                # Send subscription (example)
                # Adjust based on your QuickNode subscription format
                # await ws.send(json.dumps({...}))

                # Listen for messages
                if test:
                    # Test mode - wait for one message
                    message = await ws.recv()
                    await on_message(message)
                    console.print("[yellow]Test mode: received one message[/yellow]")
                else:
                    # Continuous mode
                    async for message in ws:
                        await on_message(message)

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Stopping listener...[/yellow]")
        except Exception as e:
            console.print(f"[red]Connection error: {e}[/red]")
            raise

    # Run async
    asyncio.run(connect_and_listen())


if __name__ == "__main__":
    app()
