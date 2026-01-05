"""
Early-stage meme filtering rules - Refined.

Key principles:
- Near-zero ignition only
- Market cap for defensive filtering only
- Require 2+ momentum signals
- Log silently if not ready
"""

import logging
from datetime import datetime
from typing import Optional, Tuple

import requests

from journaltx.filters.signals import Signal, get_signal_tracker

logger = logging.getLogger(__name__)


def get_pair_market_data(pair: str, legacy_memes: list = None) -> Optional[dict]:
    """
    Fetch market data from DexScreener.

    Returns None if data unavailable.
    """
    try:
        base_token = pair.split("/")[0].upper()

        # Check legacy list first
        if legacy_memes and base_token in legacy_memes:
            logger.info(f"[LEGACY] {pair} blocked: {base_token}")
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
                return {"wrong_quote": True}

            # Calculate pair age
            pair_created = pair_data.get("pairCreatedAt")
            if not pair_created:
                return None

            pair_age_hours = (datetime.now().timestamp() - pair_created / 1000) / 3600

            # Get liquidity (near-zero check)
            liquidity_usd = pair_data.get("liquidity", {}).get("usd", 0)

            # Get transactions
            txns = pair_data.get("txns", {})
            buys_5m = txns.get("m5", {}).get("buys", 0)
            sells_5m = txns.get("m5", {}).get("sells", 0)

            # Market cap (for defensive filtering only)
            market_cap = pair_data.get("marketCap", 0)
            fdv = pair_data.get("fdv", 0)

            return {
                "legacy_meme": False,
                "wrong_quote": False,
                "market_cap": market_cap or fdv,
                "liquidity_usd": liquidity_usd,
                "pair_age_hours": pair_age_hours,
                "buys_5m": buys_5m,
                "sells_5m": sells_5m,
            }

        return None

    except Exception as e:
        logger.error(f"Failed to fetch market data: {e}")
        return None


