"""
Parse Solana transactions to extract LP addition details.

This module handles decoding Solana transaction data to extract
liquidity pool addition information including tokens and amounts.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

import requests

from journaltx.ingest.quicknode.raydium_decoder import (
    decode_raydium_transaction,
    LPAdditionInfo,
    RAYDIUM_AMM_V4,
)
from journaltx.ingest.token_resolver import (
    get_token_resolver,
    get_price_service,
    PairInfo,
)

logger = logging.getLogger(__name__)


@dataclass
class ParsedLPEvent:
    """
    Fully parsed LP event with all metadata.
    """
    # Transaction info
    signature: str
    slot: int

    # Pool info
    pool_address: str
    is_new_pool: bool

    # Token info
    token_mint: str
    token_symbol: str
    token_name: str

    # Amounts
    sol_amount: float
    sol_amount_usd: float
    token_amount: float

    # Market data (from DexScreener)
    liquidity_usd: float
    liquidity_sol: float
    market_cap: float
    pair_age_hours: float
    price_usd: float

    # Pair info
    pair_string: str  # e.g., "BONK/SOL"
    dexscreener_url: str

    # Timestamp
    timestamp: datetime


class SolanaTransactionParser:
    """
    Parse Solana transactions to extract LP addition details.

    Uses Raydium decoder + token resolver for complete data.
    """

    def __init__(self, http_rpc_url: str):
        """
        Initialize parser.

        Args:
            http_rpc_url: QuickNode HTTP RPC URL for fetching transaction details
        """
        self.http_rpc_url = http_rpc_url
        self.session = requests.Session()
        self.token_resolver = get_token_resolver(http_rpc_url)
        self.price_service = get_price_service()

    def get_transaction(self, signature: str, retries: int = 3) -> Optional[Dict[str, Any]]:
        """
        Fetch full transaction details from QuickNode.

        Args:
            signature: Transaction signature
            retries: Number of retry attempts

        Returns:
            Transaction details or None
        """
        import time

        for attempt in range(retries):
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "getTransaction",
                    "params": [
                        signature,
                        {
                            "encoding": "jsonParsed",
                            "maxSupportedTransactionVersion": 0,
                            "commitment": "confirmed"  # Match subscription commitment
                        }
                    ]
                }

                response = self.session.post(
                    self.http_rpc_url,
                    json=payload,
                    timeout=15
                )
                response.raise_for_status()
                data = response.json()

                if data.get("error"):
                    logger.info(f"[FETCH] RPC error (attempt {attempt+1}): {data['error']}")
                    if attempt < retries - 1:
                        time.sleep(0.5)  # Wait before retry
                        continue
                    return None

                if data.get("result"):
                    logger.info(f"[FETCH] ✓ Transaction fetched successfully")
                    return data["result"]

                # Result is null - transaction not yet available
                if attempt < retries - 1:
                    logger.info(f"[FETCH] Transaction not available yet (attempt {attempt+1}), retrying...")
                    time.sleep(0.5)  # Wait before retry
                    continue

                logger.info(f"[FETCH] ❌ Transaction still not available after {retries} attempts")
                return None

            except Exception as e:
                logger.error(f"[FETCH] Error fetching transaction {signature[:12]}...: {e}")
                if attempt < retries - 1:
                    time.sleep(0.5)
                    continue
                return None

        return None

    def parse_lp_event(self, transaction: Dict[str, Any]) -> Optional[ParsedLPEvent]:
        """
        Parse a transaction into a complete LP event.

        Args:
            transaction: Parsed transaction data from QuickNode

        Returns:
            ParsedLPEvent with all metadata, or None if not an LP event
        """
        try:
            # Step 1: Decode Raydium instruction
            lp_info = decode_raydium_transaction(transaction, self.http_rpc_url)

            if not lp_info:
                return None

            if lp_info.quote_amount_sol <= 0:
                logger.debug("No SOL amount in LP addition")
                return None

            # Step 2: Get token metadata
            token_info = self.token_resolver.get_token_info(lp_info.token_mint)
            token_symbol = token_info.symbol if token_info else "???"
            token_name = token_info.name if token_info else "Unknown Token"

            # Step 3: Get pair/market data from DexScreener
            pair_info = self._get_pair_info(lp_info)

            # Step 4: Get SOL price
            sol_price = self.price_service.get_sol_price_usd()
            sol_amount_usd = lp_info.quote_amount_sol * sol_price

            # Step 5: Calculate pair age
            pair_age_hours = 0.0
            if pair_info and pair_info.pair_created_at:
                created_ts = pair_info.pair_created_at / 1000  # ms to seconds
                age_seconds = datetime.now().timestamp() - created_ts
                pair_age_hours = max(0, age_seconds / 3600)

            # If new pool, age is essentially 0
            if lp_info.is_pool_creation:
                pair_age_hours = 0.0

            # Step 6: Get slot
            slot = transaction.get("slot", 0)

            # Step 7: Build pair string
            # Use DexScreener symbol if available and different
            if pair_info and pair_info.token_symbol and pair_info.token_symbol != "???":
                token_symbol = pair_info.token_symbol
                token_name = pair_info.token_name

            pair_string = f"{token_symbol}/SOL"

            # Step 8: Build DexScreener URL
            dex_url = f"https://dexscreener.com/solana/{lp_info.token_mint}"
            if pair_info and pair_info.pair_address:
                dex_url = f"https://dexscreener.com/solana/{pair_info.pair_address}"

            # Use ON-CHAIN liquidity data (not DexScreener)
            # liquidity_before and liquidity_after come from balance delta analysis
            liquidity_before_sol = lp_info.liquidity_before_sol
            liquidity_after_sol = lp_info.liquidity_after_sol

            # Log the on-chain vs DexScreener comparison for debugging
            if pair_info:
                logger.debug(
                    f"Liquidity comparison: on-chain={liquidity_after_sol:.1f} SOL, "
                    f"DexScreener={pair_info.liquidity_quote:.1f} SOL"
                )

            return ParsedLPEvent(
                signature=lp_info.signature,
                slot=slot,
                pool_address=lp_info.pool_address,
                is_new_pool=lp_info.is_pool_creation,
                token_mint=lp_info.token_mint,
                token_symbol=token_symbol,
                token_name=token_name,
                sol_amount=lp_info.quote_amount_sol,
                sol_amount_usd=sol_amount_usd,
                token_amount=lp_info.token_amount,
                # Use ON-CHAIN liquidity (primary) with DexScreener as fallback
                liquidity_usd=liquidity_after_sol * sol_price if liquidity_after_sol > 0 else (pair_info.liquidity_usd if pair_info else sol_amount_usd * 2),
                liquidity_sol=liquidity_after_sol if liquidity_after_sol > 0 else (pair_info.liquidity_quote if pair_info else lp_info.quote_amount_sol),
                market_cap=pair_info.market_cap if pair_info else 0,
                pair_age_hours=pair_age_hours,
                price_usd=pair_info.price_usd if pair_info else 0,
                pair_string=pair_string,
                dexscreener_url=dex_url,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error parsing LP event: {e}")
            return None

    def _get_pair_info(self, lp_info: LPAdditionInfo) -> Optional[PairInfo]:
        """
        Get pair info from DexScreener.

        Tries pool address first, then token mint.
        """
        # Try by pool address first (more accurate)
        pair_info = self.token_resolver.get_pair_info_by_address(lp_info.pool_address)

        if pair_info:
            return pair_info

        # Fall back to token mint
        return self.token_resolver.get_pair_info_by_token(lp_info.token_mint)

    def extract_lp_addition(self, transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Legacy method for backwards compatibility.

        Use parse_lp_event() for full data.
        """
        parsed = self.parse_lp_event(transaction)

        if not parsed:
            return None

        return {
            "token_a": parsed.token_symbol,
            "token_b": "SOL",
            "token_mint": parsed.token_mint,
            "pool_address": parsed.pool_address,
            "amount_a": parsed.token_amount,
            "amount_b": parsed.sol_amount,
            "amount_b_usd": parsed.sol_amount_usd,
            "is_new_pool": parsed.is_new_pool,
            "liquidity_usd": parsed.liquidity_usd,
            "liquidity_sol": parsed.liquidity_sol,
            "market_cap": parsed.market_cap,
            "pair_age_hours": parsed.pair_age_hours,
            "signature": parsed.signature,
            "pair_string": parsed.pair_string,
            "dexscreener_url": parsed.dexscreener_url,
        }

    def is_raydium_lp_add(self, transaction: Dict[str, Any]) -> bool:
        """
        Check if transaction is a Raydium LP addition.

        Args:
            transaction: Parsed transaction data

        Returns:
            True if this is a Raydium LP addition
        """
        try:
            message = transaction.get("transaction", {}).get("message", {})
            instructions = message.get("instructions", [])

            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id == RAYDIUM_AMM_V4:
                    return True

            # Check inner instructions
            meta = transaction.get("meta", {})
            for inner in meta.get("innerInstructions", []):
                for ix in inner.get("instructions", []):
                    if ix.get("programId") == RAYDIUM_AMM_V4:
                        return True

            return False

        except Exception as e:
            logger.error(f"Error checking if Raydium LP: {e}")
            return False
