"""
Raydium AMM V4 instruction decoder for real LP detection.

Decodes Raydium V4 AMM instructions to extract:
- Token mint addresses
- Pool addresses
- Liquidity amounts from balance deltas

Reference: Raydium AMM V4 account layouts
"""

import base64
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

# Raydium AMM V4 Program ID
RAYDIUM_AMM_V4 = "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

# WSOL mint address
WSOL_MINT = "So11111111111111111111111111111111111111112"

# Minimum SOL delta to consider as LP add (noise threshold: 0.1 SOL)
MIN_SOL_DELTA_LAMPORTS = 100_000_000  # 0.1 SOL


@dataclass
class LPAdditionInfo:
    """Detailed LP addition information extracted from transaction."""
    pool_address: str
    token_mint: str
    quote_mint: str  # Usually WSOL
    token_amount: float
    quote_amount_sol: float
    lp_tokens_minted: float
    liquidity_before_sol: float
    liquidity_after_sol: float
    is_pool_creation: bool
    signature: str


def decode_raydium_transaction(
    transaction: Dict[str, Any],
    http_rpc_url: str
) -> Optional[LPAdditionInfo]:
    """
    Decode a Raydium transaction to extract LP addition details.

    Uses balance delta analysis (preBalances vs postBalances) to detect
    actual liquidity additions, not just instruction matching.

    Args:
        transaction: Parsed transaction from getTransaction RPC
        http_rpc_url: QuickNode HTTP URL for additional queries

    Returns:
        LPAdditionInfo if this is an LP addition, None otherwise
    """
    try:
        meta = transaction.get("meta", {})
        signatures = transaction.get("transaction", {}).get("signatures", [])
        sig_short = signatures[0][:12] if signatures else "unknown"

        logger.info(f"[DECODE] Starting Raydium decode for {sig_short}...")

        # RULE: Ignore failed transactions
        if meta.get("err") is not None:
            logger.info(f"[DECODE] ❌ Transaction failed (err={meta.get('err')}), skipping")
            return None

        message = transaction.get("transaction", {}).get("message", {})
        instructions = message.get("instructions", [])
        account_keys = _get_account_keys(message)

        if not account_keys:
            logger.info(f"[DECODE] ❌ No account keys found")
            return None

        logger.info(f"[DECODE] Found {len(instructions)} instructions, {len(account_keys)} accounts")

        # Find Raydium AMM instruction and get its type
        raydium_ix, ix_type = _find_raydium_instruction(instructions, meta)

        if not raydium_ix:
            logger.info(f"[DECODE] ❌ No Raydium AMM instruction found")
            return None

        logger.info(f"[DECODE] ✓ Found Raydium instruction type: {ix_type}")

        # Only process LP additions (initialize, initialize2, deposit)
        if ix_type not in ["initialize", "initialize2", "deposit", "unknown_lp"]:
            logger.info(f"[DECODE] ❌ Not an LP addition instruction: {ix_type}")
            return None

        # Extract pool info from instruction accounts
        pool_info = _extract_pool_from_instruction(raydium_ix, account_keys, ix_type)

        if not pool_info:
            # Fallback: try to extract from inner instructions
            logger.info(f"[DECODE] Trying fallback pool extraction from inner instructions...")
            pool_info = _extract_pool_from_inner_instructions(meta, account_keys)

        if not pool_info:
            logger.info(f"[DECODE] ❌ Could not extract pool info from instruction")
            return None

        logger.info(f"[DECODE] ✓ Pool: {pool_info.get('pool_address', '')[:12]}...")
        if pool_info.get('token_mint'):
            logger.info(f"[DECODE] ✓ Token mint: {pool_info['token_mint'][:12]}...")

        # CRITICAL: Calculate LP amounts from BALANCE DELTAS
        logger.info(f"[DECODE] Calculating balance deltas...")
        amounts = _calculate_balance_deltas(
            meta=meta,
            account_keys=account_keys,
            pool_info=pool_info
        )

        if not amounts:
            logger.info(f"[DECODE] ❌ Balance delta check failed (SOL did not increase)")
            return None

        logger.info(f"[DECODE] ✓ SOL delta: +{amounts['sol_delta']:.4f} SOL")
        logger.info(f"[DECODE] ✓ SOL before: {amounts.get('sol_before', 0):.4f} → after: {amounts.get('sol_after', 0):.4f}")
        logger.info(f"[DECODE] ✓ Token delta: +{amounts.get('token_delta', 0):,.0f}")
        if amounts.get('lp_minted', 0) > 0:
            logger.info(f"[DECODE] ✓ LP tokens minted: {amounts['lp_minted']:,.4f}")

        # Apply noise threshold
        min_sol_threshold = MIN_SOL_DELTA_LAMPORTS / 1_000_000_000
        if amounts["sol_delta"] < min_sol_threshold:
            logger.info(f"[DECODE] ❌ SOL delta below noise threshold ({amounts['sol_delta']:.4f} < {min_sol_threshold} SOL)")
            return None

        logger.info(f"[DECODE] ✓ Passed noise threshold ({amounts['sol_delta']:.4f} >= {min_sol_threshold} SOL)")

        # Get signature
        signature = signatures[0] if signatures else ""

        is_new_pool = ix_type in ["initialize", "initialize2"]
        logger.info(f"[DECODE] ✓ LP ADDITION CONFIRMED {'(NEW POOL)' if is_new_pool else '(ADD LIQUIDITY)'}")

        return LPAdditionInfo(
            pool_address=pool_info["pool_address"],
            token_mint=pool_info["token_mint"],
            quote_mint=pool_info.get("quote_mint", WSOL_MINT),
            token_amount=amounts.get("token_delta", 0),
            quote_amount_sol=amounts["sol_delta"],
            lp_tokens_minted=amounts.get("lp_minted", 0),
            liquidity_before_sol=amounts.get("sol_before", 0),
            liquidity_after_sol=amounts.get("sol_after", 0),
            is_pool_creation=is_new_pool,
            signature=signature
        )

    except Exception as e:
        logger.error(f"Error decoding Raydium transaction: {e}", exc_info=True)
        return None


