"""
QuickNode WebSocket subscriptions for Solana DEX monitoring.

Subscribes to program logs from Raydium and other DEXs to detect
liquidity pool additions in real-time.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# Solana program IDs for major DEXs
RAYDIUM_AMM_PROGRAM = "675kPX9MHTjS2zt1qf1iQiLpKcM8cCtKxEbZqE8qiVJ"
RAYDIUM_LIQUIDITY_POOL_V3 = "CAMMCzo5YL8w4VFF8KVHrK22GGUQpMpTFb5iJHJxgKWs"
ORCA_SWAP_PROGRAM = "9W959DqEETiGZocYWCQPaJe6uQ6NKkqAkAF4UhyW5xrq"
ORCA_WHIRPOOLS_PROGRAM = "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc"


def get_raydium_subscription() -> Dict[str, Any]:
    """
    Get subscription payload for Raydium AMM program logs.

    This subscribes to all transactions involving the Raydium AMM program,
    which includes liquidity additions.

    Solana logsSubscribe format:
    - params[0]: filter (mentions or all)
    - params[1]: config object with commitment level
    """
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [RAYDIUM_AMM_PROGRAM]},
            {"commitment": "confirmed"}
        ]
    }


def get_orca_subscription() -> Dict[str, Any]:
    """
    Get subscription payload for Orca swap program logs.
    """
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "logsSubscribe",
        "params": [
            {"mentions": [ORCA_SWAP_PROGRAM]},
            {"commitment": "confirmed"}
        ]
    }


def get_all_dex_subscriptions() -> list[Dict[str, Any]]:
    """
    Get subscriptions for all major DEX programs.

    Returns:
        List of subscription payloads for Raydium, Orca, etc.
    """
    return [
        get_raydium_subscription(),
        # get_orca_subscription(),  # Can add more DEXs later
    ]


def is_liquidity_addition(logs: list[str]) -> bool:
    """
    Detect if a transaction is a liquidity addition.

    Args:
        logs: List of log messages from a Solana transaction

    Returns:
        True if this appears to be an LP addition
    """
    if not logs:
        return False

    logs_text = " ".join(logs).lower()

    # Look for LP addition indicators
    # These are common log patterns for liquidity additions
    lp_indicators = [
        "initialize",
        "deposit",
        "add liquidity",
        "create pool",
        "liquidity",
    ]

    # Must have liquidity-related logs
    has_liquidity = any(indicator in logs_text for indicator in lp_indicators)

    # Exclude removals/swaps
    is_removal = any(word in logs_text for word in ["withdraw", "remove", "swap"])

    return has_liquidity and not is_removal


def extract_signature_from_notification(notification: Dict[str, Any]) -> Optional[str]:
    """
    Extract transaction signature from QuickNode notification.

    Args:
        notification: Raw notification from QuickNode

    Returns:
        Transaction signature or None
    """
    try:
        result = notification.get("params", {}).get("result", {})

        # Signature can be in different fields
        if "signature" in result:
            return result["signature"]

        # Sometimes in nested structure
        if isinstance(result, dict):
            for key, value in result.items():
                if "signature" in key.lower():
                    return str(value)

        return None

    except Exception as e:
        logger.error(f"Error extracting signature: {e}")
        return None
