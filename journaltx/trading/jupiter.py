"""
Jupiter V6 swap integration for JournalTX.

Handles token swaps via Jupiter aggregator.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from solders.transaction import VersionedTransaction

logger = logging.getLogger(__name__)

# Jupiter API endpoints
JUPITER_QUOTE_API = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_API = "https://quote-api.jup.ag/v6/swap"

# SOL mint address
SOL_MINT = "So11111111111111111111111111111111111111112"


@dataclass
class SwapQuote:
    """Quote from Jupiter for a swap."""
    input_mint: str
    output_mint: str
    in_amount: int  # lamports
    out_amount: int  # smallest unit of output token
    price_impact_pct: float
    slippage_bps: int
    route_plan: list
    raw_quote: dict  # Full quote response for swap request


@dataclass
class SwapResult:
    """Result of a swap execution."""
    success: bool
    tx_signature: Optional[str] = None
    tokens_received: Optional[float] = None
    error: Optional[str] = None


class JupiterSwap:
    """
    Jupiter V6 swap client.

    Handles quote fetching and swap transaction building.
    """

    def __init__(self, slippage_bps: int = 100, priority_fee: int = 100000):
        """
        Initialize Jupiter swap client.

        Args:
            slippage_bps: Slippage tolerance in basis points (100 = 1%)
            priority_fee: Priority fee in lamports
        """
        self.slippage_bps = slippage_bps
        self.priority_fee = priority_fee

    def get_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: Optional[int] = None
    ) -> Optional[SwapQuote]:
        """
        Get a swap quote from Jupiter.

        Args:
            input_mint: Input token mint address
            output_mint: Output token mint address
            amount: Amount in smallest unit (lamports for SOL)
            slippage_bps: Override default slippage

        Returns:
            SwapQuote object, or None on error
        """
        try:
            params = {
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps or self.slippage_bps,
                "onlyDirectRoutes": False,
                "asLegacyTransaction": False,
            }

            response = requests.get(JUPITER_QUOTE_API, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error(f"Jupiter quote error: {data['error']}")
                return None

            return SwapQuote(
                input_mint=data["inputMint"],
                output_mint=data["outputMint"],
                in_amount=int(data["inAmount"]),
                out_amount=int(data["outAmount"]),
                price_impact_pct=float(data.get("priceImpactPct", 0)),
                slippage_bps=slippage_bps or self.slippage_bps,
                route_plan=data.get("routePlan", []),
                raw_quote=data,
            )

        except Exception as e:
            logger.error(f"Failed to get Jupiter quote: {e}")
            return None

    def get_swap_transaction(
        self,
        quote: SwapQuote,
        user_pubkey: str,
        priority_fee: Optional[int] = None
    ) -> Optional[bytes]:
        """
        Get a swap transaction from Jupiter.

        Args:
            quote: Quote from get_quote()
            user_pubkey: User's wallet public key
            priority_fee: Override default priority fee

        Returns:
            Serialized transaction bytes, or None on error
        """
        try:
            payload = {
                "quoteResponse": quote.raw_quote,
                "userPublicKey": user_pubkey,
                "wrapAndUnwrapSol": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": priority_fee or self.priority_fee,
            }

            response = requests.post(JUPITER_SWAP_API, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "error" in data:
                logger.error(f"Jupiter swap error: {data['error']}")
                return None

            # Decode base64 transaction
            import base64
            swap_tx_bytes = base64.b64decode(data["swapTransaction"])
            return swap_tx_bytes

        except Exception as e:
            logger.error(f"Failed to get Jupiter swap transaction: {e}")
            return None

    def buy_token(
        self,
        token_mint: str,
        sol_amount: float,
        user_pubkey: str,
        slippage_bps: Optional[int] = None
    ) -> tuple[Optional[SwapQuote], Optional[bytes]]:
        """
        Build a buy transaction for a token.

        Args:
            token_mint: Token to buy
            sol_amount: SOL amount to spend
            user_pubkey: User's wallet public key
            slippage_bps: Override slippage

        Returns:
            Tuple of (quote, transaction_bytes)
        """
        # Convert SOL to lamports
        lamports = int(sol_amount * 1e9)

        # Get quote: SOL -> Token
        quote = self.get_quote(
            input_mint=SOL_MINT,
            output_mint=token_mint,
            amount=lamports,
            slippage_bps=slippage_bps
        )

        if not quote:
            return None, None

        # Get swap transaction
        tx_bytes = self.get_swap_transaction(quote, user_pubkey)

        return quote, tx_bytes
