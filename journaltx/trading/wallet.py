"""
Wallet management for JournalTX trading.

Handles encrypted wallet storage and signing.
"""

import logging
import os
from typing import Optional, Tuple

import base58
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.api import Client

logger = logging.getLogger(__name__)


class WalletManager:
    """
    Manages encrypted wallet storage and signing.

    Uses AES-256-GCM encryption with per-user random salts.
    """

    def __init__(self, encryption_key: str, rpc_url: str):
        """
        Initialize wallet manager.

        Args:
            encryption_key: 32-byte hex-encoded encryption key
            rpc_url: Solana RPC endpoint URL
        """
        if not encryption_key:
            raise ValueError("WALLET_ENCRYPTION_KEY is required")

        self.encryption_key = bytes.fromhex(encryption_key)
        if len(self.encryption_key) != 32:
            raise ValueError("WALLET_ENCRYPTION_KEY must be 32 bytes (64 hex chars)")

        self.aesgcm = AESGCM(self.encryption_key)
        self.rpc_client = Client(rpc_url)

    def validate_private_key(self, private_key_base58: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate a base58 private key.

        Args:
            private_key_base58: Base58-encoded private key

        Returns:
            Tuple of (is_valid, pubkey_str, error_message)
        """
        try:
            # Decode base58
            key_bytes = base58.b58decode(private_key_base58)

            # Solana private keys are 64 bytes (32 private + 32 public)
            # or 32 bytes (private only, public derived)
            if len(key_bytes) == 64:
                keypair = Keypair.from_bytes(key_bytes)
            elif len(key_bytes) == 32:
                keypair = Keypair.from_seed(key_bytes)
            else:
                return False, None, f"Invalid key length: {len(key_bytes)} bytes"

            pubkey = str(keypair.pubkey())
            return True, pubkey, None

        except Exception as e:
            return False, None, str(e)

    def encrypt_wallet(self, private_key_base58: str) -> Tuple[bytes, bytes]:
        """
        Encrypt a private key for storage.

        Args:
            private_key_base58: Base58-encoded private key

        Returns:
            Tuple of (encrypted_wallet, salt)
        """
        # Generate random salt/nonce (12 bytes for GCM)
        salt = os.urandom(12)

        # Encrypt
        plaintext = private_key_base58.encode('utf-8')
        ciphertext = self.aesgcm.encrypt(salt, plaintext, None)

        return ciphertext, salt

    def decrypt_wallet(self, encrypted_wallet: bytes, salt: bytes) -> Optional[str]:
        """
        Decrypt a stored wallet.

        Args:
            encrypted_wallet: Encrypted private key
            salt: Salt used for encryption

        Returns:
            Base58-encoded private key, or None on error
        """
        try:
            plaintext = self.aesgcm.decrypt(salt, encrypted_wallet, None)
            return plaintext.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt wallet: {e}")
            return None

    def get_keypair(self, encrypted_wallet: bytes, salt: bytes) -> Optional[Keypair]:
        """
        Get a Keypair from encrypted storage.

        Args:
            encrypted_wallet: Encrypted private key
            salt: Salt used for encryption

        Returns:
            Keypair object, or None on error
        """
        private_key_base58 = self.decrypt_wallet(encrypted_wallet, salt)
        if not private_key_base58:
            return None

        try:
            key_bytes = base58.b58decode(private_key_base58)
            if len(key_bytes) == 64:
                return Keypair.from_bytes(key_bytes)
            elif len(key_bytes) == 32:
                return Keypair.from_seed(key_bytes)
            return None
        except Exception as e:
            logger.error(f"Failed to create keypair: {e}")
            return None
        finally:
            # Zeroize private key from memory
            private_key_base58 = None

    def get_balance(self, pubkey: str) -> Optional[float]:
        """
        Get SOL balance for a wallet.

        Args:
            pubkey: Public key string

        Returns:
            Balance in SOL, or None on error
        """
        try:
            pubkey_obj = Pubkey.from_string(pubkey)
            response = self.rpc_client.get_balance(pubkey_obj)
            if response.value is not None:
                return response.value / 1e9  # lamports to SOL
            return None
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return None

    def get_sol_price(self) -> Optional[float]:
        """
        Get current SOL/USD price from CoinGecko.

        Returns:
            SOL price in USD, or None on error
        """
        try:
            import requests
            response = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "solana", "vs_currencies": "usd"},
                timeout=5
            )
            response.raise_for_status()
            return response.json()["solana"]["usd"]
        except Exception as e:
            logger.error(f"Failed to get SOL price: {e}")
            return 200.0  # Fallback price
