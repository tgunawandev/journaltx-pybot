"""
Parse Solana transactions to extract LP addition details.

This module handles decoding Solana transaction data to extract
liquidity pool addition information including tokens and amounts.
"""

import base64
import logging
from typing import Dict, Any, Optional, Tuple
from struct import unpack_from

import requests

logger = logging.getLogger(__name__)


class SolanaTransactionParser:
    """
    Parse Solana transactions to extract LP addition details.
    """

    def __init__(self, http_rpc_url: str):
        """
        Initialize parser.

        Args:
            http_rpc_url: QuickNode HTTP RPC URL for fetching transaction details
        """
        self.http_rpc_url = http_rpc_url
        self.session = requests.Session()

    def get_transaction(self, signature: str) -> Optional[Dict[str, Any]]:
        """
        Fetch full transaction details from QuickNode.

        Args:
            signature: Transaction signature

        Returns:
            Transaction details or None
        """
        try:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    signature,
                    {"encoding": "jsonParsed"}
                ]
            }

            response = self.session.post(
                self.http_rpc_url,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("result"):
                return data["result"]

            return None

        except Exception as e:
            logger.error(f"Error fetching transaction {signature}: {e}")
            return None

    def extract_lp_addition(self, transaction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract LP addition details from a transaction.

        Args:
            transaction: Parsed transaction data from QuickNode

        Returns:
            Dict with 'token_a', 'token_b', 'amount_a', 'amount_b' or None
        """
        try:
            # Get transaction instructions
            meta = transaction.get("meta", {})
            pre_balances = meta.get("preBalances", [])
            post_balances = meta.get("postBalances", [])
            account_keys = transaction.get("transaction", {}).get("message", {}).get("accountKeys", [])

            if not account_keys or len(pre_balances) == 0 or len(post_balances) == 0:
                return None

            # Find SOL balance changes
            sol_changes = []

            for i, (pre, post) in enumerate(zip(pre_balances, post_balances)):
                change = int(post) - int(pre)
                # Only consider positive changes (deposits)
                if change > 0:
                    sol_changes.append({
                        "account": account_keys[i],
                        "change_lamports": change,
                        "change_sol": change / 1_000_000_000  # Convert to SOL
                    })

            if not sol_changes:
                return None

            # Sort by amount descending (largest deposit is likely the LP)
            sol_changes.sort(key=lambda x: x["change_sol"], reverse=True)

            # Use the largest SOL deposit as our estimate
            largest_deposit = sol_changes[0]

            # For now, we'll use a simplified approach
            # In production, you'd want to decode actual instruction data
            # to get exact token amounts and mint addresses

            return {
                "token_a": "UNKNOWN",
                "token_b": "SOL",
                "amount_a": 0.0,  # Would need instruction decoding
                "amount_b": largest_deposit["change_sol"],
                "signature": transaction.get("signatures", [""])[0]
            }

        except Exception as e:
            logger.error(f"Error parsing transaction: {e}")
            return None

    def is_raydium_lp_add(self, transaction: Dict[str, Any]) -> bool:
        """
        Check if transaction is a Raydium LP addition.

        Args:
            transaction: Parsed transaction data

        Returns:
            True if this is a Raydium LP addition
        """
        try:
            # Check if any instruction invokes Raydium AMM
            message = transaction.get("transaction", {}).get("message", {})
            instructions = message.get("instructions", [])

            for instruction in instructions:
                program_id = instruction.get("programId")
                if program_id == "675kPX9MHTjS2zt1qf1iQiLpKcM8cCtKxEbZqE8qiVJ":
                    # This is a Raydium instruction
                    # Would need to decode instruction data to confirm it's an LP add
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking if Raydium LP: {e}")
            return False