def check_early_stage_opportunity(
    pair: str,
    lp_added_sol: float,
    lp_before_sol: float = 0,
    max_pair_age_hours: int = 24,
    preferred_pair_age_hours: int = 6,
    near_zero_baseline_sol: float = 10.0,
    hard_reject_baseline_liquidity: float = 20.0,
    hard_reject_pair_age_hours: int = 24,
    hard_reject_market_cap: float = 20_000_000.0,
    min_lp_ignite_sol: float = 300.0,
    max_market_cap_defensive: float = 20_000_000.0,
    signal_window_minutes: int = 30,
    legacy_memes: list = None,
    is_new_pool: bool = False,
    require_multi_signal: bool = True,
) -> Tuple[bool, bool, dict]:
    """
    Check if this is an early-stage opportunity with momentum.

    Returns (should_alert, should_log, details)

    - should_alert: Send to Telegram
    - should_log: Log to database (even if no alert)
    - details: Diagnostic info
    """
    logger.info(f"[EARLY] ─────────────────────────────────────────────────")
    logger.info(f"[EARLY] Checking early-stage opportunity for: {pair}")
    logger.info(f"[EARLY]   LP Added: {lp_added_sol:.2f} SOL, LP Before: {lp_before_sol:.2f} SOL")
    logger.info(f"[EARLY]   Is New Pool: {is_new_pool}")

    details = {
        "pair": pair,
        "lp_added_sol": lp_added_sol,
        "lp_before_sol": lp_before_sol,
        "checks": [],
    }

    # Always log for analysis
    should_log = True

    # Rule 1: Pair type - must be TOKEN/SOL
    if "/" not in pair:
        logger.info(f"[EARLY] ❌ Rule 1 FAIL: Invalid pair format (no /)")
        details["checks"].append({"rule": "Pair format", "status": "FAIL", "reason": "Invalid format"})
        return False, should_log, details

    quote = pair.split("/")[1].upper()
    if quote != "SOL":
        logger.info(f"[EARLY] ❌ Rule 1 FAIL: Not SOL pair (quote={quote})")
        details["checks"].append({"rule": "Pair type", "status": "FAIL", "reason": f"Not SOL pair ({quote})"})
        return False, should_log, details

    logger.info(f"[EARLY] ✓ Rule 1 PASS: Valid TOKEN/SOL pair")
    details["checks"].append({"rule": "Pair type", "status": "PASS", "reason": "TOKEN/SOL"})

    # Get market data
    logger.info(f"[EARLY] Fetching market data from DexScreener...")
    market_data = get_pair_market_data(pair, legacy_memes)

    if not market_data:
        logger.info(f"[EARLY] ❌ Rule 2 SKIP: No market data available from DexScreener")
        details["checks"].append({"rule": "Market data", "status": "SKIP", "reason": "No data"})
        return False, should_log, details

    # Rule 2: Legacy meme exclusion
    if market_data.get("legacy_meme"):
        logger.info(f"[EARLY] ❌ Rule 2 BLOCK: Legacy meme (hard exclusion list)")
        details["checks"].append({"rule": "Legacy meme", "status": "BLOCK", "reason": "Hard exclusion list"})
        return False, should_log, details

    logger.info(f"[EARLY] ✓ Rule 2 PASS: Not a legacy meme")

    # Rule 3: Pair age - HARD GATES (using hard_reject thresholds)
    pair_age = market_data.get("pair_age_hours", 999)
    details["pair_age_hours"] = pair_age

    logger.info(f"[EARLY] Rule 3: Checking pair age ({pair_age:.2f}h vs max {hard_reject_pair_age_hours}h)...")

    # Hard reject: Too old
    if pair_age > hard_reject_pair_age_hours:
        logger.info(f"[EARLY] ❌ Rule 3 BLOCK: Too old ({pair_age:.1f}h > {hard_reject_pair_age_hours}h)")
        details["checks"].append({
            "rule": "Pair age (hard reject)",
            "status": "BLOCK",
            "reason": f"Too old: {pair_age:.1f}h > {hard_reject_pair_age_hours}h (auto-ignored)"
        })
        return False, should_log, details

    # Check age status for priority tagging
    if pair_age <= 0.5:  # <30 min
        age_status = "🔥 HIGH (golden window)"
        priority = "HIGH"
    elif pair_age <= 2.0:  # <2 hours
        age_status = "⚡ MEDIUM (early discovery)"
        priority = "MEDIUM"
    elif pair_age <= preferred_pair_age_hours:  # <6 hours (sweet spot)
        age_status = "✅ LOW (sweet spot)"
        priority = "LOW"
    else:  # 6-24 hours
        age_status = "✅ VALID (late window)"
        priority = "LOW"

    details["priority"] = priority
    logger.info(f"[EARLY] ✓ Rule 3 PASS: Pair age {pair_age:.2f}h - Priority: {priority}")

    details["checks"].append({
        "rule": "Pair age",
        "status": age_status,
        "reason": f"{pair_age:.1f}h old"
    })

    # Rule 4: Market cap - HARD REJECT using hard_reject threshold
    market_cap = market_data.get("market_cap", 0)
    details["market_cap"] = market_cap

    logger.info(f"[EARLY] Rule 4: Checking market cap (${market_cap:,.0f} vs max ${hard_reject_market_cap:,.0f})...")

    if market_cap >= hard_reject_market_cap:
        logger.info(f"[EARLY] ❌ Rule 4 BLOCK: Market cap too large (${market_cap/1e6:.1f}M >= ${hard_reject_market_cap/1e6:.0f}M)")
        details["checks"].append({
            "rule": "Market cap (hard reject)",
            "status": "BLOCK",
            "reason": f"Too large: ${market_cap/1_000_000:.0f}M ≥ ${hard_reject_market_cap/1_000_000:.0f}M (auto-ignored)"
        })
        return False, should_log, details

    logger.info(f"[EARLY] ✓ Rule 4 PASS: Market cap ${market_cap/1e6:.2f}M within limit")

    details["checks"].append({
        "rule": "Market cap",
        "status": "PASS",
        "reason": f"${market_cap/1_000_000:.2f}M (within limit)"
    })

    # Rule 5: Near-zero ignition check (using hard_reject baseline)
    # LP must come from near-zero baseline AND significant addition
    is_near_zero = lp_before_sol <= hard_reject_baseline_liquidity
    is_significant = lp_added_sol >= min_lp_ignite_sol

    logger.info(f"[EARLY] Rule 5: Near-zero ignition check...")
    logger.info(f"[EARLY]   Baseline: {lp_before_sol:.2f} SOL (need ≤{hard_reject_baseline_liquidity} SOL) → {'✓' if is_near_zero else '❌'}")
    logger.info(f"[EARLY]   Added: {lp_added_sol:.2f} SOL (need ≥{min_lp_ignite_sol} SOL) → {'✓' if is_significant else '❌'}")

    ignition_pass = is_near_zero and is_significant
    details["ignition_pass"] = ignition_pass

    if ignition_pass:
        logger.info(f"[EARLY] ✓ Rule 5 PASS: Near-zero ignition confirmed!")
        details["checks"].append({
            "rule": "LP ignition",
            "status": "✅ PASS",
            "reason": f"Near-zero ignition: {lp_before_sol:.1f}SOL → +{lp_added_sol:.0f}SOL"
        })
    else:
        logger.info(f"[EARLY] ❌ Rule 5 FAIL: Ignition criteria not met")
        details["checks"].append({
            "rule": "LP ignition",
            "status": "FAIL",
            "reason": f"Baseline: {lp_before_sol:.1f}SOL (need ≤{hard_reject_baseline_liquidity}), "
                     f"Added: {lp_added_sol:.0f}SOL (need ≥{min_lp_ignite_sol})"
        })
        # Don't alert yet, but log
        return False, should_log, details

    # Rule 6: Multi-signal requirement (conditional)
    # For NEW POOL CREATIONS: Skip multi-signal - pool creation IS the birth event
    # For existing pools: Require 2+ momentum signals within window

    logger.info(f"[EARLY] Rule 6: Multi-signal requirement check...")

    tracker = get_signal_tracker()

    # Add LP add signal
    signal = Signal(
        signal_type="lp_add",
        timestamp=datetime.now(),
        pair=pair,
        details={"lp_added": lp_added_sol, "lp_before": lp_before_sol}
    )

    # For new pools with near-zero baseline, alert immediately
    # This IS the ignition event - no need to wait for confirmation
    if is_new_pool or (lp_before_sol <= near_zero_baseline_sol and pair_age <= 1.0):
        # New pool creation - this is the ignition signal
        logger.info(f"[EARLY] ✓ Rule 6 BYPASS: New pool ignition event!")
        logger.info(f"[EARLY]   is_new_pool={is_new_pool}, baseline={lp_before_sol:.2f} SOL, age={pair_age:.2f}h")
        details["checks"].append({
            "rule": "Multi-signal",
            "status": "✅ BYPASS",
            "reason": f"New pool ignition (baseline: {lp_before_sol:.1f} SOL, age: {pair_age:.1f}h)"
        })
        should_alert = True
    elif not require_multi_signal:
        # Multi-signal disabled - alert on single LP add
        logger.info(f"[EARLY] ✓ Rule 6 DISABLED: Single-signal mode enabled")
        details["checks"].append({
            "rule": "Multi-signal",
            "status": "✅ DISABLED",
            "reason": "Single-signal mode enabled"
        })
        should_alert = True
    else:
        # Standard mode: require multi-signal confirmation
        should_alert = tracker.add_signal(signal)
        signal_counts = tracker.get_signal_count(pair)
        details["signal_counts"] = signal_counts

        if should_alert:
            logger.info(f"[EARLY] ✓ Rule 6 PASS: Multi-signal confirmed ({signal_counts['total']} signals)")
            details["checks"].append({
                "rule": "Multi-signal",
                "status": "✅ PASS",
                "reason": f"{signal_counts['total']} signals: {list(signal_counts['types'].keys())}"
            })
        else:
            logger.info(f"[EARLY] ⏳ Rule 6 WAIT: Need more signals ({signal_counts['total']}/2)")
            details["checks"].append({
                "rule": "Multi-signal",
                "status": "WAIT",
                "reason": f"Need 2+ signals, have {signal_counts['total']}: {list(signal_counts['types'].keys())}"
            })
            # Log but don't alert yet
            return False, should_log, details

    # All checks passed - ready to alert!
    logger.info(f"[EARLY] ═══════════════════════════════════════════════════════")
    logger.info(f"[EARLY] 🚨 ALL CHECKS PASSED - SENDING ALERT!")
    logger.info(f"[EARLY] ═══════════════════════════════════════════════════════")

    details["checks"].append({
        "rule": "FINAL",
        "status": "🚨 ALERT",
        "reason": "Early-stage opportunity confirmed"
    })

    return True, should_log, details