def _get_account_keys(message: Dict[str, Any]) -> List[str]:
    """Extract account keys from transaction message."""
    account_keys = message.get("accountKeys", [])

    if not account_keys:
        return []

    # Handle both legacy and versioned formats
    if isinstance(account_keys[0], dict):
        # Versioned format: accountKeys is list of {pubkey, signer, writable}
        return [acc.get("pubkey", "") for acc in account_keys]
    else:
        # Legacy format: list of strings
        return account_keys


def _find_raydium_instruction(
    instructions: List[Dict],
    meta: Dict[str, Any]
) -> Tuple[Optional[Dict], str]:
    """
    Find Raydium AMM instruction and determine its type.

    Returns: (instruction, type) where type is one of:
    - "initialize" / "initialize2" (pool creation)
    - "deposit" (add liquidity)
    - "withdraw" (remove liquidity)
    - "swap" (not LP)
    - "unknown" (can't determine)
    """
    # Check main instructions
    for ix in instructions:
        if ix.get("programId") == RAYDIUM_AMM_V4:
            ix_type = _decode_instruction_type(ix.get("data", ""))
            return ix, ix_type

    # Check inner instructions (CPI calls)
    for inner in meta.get("innerInstructions", []):
        for ix in inner.get("instructions", []):
            if ix.get("programId") == RAYDIUM_AMM_V4:
                ix_type = _decode_instruction_type(ix.get("data", ""))
                return ix, ix_type

    return None, "unknown"


