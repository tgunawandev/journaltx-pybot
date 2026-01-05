"""
Database models for JournalTX.

Models: Trade, Journal, Alert, TelegramUser, BuyOrder.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class ContinuationQuality(str, Enum):
    """Quality of trade continuation logic."""
    POOR = "❌"
    MIXED = "⚠️"
    STRONG = "✅"


class Trade(Base):
    """
    A single trade entry.

    Represents a manual trade taken by the user.
    Exit data is nullable until trade is closed.
    """

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    chain: Mapped[str] = mapped_column(String(50), default="solana")
    pair_base: Mapped[str] = mapped_column(String(50), nullable=False)
    pair_quote: Mapped[str] = mapped_column(String(50), default="SOL")
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_followed: Mapped[bool] = mapped_column(Integer, default=False)
    scale_out_used: Mapped[bool] = mapped_column(Integer, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship
    journals: Mapped[list["Journal"]] = relationship(
        "Journal", back_populates="trade", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Trade {self.id}: {self.pair_base}/{self.pair_quote} @ {self.entry_price}>"


class Journal(Base):
    """
    Journal entry for a trade.

    Captures behavioral reflections on a single trade.
    """

    __tablename__ = "journals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trades.id"), nullable=False
    )
    rule_followed: Mapped[bool] = mapped_column(Integer, default=False)
    continuation_quality: Mapped[ContinuationQuality] = mapped_column(
        SQLEnum(ContinuationQuality), default=ContinuationQuality.MIXED
    )
    lesson: Mapped[str] = mapped_column(String(500), nullable=False)

    # Relationship
    trade: Mapped["Trade"] = relationship("Trade", back_populates="journals")

    def __repr__(self) -> str:
        return f"<Journal {self.id}: trade_id={self.trade_id} quality={self.continuation_quality.value}>"


class AlertType(str, Enum):
    """Type of on-chain alert."""
    LP_ADD = "lp_add"
    LP_REMOVE = "lp_remove"
    VOLUME_SPIKE = "volume_spike"


class Alert(Base):
    """
    On-chain event alert.

    Logged from QuickNode listeners.
    Optionally linked to a trade if one was taken.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[AlertType] = mapped_column(SQLEnum(AlertType), nullable=False)
    chain: Mapped[str] = mapped_column(String(50), default="solana")
    pair: Mapped[str] = mapped_column(String(100), nullable=False)
    token_mint: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Token mint address
    pool_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Raydium pool address
    tx_signature: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Transaction signature
    value_sol: Mapped[float] = mapped_column(Float, nullable=False)
    value_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lp_sol_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Liquidity before LP add
    lp_sol_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # Liquidity after LP add
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Market cap at time of alert
    pair_age_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Pair age in hours
    is_new_pool: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)  # True if pool was just created
    early_stage_passed: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)  # Early-stage filter result
    mode: Mapped[str] = mapped_column(String(10), default="LIVE")  # LIVE or TEST mode
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )
    trade_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("trades.id"), nullable=True
    )

    def __repr__(self) -> str:
        return f"<Alert {self.id}: {self.type.value} {self.pair} {self.value_sol} SOL>"


class BuyOrderStatus(str, Enum):
    """Status of a buy order."""
    PENDING = "pending"
    QUOTING = "quoting"
    EXECUTING = "executing"
    CONFIRMED = "confirmed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TelegramUser(Base):
    """
    Registered Telegram user for trading.

    Stores encrypted wallet and spending limits.
    """

    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Encrypted wallet storage
    encrypted_wallet: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    wallet_salt: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    wallet_pubkey: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Spending tracking
    daily_spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    daily_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    weekly_spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    weekly_reset_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_trade_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationship
    buy_orders: Mapped[list["BuyOrder"]] = relationship(
        "BuyOrder", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TelegramUser {self.id}: @{self.telegram_username} pubkey={self.wallet_pubkey}>"


class BuyOrder(Base):
    """
    Buy order execution log.

    Records all buy attempts from Telegram callbacks.
    """

    __tablename__ = "buy_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("telegram_users.id"), nullable=False)
    alert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alerts.id"), nullable=True)

    # Order details
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # low/medium/high
    amount_usd: Mapped[float] = mapped_column(Float, nullable=False)
    amount_sol: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    token_mint: Mapped[str] = mapped_column(String(50), nullable=False)

    # Execution
    status: Mapped[BuyOrderStatus] = mapped_column(
        SQLEnum(BuyOrderStatus), default=BuyOrderStatus.PENDING
    )
    tx_signature: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tokens_received: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["TelegramUser"] = relationship("TelegramUser", back_populates="buy_orders")

    def __repr__(self) -> str:
        return f"<BuyOrder {self.id}: {self.tier} ${self.amount_usd} {self.status.value}>"
