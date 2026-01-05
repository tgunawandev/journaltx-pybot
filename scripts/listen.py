#!/usr/bin/env python3
"""
QuickNode WebSocket listener for real-time Solana LP detection.

This is the REAL on-chain ingestion system:
- Connects to QuickNode WebSocket
- Subscribes to Raydium AMM program logs
- Detects LP additions via transaction parsing
- Extracts token mints and amounts from balance deltas
- Enriches with metadata from Jupiter/DexScreener (optional)
- Sends alerts to Telegram

NOT a mock. NOT a demo. Real on-chain data.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import logging
import signal
import time
from datetime import datetime
from typing import Optional

import websockets
import typer
from typer import Typer, Option
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from journaltx.core.config import Config
from journaltx.core.db import init_db
from journaltx.core.utils import format_pair_age
from journaltx.ingest.quicknode.lp_events import LPEventListener
from journaltx.ingest.quicknode.raydium_subscriptions import (
    get_all_dex_subscriptions,
    extract_signature_from_notification,
    is_liquidity_addition,
)
from journaltx.ingest.quicknode.transaction_parser import SolanaTransactionParser
from journaltx.notify.telegram import TelegramNotifier
from journaltx.notify.telegram_bot import TelegramBotHandler

app = Typer(help="QuickNode WebSocket listener for Solana LP detection")
console = Console()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("listen")


def mask_url(url: str) -> str:
    """Mask sensitive parts of a URL for safe logging."""
    if not url:
        return "Not configured"

    try:
        if "quiknode" in url.lower() or "quicknode" in url.lower():
            parts = url.split("/")
            if len(parts) >= 4:
                base = "/".join(parts[:3])
                return f"{base}/***MASKED***/"

        from urllib.parse import urlparse
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/***MASKED***"

    except Exception:
        return "***MASKED***"


class LPListener:
    """
    Real-time LP listener using Helius or QuickNode WebSocket.

    Implements automatic reconnection with exponential backoff.
    Helius is preferred (FREE, no rate limits).
    """

    def __init__(self, config: Config):
        self.config = config
        self.running = False
        self.ws = None
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = 60  # Max 60 seconds
        self.message_count = 0
        self.lp_events_detected = 0
        self.alerts_sent = 0
        self.start_time = None

        # Signature deduplication cache (last 1000 signatures)
        self.processed_signatures: set = set()
        self.max_cache_size = 1000

        # Select provider: Helius (primary) or QuickNode (fallback)
        self.provider = "helius" if config.helius_ws_url else "quicknode"
        self.ws_url = config.helius_ws_url or config.quicknode_ws_url
        self.rpc_url = config.helius_rpc_url or config.quicknode_http_url

        # Initialize components
        self.lp_listener = LPEventListener(config)
        self.tx_parser = None
        self.telegram = None

        if self.rpc_url:
            self.tx_parser = SolanaTransactionParser(self.rpc_url)

        if config.telegram_bot_token and config.telegram_chat_id:
            self.telegram = TelegramNotifier(config)

    def handle_alert(self, alert):
        """Handle generated alert - send to Telegram if configured."""
        self.alerts_sent += 1

        console.print(Panel(
            f"[bold green]ALERT: {alert.pair}[/bold green]\n"
            f"LP Added: {alert.value_sol:.0f} SOL (~${alert.value_usd:.0f})\n"
            f"Token: {alert.token_mint[:8]}...{alert.token_mint[-8:] if alert.token_mint else 'N/A'}\n"
            f"Pool: {alert.pool_address[:8]}...{alert.pool_address[-8:] if alert.pool_address else 'N/A'}\n"
            f"New Pool: {'Yes' if alert.is_new_pool else 'No'}\n"
            f"Age: {format_pair_age(alert.pair_age_hours, short=True)} | MCap: ${alert.market_cap/1e6:.2f}M",
            title="[bold yellow]Early-Stage Opportunity[/bold yellow]",
            border_style="green"
        ))

        if self.telegram:
            success = self.telegram.send_alert(alert)
            if success:
                console.print("[dim]Telegram notification sent[/dim]")
            else:
                console.print("[yellow]Telegram notification failed[/yellow]")

    async def process_message(self, ws_message: str):
        """Process incoming WebSocket message from QuickNode."""
        try:
            data = json.loads(ws_message)

            # Handle RPC errors (rate limit, auth, etc.)
            if "error" in data:
                error = data["error"]
                error_code = error.get("code", 0)
                error_msg = error.get("message", "Unknown error")
                if error_code == -32003:  # Rate limit
                    logger.error(f"[WS] ⚠️ QuickNode rate limit reached: {error_msg}")
                    console.print(f"[bold red]RATE LIMIT: {error_msg}[/bold red]")
                    # Set longer reconnect delay for rate limit
                    self.reconnect_delay = 60
                else:
                    logger.error(f"[WS] ⚠️ RPC Error ({error_code}): {error_msg}")
                return

            # Handle subscription confirmations
            if "result" in data and isinstance(data["result"], int):
                logger.info(f"[WS] ✓ Subscription confirmed: ID {data['result']}")
                return

            # Check if this is a logs notification
            if "params" not in data or "result" not in data["params"]:
                return

            result = data["params"]["result"]

            # QuickNode logsNotification has nested structure:
            # result.value.logs and result.value.err and result.value.signature
            value = result.get("value", result)  # Fallback to result if no value

            # CHECK: Ignore failed transactions (err != null)
            if value.get("err") is not None:
                logger.info(f"[WS] ❌ Ignoring failed transaction: {value.get('err')}")
                return

            logs = value.get("logs", [])

            if not logs:
                return

            # Extract transaction signature
            signature = extract_signature_from_notification(data)

            if not signature:
                logger.info("[WS] ❌ Could not extract signature from notification")
                return

            # CHECK: Deduplicate signatures
            if signature in self.processed_signatures:
                logger.info(f"[WS] ⏭️ Skipping duplicate signature: {signature[:12]}...")
                return

            # Add to cache (with size limit)
            self.processed_signatures.add(signature)
            if len(self.processed_signatures) > self.max_cache_size:
                # Remove oldest (convert to list, remove first 100)
                to_remove = list(self.processed_signatures)[:100]
                for sig in to_remove:
                    self.processed_signatures.discard(sig)

            # Log receipt of Raydium log with log preview
            log_preview = logs[0][:50] if logs else "empty"
            logger.info(f"[WS] ✓ Received Raydium log: {signature[:16]}...")
            logger.info(f"[WS]   Log[0]: {log_preview}...")

            # Check if this looks like a liquidity operation
            if not is_liquidity_addition(logs):
                logger.info(f"[WS] ⏭️ Not a liquidity addition (no LP keywords in logs)")
                return

            if not self.tx_parser:
                logger.warning("[WS] ⚠️ Transaction parser not initialized (no HTTP URL)")
                return

            logger.info(f"[LP] ═══════════════════════════════════════════════════════")
            logger.info(f"[LP] POTENTIAL LP DETECTED: {signature[:16]}...")
            logger.info(f"[LP] Fetching full transaction from QuickNode HTTP RPC...")

            # Fetch full transaction
            transaction = self.tx_parser.get_transaction(signature)

            if not transaction:
                logger.warning(f"[LP] ❌ Could not fetch transaction: {signature[:16]}...")
                return

            logger.info(f"[LP] ✓ Transaction fetched, starting decode...")

            # Parse the LP event (this does the real on-chain decoding)
            parsed_event = self.tx_parser.parse_lp_event(transaction)

            if not parsed_event:
                logger.info(f"[LP] ❌ Transaction is not an LP addition or failed to parse")
                logger.info(f"[LP] ═══════════════════════════════════════════════════════")
                return

            self.lp_events_detected += 1

            logger.info(f"[LP] ✓ LP EVENT #{self.lp_events_detected} CONFIRMED!")
            logger.info(f"[LP]   Pair: {parsed_event.pair_string}")
            logger.info(f"[LP]   SOL Added: +{parsed_event.sol_amount:.2f} SOL (~${parsed_event.sol_amount_usd:,.0f})")
            logger.info(f"[LP]   Token Added: +{parsed_event.token_amount:,.0f}")
            logger.info(f"[LP]   Token Mint: {parsed_event.token_mint}")
            logger.info(f"[LP]   Pool: {parsed_event.pool_address}")
            logger.info(f"[LP]   New Pool: {parsed_event.is_new_pool}")
            logger.info(f"[LP]   Liquidity: {parsed_event.liquidity_sol:.2f} SOL (~${parsed_event.liquidity_usd:,.0f})")
            logger.info(f"[LP]   Market Cap: ${parsed_event.market_cap:,.0f}")
            logger.info(f"[LP]   Pair Age: {format_pair_age(parsed_event.pair_age_hours)}")
            logger.info(f"[LP]   DexScreener: {parsed_event.dexscreener_url}")

            console.print(
                f"[cyan]LP Event:[/cyan] {parsed_event.pair_string} | "
                f"+{parsed_event.sol_amount:.1f} SOL (~${parsed_event.sol_amount_usd:.0f}) | "
                f"{'[NEW POOL]' if parsed_event.is_new_pool else f'Age: {format_pair_age(parsed_event.pair_age_hours, short=True)}'} | "
                f"MCap: ${parsed_event.market_cap/1e6:.2f}M"
            )

            logger.info(f"[FILTER] Applying early-stage filters...")

            # Process through LP listener (applies filters and creates alert)
            alert = self.lp_listener.process_parsed_lp_event(
                parsed_event,
                on_alert=self.handle_alert
            )

            if alert and not alert.early_stage_passed:
                logger.info(f"[FILTER] ❌ Filtered out: early_stage_passed=False")
                console.print(f"[dim]  └── Filtered: early_stage_passed=False[/dim]")
            elif alert:
                logger.info(f"[FILTER] ✓ Passed all filters! Alert sent.")
            else:
                logger.info(f"[FILTER] ❌ Filtered out by early_meme.py rules")

            logger.info(f"[LP] ═══════════════════════════════════════════════════════")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    async def connect_and_listen(self):
        """Connect to WebSocket and listen for events with auto-reconnection."""
        self.running = True
        self.start_time = datetime.now()

        provider_name = self.provider.capitalize()

        while self.running:
            try:
                logger.info(f"Connecting to {provider_name}: {mask_url(self.ws_url)}")

                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self.ws = ws
                    self.reconnect_delay = 1  # Reset delay on successful connection

                    console.print(f"[bold green]Connected to {provider_name}![/bold green]\n")

                    # Subscribe to DEX logs
                    subscriptions = get_all_dex_subscriptions()
                    console.print(f"[bold]Subscribing to {len(subscriptions)} DEX program(s)...[/bold]")

                    for sub in subscriptions:
                        await ws.send(json.dumps(sub))
                        logger.info(f"Sent subscription: {sub['method']}")

                    # Print status
                    self._print_status()

                    # Listen for messages
                    async for message in ws:
                        self.message_count += 1
                        await self.process_message(message)

                        # Print periodic status
                        if self.message_count % 100 == 0:
                            self._print_stats()

            except websockets.ConnectionClosed as e:
                logger.warning(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if self.running:
                # Exponential backoff
                logger.info(f"Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)

    def _print_status(self):
        """Print current configuration status."""
        table = Table(title="JournalTX LP Listener", show_header=False)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Provider", f"{self.provider.capitalize()} (FREE)" if self.provider == "helius" else self.provider.capitalize())
        table.add_row("Mode", self.config.mode)
        table.add_row("Profile", self.config.profile_template)
        table.add_row("Filter", self.config.filter_template)
        table.add_row("Min LP SOL", f"{self.config.lp_add_min_sol:.0f} SOL")
        table.add_row("Max Pair Age", f"{self.config.max_pair_age_hours}h")
        table.add_row("Max Market Cap", f"${self.config.max_market_cap/1e6:.0f}M")
        table.add_row("Telegram", "Enabled" if self.telegram else "Disabled")

        console.print(table)
        console.print("\n[green]Listening for Raydium LP events...[/green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    def _print_stats(self):
        """Print current statistics."""
        runtime = datetime.now() - self.start_time if self.start_time else None
        runtime_str = str(runtime).split('.')[0] if runtime else "N/A"

        console.print(
            f"[dim]Stats: {self.message_count} msgs | "
            f"{self.lp_events_detected} LP events | "
            f"{self.alerts_sent} alerts | "
            f"Runtime: {runtime_str}[/dim]"
        )

    def stop(self):
        """Stop the listener."""
        self.running = False
        if self.ws:
            asyncio.create_task(self.ws.close())


@app.command()
def main(
    test: bool = Option(False, "--test", "-t", help="Test mode (single message)"),
    verbose: bool = Option(False, "--verbose", "-v", help="Verbose logging"),
):
    """
    Connect to Helius/QuickNode WebSocket and listen for Raydium LP events.

    This is REAL on-chain ingestion:
    - Subscribes to Raydium AMM program logs via WebSocket
    - Parses transactions to decode LP additions
    - Extracts token mints and amounts from balance deltas
    - Applies early-stage filters
    - Sends alerts to Telegram

    Requires HELIUS_API_KEY (preferred, FREE) or QUICKNODE_WS_URL in .env
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Load config
    config = Config.from_env()

    # Validate required config - need either Helius or QuickNode
    has_helius = config.helius_api_key and config.helius_ws_url
    has_quicknode = config.quicknode_ws_url and config.quicknode_http_url

    if not has_helius and not has_quicknode:
        console.print("[red]ERROR: No RPC provider configured.[/red]")
        console.print("\nSet HELIUS_API_KEY (recommended, FREE) or QuickNode URLs in .env:")
        console.print("HELIUS_API_KEY=your-helius-api-key")
        console.print("  OR")
        console.print("QUICKNODE_WS_URL=wss://your-endpoint.solana-mainnet.quiknode.pro/your-key/")
        console.print("QUICKNODE_HTTP_URL=https://your-endpoint.solana-mainnet.quiknode.pro/your-key/")
        raise typer.Exit(1)

    # Show which provider is being used
    if has_helius:
        console.print("[green]Using Helius (FREE, no rate limits)[/green]")
    else:
        console.print("[yellow]Using QuickNode (credit-based billing)[/yellow]")

    # Initialize database
    init_db(config)
    console.print("[dim]Database initialized[/dim]")

    # Create listener
    listener = LPListener(config)

    if listener.telegram:
        console.print("[green]Telegram notifications enabled[/green]")
    else:
        console.print("[yellow]Telegram not configured - alerts will only be logged[/yellow]")

    # Initialize trading bot if enabled
    telegram_bot = None
    if config.trading_enabled and config.telegram_bot_token and config.wallet_encryption_key:
        try:
            telegram_bot = TelegramBotHandler(config)
            console.print("[green]Trading automation enabled[/green]")
        except Exception as e:
            console.print(f"[yellow]Trading bot init failed: {e}[/yellow]")
            telegram_bot = None
    elif config.trading_enabled:
        console.print("[yellow]Trading enabled but missing config (WALLET_ENCRYPTION_KEY required)[/yellow]")

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        console.print("\n[yellow]Shutting down...[/yellow]")
        listener.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Run the listener
    provider_info = f"{listener.provider.capitalize()} WebSocket"
    trading_info = "Trading: Enabled" if telegram_bot else "Trading: Disabled"
    console.print(Panel(
        "[bold]JournalTX - Real-Time Solana LP Monitor[/bold]\n\n"
        "Monitoring Raydium AMM for liquidity additions.\n"
        f"Detection: {provider_info} + Transaction Parsing\n"
        f"Enrichment: DexScreener + CoinGecko (metadata only)\n"
        f"{trading_info}",
        title="Starting",
        border_style="blue"
    ))

    # Run both listener and bot together
    async def run_all():
        tasks = [listener.connect_and_listen()]
        if telegram_bot:
            tasks.append(telegram_bot.start_polling())

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            if telegram_bot:
                await telegram_bot.stop()

    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        pass

    console.print(
        f"\n[bold]Session Summary:[/bold]\n"
        f"  Messages processed: {listener.message_count}\n"
        f"  LP events detected: {listener.lp_events_detected}\n"
        f"  Alerts sent: {listener.alerts_sent}"
    )


if __name__ == "__main__":
    app()
