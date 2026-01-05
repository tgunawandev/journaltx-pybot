"""
Telegram notification module.

Sends neutral, boring alerts to Telegram.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from journaltx.core.config import Config
from journaltx.core.models import Alert

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """
    Sends alerts to Telegram bot.

    Messages are intentionally neutral and non-urgent.
    """

    def __init__(self, config: Config):
        self.config = config
        self.bot_token = config.telegram_bot_token
        self.chat_id = config.telegram_chat_id
        self.timezone = ZoneInfo(config.timezone)

    def _get_market_info(self, pair: str) -> dict:
        """
        Fetch market cap info from DexScreener.

        Args:
            pair: Trading pair (e.g., "BONK/SOL")

        Returns:
            Dict with market_cap, pair_age, liquidity info
        """
        try:
            base_token = pair.split("/")[0]
            url = f"https://api.dexscreener.com/latest/dex/search/?q={base_token}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if not data.get("pairs"):
                return None

            # Find first SOL pair
            for pair_data in data["pairs"]:
                if pair_data.get("chainId") == "solana" and pair_data.get("quoteToken", {}).get("symbol") == "SOL":
                    market_cap = pair_data.get("marketCap", 0)
                    liquidity = pair_data.get("liquidity", {}).get("usd", 0)
                    pair_created = pair_data.get("pairCreatedAt")

                    # Calculate pair age
                    age_str = "Unknown"
                    if pair_created:
                        pair_age = datetime.now() - datetime.fromtimestamp(pair_created / 1000)
                        if pair_age.days > 0:
                            age_str = f"{pair_age.days}d"
                        elif pair_age.seconds >= 3600:
                            hours = pair_age.seconds // 3600
                            age_str = f"{hours}h"
                        else:
                            minutes = pair_age.seconds // 60
                            age_str = f"{minutes}m"

                    return {
                        "market_cap": market_cap,
                        "liquidity": liquidity,
                        "pair_age": age_str,
                    }

            return None

        except Exception as e:
            logger.error(f"Failed to fetch market info: {e}")
            return None

    def _format_alert(self, alert: Alert) -> str:
        """
        Format alert as HTML message - Early-stage meme format.
        """
        # Format type
        type_names = {
            "lp_add": "LP Added",
            "lp_remove": "LP Removed",
            "volume_spike": "Volume Spike",
        }
        type_name = type_names.get(alert.type.value, alert.type.value)

        # Format LP added amount
        if alert.value_usd:
            lp_added_str = f"+{alert.value_sol:,.0f} SOL (~${alert.value_usd:,.0f})"
        else:
            lp_added_str = f"+{alert.value_sol:,.0f} SOL"

        # Get pair from alert
        pair_display = alert.pair.replace("/", " / ")

        # Format pair age
        if alert.pair_age_hours:
            if alert.pair_age_hours < 1:
                age_minutes = int(alert.pair_age_hours * 60)
                pair_age_str = f"{age_minutes} minutes"
            else:
                pair_age_str = f"{alert.pair_age_hours:,.0f} hours"
        else:
            pair_age_str = "Unknown"

        # Format liquidity before/after
        lp_before = alert.lp_sol_before if alert.lp_sol_before else 0
        lp_after = alert.lp_sol_after if alert.lp_sol_after else (lp_before + alert.value_sol)

        # Format time - just HH:MM WIB
        local_time = alert.triggered_at.astimezone(self.timezone)
        time_str = local_time.strftime("%H:%M %Z")

        # Early-stage check status
        early_stage_status = "✅ PASSED" if alert.early_stage_passed else "❌ FAILED"

        # Mode badge - show TEST clearly
        mode_badge = f"🧪 {alert.mode} MODE" if alert.mode == "TEST" else f"🔴 {alert.mode} MODE"

        # Build message
        message = f"""<b>🟡 JournalTX Alert [{mode_badge}]</b>

<b>Type:</b> {type_name}
<b>Pair:</b> {pair_display}
<b>LP Added:</b> {lp_added_str}
<b>Pair Age:</b> {pair_age_str}
<b>Liquidity Before:</b> {lp_before:,.0f} SOL
<b>Liquidity After:</b> {lp_after:,.0f} SOL
<b>Time:</b> {time_str}

<b>Early-Stage Check:</b> {early_stage_status}

<i>Reminder:
This is NOT a trade signal.
Check risk/reward and rules first.</i>"""

        return message

    def get_pair_urls(self, pair: str) -> dict:
        """
        Generate research URLs for a pair.

        Args:
            pair: Trading pair (e.g., "BONK/SOL")

        Returns:
            Dict of URL names to URLs
        """
        base_token = pair.split("/")[0].lower()

        return {
            "dexscreener": f"https://dexscreener.com/solana/{base_token}",
            "photon": f"https://photon-sol.tinyastro.io/?token={base_token}",
            "birdeye": f"https://birdeye.so/token/{base_token}?chain=solana",
            "jupiter": f"https://jup.ag/quote/SOL/{base_token}",  # Use jup.ag instead of jupiter.ag
        }

    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to Telegram with HTML formatting and link buttons.

        Returns True if successful, False otherwise.
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured, skipping notification")
            return False

        # Check market cap filter (skip big established coins)
        market_info = self._get_market_info(alert.pair)
        if market_info:
            market_cap = market_info.get("market_cap", 0)
            if market_cap > self.config.max_market_cap:
                logger.info(f"Skipping {alert.pair}: market cap ${market_cap:,.0f} > ${self.config.max_market_cap:,.0f}")
                return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        message = self._format_alert(alert)

        # Get research URLs
        urls = self.get_pair_urls(alert.pair)

        # Create inline keyboard with link buttons
        # Note: We can't add callback buttons yet because that requires
        # the bot to be running to handle callbacks. For now, just URL buttons.
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "📊 DexScreener", "url": urls["dexscreener"]},
                    {"text": "⚡ Photon", "url": urls["photon"]},
                ],
                [
                    {"text": "🦅 Birdeye", "url": urls["birdeye"]},
                    {"text": "🪐 Jupiter", "url": urls["jupiter"]},
                ],
            ]
        }

        try:
            response = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                    "reply_markup": reply_markup,
                },
                timeout=10,
            )
            response.raise_for_status()

            logger.info(f"Telegram notification sent: {alert.id}")
            return True

        except requests.RequestException as e:
            logger.error(f"Telegram notification failed: {e}")
            return False

    def send_message(self, text: str) -> bool:
        """
        Send arbitrary message to Telegram.

        Useful for weekly review summaries. Supports HTML formatting.
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram not configured, skipping notification")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        try:
            response = requests.post(
                url,
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=10,
            )
            response.raise_for_status()

            logger.info("Telegram message sent")
            return True

        except requests.RequestException as e:
            logger.error(f"Telegram message failed: {e}")
            return False