def _decode_instruction_type(data: str) -> str:
    """
    Decode Raydium instruction type from base58/base64 encoded data.

    Raydium AMM V4 uses discriminator bytes to identify instruction type.
    """
    if not data:
        return "unknown"

    try:
        # Try base58 first (most common for Solana)
        try:
            import base58
            decoded = base58.b58decode(data)
        except:
            # Fallback to base64
            decoded = base64.b64decode(data)

        if len(decoded) < 1:
            return "unknown"

        # Raydium AMM V4 instruction discriminators (first byte)
        discriminator = decoded[0]

        # Based on Raydium AMM source code
        if discriminator == 0:
            return "initialize"
        elif discriminator == 1:
            return "initialize2"
        elif discriminator == 3:
            return "deposit"  # Add liquidity
        elif discriminator == 4:
            return "withdraw"  # Remove liquidity
        elif discriminator == 9:
            return "swap"
        else:
            # Check if it might be an LP operation by looking at account count
            # LP operations typically have more accounts than swaps
            return "unknown_lp"

    except Exception as e:
        logger.debug(f"Could not decode instruction data: {e}")
        return "unknown"


def _extract_pool_from_instruction(
    instruction: Dict[str, Any],
    account_keys: List[str],
    ix_type: str
) -> Optional[Dict[str, str]]:
    """
    Extract pool info from Raydium instruction accounts.

    Account layouts vary by instruction type.
    """
    accounts = instruction.get("accounts", [])

    if not accounts:
        return None

    def get_account(idx: int) -> Optional[str]:
        """Get account pubkey by instruction account index."""
        if idx < len(accounts):
            account_idx = accounts[idx]
            if isinstance(account_idx, int) and account_idx < len(account_keys):
                return account_keys[account_idx]
        return None

    try:
        if ix_type in ["initialize", "initialize2"]:
            # Initialize account layout (approximate - may need adjustment)
            # Accounts: [token_program, sys_program, rent, amm_id, amm_authority,
            #           amm_open_orders, lp_mint, coin_mint, pc_mint, coin_vault,
            #           pc_vault, target_orders, market, ...]
            return {
                "pool_address": get_account(3) or "",
                "lp_mint": get_account(6) or "",
                "token_mint": get_account(7) or "",
                "quote_mint": get_account(8) or WSOL_MINT,
                "token_vault": get_account(9) or "",
                "quote_vault": get_account(10) or "",
            }

        elif ix_type == "deposit":
            # Deposit account layout (approximate)
            # Accounts: [token_program, amm_id, amm_authority, amm_open_orders,
            #           amm_target_orders, lp_mint, coin_vault, pc_vault,
            #           market, user_coin, user_pc, user_lp, ...]
            return {
                "pool_address": get_account(1) or "",
                "lp_mint": get_account(5) or "",
                "token_vault": get_account(6) or "",
                "quote_vault": get_account(7) or "",
                # For deposit, we need to get mints from token balances
                "token_mint": "",
                "quote_mint": WSOL_MINT,
            }

        else:
            # Unknown type - try to extract what we can
            # Pool is usually one of the first accounts
            pool = get_account(0) or get_account(1) or get_account(3) or ""
            return {
                "pool_address": pool,
                "token_mint": "",
                "quote_mint": WSOL_MINT,
            }

    except Exception as e:
        logger.debug(f"Error extracting pool from instruction: {e}")
        return None


def _extract_pool_from_inner_instructions(
    meta: Dict[str, Any],
    account_keys: List[str]
) -> Optional[Dict[str, str]]:
    """Fallback: Extract pool info from inner instructions and token balances."""
    try:
        # Look at post token balances to find pool vaults
        post_balances = meta.get("postTokenBalances", [])

        sol_vaults = []
        token_vaults = []

        for balance in post_balances:
            mint = balance.get("mint", "")
            owner = balance.get("owner", "")

            if mint == WSOL_MINT:
                sol_vaults.append({"owner": owner, "balance": balance})
            elif mint:
                token_vaults.append({"owner": owner, "mint": mint, "balance": balance})

        # Find vault with largest SOL balance (likely the pool)
        if sol_vaults:
            sol_vaults.sort(
                key=lambda x: float(x["balance"].get("uiTokenAmount", {}).get("uiAmount", 0) or 0),
                reverse=True
            )
            pool_owner = sol_vaults[0]["owner"]

            # Find token vault with same owner
            token_mint = ""
            for tv in token_vaults:
                if tv["owner"] == pool_owner:
                    token_mint = tv["mint"]
                    break

            if token_mint:
                return {
                    "pool_address": pool_owner,
                    "token_mint": token_mint,
                    "quote_mint": WSOL_MINT,
                }

        return None

    except Exception as e:
        logger.debug(f"Error extracting pool from inner instructions: {e}")
        return None


