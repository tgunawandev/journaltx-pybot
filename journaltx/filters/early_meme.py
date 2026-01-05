"""
Early-stage meme coin filtering rules.

Implements strict multi-stage filtering for early meme detection.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Legacy meme exclusion list (hard block)
LEGACY_MEMES = {
    "BONK", "WIF", "DOGE", "SHIB", "PEPE", "FLOKI", "BABYDOGE",
    "MOON", "SAMO", "KING", "MONKY"
}


def get_pair_market_data(pair: str) -> Optional[dict]:
    """
    Fetch comprehensive pair data from DexScreener.

    Returns None if data unavailable.
    """
    try:
        base_token = pair.split("/")[0].upper()

        # Check legacy list first
        if base_token in LEGACY_MEMES:
            logger.info(f"{pair} blocked: Legacy meme ({base_token})")
            return {"legacy_meme": True}

        # Fetch from DexScreener
        url = f"https://api.dexscreener.com/latest/dex/search/?q={base_token}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()

        if not data.get("pairs"):
            return None

        # Find first SOL pair
        for pair_data in data["pairs"]:
            if pair_data.get("chainId") != "solana":
                continue

            quote_symbol = pair_data.get("quoteToken", {}).get("symbol", "")
            if quote_symbol != "SOL":
                logger.info(f"{pair} skipped: Quote token is {quote_symbol}, not SOL")
                return {"wrong_quote": True}

            # Calculate pair age
            pair_created = pair_data.get("pairCreatedAt")
            if not pair_created:
                return None

            pair_age_seconds = (datetime.now().timestamp() - pair_created / 1000)
            pair_age_hours = pair_age_seconds / 3600

            # Get LP liquidity
            liquidity = pair_data.get("liquidity", {}).get("usd", 0)

            # Get transactions for volume spike check
            txns = pair_data.get("txns", {})
            volume_24h = pair_data.get("volume", {}).get("h24", 0)

            # Market cap
            market_cap = pair_data.get("marketCap", 0)
            fdv = pair_data.get("fdv", 0)

            return {
                "legacy_meme": False,
                "wrong_quote": False,
                "market_cap": market_cap or fdv,
                "liquidity_usd": liquidity,
                "liquidity_sol": liquidity / 150.0 if liquidity else 0,  # Approx SOL price
                "pair_age_hours": pair_age_hours,
                "pair_created_at": pair_created,
                "volume_24h": volume_24h,
                "txns_m5_buys": txns.get("m5", {}).get("buys", 0),
                "txns_m5_sells": txns.get("m5", {}).get("m5", {}).get("sells", 0),
                "url": pair_data.get("url", ""),
            }

        return None

    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        return None


def check_early_stage_rules(
    pair: str,
    lp_added_sol: float,
    lp_before_sol: float = 0,
    max_pair_age_hours: int = 24,
    min_sol_threshold: float = 300.0,
    small_baseline: float = 20.0,
    max_market_cap: float = 20_000_000.0,
) -> Tuple[bool, dict]:
    """
    Apply early-stage meme filtering rules.

    Returns (should_alert, details) tuple.
    """
    details = {
        "pair": pair,
        "lp_added_sol": lp_added_sol,
        "lp_before_sol": lp_before_sol,
        "checks": [],
        "passed": False,
    }

    # Rule 1: Check pair type (must be TOKEN/SOL)
    if "/" not in pair:
        details["checks"].append({"rule": "Pair format", "status": "FAIL", "reason": "Invalid pair format"})
        return False, details

    quote = pair.split("/")[1].upper() if len(pair.split("/")) > 1 else ""
    if quote != "SOL":
        details["checks"].append({"rule": "Pair type", "status": "FAIL", "reason": f"Quote is {quote}, not SOL"})
        return False, details

    details["checks"].append({"rule": "Pair type", "status": "PASS", "reason": "TOKEN/SOL pair"})

    # Get market data
    market_data = get_pair_market_data(pair)

    if not market_data:
        details["checks"].append({"rule": "Market data", "status": "SKIP", "reason": "No data available"})
        return False, details

    # Rule 8: Legacy meme exclusion
    if market_data.get("legacy_meme"):
        details["checks"].append({"rule": "Legacy meme", "status": "FAIL", "reason": "In legacy exclusion list"})
        return False, details

    # Rule 8: Wrong quote token
    if market_data.get("wrong_quote"):
        details["checks"].append({"rule": "Quote token", "status": "FAIL", "reason": "Not SOL pair"})
        return False, details

    # Rule 2: Pair age (HARD GATE)
    pair_age = market_data.get("pair_age_hours", 999)
    details["pair_age_hours"] = pair_age

    if pair_age > max_pair_age_hours:
        details["checks"].append({
            "rule": "Pair age",
            "status": "FAIL",
            "reason": f"Pair age {pair_age:.1f}h > {max_pair_age_hours}h limit"
        })
        return False, details

    age_status = "PREFERRED" if pair_age <= 6 else "PASS"
    details["checks"].append({
        "rule": "Pair age",
        "status": age_status,
        "reason": f"Pair age {pair_age:.1f}h"
    })

    # Rule 6: Market cap (DEFENSIVE ONLY)
    market_cap = market_data.get("market_cap", 0)
    details["market_cap"] = market_cap

    if market_cap >= max_market_cap:
        details["checks"].append({
            "rule": "Market cap",
            "status": "FAIL",
            "reason": f"MC ${market_cap/1_000_000:.0f}M >= ${max_market_cap/1_000_000:.0f}M limit"
        })
        return False, details

    details["checks"].append({
        "rule": "Market cap",
        "status": "PASS",
        "reason": f"MC ${market_cap/1_000_000:.2f}M"
    })

    # Rule 3: Liquidity ignition (OFFENSE SIGNAL)
    ignition_pass = lp_added_sol >= min_sol_threshold and lp_before_sol <= small_baseline
    details["ignition_pass"] = ignition_pass

    if ignition_pass:
        details["checks"].append({
            "rule": "LP ignition",
            "status": "PASS",
            "reason": f"+{lp_added_sol:.0f} SOL added (≥{min_sol_threshold}), baseline {lp_before_sol:.0f} SOL (≤{small_baseline})"
        })
    else:
        details["checks"].append({
            "rule": "LP ignition",
            "status": "FAIL",
            "reason": f"LP added {lp_added_sol:.0f} SOL (need ≥{min_sol_threshold}) or baseline {lp_before_sol:.0f} SOL (need ≤{small_baseline})"
        })

    # Rule 9: ALERT OUTPUT RULE
    # All must pass
    all_pass = all(
        check["status"] in ["PASS", "PREFERRED"]
        for check in details["checks"]
    )

    details["passed"] = all_pass

    if all_pass:
        details["checks"].append({
            "rule": "FINAL",
            "status": "ALERT",
            "reason": "All early-stage rules passed"
        })

    return all_pass, details
