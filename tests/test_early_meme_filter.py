"""
Unit tests for early-stage meme filtering.

Tests the filtering logic that determines if an LP event
is an early-stage opportunity worth alerting on.
"""

import pytest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from journaltx.filters.early_meme import check_early_stage_opportunity


class TestPairTypeFiltering:
    """Test TOKEN/SOL pair filtering."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_invalid_pair_format(self, mock_market):
        """Pair without / should fail."""
        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKENSOL",  # Missing /
            lp_added_sol=500,
            lp_before_sol=0,
        )
        assert should_alert is False
        assert "FAIL" in str(details["checks"])

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_non_sol_quote_rejected(self, mock_market):
        """Non-SOL quote pairs should fail."""
        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/USDC",
            lp_added_sol=500,
            lp_before_sol=0,
        )
        assert should_alert is False

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_sol_quote_passes(self, mock_market):
        """TOKEN/SOL pairs should pass pair type check."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 1.0,
            "market_cap": 1_000_000,
            "liquidity_usd": 50000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="NEWTOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=5,
            is_new_pool=True,
        )

        # Should pass pair type check (first rule)
        first_check = details["checks"][0]
        assert first_check["status"] == "PASS"


class TestLegacyMemeFiltering:
    """Test legacy meme exclusion."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_legacy_meme_blocked(self, mock_market):
        """Legacy memes (BONK, WIF, etc.) should be blocked."""
        mock_market.return_value = {"legacy_meme": True}

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="BONK/SOL",
            lp_added_sol=1000,
            lp_before_sol=0,
            legacy_memes=["BONK", "WIF", "DOGE"],
        )

        assert should_alert is False
        assert "BLOCK" in str(details["checks"])


class TestPairAgeFiltering:
    """Test pair age filtering rules."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_old_pair_blocked(self, mock_market):
        """Pairs older than hard_reject_pair_age_hours should be blocked."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 30.0,  # Too old
            "market_cap": 1_000_000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="OLDTOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=0,
            hard_reject_pair_age_hours=24,
        )

        assert should_alert is False
        assert "BLOCK" in str(details["checks"])

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_early_pair_high_priority(self, mock_market):
        """Pairs <30 min should be HIGH priority."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 0.3,  # 18 minutes
            "market_cap": 500_000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="NEWTOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=5,
            is_new_pool=True,
        )

        assert details.get("priority") == "HIGH"


class TestMarketCapFiltering:
    """Test market cap defensive filtering."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_large_cap_blocked(self, mock_market):
        """Large market cap (>$20M) should be blocked."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 2.0,
            "market_cap": 25_000_000,  # $25M - too big
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="BIGTOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=0,
            hard_reject_market_cap=20_000_000,
        )

        assert should_alert is False

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_small_cap_passes(self, mock_market):
        """Small market cap (<$20M) should pass."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 1.0,
            "market_cap": 500_000,  # $500K - good
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="SMALLTOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=5,
            is_new_pool=True,
        )

        # Market cap check should pass
        market_check = [c for c in details["checks"] if "Market cap" in c["rule"]]
        assert any(c["status"] == "PASS" for c in market_check)


class TestNearZeroIgnition:
    """Test near-zero ignition filtering."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_near_zero_ignition_passes(self, mock_market):
        """Near-zero baseline + significant add should pass."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 0.5,
            "market_cap": 100_000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/SOL",
            lp_added_sol=500,  # Significant addition
            lp_before_sol=5,   # Near-zero baseline
            hard_reject_baseline_liquidity=20.0,
            min_lp_ignite_sol=300.0,
            is_new_pool=True,
        )

        assert details.get("ignition_pass") is True

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_high_baseline_fails(self, mock_market):
        """High baseline liquidity should fail ignition check."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 1.0,
            "market_cap": 1_000_000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=100,  # Too high baseline
            hard_reject_baseline_liquidity=20.0,
        )

        assert details.get("ignition_pass") is False
        assert should_alert is False

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_small_addition_fails(self, mock_market):
        """Small LP addition should fail ignition check."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 1.0,
            "market_cap": 100_000,
        }

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/SOL",
            lp_added_sol=50,  # Too small
            lp_before_sol=5,
            min_lp_ignite_sol=300.0,
        )

        assert details.get("ignition_pass") is False
        assert should_alert is False


class TestNewPoolBypass:
    """Test new pool multi-signal bypass."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    @patch("journaltx.filters.early_meme.get_signal_tracker")
    def test_new_pool_bypasses_multi_signal(self, mock_tracker, mock_market):
        """New pool creation should bypass multi-signal requirement."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 0.1,  # Very new
            "market_cap": 50_000,
        }
        mock_tracker.return_value = MagicMock()

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=0,
            is_new_pool=True,
            require_multi_signal=True,
        )

        # Should alert even without multi-signal (new pool bypass)
        multi_check = [c for c in details["checks"] if "Multi-signal" in c["rule"]]
        if multi_check:
            assert "BYPASS" in multi_check[0]["status"]

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    @patch("journaltx.filters.early_meme.get_signal_tracker")
    def test_existing_pool_needs_multi_signal(self, mock_tracker, mock_market):
        """Existing pool additions should require multi-signal."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 12.0,  # Older pool
            "market_cap": 5_000_000,
        }

        # Mock signal tracker to return no alert (not enough signals)
        mock_tracker_instance = MagicMock()
        mock_tracker_instance.add_signal.return_value = False
        mock_tracker_instance.get_signal_count.return_value = {"total": 1, "types": {"lp_add": 1}}
        mock_tracker.return_value = mock_tracker_instance

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="TOKEN/SOL",
            lp_added_sol=500,
            lp_before_sol=5,
            is_new_pool=False,
            require_multi_signal=True,
        )

        # Should NOT alert (waiting for more signals)
        assert should_alert is False


class TestShouldLog:
    """Test that events are always logged."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    def test_always_logs(self, mock_market):
        """All events should be logged (should_log=True)."""
        mock_market.return_value = {"legacy_meme": True}

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="BONK/SOL",
            lp_added_sol=1000,
            lp_before_sol=0,
        )

        assert should_log is True  # Always log for analysis


class TestIntegration:
    """Integration tests for full filtering flow."""

    @patch("journaltx.filters.early_meme.get_pair_market_data")
    @patch("journaltx.filters.early_meme.get_signal_tracker")
    def test_perfect_early_stage_opportunity(self, mock_tracker, mock_market):
        """Test a perfect early-stage opportunity scenario."""
        mock_market.return_value = {
            "legacy_meme": False,
            "pair_age_hours": 0.2,  # 12 minutes old
            "market_cap": 100_000,  # $100K
            "liquidity_usd": 15_000,
        }
        mock_tracker.return_value = MagicMock()

        should_alert, should_log, details = check_early_stage_opportunity(
            pair="NEWMEME/SOL",
            lp_added_sol=500,     # 500 SOL added
            lp_before_sol=3,      # Near-zero baseline
            is_new_pool=True,     # New pool creation
            min_lp_ignite_sol=100,
            hard_reject_baseline_liquidity=20,
        )

        assert should_alert is True
        assert details.get("priority") == "HIGH"
        assert details.get("ignition_pass") is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
