"""
Trading automation module for JournalTX.

Handles wallet management, Jupiter swaps, and spending limits.
"""

from journaltx.trading.wallet import WalletManager
from journaltx.trading.jupiter import JupiterSwap
from journaltx.trading.executor import TransactionExecutor
from journaltx.trading.spending import SpendingGuard

__all__ = ["WalletManager", "JupiterSwap", "TransactionExecutor", "SpendingGuard"]
