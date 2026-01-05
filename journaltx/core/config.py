"""
Configuration management for JournalTX.

Loads settings from JSON templates and environment variables.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any


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

    # Alert thresholds (from profile JSON)
    lp_add_min_sol: float = 500.0
    lp_add_min_usd: float = 10000.0
    lp_remove_min_pct: float = 50.0
    volume_spike_multiplier: float = 3.0

    # Guardrails (from profile JSON)
    max_actions_per_day: int = 2

    # Timezone
    timezone: str = "Asia/Jakarta"

    # Early-stage meme filters (from filter JSON)
    max_market_cap: float = 20_000_000.0
    max_pair_age_hours: int = 24
    preferred_pair_age_hours: int = 6
    min_lp_sol_threshold: float = 300.0
    near_zero_baseline_sol: float = 10.0
    signal_window_minutes: int = 30
    require_multi_signal: bool = True
    min_signals_required: int = 2

    # Hard reject thresholds (from filter JSON)
    hard_reject_pair_age_hours: int = 24
    hard_reject_market_cap_usd: float = 20_000_000.0
    hard_reject_baseline_liquidity_sol: float = 20.0

    # Auto-ignore rules (from profile JSON - overrides filter defaults)
    auto_ignore_pair_age_hours: int = None  # None means use filter default
    auto_ignore_market_cap_usd: float = None  # None means use filter default

    # Legacy memes (from filter JSON)
    legacy_memes: list = None

    # Mode: LIVE or TEST
    mode: str = "TEST"

    # Profile/filter template names
    profile_template: str = "balanced"
    filter_template: str = "default"

    @classmethod
    def _load_json(cls, json_path: Path) -> Dict[str, Any]:
        """Load JSON configuration file."""
        if not json_path.exists():
            raise FileNotFoundError(f"Config file not found: {json_path}")

        with open(json_path, 'r') as f:
            return json.load(f)

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from JSON templates + environment variables."""
        # Load profile template
        profile_name = os.getenv("PROFILE_TEMPLATE", "balanced")
        profile_path = Path(f"config/profiles/{profile_name}.json")
        profile_data = cls._load_json(profile_path)

        # Load filter template
        filter_name = os.getenv("FILTER_TEMPLATE", "default")
        filter_path = Path(f"config/filters/{filter_name}.json")
        filter_data = cls._load_json(filter_path)

        # Extract filter settings
        filters = profile_data.get("filters", {})
        early_stage = profile_data.get("early_stage", {})
        auto_ignore = profile_data.get("auto_ignore", {})

        # Extract hard reject rules from filter JSON
        hard_reject = filter_data.get("hard_reject_if", {})

        # Build config
        config = cls(
            database_path=os.getenv("JOURNALTX_DB_PATH", "data/journaltx.db"),
            quicknode_ws_url=os.getenv("QUICKNODE_WS_URL"),
            quicknode_http_url=os.getenv("QUICKNODE_HTTP_URL"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),

            # From profile JSON
            lp_add_min_sol=filters.get("lp_add_min_sol", 500.0),
            lp_add_min_usd=filters.get("lp_add_min_usd", 10000.0),
            lp_remove_min_pct=filters.get("lp_remove_min_pct", 50.0),
            volume_spike_multiplier=filters.get("volume_spike_multiplier", 3.0),
            max_actions_per_day=filters.get("max_actions_per_day", 2),

            # Timezone
            timezone=os.getenv("TIMEZONE", "Asia/Jakarta"),

            # Early-stage filters (combine profile + filter JSON)
            max_market_cap=filter_data.get("max_market_cap", 20_000_000.0),
            max_pair_age_hours=filter_data.get("max_pair_age_hours", 24),
            preferred_pair_age_hours=filter_data.get("preferred_pair_age_hours", 6),
            min_lp_sol_threshold=early_stage.get("min_lp_ignite_sol", 300.0),
            near_zero_baseline_sol=early_stage.get("near_zero_baseline_sol", 10.0),
            signal_window_minutes=filter_data.get("signal_window_minutes", 30),
            require_multi_signal=early_stage.get("require_multi_signal", True),
            min_signals_required=early_stage.get("min_signals_required", 2),

            # Hard reject thresholds
            hard_reject_pair_age_hours=hard_reject.get("pair_age_hours_gt", 24),
            hard_reject_market_cap_usd=hard_reject.get("market_cap_usd_gte", 20_000_000.0),
            hard_reject_baseline_liquidity_sol=hard_reject.get("baseline_liquidity_sol_gt", 20.0),

            # Auto-ignore overrides from profile
            auto_ignore_pair_age_hours=auto_ignore.get("pair_age_hours_gt"),
            auto_ignore_market_cap_usd=auto_ignore.get("market_cap_usd_gt"),

            legacy_memes=filter_data.get("legacy_memes", []),

            # Mode
            mode=os.getenv("MODE", "TEST").upper(),

            # Template names
            profile_template=profile_name,
            filter_template=filter_name,
        )

        return config

    def get_active_profile_name(self) -> str:
        """Get the active profile template name."""
        return self.profile_template

    def get_filter_summary(self) -> str:
        """Get a summary of current filter settings."""
        return f"""Profile: {self.profile_template}
Filter: {self.filter_template}
Mode: {self.mode}

Alert Thresholds:
  LP Add Min: {self.lp_add_min_sol:,.0f} SOL (~${self.lp_add_min_usd:,.0f})
  LP Remove Min: {self.lp_remove_min_pct:.0f}%
  Volume Spike: {self.volume_spike_multiplier}x
  Max Actions/Day: {self.max_actions_per_day}

Early-Stage Filters:
  Max Market Cap: ${self.max_market_cap:,.0f}
  Max Pair Age: {self.max_pair_age_hours}h
  Preferred Age: {self.preferred_pair_age_hours}h (sweet spot)
  Near-Zero Baseline: {self.near_zero_baseline_sol} SOL
  Min LP Ignition: {self.min_lp_sol_threshold} SOL
  Signal Window: {self.signal_window_minutes} min

Hard Reject Rules (auto-ignore):
  Pair Age >: {self.hard_reject_pair_age_hours}h
  Market Cap ≥: ${self.hard_reject_market_cap_usd:,.0f}
  Baseline >: {self.hard_reject_baseline_liquidity_sol} SOL

Legacy Memes Excluded: {len(self.legacy_memes) if self.legacy_memes else 0}
"""
