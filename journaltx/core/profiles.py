"""
Profile system for threshold configurations.

Allows switching between pre-configured threshold profiles for different trading styles.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from journaltx.core.config import Config

logger = logging.getLogger(__name__)


@dataclass
class ThresholdProfile:
    """Pre-configured threshold settings for different trading styles."""
    name: str
    description: str
    lp_add_min_sol: float
    lp_add_min_usd: float
    lp_remove_min_pct: float
    volume_spike_multiplier: float
    max_trades_per_day: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "lp_add_min_sol": self.lp_add_min_sol,
            "lp_add_min_usd": self.lp_add_min_usd,
            "lp_remove_min_pct": self.lp_remove_min_pct,
            "volume_spike_multiplier": self.volume_spike_multiplier,
            "max_trades_per_day": self.max_trades_per_day,
        }

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "ThresholdProfile":
        """Create from dictionary."""
        return cls(
            name=name,
            description=data.get("description", ""),
            lp_add_min_sol=data.get("lp_add_min_sol", 500.0),
            lp_add_min_usd=data.get("lp_add_min_usd", 10000.0),
            lp_remove_min_pct=data.get("lp_remove_min_pct", 50.0),
            volume_spike_multiplier=data.get("volume_spike_multiplier", 3.0),
            max_trades_per_day=data.get("max_trades_per_day", 2),
        )


# Built-in profiles
BUILT_IN_PROFILES: Dict[str, ThresholdProfile] = {
    "conservative": ThresholdProfile(
        name="Conservative",
        description="Only high-quality LP additions, lower trade frequency",
        lp_add_min_sol=2000.0,
        lp_add_min_usd=300000.0,
        lp_remove_min_pct=70.0,
        volume_spike_multiplier=5.0,
        max_trades_per_day=1,
    ),
    "balanced": ThresholdProfile(
        name="Balanced",
        description="Balanced alert frequency and trade opportunities",
        lp_add_min_sol=500.0,
        lp_add_min_usd=50000.0,
        lp_remove_min_pct=50.0,
        volume_spike_multiplier=3.0,
        max_trades_per_day=2,
    ),
    "aggressive": ThresholdProfile(
        name="Aggressive",
        description="More alerts, earlier entries, higher frequency",
        lp_add_min_sol=100.0,
        lp_add_min_usd=5000.0,
        lp_remove_min_pct=30.0,
        volume_spike_multiplier=2.0,
        max_trades_per_day=5,
    ),
    "degens_only": ThresholdProfile(
        name="Degens Only",
        description="Maximum alerts, use at your own risk",
        lp_add_min_sol=50.0,
        lp_add_min_usd=1000.0,
        lp_remove_min_pct=20.0,
        volume_spike_multiplier=1.5,
        max_trades_per_day=10,
    ),
}


class ProfileManager:
    """Manage and switch between threshold profiles."""

    def __init__(self, config_path: Path = None):
        """
        Initialize profile manager.

        Args:
            config_path: Path to data directory (defaults to data/)
        """
        if config_path is None:
            config_path = Path("data")

        self.config_path = config_path
        self.custom_profiles: Dict[str, ThresholdProfile] = {}
        self.load_custom_profiles()

    def load_custom_profiles(self):
        """Load user-defined profiles from JSON file."""
        profiles_file = self.config_path / "profiles.json"

        if not profiles_file.exists():
            logger.debug(f"No custom profiles file at {profiles_file}")
            return

        try:
            data = json.loads(profiles_file.read_text())

            for name, params in data.items():
                self.custom_profiles[name] = ThresholdProfile.from_dict(name, params)

            logger.info(f"Loaded {len(self.custom_profiles)} custom profiles")

        except Exception as e:
            logger.error(f"Failed to load custom profiles: {e}")

    def get_profile(self, name: str) -> ThresholdProfile:
        """
        Get profile by name.

        Args:
            name: Profile name (conservative, balanced, aggressive, degens_only, or custom)

        Returns:
            ThresholdProfile

        Raises:
            ValueError: If profile not found
        """
        if name in BUILT_IN_PROFILES:
            return BUILT_IN_PROFILES[name]

        if name in self.custom_profiles:
            return self.custom_profiles[name]

        raise ValueError(
            f"Profile '{name}' not found. "
            f"Available: {', '.join(self.list_profile_names())}"
        )

    def list_profiles(self) -> List[ThresholdProfile]:
        """List all available profiles (built-in + custom)."""
        return list(BUILT_IN_PROFILES.values()) + list(self.custom_profiles.values())

    def list_profile_names(self) -> List[str]:
        """List all profile names."""
        return list(BUILT_IN_PROFILES.keys()) + list(self.custom_profiles.keys())

    def create_profile(
        self,
        name: str,
        description: str,
        lp_add_min_sol: float = 500.0,
        lp_add_min_usd: float = 10000.0,
        lp_remove_min_pct: float = 50.0,
        volume_spike_multiplier: float = 3.0,
        max_trades_per_day: int = 2,
    ) -> ThresholdProfile:
        """
        Create and save a custom profile.

        Args:
            name: Profile name
            description: Profile description
            lp_add_min_sol: Minimum SOL for LP add alerts
            lp_add_min_usd: Minimum USD for LP add alerts
            lp_remove_min_pct: Minimum % for LP remove alerts
            volume_spike_multiplier: Volume spike multiplier
            max_trades_per_day: Maximum trades per day

        Returns:
            Created ThresholdProfile
        """
        profile = ThresholdProfile(
            name=name,
            description=description,
            lp_add_min_sol=lp_add_min_sol,
            lp_add_min_usd=lp_add_min_usd,
            lp_remove_min_pct=lp_remove_min_pct,
            volume_spike_multiplier=volume_spike_multiplier,
            max_trades_per_day=max_trades_per_day,
        )

        self.custom_profiles[name] = profile
        self.save_profiles()

        logger.info(f"Created custom profile: {name}")
        return profile

    def save_profiles(self):
        """Persist custom profiles to JSON file."""
        profiles_file = self.config_path / "profiles.json"

        # Ensure data directory exists
        self.config_path.mkdir(parents=True, exist_ok=True)

        data = {
            name: profile.to_dict()
            for name, profile in self.custom_profiles.items()
        }

        try:
            profiles_file.write_text(json.dumps(data, indent=2))
            logger.info(f"Saved {len(self.custom_profiles)} custom profiles")

        except Exception as e:
            logger.error(f"Failed to save custom profiles: {e}")

    def apply_profile_to_config(self, profile: ThresholdProfile, config: Config) -> Config:
        """
        Apply profile thresholds to a config object.

        Args:
            profile: ThresholdProfile to apply
            config: Config object to update

        Returns:
            Updated Config object
        """
        config.lp_add_min_sol = profile.lp_add_min_sol
        config.lp_add_min_usd = profile.lp_add_min_usd
        config.lp_remove_min_pct = profile.lp_remove_min_pct
        config.volume_spike_multiplier = profile.volume_spike_multiplier
        config.max_trades_per_day = profile.max_trades_per_day

        return config

    def get_active_profile_name(self) -> str:
        """
        Get the active profile name from environment variable.

        Returns:
            Profile name (defaults to 'balanced')
        """
        return os.getenv("JOURNALTX_PROFILE", "balanced")
