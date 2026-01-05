"""
Spending limits guard for JournalTX trading.

Enforces per-user daily and weekly spending limits.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from journaltx.core.models import TelegramUser

logger = logging.getLogger(__name__)


class SpendingGuard:
    """
    Enforces spending limits for trading users.

    Tracks daily and weekly USD spending per user.
    """

    def __init__(
        self,
        daily_limit: float = 100.0,
        weekly_limit: float = 300.0,
        max_per_trade: float = 50.0
    ):
        """
        Initialize spending guard.

        Args:
            daily_limit: Maximum USD per day
            weekly_limit: Maximum USD per week
            max_per_trade: Maximum USD per single trade
        """
        self.daily_limit = daily_limit
        self.weekly_limit = weekly_limit
        self.max_per_trade = max_per_trade

    def check_limits(
        self,
        user: TelegramUser,
        amount_usd: float,
        session: Session
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a trade amount is within limits.

        Automatically resets daily/weekly counters if needed.

        Args:
            user: TelegramUser to check
            amount_usd: Proposed trade amount in USD
            session: Database session for updates

        Returns:
            Tuple of (is_allowed, error_message)
        """
        now = datetime.utcnow()

        # Check per-trade limit
        if amount_usd > self.max_per_trade:
            return False, f"Amount ${amount_usd:.0f} exceeds max per trade (${self.max_per_trade:.0f})"

        # Reset daily counter if needed
        if now - user.daily_reset_at > timedelta(days=1):
            user.daily_spent_usd = 0.0
            user.daily_reset_at = now
            session.commit()
            logger.info(f"Reset daily counter for user {user.telegram_user_id}")

        # Reset weekly counter if needed
        if now - user.weekly_reset_at > timedelta(weeks=1):
            user.weekly_spent_usd = 0.0
            user.weekly_reset_at = now
            session.commit()
            logger.info(f"Reset weekly counter for user {user.telegram_user_id}")

        # Check daily limit
        if user.daily_spent_usd + amount_usd > self.daily_limit:
            remaining = self.daily_limit - user.daily_spent_usd
            return False, f"Daily limit exceeded. Remaining: ${remaining:.0f}/${self.daily_limit:.0f}"

        # Check weekly limit
        if user.weekly_spent_usd + amount_usd > self.weekly_limit:
            remaining = self.weekly_limit - user.weekly_spent_usd
            return False, f"Weekly limit exceeded. Remaining: ${remaining:.0f}/${self.weekly_limit:.0f}"

        return True, None

    def record_spend(
        self,
        user: TelegramUser,
        amount_usd: float,
        session: Session
    ) -> None:
        """
        Record a successful trade spend.

        Args:
            user: TelegramUser who made the trade
            amount_usd: Amount spent in USD
            session: Database session
        """
        user.daily_spent_usd += amount_usd
        user.weekly_spent_usd += amount_usd
        user.last_trade_at = datetime.utcnow()
        session.commit()

        logger.info(
            f"Recorded ${amount_usd:.0f} spend for user {user.telegram_user_id}. "
            f"Daily: ${user.daily_spent_usd:.0f}/{self.daily_limit:.0f}, "
            f"Weekly: ${user.weekly_spent_usd:.0f}/{self.weekly_limit:.0f}"
        )

    def get_limits_status(self, user: TelegramUser) -> dict:
        """
        Get current spending status for a user.

        Args:
            user: TelegramUser to check

        Returns:
            Dict with spending status
        """
        now = datetime.utcnow()

        # Calculate remaining (accounting for potential resets)
        daily_spent = user.daily_spent_usd
        weekly_spent = user.weekly_spent_usd

        if now - user.daily_reset_at > timedelta(days=1):
            daily_spent = 0.0

        if now - user.weekly_reset_at > timedelta(weeks=1):
            weekly_spent = 0.0

        return {
            "daily_spent": daily_spent,
            "daily_limit": self.daily_limit,
            "daily_remaining": max(0, self.daily_limit - daily_spent),
            "weekly_spent": weekly_spent,
            "weekly_limit": self.weekly_limit,
            "weekly_remaining": max(0, self.weekly_limit - weekly_spent),
            "max_per_trade": self.max_per_trade,
        }
