"""
Token metadata resolution for Solana tokens.

Resolves token mint addresses to symbols, names, and other metadata.
Uses Jupiter API (free, no auth required) and DexScreener.
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from functools import lru_cache
import time

import requests

logger = logging.getLogger(__name__)

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes

# Rate limiting
_last_request_time = 0
MIN_REQUEST_INTERVAL = 0.2  # 200ms between requests


@dataclass
class TokenInfo:
    """Token metadata."""
    mint: str
    symbol: str
    name: str
    decimals: int
    logo_uri: Optional[str] = None
    coingecko_id: Optional[str] = None


@dataclass
class PairInfo:
    """Trading pair information from DexScreener."""
    pair_address: str
    token_mint: str
    token_symbol: str
    token_name: str
    quote_mint: str
    quote_symbol: str
    liquidity_usd: float
    liquidity_base: float
    liquidity_quote: float
    market_cap: float
    fdv: float
    pair_created_at: int  # Unix timestamp in ms
    price_usd: float
    price_native: float
    volume_24h: float
    buys_5m: int
    sells_5m: int
    dex_id: str
    url: str


def _rate_limit():
    """Simple rate limiter."""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    if elapsed < MIN_REQUEST_INTERVAL:
        time.sleep(MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.time()


class TokenResolver:
    """
    Resolves token mint addresses to metadata.

    Uses multiple sources:
    1. Jupiter Token List (fast, reliable)
    2. DexScreener (has pair info, liquidity)
    3. On-chain metadata (fallback)
    """

    def __init__(self, http_rpc_url: Optional[str] = None):
        self.http_rpc_url = http_rpc_url
        self.session = requests.Session()
        self._jupiter_tokens: Dict[str, TokenInfo] = {}
        self._jupiter_loaded = False

    def _load_jupiter_tokens(self):
        """Load Jupiter token list (cached)."""
        if self._jupiter_loaded:
            return

        try:
            _rate_limit()
            # Use Jupiter's strict list for known tokens
            response = self.session.get(
                "https://token.jup.ag/strict",
                timeout=15
            )
            response.raise_for_status()
            tokens = response.json()

            for token in tokens:
                mint = token.get("address", "")
                self._jupiter_tokens[mint] = TokenInfo(
                    mint=mint,
                    symbol=token.get("symbol", "UNKNOWN"),
                    name=token.get("name", "Unknown Token"),
                    decimals=token.get("decimals", 9),
                    logo_uri=token.get("logoURI"),
                    coingecko_id=token.get("extensions", {}).get("coingeckoId")
                )

            self._jupiter_loaded = True
            logger.info(f"Loaded {len(self._jupiter_tokens)} tokens from Jupiter")

        except Exception as e:
            logger.error(f"Failed to load Jupiter token list: {e}")

    def get_token_info(self, mint: str) -> Optional[TokenInfo]:
        """
        Get token info by mint address.

        Args:
            mint: Token mint address

        Returns:
            TokenInfo or None
        """
        # Check Jupiter cache first
        self._load_jupiter_tokens()
        if mint in self._jupiter_tokens:
            return self._jupiter_tokens[mint]

        # Try DexScreener for unknown tokens
        pair_info = self.get_pair_info_by_token(mint)
        if pair_info:
            return TokenInfo(
                mint=mint,
                symbol=pair_info.token_symbol,
                name=pair_info.token_name,
                decimals=9  # Assume 9 for meme tokens
            )

        # Fallback: query on-chain metadata
        return self._get_onchain_metadata(mint)

    def get_pair_info_by_token(self, token_mint: str) -> Optional[PairInfo]:
        """
        Get trading pair info from DexScreener by token mint.

        Args:
            token_mint: Token mint address

        Returns:
            PairInfo for the most liquid SOL pair, or None
        """
        try:
            _rate_limit()
            url = f"https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            pairs = data.get("pairs", [])
            if not pairs:
                return None

            # Find most liquid Solana SOL pair
            best_pair = None
            best_liquidity = 0

            for pair in pairs:
                if pair.get("chainId") != "solana":
                    continue

                quote_symbol = pair.get("quoteToken", {}).get("symbol", "")
                if quote_symbol not in ["SOL", "WSOL"]:
                    continue

                liquidity = pair.get("liquidity", {}).get("usd", 0) or 0
                if liquidity > best_liquidity:
                    best_liquidity = liquidity
                    best_pair = pair

            if not best_pair:
                return None

            return self._parse_dexscreener_pair(best_pair)

        except Exception as e:
            logger.error(f"Failed to get pair info for {token_mint}: {e}")
            return None

    def get_pair_info_by_address(self, pair_address: str) -> Optional[PairInfo]:
        """
        Get trading pair info from DexScreener by pair address.

        Args:
            pair_address: Raydium pool address

        Returns:
            PairInfo or None
        """
        # Validate pair_address is not empty
        if not pair_address or not pair_address.strip():
            logger.debug("Skipping DexScreener lookup - empty pair address")
            return None

        try:
            _rate_limit()
            url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            pair = data.get("pair")
            if not pair:
                # Try alternate endpoint
                pairs = data.get("pairs", [])
                if pairs:
                    pair = pairs[0]

            if not pair:
                return None

            return self._parse_dexscreener_pair(pair)

        except Exception as e:
            logger.error(f"Failed to get pair info for address {pair_address}: {e}")
            return None

    def _parse_dexscreener_pair(self, pair: Dict[str, Any]) -> PairInfo:
        """Parse DexScreener pair response into PairInfo."""
        base_token = pair.get("baseToken", {})
        quote_token = pair.get("quoteToken", {})
        liquidity = pair.get("liquidity", {})
        txns = pair.get("txns", {})
        m5 = txns.get("m5", {})

        return PairInfo(
            pair_address=pair.get("pairAddress", ""),
            token_mint=base_token.get("address", ""),
            token_symbol=base_token.get("symbol", "UNKNOWN"),
            token_name=base_token.get("name", "Unknown"),
            quote_mint=quote_token.get("address", ""),
            quote_symbol=quote_token.get("symbol", "SOL"),
            liquidity_usd=liquidity.get("usd", 0) or 0,
            liquidity_base=liquidity.get("base", 0) or 0,
            liquidity_quote=liquidity.get("quote", 0) or 0,
            market_cap=pair.get("marketCap", 0) or pair.get("fdv", 0) or 0,
            fdv=pair.get("fdv", 0) or 0,
            pair_created_at=pair.get("pairCreatedAt", 0) or 0,
            price_usd=float(pair.get("priceUsd", 0) or 0),
            price_native=float(pair.get("priceNative", 0) or 0),
            volume_24h=pair.get("volume", {}).get("h24", 0) or 0,
            buys_5m=m5.get("buys", 0),
            sells_5m=m5.get("sells", 0),
            dex_id=pair.get("dexId", "raydium"),
            url=pair.get("url", "")
        )

    def _get_onchain_metadata(self, mint: str) -> Optional[TokenInfo]:
        """
        Get token metadata from on-chain (Metaplex).

        This is a fallback for tokens not in Jupiter or DexScreener.
        """
        if not self.http_rpc_url:
            return None

        try:
            # Get token mint info
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getAccountInfo",
                "params": [
                    mint,
                    {"encoding": "jsonParsed"}
                ]
            }

            response = self.session.post(self.http_rpc_url, json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()

            result = data.get("result", {})
            value = result.get("value")

            if not value:
                return None

            parsed = value.get("data", {}).get("parsed", {})
            info = parsed.get("info", {})

            return TokenInfo(
                mint=mint,
                symbol="???",  # Can't get symbol from mint account
                name="Unknown Token",
                decimals=info.get("decimals", 9)
            )

        except Exception as e:
            logger.error(f"Failed to get on-chain metadata for {mint}: {e}")
            return None


class PriceService:
    """
    Real-time price service for SOL and tokens.

    Uses Jupiter Price API (free, no auth).
    """

    def __init__(self):
        self.session = requests.Session()
        self._sol_price_cache: Optional[float] = None
        self._sol_price_time: float = 0
        self._cache_ttl = 60  # 1 minute cache

    def get_sol_price_usd(self) -> float:
        """
        Get current SOL price in USD.

        Uses multiple sources with fallback:
        1. Jupiter Price API
        2. CoinGecko API
        3. Cached value or default

        Returns:
            SOL price or default if unavailable
        """
        now = time.time()

        # Check cache
        if self._sol_price_cache and (now - self._sol_price_time) < self._cache_ttl:
            return self._sol_price_cache

        # Try Jupiter first
        try:
            _rate_limit()
            response = self.session.get(
                "https://price.jup.ag/v6/price?ids=SOL",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            sol_data = data.get("data", {}).get("SOL", {})
            price = sol_data.get("price", 0)

            if price > 0:
                self._sol_price_cache = price
                self._sol_price_time = now
                return price

        except Exception as e:
            logger.debug(f"Jupiter price API failed: {e}")

        # Try CoinGecko as fallback
        try:
            _rate_limit()
            response = self.session.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            price = data.get("solana", {}).get("usd", 0)
            if price > 0:
                self._sol_price_cache = price
                self._sol_price_time = now
                return price

        except Exception as e:
            logger.debug(f"CoinGecko price API failed: {e}")

        # Return cached value or default
        return self._sol_price_cache or 200.0  # Default to $200 as reasonable fallback

    def get_token_price_usd(self, mint: str) -> Optional[float]:
        """
        Get token price in USD.

        Args:
            mint: Token mint address

        Returns:
            Price in USD or None
        """
        try:
            _rate_limit()
            response = self.session.get(
                f"https://price.jup.ag/v6/price?ids={mint}",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            token_data = data.get("data", {}).get(mint, {})
            return token_data.get("price")

        except Exception as e:
            logger.debug(f"Failed to get price for {mint}: {e}")
            return None


# Global instances
_token_resolver: Optional[TokenResolver] = None
_price_service: Optional[PriceService] = None


def get_token_resolver(http_rpc_url: Optional[str] = None) -> TokenResolver:
    """Get or create global TokenResolver instance."""
    global _token_resolver
    if _token_resolver is None:
        _token_resolver = TokenResolver(http_rpc_url)
    return _token_resolver


def get_price_service() -> PriceService:
    """Get or create global PriceService instance."""
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
    return _price_service