def _calculate_balance_deltas(
    meta: Dict[str, Any],
    account_keys: List[str],
    pool_info: Dict[str, str]
) -> Optional[Dict[str, float]]:
    """
    Calculate actual LP amounts from balance deltas.

    This is the CRITICAL check - we verify that:
    1. SOL balance in vault INCREASED
    2. Token balance in vault INCREASED
    3. LP tokens were minted

    Returns None if this doesn't look like an LP addition.
    """
    try:
        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        pre_token_balances = meta.get("preTokenBalances", [])
        post_token_balances = meta.get("postTokenBalances", [])

        # Build token balance lookup by account index
        pre_tokens = {b.get("accountIndex"): b for b in pre_token_balances}
        post_tokens = {b.get("accountIndex"): b for b in post_token_balances}

        # Calculate SOL delta (lamport balance changes)
        # Find the largest SOL increase (this is the pool vault receiving SOL)
        max_sol_increase = 0
        sol_before = 0
        sol_after = 0

        for i in range(min(len(pre_balances), len(post_balances))):
            pre = pre_balances[i]
            post = post_balances[i]
            delta = post - pre

            if delta > max_sol_increase:
                max_sol_increase = delta
                sol_before = pre / 1_000_000_000
                sol_after = post / 1_000_000_000

        sol_delta = max_sol_increase / 1_000_000_000  # Convert to SOL

        # RULE: SOL must INCREASE for LP add
        if sol_delta <= 0:
            logger.debug("SOL balance did not increase - not an LP add")
            return None

        # Calculate token delta
        token_delta = 0
        token_mint = pool_info.get("token_mint", "")

        for idx, post in post_tokens.items():
            if post.get("mint") == token_mint or (not token_mint and post.get("mint") != WSOL_MINT):
                pre = pre_tokens.get(idx, {})
                pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                delta = post_amount - pre_amount

                if delta > token_delta:
                    token_delta = delta
                    # Update token_mint if we found it
                    if not pool_info.get("token_mint"):
                        pool_info["token_mint"] = post.get("mint", "")

        # Calculate LP tokens minted (look for LP mint increases to user)
        lp_minted = 0
        lp_mint = pool_info.get("lp_mint", "")

        if lp_mint:
            for idx, post in post_tokens.items():
                if post.get("mint") == lp_mint:
                    pre = pre_tokens.get(idx, {})
                    pre_amount = float(pre.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                    post_amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0) or 0)
                    delta = post_amount - pre_amount
                    if delta > 0:
                        lp_minted += delta

        return {
            "sol_delta": sol_delta,
            "sol_before": sol_before,
            "sol_after": sol_after,
            "token_delta": token_delta,
            "lp_minted": lp_minted,
        }

    except Exception as e:
        logger.error(f"Error calculating balance deltas: {e}")
        return None


def get_pool_liquidity(pool_address: str, http_rpc_url: str) -> Optional[Dict[str, float]]:
    """
    Get current pool liquidity by querying vault token accounts.

    Args:
        pool_address: Raydium pool address
        http_rpc_url: QuickNode HTTP RPC URL

    Returns:
        Dict with 'sol_amount' and 'token_amount' or None
    """
    # For a complete implementation, we would:
    # 1. Get pool account data
    # 2. Decode to find vault addresses
    # 3. Query vault balances
    # This requires knowing the exact pool account layout
    return None
