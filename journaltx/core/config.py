"""
Configuration management for JournalTX.

Loads settings from environment variables with sensible defaults.
"""

from dataclasses import dataclass
import os
from typing import Optional


@dataclass
class Config:
    """Application configuration."""

    # Database
    database_path: str = "data/journaltx.db"

    # QuickNode
    quicknode_ws_url: Optional[str] = None
    quicknode_http_url: Optional[str] = None

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Alert thresholds
    lp_add_min_sol: float = 500.0
    lp_add_min_usd: float = 10000.0
    lp_remove_min_pct: float = 50.0
    volume_spike_multiplier: float = 3.0

    # Guardrails
    max_trades_per_day: int = 2

    # Timezone
    timezone: str = "Asia/Jakarta"

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        return cls(
            database_path=os.getenv("JOURNALTX_DB_PATH", "data/journaltx.db"),
            quicknode_ws_url=os.getenv("QUICKNODE_WS_URL"),
            quicknode_http_url=os.getenv("QUICKNODE_HTTP_URL"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            lp_add_min_sol=float(os.getenv("LP_ADD_MIN_SOL", "500.0")),
            lp_add_min_usd=float(os.getenv("LP_ADD_MIN_USD", "10000.0")),
            lp_remove_min_pct=float(os.getenv("LP_REMOVE_MIN_PCT", "50.0")),
            volume_spike_multiplier=float(os.getenv("VOLUME_SPIKE_MULTIPLIER", "3.0")),
            max_trades_per_day=int(os.getenv("MAX_TRADES_PER_DAY", "2")),
            timezone=os.getenv("TIMEZONE", "Asia/Jakarta"),
        )
