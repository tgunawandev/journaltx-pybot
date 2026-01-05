"""
Transaction executor for JournalTX trading.

Handles signing and sending transactions to Solana.
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

from solana.rpc.api import Client
from solana.rpc.commitment import Confirmed
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of transaction execution."""
    success: bool
    signature: Optional[str] = None
    error: Optional[str] = None
    retries: int = 0


class TransactionExecutor:
    """
    Executes and confirms Solana transactions.

    Handles signing, sending, and confirmation with retry logic.
    """

    def __init__(self, rpc_url: str, max_retries: int = 3, confirm_timeout: int = 60):
        """
        Initialize transaction executor.

        Args:
            rpc_url: Solana RPC endpoint
            max_retries: Maximum retry attempts
            confirm_timeout: Timeout in seconds for confirmation
        """
        self.rpc_client = Client(rpc_url)
        self.max_retries = max_retries
        self.confirm_timeout = confirm_timeout

    def sign_and_send(
        self,
        tx_bytes: bytes,
        keypair: Keypair,
        skip_preflight: bool = False
    ) -> ExecutionResult:
        """
        Sign and send a transaction.

        Args:
            tx_bytes: Serialized transaction bytes
            keypair: Keypair for signing
            skip_preflight: Skip preflight simulation

        Returns:
            ExecutionResult with signature or error
        """
        retries = 0

        while retries < self.max_retries:
            try:
                # Deserialize transaction
                tx = VersionedTransaction.from_bytes(tx_bytes)

                # Sign transaction
                tx.sign([keypair], self._get_recent_blockhash())

                # Send transaction
                opts = {"skip_preflight": skip_preflight}
                result = self.rpc_client.send_transaction(tx, opts=opts)

                if result.value:
                    signature = str(result.value)
                    logger.info(f"Transaction sent: {signature}")
                    return ExecutionResult(success=True, signature=signature, retries=retries)
                else:
                    logger.warning(f"Send failed, retrying... ({retries + 1}/{self.max_retries})")
                    retries += 1
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Transaction error: {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(2)
                else:
                    return ExecutionResult(success=False, error=str(e), retries=retries)

        return ExecutionResult(success=False, error="Max retries exceeded", retries=retries)

    def _get_recent_blockhash(self):
        """Get recent blockhash for transaction."""
        response = self.rpc_client.get_latest_blockhash(commitment=Confirmed)
        return response.value.blockhash

    def confirm_transaction(self, signature: str) -> bool:
        """
        Wait for transaction confirmation.

        Args:
            signature: Transaction signature

        Returns:
            True if confirmed, False otherwise
        """
        start_time = time.time()

        while time.time() - start_time < self.confirm_timeout:
            try:
                result = self.rpc_client.get_signature_statuses([signature])

                if result.value and result.value[0]:
                    status = result.value[0]
                    if status.err:
                        logger.error(f"Transaction failed: {status.err}")
                        return False
                    if status.confirmation_status in ["confirmed", "finalized"]:
                        logger.info(f"Transaction confirmed: {signature}")
                        return True

                time.sleep(2)

            except Exception as e:
                logger.error(f"Confirmation error: {e}")
                time.sleep(2)

        logger.error(f"Transaction confirmation timeout: {signature}")
        return False

    def execute(
        self,
        tx_bytes: bytes,
        keypair: Keypair,
        wait_confirm: bool = True
    ) -> ExecutionResult:
        """
        Execute a transaction with optional confirmation wait.

        Args:
            tx_bytes: Serialized transaction bytes
            keypair: Keypair for signing
            wait_confirm: Wait for confirmation

        Returns:
            ExecutionResult with final status
        """
        # Sign and send
        result = self.sign_and_send(tx_bytes, keypair)

        if not result.success:
            return result

        # Optionally wait for confirmation
        if wait_confirm and result.signature:
            confirmed = self.confirm_transaction(result.signature)
            if not confirmed:
                result.success = False
                result.error = "Confirmation failed"

        return result
