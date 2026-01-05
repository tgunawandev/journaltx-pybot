"""
Market cap filter using DexScreener API.

Filters out established coins with high market cap.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def check_dexscreener(pair: str) -> Optional[dict]:
    """
    Fetch pair data from DexScreener.

    Args:
        pair: Trading pair (e.g., "BONK/SOL")

    Returns:
        Dict with market cap, pair age, or None if not found
    """
    try:
        # Extract base token
        base_token = pair.split("/")[0]

        # Search for pair
        url = f"https://api.dexscreener.com/latest/dex/search/?q={base_token}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("pairs"):
            logger.warning(f"No pairs found for {pair}")
            return None

        # Find first SOL pair
        for pair_data in data["pairs"]:
            if pair_data.get("chainId") == "solana" and pair_data.get("quoteToken", {}).get("symbol") == "SOL":
                return {
                    "market_cap": pair_data.get("marketCap", 0),
                    "fdv": pair_data.get("fdv", 0),
                    "liquidity_usd": pair_data.get("liquidity", {}).get("usd", 0),
                    "pair_created_at": pair_data.get("pairCreatedAt"),
                    "pair_address": pair_data.get("pairAddress"),
                    "url": pair_data.get("url"),
                }

        logger.warning(f"No SOL pair found for {base_token}")
        return None

    except Exception as e:
        logger.error(f"DexScreener API error: {e}")
        return None


def is_early_meme_coin(
    pair: str,
    max_market_cap: float = 1000000.0,  # $1M default
    max_pair_age_hours: int = 24,  # 24 hours default
) -> tuple[bool, Optional[dict]]:
    """
    Check if pair is an early meme coin.

    Args:
        pair: Trading pair (e.g., "BONK/SOL")
        max_market_cap: Maximum market cap in USD
        max_pair_age_hours: Maximum pair age in hours

    Returns:
        (is_early, data) tuple where data has market cap and age info
    """
    data = check_dexscreener(pair)

    if not data:
        # If we can't fetch data, be conservative and allow it
        logger.warning(f"Could not fetch DexScreener data for {pair}, allowing")
        return True, None

    market_cap = data.get("market_cap", 0)
    pair_created_at = data.get("pair_created_at")

    # Check market cap
    if market_cap > max_market_cap:
        logger.info(f"{pair} rejected: market cap ${market_cap:,.0f} > ${max_market_cap:,.0f}")
        return False, data

    # Check pair age
    if pair_created_at:
        pair_age = datetime.now() - datetime.fromtimestamp(pair_created_at / 1000)
        max_age = timedelta(hours=max_pair_age_hours)

        if pair_age > max_age:
            logger.info(f"{pair} rejected: pair age {pair_age.days} days > {max_pair_age_hours} hours")
            return False, data

    # Passed all filters
    logger.info(f"{pair} passed: MC ${market_cap:,.0f}, age {pair_age if pair_created_at else 'unknown'}")
    return True, data
