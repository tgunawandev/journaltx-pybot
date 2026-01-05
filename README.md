# JournalTX

**Personal Trading Discipline System**

A self-hosted Python system for detecting on-chain asymmetry, logging trades, and improving behavioral discipline for Solana meme trading.

---

## What This Is NOT

This is **NOT** a trading bot.

This is **NOT** a signal service.

This is **NOT** a public product.

This system exists to reduce activity, not increase it.

---

## Philosophy

Money movement > narratives

Reaction > prediction

Journaling > dashboards

Review > activity

Exits matter more than entries

---

## Features

### Detection

Monitors Solana on-chain activity via QuickNode:

- **LP additions** above configurable threshold
- **LP removals** above configurable percentage
- **Volume spikes** above rolling baseline

Sends neutral Telegram alerts (no buy/sell language).

### Journaling

Mandatory journaling for every trade:

- Why did I enter?
- Was risk defined before entry?
- Was scale-out used?
- Where was invalidation?
- Rule adherence tracking
- Continuation quality assessment

### Review

Weekly behavioral analysis:

- Win rate and average win/loss
- Rules followed percentage
- Scale-out usage
- Continuation quality breakdown
- **ONE specific change for next week**

### Guardrails

Soft warnings for:

- Daily trade limit exceeded (default: 2)
- Missing journal entries
- Scale-out not used
- Too many open positions

**Never blocks execution** - only logs warnings.

---

## Installation

### Prerequisites

- Python 3.11+
- QuickNode account (Solana HTTP/WebSocket endpoint)
- Telegram bot (optional, for notifications)

### Setup

1. Clone repository:
```bash
git clone <repo-url>
cd journaltx-pybot
```

2. Create virtual environment:
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -e .
```

4. Copy environment file:
```bash
cp .env.example .env
```

5. Configure QuickNode (add to `.env`):
```bash
QUICKNODE_WS_URL=wss://your-quicknode-url
QUICKNODE_HTTP_URL=https://your-quicknode-url
```

6. **Setup Telegram (REQUIRED):**
```bash
# Step 1: Message the bot on Telegram
# Open Telegram → Search @journaltx_pybot → Send: /start

# Step 2: Get your Chat ID
venv/bin/python scripts/get_chat_id.py

# Step 3: Test
venv/bin/python scripts/test_telegram.py
```

See [TELEGRAM.md](TELEGRAM.md) for detailed Telegram setup.

7. Initialize database:
```bash
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; init_db(Config.from_env())"
```

---

## Usage

### Log a Trade

**This is the only way trades should be entered.**

```bash
python scripts/log_trade.py --pair TOKEN --entry 0.045
```

Prompts for:
- Why did I enter?
- Was risk defined before entry?
- Was scale-out used?
- Where was invalidation?
- Continuation quality
- One sentence lesson

### Close a Trade

```bash
python scripts/log_trade.py exit 1 --price 0.058
```

### Weekly Review

```bash
python scripts/review_week.py
```

Output:

```
JournalTX - Weekly Review (Last 7 days)

Trades: 11
Closed: 9
Open: 2

Performance:
Win rate: 55%
Avg win: +33%
Avg loss: -14%

Discipline:
Rules followed: 82%
Scale-out used: 44%

Continuation:
Not justified: 6
Mixed: 3
Strong: 2

ONE CHANGE NEXT WEEK:
-> Take partial profits earlier on first impulse
```

### Screener

Review historical alerts (never suggests trades):

```bash
python scripts/screener.py --hours 24 --type lp_add --min-sol 500
```

Output:

```
JournalTX Screener - Last 24h

TOKEN1 / SOL
- LP Added: 1,250 SOL
- Volume Spike: Yes
- Trade Taken: No

TOKEN2 / SOL
- LP Added: 800 SOL
- Volume Spike: No
- Trade Taken: Yes
```

### Export Data

```bash
# Export trades
python scripts/export_csv.py trades

# Export alerts
python scripts/export_csv.py alerts
```

### Listen for Events (Optional)

Run QuickNode WebSocket listener:

```bash
python scripts/listen.py
```

---

## Database Models

### Trade

- `id` - Primary key
- `timestamp` - Entry time
- `chain` - Default: solana
- `pair_base` - Token symbol
- `pair_quote` - Quote currency (SOL)
- `entry_price` - Entry price
- `exit_price` - Exit price (nullable)
- `pnl_pct` - Profit/loss % (nullable)
- `risk_followed` - Boolean
- `scale_out_used` - Boolean
- `notes` - Free text

### Journal

- `id` - Primary key
- `trade_id` - Foreign key to Trade
- `rule_followed` - Boolean
- `continuation_quality` - Enum: ❌ / ⚠️ / ✅
- `lesson` - Single sentence

### Alert

- `id` - Primary key
- `type` - Enum: lp_add, lp_remove, volume_spike
- `chain` - Default: solana
- `pair` - Trading pair
- `value_sol` - Amount in SOL
- `value_usd` - Amount in USD (display only)
- `triggered_at` - Timestamp
- `trade_id` - Foreign key to Trade (nullable)

---

## Telegram Alerts

**Neutral, boring messages.**

```
JournalTX Alert

Type: LP Added
Chain: Solana
Pair: TOKEN / SOL
LP Added: 1,250 SOL (~$72,000)
Time: 14:32 UTC

Reminder:
This is NOT a trade signal.
Check risk/reward and rules first.
```

No urgency language. No buy/sell suggestions.

---

## Asymmetric Meme Trading

Edge in meme trading comes from:

1. **Timing** - Early detection of LP/volume ignition
2. **Exits** - Taking profits before collapse
3. **Discipline** - Following rules consistently

This system helps with all three by:

- Detecting early on-chain asymmetry (LP + volume)
- Forcing journaling and reflection
- Enabling weekly behavioral review
- Actively reducing overtrading and FOMO

---

## Project Structure

```
journaltx-pybot/
├── journaltx/
│   ├── core/
│   │   ├── db.py          # Database session management
│   │   ├── models.py      # Trade, Journal, Alert models
│   │   └── config.py      # Configuration from env
│   ├── ingest/
│   │   ├── manual.py      # Manual alert logging
│   │   └── quicknode/
│   │       ├── lp_events.py       # LP event listener
│   │       ├── volume_events.py   # Volume spike listener
│   │       └── schemas.py         # Event data schemas
│   ├── notify/
│   │   └── telegram.py     # Telegram notifications
│   ├── review/
│   │   ├── weekly.py       # Weekly review generator
│   │   ├── stats.py        # Statistics queries
│   │   └── screener.py     # Historical alerts screener
│   └── guardrails/
│       └── rules.py        # Behavioral guardrails
├── scripts/
│   ├── log_trade.py        # Log/close trades
│   ├── review_week.py      # Weekly review
│   ├── screener.py         # Alert screener
│   └── export_csv.py       # Export to CSV
├── data/
│   └── journaltx.db        # SQLite database
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black journaltx/ scripts/
ruff check journaltx/ scripts/
```

---

## License

MIT

---

## Disclaimer

This system is for personal educational purposes only. It does not provide financial advice. Cryptocurrency trading involves substantial risk of loss. Past performance is not indicative of future results.

**This system exists to reduce activity, not increase it.**
