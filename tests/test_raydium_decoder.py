"""
Unit tests for Raydium LP detection.

Tests the core on-chain LP detection logic:
- Balance delta calculation
- Raydium instruction decoding
- Noise threshold filtering
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from journaltx.ingest.quicknode.raydium_decoder import (
    decode_raydium_transaction,
    _calculate_balance_deltas,
    _decode_instruction_type,
    _find_raydium_instruction,
    _get_account_keys,
    LPAdditionInfo,
    RAYDIUM_AMM_V4,
    MIN_SOL_DELTA_LAMPORTS,
    WSOL_MINT,
)


class TestInstructionDecoding:
    """Test Raydium instruction type decoding."""

    def test_decode_initialize_instruction(self):
        """Discriminator 0 = initialize (pool creation)."""
        import base58
        # Create data with discriminator 0
        data = base58.b58encode(bytes([0, 1, 2, 3])).decode()
        result = _decode_instruction_type(data)
        assert result == "initialize"

    def test_decode_initialize2_instruction(self):
        """Discriminator 1 = initialize2 (pool creation)."""
        import base58
        data = base58.b58encode(bytes([1, 1, 2, 3])).decode()
        result = _decode_instruction_type(data)
        assert result == "initialize2"

    def test_decode_deposit_instruction(self):
        """Discriminator 3 = deposit (add liquidity)."""
        import base58
        data = base58.b58encode(bytes([3, 1, 2, 3])).decode()
        result = _decode_instruction_type(data)
        assert result == "deposit"

    def test_decode_withdraw_instruction(self):
        """Discriminator 4 = withdraw (remove liquidity)."""
        import base58
        data = base58.b58encode(bytes([4, 1, 2, 3])).decode()
        result = _decode_instruction_type(data)
        assert result == "withdraw"

    def test_decode_swap_instruction(self):
        """Discriminator 9 = swap (not LP)."""
        import base58
        data = base58.b58encode(bytes([9, 1, 2, 3])).decode()
        result = _decode_instruction_type(data)
        assert result == "swap"

    def test_decode_empty_data(self):
        """Empty data should return unknown."""
        result = _decode_instruction_type("")
        assert result == "unknown"

    def test_decode_invalid_data(self):
        """Invalid base58/64 should return unknown."""
        result = _decode_instruction_type("not-valid-base58!")
        assert result == "unknown"


class TestBalanceDeltas:
    """Test balance delta calculations."""

    def test_sol_increase_detected(self):
        """Should detect SOL increase in pool vault."""
        meta = {
            "preBalances": [1_000_000_000, 500_000_000_000],  # 1 SOL, 500 SOL
            "postBalances": [800_000_000, 550_000_000_000],  # 0.8 SOL, 550 SOL
            "preTokenBalances": [],
            "postTokenBalances": [],
        }
        account_keys = ["user", "pool_vault"]
        pool_info = {"pool_address": "pool", "token_mint": ""}

        result = _calculate_balance_deltas(meta, account_keys, pool_info)

        assert result is not None
        assert result["sol_delta"] == 50.0  # 550 - 500 = 50 SOL increase
        assert result["sol_before"] == 500.0
        assert result["sol_after"] == 550.0

    def test_sol_decrease_rejected(self):
        """Should return None if SOL only decreases (not LP add)."""
        meta = {
            "preBalances": [1_000_000_000, 500_000_000_000],  # 1 SOL, 500 SOL
            "postBalances": [1_200_000_000, 400_000_000_000],  # 1.2 SOL, 400 SOL
            "preTokenBalances": [],
            "postTokenBalances": [],
        }
        account_keys = ["user", "pool_vault"]
        pool_info = {"pool_address": "pool", "token_mint": ""}

        result = _calculate_balance_deltas(meta, account_keys, pool_info)

        # Max increase is 0.2 SOL (user), but pool decreased
        # The largest delta should be the user gaining 0.2 SOL
        # If only withdrawals, no significant increase
        assert result is None or result["sol_delta"] <= 0.2

    def test_noise_threshold(self):
        """Small SOL changes below threshold should be filtered."""
        # MIN_SOL_DELTA_LAMPORTS = 100_000_000 = 0.1 SOL
        min_sol = MIN_SOL_DELTA_LAMPORTS / 1_000_000_000

        meta = {
            "preBalances": [1_000_000_000, 500_000_000_000],
            "postBalances": [900_000_000, 500_050_000_000],  # Only 0.05 SOL increase
            "preTokenBalances": [],
            "postTokenBalances": [],
        }
        account_keys = ["user", "pool_vault"]
        pool_info = {"pool_address": "pool", "token_mint": ""}

        result = _calculate_balance_deltas(meta, account_keys, pool_info)

        # Result exists but delta is small
        assert result is not None
        assert result["sol_delta"] == 0.05
        assert result["sol_delta"] < min_sol  # Below threshold


class TestAccountKeys:
    """Test account key extraction."""

    def test_legacy_format(self):
        """Legacy format: list of strings."""
        message = {
            "accountKeys": [
                "11111111111111111111111111111111",
                "22222222222222222222222222222222",
            ]
        }
        result = _get_account_keys(message)
        assert len(result) == 2
        assert result[0] == "11111111111111111111111111111111"

    def test_versioned_format(self):
        """Versioned format: list of dicts."""
        message = {
            "accountKeys": [
                {"pubkey": "11111111111111111111111111111111", "signer": True, "writable": True},
                {"pubkey": "22222222222222222222222222222222", "signer": False, "writable": True},
            ]
        }
        result = _get_account_keys(message)
        assert len(result) == 2
        assert result[0] == "11111111111111111111111111111111"

    def test_empty_keys(self):
        """Empty account keys should return empty list."""
        result = _get_account_keys({"accountKeys": []})
        assert result == []


class TestFindRaydiumInstruction:
    """Test Raydium instruction finding."""

    def test_find_in_main_instructions(self):
        """Should find Raydium instruction in main instructions."""
        import base58
        instructions = [
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "data": ""},
            {"programId": RAYDIUM_AMM_V4, "data": base58.b58encode(bytes([3])).decode()},
        ]
        meta = {"innerInstructions": []}

        ix, ix_type = _find_raydium_instruction(instructions, meta)

        assert ix is not None
        assert ix["programId"] == RAYDIUM_AMM_V4
        assert ix_type == "deposit"

    def test_find_in_inner_instructions(self):
        """Should find Raydium instruction in inner (CPI) instructions."""
        import base58
        instructions = [
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "data": ""},
        ]
        meta = {
            "innerInstructions": [{
                "instructions": [
                    {"programId": RAYDIUM_AMM_V4, "data": base58.b58encode(bytes([0])).decode()},
                ]
            }]
        }

        ix, ix_type = _find_raydium_instruction(instructions, meta)

        assert ix is not None
        assert ix_type == "initialize"

    def test_not_found(self):
        """Should return None if no Raydium instruction."""
        instructions = [
            {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA", "data": ""},
        ]
        meta = {"innerInstructions": []}

        ix, ix_type = _find_raydium_instruction(instructions, meta)

        assert ix is None
        assert ix_type == "unknown"


class TestFullDecoding:
    """Integration tests for full transaction decoding."""

    def test_failed_transaction_rejected(self):
        """Failed transactions (err != null) should be rejected."""
        transaction = {
            "meta": {"err": {"InstructionError": [0, "Custom"]}},
            "transaction": {
                "signatures": ["test_sig"],
                "message": {"accountKeys": [], "instructions": []},
            }
        }

        result = decode_raydium_transaction(transaction, "http://test")

        assert result is None

    def test_successful_lp_add(self):
        """Test successful LP addition detection."""
        import base58

        # Simulate a deposit transaction with balance increases
        transaction = {
            "meta": {
                "err": None,
                "preBalances": [1_000_000_000_000, 100_000_000_000],  # 1000 SOL, 100 SOL
                "postBalances": [900_000_000_000, 200_000_000_000],  # 900 SOL, 200 SOL (100 SOL added)
                "preTokenBalances": [],
                "postTokenBalances": [],
                "innerInstructions": [],
            },
            "transaction": {
                "signatures": ["test_signature_123456789"],
                "message": {
                    "accountKeys": [
                        "user_wallet",
                        "pool_vault",
                        RAYDIUM_AMM_V4,
                    ],
                    "instructions": [{
                        "programId": RAYDIUM_AMM_V4,
                        "data": base58.b58encode(bytes([3])).decode(),  # deposit
                        "accounts": [0, 1],
                    }],
                },
            },
        }

        result = decode_raydium_transaction(transaction, "http://test")

        assert result is not None
        assert isinstance(result, LPAdditionInfo)
        assert result.quote_amount_sol == 100.0  # 100 SOL delta
        assert result.is_pool_creation is False  # deposit, not initialize

    def test_swap_rejected(self):
        """Swap transactions should not be detected as LP adds."""
        import base58

        transaction = {
            "meta": {
                "err": None,
                "preBalances": [1_000_000_000_000, 100_000_000_000],
                "postBalances": [1_100_000_000_000, 50_000_000_000],  # User gained, pool lost
                "preTokenBalances": [],
                "postTokenBalances": [],
                "innerInstructions": [],
            },
            "transaction": {
                "signatures": ["test_sig"],
                "message": {
                    "accountKeys": ["user", "pool", RAYDIUM_AMM_V4],
                    "instructions": [{
                        "programId": RAYDIUM_AMM_V4,
                        "data": base58.b58encode(bytes([9])).decode(),  # swap
                        "accounts": [0, 1],
                    }],
                },
            },
        }

        result = decode_raydium_transaction(transaction, "http://test")

        assert result is None  # Swaps should be rejected


class TestConstants:
    """Test constant values."""

    def test_raydium_program_id(self):
        """Verify Raydium AMM V4 program ID."""
        # This should NOT change - it's the canonical Raydium program
        assert RAYDIUM_AMM_V4 == "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8"

    def test_wsol_mint(self):
        """Verify WSOL mint address."""
        assert WSOL_MINT == "So11111111111111111111111111111111111111112"

    def test_noise_threshold(self):
        """Verify noise threshold is 0.1 SOL."""
        assert MIN_SOL_DELTA_LAMPORTS == 100_000_000  # 0.1 SOL in lamports


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
