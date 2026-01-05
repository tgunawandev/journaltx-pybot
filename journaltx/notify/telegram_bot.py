"""
Telegram bot handler for JournalTX trading.

Handles user registration, buy callbacks, and account management.
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

from journaltx.core.config import Config
from journaltx.core.models import Base, TelegramUser, BuyOrder, BuyOrderStatus
from journaltx.trading.wallet import WalletManager
from journaltx.trading.jupiter import JupiterSwap
from journaltx.trading.executor import TransactionExecutor
from journaltx.trading.spending import SpendingGuard

logger = logging.getLogger(__name__)


class RegState(Enum):
    """Registration wizard states."""
    WAITING_WALLET = auto()
    WAITING_FUND = auto()
    WAITING_KEY = auto()


class TelegramBotHandler:
    """
    Handles Telegram bot interactions for trading.

    Manages registration, buy callbacks, and user commands.
    """

    def __init__(self, config: Config):
        """Initialize bot handler with config."""
        self.config = config
        self.bot_token = config.telegram_bot_token

        # Database setup
        engine = create_engine(f"sqlite:///{config.database_path}")
        Base.metadata.create_all(engine)
        self.Session = sessionmaker(bind=engine)

        # Trading components
        rpc_url = config.helius_rpc_url or config.quicknode_http_url
        if not rpc_url:
            raise ValueError("No RPC URL configured")

        self.wallet_manager = WalletManager(
            encryption_key=config.wallet_encryption_key,
            rpc_url=rpc_url
        ) if config.wallet_encryption_key else None

        self.jupiter = JupiterSwap(
            slippage_bps=config.trading_slippage_bps,
            priority_fee=config.trading_priority_fee
        )

        self.executor = TransactionExecutor(rpc_url) if rpc_url else None

        self.spending_guard = SpendingGuard(
            daily_limit=config.trading_daily_limit,
            weekly_limit=config.trading_weekly_limit,
            max_per_trade=config.trading_max_per_trade
        )

        self.tiers = config.trading_tiers or [10, 25, 50]
        self.application: Optional[Application] = None

    def _is_dm(self, update: Update) -> bool:
        """Check if message is a DM (private chat)."""
        return update.effective_chat.type == "private"

    async def _get_or_create_user(self, update: Update) -> Optional[TelegramUser]:
        """Get or create a TelegramUser from update."""
        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()
            return user
        finally:
            session.close()

    # =========================
    # Command Handlers
    # =========================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - welcome message."""
        if not self._is_dm(update):
            await update.message.reply_text(
                "Please DM me to get started with trading setup."
            )
            return

        keyboard = [
            [
                InlineKeyboardButton("Get Started", callback_data="wizard_start"),
                InlineKeyboardButton("How it Works", callback_data="wizard_info"),
            ]
        ]

        await update.message.reply_html(
            "<b>Welcome to JournalTX!</b>\n\n"
            "I help you buy early-stage Solana tokens directly from alert notifications.\n\n"
            "Click <b>Get Started</b> to set up your trading wallet.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def cmd_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /balance command."""
        if not self._is_dm(update):
            await update.message.reply_text("Please use this command in DM.")
            return

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user or not user.wallet_pubkey:
                await update.message.reply_text(
                    "You haven't registered a wallet yet.\n"
                    "Use /start to begin setup."
                )
                return

            balance = self.wallet_manager.get_balance(user.wallet_pubkey)
            sol_price = self.wallet_manager.get_sol_price()

            if balance is not None:
                usd_value = balance * sol_price
                await update.message.reply_html(
                    f"<b>Wallet Balance</b>\n\n"
                    f"Address: <code>{user.wallet_pubkey[:8]}...{user.wallet_pubkey[-8:]}</code>\n"
                    f"Balance: <b>{balance:.4f} SOL</b> (~${usd_value:.0f})"
                )
            else:
                await update.message.reply_text("Failed to fetch balance. Try again later.")
        finally:
            session.close()

    async def cmd_limits(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /limits command."""
        if not self._is_dm(update):
            await update.message.reply_text("Please use this command in DM.")
            return

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user:
                await update.message.reply_text(
                    "You haven't registered yet. Use /start to begin."
                )
                return

            status = self.spending_guard.get_limits_status(user)

            await update.message.reply_html(
                f"<b>Spending Limits</b>\n\n"
                f"<b>Today:</b> ${status['daily_spent']:.0f} / ${status['daily_limit']:.0f}\n"
                f"Remaining: ${status['daily_remaining']:.0f}\n\n"
                f"<b>This Week:</b> ${status['weekly_spent']:.0f} / ${status['weekly_limit']:.0f}\n"
                f"Remaining: ${status['weekly_remaining']:.0f}\n\n"
                f"<b>Max per Trade:</b> ${status['max_per_trade']:.0f}"
            )
        finally:
            session.close()

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command."""
        if not self._is_dm(update):
            await update.message.reply_text("Please use this command in DM.")
            return

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user:
                await update.message.reply_text(
                    "You haven't registered yet. Use /start to begin."
                )
                return

            orders = session.query(BuyOrder).filter_by(
                user_id=user.id
            ).order_by(BuyOrder.requested_at.desc()).limit(10).all()

            if not orders:
                await update.message.reply_text("No trade history yet.")
                return

            lines = ["<b>Recent Trades</b>\n"]
            for order in orders:
                status_emoji = {
                    BuyOrderStatus.CONFIRMED: "",
                    BuyOrderStatus.FAILED: "",
                    BuyOrderStatus.PENDING: "",
                    BuyOrderStatus.SKIPPED: "",
                }.get(order.status, "")

                lines.append(
                    f"{status_emoji} ${order.amount_usd:.0f} - "
                    f"{order.token_mint[:8]}... "
                    f"({order.requested_at.strftime('%m/%d %H:%M')})"
                )

            await update.message.reply_html("\n".join(lines))
        finally:
            session.close()

    async def cmd_unregister(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unregister command."""
        if not self._is_dm(update):
            await update.message.reply_text("Please use this command in DM.")
            return

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user:
                await update.message.reply_text("You're not registered.")
                return

            keyboard = [
                [
                    InlineKeyboardButton("Yes, Delete", callback_data="unregister_confirm"),
                    InlineKeyboardButton("Cancel", callback_data="unregister_cancel"),
                ]
            ]

            await update.message.reply_html(
                "<b>Are you sure?</b>\n\n"
                "This will delete your encrypted wallet and all settings.\n"
                "Your trade history will be preserved.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        finally:
            session.close()

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        await update.message.reply_html(
            "<b>JournalTX Trading Bot</b>\n\n"
            "<b>Commands:</b>\n"
            "/start - Get started / registration\n"
            "/balance - Check wallet balance\n"
            "/limits - View spending limits\n"
            "/history - View recent trades\n"
            "/unregister - Remove your wallet\n"
            "/help - Show this message\n\n"
            "<b>How it works:</b>\n"
            "1. Register your trading wallet (DM only)\n"
            "2. Fund it with small SOL amount\n"
            "3. Click Buy buttons on alerts\n"
            "4. Bot executes swap automatically\n\n"
            "<i>Use a SEPARATE wallet for trading!</i>"
        )

    async def cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /menu command - account management."""
        if not self._is_dm(update):
            await update.message.reply_text("Please use this command in DM.")
            return

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user or not user.wallet_pubkey:
                await update.message.reply_text(
                    "You haven't registered yet. Use /start to begin."
                )
                return

            balance = self.wallet_manager.get_balance(user.wallet_pubkey)
            sol_price = self.wallet_manager.get_sol_price()
            status = self.spending_guard.get_limits_status(user)

            keyboard = [
                [InlineKeyboardButton("Refresh Balance", callback_data="menu_balance")],
                [InlineKeyboardButton("Spending History", callback_data="menu_history")],
                [InlineKeyboardButton("Update Wallet", callback_data="wizard_start")],
                [InlineKeyboardButton("Delete Account", callback_data="menu_delete")],
            ]

            usd_value = (balance or 0) * sol_price
            pubkey_short = f"{user.wallet_pubkey[:6]}...{user.wallet_pubkey[-6:]}"

            await update.message.reply_html(
                f"<b>Account Settings</b>\n\n"
                f"Wallet: <code>{pubkey_short}</code>\n"
                f"Balance: {balance:.4f} SOL (~${usd_value:.0f})\n\n"
                f"Today: ${status['daily_spent']:.0f} / ${status['daily_limit']:.0f}\n"
                f"This Week: ${status['weekly_spent']:.0f} / ${status['weekly_limit']:.0f}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        finally:
            session.close()

    # =========================
    # Wizard Callbacks
    # =========================

    async def wizard_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle registration wizard callbacks."""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "wizard_start":
            keyboard = [
                [
                    InlineKeyboardButton("I have a wallet", callback_data="wizard_have_wallet"),
                    InlineKeyboardButton("Download Phantom", url="https://phantom.app/"),
                ]
            ]

            await query.edit_message_text(
                "<b>STEP 1 OF 3: Create Wallet</b>\n\n"
                "First, create a NEW Solana wallet:\n\n"
                "IMPORTANT: Use a SEPARATE wallet!\n"
                "- Don't use your main wallet\n"
                "- Only fund what you can lose\n\n"
                "Recommended apps:\n"
                "- Phantom (mobile/browser)\n"
                "- Solflare (mobile/browser)",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data == "wizard_info":
            keyboard = [[InlineKeyboardButton("Back", callback_data="wizard_back_start")]]

            await query.edit_message_text(
                "<b>How JournalTX Trading Works</b>\n\n"
                "1. <b>Register</b> - Connect a separate Solana wallet\n"
                "2. <b>Fund</b> - Add small SOL amount (0.1-0.5 SOL)\n"
                "3. <b>Trade</b> - Click Buy buttons on alerts\n\n"
                "<b>Safety Features:</b>\n"
                "- Daily limit: $100\n"
                "- Weekly limit: $300\n"
                "- Max per trade: $50\n"
                "- Your key is encrypted (AES-256)\n\n"
                "<b>Risk Warning:</b>\n"
                "- Only use funds you can afford to lose\n"
                "- Meme tokens are extremely risky\n"
                "- This is NOT financial advice",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data == "wizard_back_start":
            keyboard = [
                [
                    InlineKeyboardButton("Get Started", callback_data="wizard_start"),
                    InlineKeyboardButton("How it Works", callback_data="wizard_info"),
                ]
            ]

            await query.edit_message_text(
                "<b>Welcome to JournalTX!</b>\n\n"
                "I help you buy early-stage Solana tokens directly from alert notifications.\n\n"
                "Click <b>Get Started</b> to set up your trading wallet.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data == "wizard_have_wallet":
            keyboard = [
                [
                    InlineKeyboardButton("Wallet is funded", callback_data="wizard_funded"),
                    InlineKeyboardButton("Skip for now", callback_data="wizard_funded"),
                ]
            ]

            await query.edit_message_text(
                "<b>STEP 2 OF 3: Fund Wallet</b>\n\n"
                "Fund your trading wallet with SOL:\n\n"
                "- Minimum: 0.1 SOL (~$20)\n"
                "- Recommended: 0.5 SOL (~$100)\n"
                "- Maximum: Keep it small!\n\n"
                "This wallet is for trading ONLY.\n"
                "Never store large amounts.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data == "wizard_funded":
            # Store state - waiting for private key
            context.user_data["wizard_state"] = "waiting_key"

            keyboard = [
                [InlineKeyboardButton("Cancel", callback_data="wizard_cancel")]
            ]

            await query.edit_message_text(
                "<b>STEP 3 OF 3: Connect Wallet</b>\n\n"
                "Export your private key from your wallet:\n\n"
                "<b>Phantom:</b>\n"
                "  Settings - Security - Export Private Key\n\n"
                "<b>Solflare:</b>\n"
                "  Settings - Export Private Key\n\n"
                "Then <b>paste it below</b> (base58 format):",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        elif data == "wizard_cancel":
            context.user_data.pop("wizard_state", None)

            await query.edit_message_text(
                "Registration cancelled.\n\n"
                "Use /start when you're ready to try again."
            )

    async def handle_private_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle private key message during registration."""
        # Only process if in wizard state and DM
        if not self._is_dm(update):
            return

        if context.user_data.get("wizard_state") != "waiting_key":
            return

        private_key = update.message.text.strip()

        # Delete the message containing private key immediately
        try:
            await update.message.delete()
        except Exception:
            pass

        # Validate the key
        if not self.wallet_manager:
            await update.message.reply_text(
                "Trading is not configured. Contact admin."
            )
            return

        is_valid, pubkey, error = self.wallet_manager.validate_private_key(private_key)

        if not is_valid:
            await update.effective_chat.send_message(
                f"Invalid private key: {error}\n\n"
                "Please try again with a valid base58 private key."
            )
            return

        # Encrypt and store
        encrypted_wallet, salt = self.wallet_manager.encrypt_wallet(private_key)

        session = self.Session()
        try:
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if user:
                # Update existing user
                user.encrypted_wallet = encrypted_wallet
                user.wallet_salt = salt
                user.wallet_pubkey = pubkey
                user.is_active = True
            else:
                # Create new user
                user = TelegramUser(
                    telegram_user_id=update.effective_user.id,
                    telegram_username=update.effective_user.username,
                    encrypted_wallet=encrypted_wallet,
                    wallet_salt=salt,
                    wallet_pubkey=pubkey,
                )
                session.add(user)

            session.commit()

            # Get balance
            balance = self.wallet_manager.get_balance(pubkey)
            sol_price = self.wallet_manager.get_sol_price()
            usd_value = (balance or 0) * sol_price

            # Clear wizard state
            context.user_data.pop("wizard_state", None)

            keyboard = [
                [
                    InlineKeyboardButton("Check Balance", callback_data="menu_balance"),
                    InlineKeyboardButton("View Limits", callback_data="menu_limits"),
                ]
            ]

            pubkey_short = f"{pubkey[:6]}...{pubkey[-6:]}"
            tiers_str = " / ".join([f"${t}" for t in self.tiers])

            await update.effective_chat.send_message(
                f"<b>WALLET CONNECTED!</b>\n\n"
                f"Address: <code>{pubkey_short}</code>\n"
                f"Balance: {balance:.4f} SOL (~${usd_value:.0f})\n\n"
                f"Daily Limit: ${self.config.trading_daily_limit:.0f}\n"
                f"Weekly Limit: ${self.config.trading_weekly_limit:.0f}\n"
                f"Tiers: {tiers_str}\n\n"
                f"You're all set!\n"
                f"Buy buttons will appear on alerts.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )

        except Exception as e:
            logger.error(f"Registration error: {e}")
            await update.effective_chat.send_message(
                "Registration failed. Please try again or contact admin."
            )
        finally:
            session.close()

    # =========================
    # Buy Callbacks
    # =========================

    async def buy_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle buy button callbacks."""
        query = update.callback_query

        # Parse callback data: buy_{tier}_{token_mint}_{alert_id}
        parts = query.data.split("_")
        if len(parts) < 4 or parts[0] != "buy":
            await query.answer("Invalid callback")
            return

        tier = parts[1]
        token_mint = parts[2]
        alert_id = int(parts[3]) if parts[3].isdigit() else None

        # Get amount from tier
        tier_map = {"low": 0, "medium": 1, "high": 2}
        tier_idx = tier_map.get(tier, 0)
        amount_usd = self.tiers[tier_idx] if tier_idx < len(self.tiers) else self.tiers[0]

        await query.answer(f"Processing ${amount_usd} buy...")

        session = self.Session()
        try:
            # Get user
            user = session.query(TelegramUser).filter_by(
                telegram_user_id=update.effective_user.id
            ).first()

            if not user or not user.encrypted_wallet:
                await query.answer("Not registered! DM me to set up.", show_alert=True)
                return

            # Check spending limits
            allowed, error = self.spending_guard.check_limits(user, amount_usd, session)
            if not allowed:
                await query.answer(error, show_alert=True)
                return

            # Create order
            order = BuyOrder(
                user_id=user.id,
                alert_id=alert_id,
                tier=tier,
                amount_usd=amount_usd,
                token_mint=token_mint,
                status=BuyOrderStatus.QUOTING,
            )
            session.add(order)
            session.commit()

            # Get SOL price and calculate SOL amount
            sol_price = self.wallet_manager.get_sol_price()
            sol_amount = amount_usd / sol_price

            # Check balance
            balance = self.wallet_manager.get_balance(user.wallet_pubkey)
            if balance is None or balance < sol_amount + 0.01:  # 0.01 SOL for fees
                order.status = BuyOrderStatus.FAILED
                order.error_message = "Insufficient balance"
                session.commit()
                await query.answer("Insufficient SOL balance!", show_alert=True)
                return

            # Update message
            await query.edit_message_text(
                query.message.text + f"\n\n Getting quote from Jupiter...",
                parse_mode="HTML"
            )

            # Get Jupiter quote
            quote, tx_bytes = self.jupiter.buy_token(
                token_mint=token_mint,
                sol_amount=sol_amount,
                user_pubkey=user.wallet_pubkey
            )

            if not quote or not tx_bytes:
                order.status = BuyOrderStatus.FAILED
                order.error_message = "Failed to get quote"
                session.commit()
                await query.edit_message_text(
                    query.message.text.replace(" Getting quote", " Quote failed"),
                    parse_mode="HTML"
                )
                return

            order.amount_sol = sol_amount
            order.status = BuyOrderStatus.EXECUTING
            session.commit()

            # Update message
            await query.edit_message_text(
                query.message.text.replace(" Getting quote", " Executing swap..."),
                parse_mode="HTML"
            )

            # Get keypair and execute
            keypair = self.wallet_manager.get_keypair(
                user.encrypted_wallet,
                user.wallet_salt
            )

            if not keypair:
                order.status = BuyOrderStatus.FAILED
                order.error_message = "Failed to decrypt wallet"
                session.commit()
                return

            result = self.executor.execute(tx_bytes, keypair, wait_confirm=True)

            if result.success:
                order.status = BuyOrderStatus.CONFIRMED
                order.tx_signature = result.signature
                order.tokens_received = quote.out_amount / 1e6  # Assuming 6 decimals
                order.executed_at = datetime.utcnow()
                session.commit()

                # Record spending
                self.spending_guard.record_spend(user, amount_usd, session)

                # Update message with success
                tokens_str = f"{order.tokens_received:,.0f}" if order.tokens_received else "?"
                sig_short = result.signature[:8] if result.signature else "?"

                await query.edit_message_text(
                    query.message.text.replace(" Executing swap...",
                        f"\n\n Bought {tokens_str} tokens for ${amount_usd}\n"
                        f"Tx: {sig_short}..."
                    ),
                    parse_mode="HTML"
                )
            else:
                order.status = BuyOrderStatus.FAILED
                order.error_message = result.error
                session.commit()

                await query.edit_message_text(
                    query.message.text.replace(" Executing swap...",
                        f"\n\n Transaction failed: {result.error}"
                    ),
                    parse_mode="HTML"
                )

        except Exception as e:
            logger.error(f"Buy callback error: {e}")
            await query.answer("Error processing buy. Check logs.", show_alert=True)
        finally:
            session.close()

    async def skip_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle skip button callback."""
        query = update.callback_query
        await query.answer("Skipped")

        # Just acknowledge - no action needed
        await query.edit_message_text(
            query.message.text + "\n\n Skipped",
            parse_mode="HTML"
        )

    async def unregister_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unregister confirmation callback."""
        query = update.callback_query
        await query.answer()

        if query.data == "unregister_confirm":
            session = self.Session()
            try:
                user = session.query(TelegramUser).filter_by(
                    telegram_user_id=update.effective_user.id
                ).first()

                if user:
                    # Clear sensitive data but keep record
                    user.encrypted_wallet = None
                    user.wallet_salt = None
                    user.wallet_pubkey = None
                    user.is_active = False
                    session.commit()

                await query.edit_message_text(
                    "Your wallet has been removed.\n\n"
                    "Use /start to register again."
                )
            finally:
                session.close()

        elif query.data == "unregister_cancel":
            await query.edit_message_text("Unregister cancelled.")

    async def menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle menu button callbacks."""
        query = update.callback_query
        await query.answer()

        if query.data == "menu_balance":
            await self.cmd_balance(update, context)
        elif query.data == "menu_history":
            await self.cmd_history(update, context)
        elif query.data == "menu_limits":
            await self.cmd_limits(update, context)
        elif query.data == "menu_delete":
            await self.cmd_unregister(update, context)

    # =========================
    # Application Setup
    # =========================

    def build_application(self) -> Application:
        """Build and configure the Telegram application."""
        self.application = Application.builder().token(self.bot_token).build()

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("balance", self.cmd_balance))
        self.application.add_handler(CommandHandler("limits", self.cmd_limits))
        self.application.add_handler(CommandHandler("history", self.cmd_history))
        self.application.add_handler(CommandHandler("unregister", self.cmd_unregister))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("menu", self.cmd_menu))

        # Callback handlers
        self.application.add_handler(
            CallbackQueryHandler(self.wizard_callback, pattern="^wizard_")
        )
        self.application.add_handler(
            CallbackQueryHandler(self.buy_callback, pattern="^buy_")
        )
        self.application.add_handler(
            CallbackQueryHandler(self.skip_callback, pattern="^skip_")
        )
        self.application.add_handler(
            CallbackQueryHandler(self.unregister_callback, pattern="^unregister_")
        )
        self.application.add_handler(
            CallbackQueryHandler(self.menu_callback, pattern="^menu_")
        )

        # Private key handler (messages in DM during registration)
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND,
                self.handle_private_key
            )
        )

        return self.application

    async def start_polling(self):
        """Start the bot with polling."""
        if not self.application:
            self.build_application()

        logger.info("Starting Telegram bot polling...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        """Stop the bot."""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info("Telegram bot stopped")
