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
from journaltx.ingest.quicknode.raydium_subscriptions import (
    get_all_dex_subscriptions,
    extract_signature_from_notification,
)
from journaltx.ingest.quicknode.transaction_parser import SolanaTransactionParser
from journaltx.notify.telegram import TelegramNotifier
import requests

app = Typer(help="QuickNode WebSocket listener")
console = Console()


def mask_url(url: str) -> str:
    """
    Mask sensitive parts of a URL for safe logging.

    Args:
        url: The URL to mask

    Returns:
        Masked URL with credentials hidden
    """
    if not url:
        return "Not configured"

    try:
        # For WebSocket URLs, mask the endpoint ID
        if "quiknode" in url.lower():
            # Extract the base and mask the unique ID
            parts = url.split("/")
            if len(parts) >= 4:
                # wss://<endpoint>.solana-mainnet.quiknode.pro/<id>/
                base = "/".join(parts[:3])
                return f"{base}/***MASKED***/"

        # For other URLs, just show protocol and domain
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/***MASKED***"

    except Exception:
        # If parsing fails, return generic mask
        return "***MASKED***"


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

    # Initialize transaction parser if QuickNode HTTP URL available
    tx_parser = None
    if config.quicknode_http_url:
        tx_parser = SolanaTransactionParser(config.quicknode_http_url)

    async def on_message(ws_message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(ws_message)

            # Check if this is a logs notification
            if "params" in data and "result" in data["params"]:
                result = data["params"]["result"]

                # Extract logs
                logs = result.get("logs", [])

                # Check if this is a liquidity addition
                if logs:
                    from journaltx.ingest.quicknode.raydium_subscriptions import is_liquidity_addition

                    if is_liquidity_addition(logs):
                        # Extract transaction signature
                        signature = extract_signature_from_notification(data)

                        if signature and tx_parser:
                            console.print(f"[yellow]Detected LP addition: {signature[:8]}...[/yellow]")

                            # Fetch full transaction
                            transaction = tx_parser.get_transaction(signature)

                            if transaction:
                                # Extract LP details
                                lp_details = tx_parser.extract_lp_addition(transaction)

                                if lp_details and lp_details.get("amount_b", 0) > 0:
                                    # Get pair name from logs or transaction
                                    # For now, use a placeholder
                                    pair = "DETECTED/SOL"

                                    # Process the LP event
                                    lp_listener.process_lp_add(
                                        token_a=lp_details.get("token_a", "UNKNOWN"),
                                        token_b=lp_details.get("token_b", "SOL"),
                                        amount_a=lp_details.get("amount_a", 0.0),
                                        amount_b=lp_details.get("amount_b", 0.0),
                                        raw_data={"signature": signature, "logs": logs},
                                        on_alert=lambda alert: handle_alert(alert, telegram)
                                    )

                        else:
                            logging.warning(f"Could not get transaction details for {signature}")

        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def handle_alert(alert, telegram_notifier):
        """Handle generated alert - send to Telegram if configured."""
        console.print(f"[green]Alert generated: {alert.pair} - {alert.value_sol:.0f} SOL[/green]")

        if telegram_notifier:
            # Send to Telegram
            telegram_notifier.send_alert(alert)

    async def connect_and_listen():
        """Connect to WebSocket and listen."""
        console.print(f"[bold]Connecting to QuickNode...[/bold]\n")
        console.print(f"URL: {mask_url(config.quicknode_ws_url)}\n")

        try:
            async with websockets.connect(config.quicknode_ws_url) as ws:
                console.print("[green]Connected to QuickNode![/green]\n")

                # Subscribe to DEX logs
                subscriptions = get_all_dex_subscriptions()
                console.print(f"[bold]Subscribing to {len(subscriptions)} DEX program(s)...[/bold]\n")

                for sub in subscriptions:
                    await ws.send(json.dumps(sub))
                    console.print(f"[dim]Subscribed: {sub['method']}[/dim]")

                console.print("\n[green]✓ Listening for Raydium LP events...[/green]\n")
                console.print("[dim]Press Ctrl+C to stop[/dim]\n")

                # Listen for messages
                if test:
                    # Test mode - wait for one message
                    console.print("[yellow]Test mode: waiting for one message...[/yellow]\n")
                    message = await ws.recv()
                    await on_message(message)
                    console.print("[yellow]Test mode: received one message[/yellow]")
                else:
                    # Continuous mode
                    message_count = 0
                    async for message in ws:
                        await on_message(message)
                        message_count += 1
                        if message_count % 10 == 0:
                            console.print(f"[dim]Processed {message_count} messages...[/dim]")

        except KeyboardInterrupt:
            console.print("\n\n[yellow]Stopping listener...[/yellow]")
        except Exception as e:
            console.print(f"[red]Connection error: {e}[/red]")
            raise

    # Run async
    asyncio.run(connect_and_listen())


if __name__ == "__main__":
    app()
