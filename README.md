# JournalTX - Early-Stage Solana Meme Coin Detection

> **Philosophy:** This system exists to reduce activity, not increase it.

JournalTX monitors Solana blockchain for early-stage meme coin opportunities, filtering through noise to alert you on high-quality LP additions and momentum signals.

---

## 🎯 What It Does

- **Monitors** LP additions on Solana DEXs (Raydium, Orca, etc.)
- **Filters** for early-stage opportunities (<24h old, near-zero ignition)
- **Tracks** momentum signals (LP adds, volume spikes, buy pressure)
- **Alerts** only when multiple signals confirm opportunity
- **Logs** all events to database for analysis

---

## ⚠️ Critical Philosophy: Alert Rarity

> **"If alerts feel frequent, the system is wrong — not the market."**

### Expected Alert Frequency

**Early asymmetric opportunities are RARE by definition.**

**Real early trades are measured in singles per week, not dozens.**

| Profile | Alerts Per Week | Alert Quality | What This Means |
|---------|----------------|---------------|-----------------|
| **Conservative** | 1-3 | Very High | Only the best opportunities |
| **Balanced** | 3-7 | High | Quality opportunities |
| **Exploratory** | 5-10 | Medium | Some noise, but manageable |

**Note:** Degens Only profile exists but is hidden from normal usage (see Experimental Profiles below).

### If You're Getting Too Many Alerts

**Something is wrong.** Consider:

1. **Switch to more conservative profile**
   ```bash
   python scripts/profile.py switch conservative
   ```

2. **Check your filter settings**
   ```bash
   python scripts/profile.py current
   ```

3. **Adjust thresholds**
   - Create custom profile with higher LP minimums
   - Reduce signal window (requires faster confirmation)

### Red Flags

🔴 **WRONG:** "I got 50 alerts this week!"
→ Your thresholds are too low. Switch to Conservative.

🔴 **WRONG:** "I'm trading every alert."
→ You're missing the point. Alerts ≠ trades. 10% alert-to-trade ratio is HEALTHY.

🔴 **WRONG:** "Let me switch to Aggressive, I'm not getting enough alerts."
→ **DANGER ZONE.** This is emotional escalation. Stick to your profile for 7 days minimum.

✅ **RIGHT:** "I got 3 alerts this week, traded 1."
→ Perfect. Early asymmetry is rare.

✅ **RIGHT:** "Most alerts I skip after research."
→ Healthy filtering behavior.

✅ **RIGHT:** "I went 4 days without a single alert."
→ Normal. The market doesn't owe you opportunities.

### The Golden Rule

**Quality > Quantity**

One good alert per week > 20 mediocre alerts.

If you're not sure if your alert frequency is right, **it's probably too high.**

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp .env.example .env
nano .env  # Add your QuickNode and Telegram credentials
```

### 3. Choose Profile

```bash
# For early meme hunting (recommended)
PROFILE_TEMPLATE=aggressive

# Or use CLI
python scripts/profile.py switch aggressive
```

### 4. Initialize Database

```bash
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; from dotenv import load_dotenv; load_dotenv(); init_db(Config.from_env())"
```

### 5. Test Alert

```bash
python scripts/alert.py --type lp_add --pair TEST/SOL --sol 500 --lp-before 5 --pair-age 0.5
```

### 6. Start Listening

```bash
python scripts/listen.py
```

---

## 📊 Trading Profiles

Profiles control **when** you get alerts and **how many** per day.

### Conservative

**Best for:** High-quality trades only, minimal noise

**Thresholds:**
- **LP Add Minimum:** 2,000 SOL (~$300,000)
- **Max Trades Per Day:** 1
- **Volume Spike:** 5x baseline
- **LP Remove:** 70% of liquidity

**When to Use:**
- ✅ You only want high-quality LP additions
- ✅ You have limited time to trade
- ✅ You prefer quality over quantity
- ✅ You're trading with larger capital

**Example Scenario:**
```
Alert: NEWSOL/SOL LP Added - 2,500 SOL (pair age: 2 hours)
→ This is significant liquidity. Worth investigating.
→ Only 1 alert/day means you can focus on this one.
→ Early-stage opportunity confirmed.
```

**Trade Frequency:** 2-5 alerts per week

---

### Balanced (Default)

**Best for:** Balanced approach, moderate alert frequency

**Thresholds:**
- **LP Add Minimum:** 500 SOL (~$50,000)
- **Max Trades Per Day:** 2
- **Volume Spike:** 3x baseline
- **LP Remove:** 50% of liquidity

**When to Use:**
- ✅ You want a mix of quality and opportunity
- ✅ You can handle 2-3 trades per day
- ✅ You're comfortable with moderate risk
- ✅ You want to catch early momentum without overtrading

**Example Scenario:**
```
Alert 1: NEWCOIN/SOL LP Added - 650 SOL
→ Good liquidity, check it out.

Alert 2: Another token LP Removed - 60%
→ Possible exit signal.
→ Max 2 trades/day prevents overtrading.
```

**Trade Frequency:** 10-20 alerts per week

---

### Exploratory ⚡

**Best for:** Early entry with balanced noise filtering

**Thresholds:**
- **LP Add Minimum:** 100 SOL (~$5,000)
- **Max Actions Per Day:** 5
- **Volume Spike:** 2x baseline
- **LP Remove:** 30% of liquidity

**When to Use:**
- ✅ You want to catch early-stage opportunities
- ✅ You're experienced with meme coins
- ✅ You can react quickly to alerts
- ✅ You accept higher risk for earlier entry
- ✅ **RECOMMENDED for early meme hunting**

**Example Scenario:**
```
Alert 1: EARLY/SOL LP Added - 150 SOL (pair age: 18 min)
→ Near-zero ignition! 5 SOL → 155 SOL
→ This is exactly what you're looking for.

Alert 2: Volume spike 3x on same token (within 30 min)
→ Multi-signal confirmation!
→ Second momentum signal confirms opportunity.
```

**Trade Frequency:** 5-10 alerts per week

**⚠️ Warning:** Early opportunities are rare by definition. Expect singles, not dozens. Early asymmetric opportunities are RARE.

---

## 🔬 Experimental Profiles

### ⚠️ Degens Only (HIDDEN/EXPERIMENTAL)

**This profile is hidden from normal usage because it contradicts the core philosophy.**

**Philosophy Violation:**
- Core: "Reduce activity, not increase it"
- Degens Only: "See everything, maximum alerts"
- **Result:** Alert addiction risk

**Still Exists Because:**
- Advanced users may want experimental research
- Data collection for improving filters
- "Do nothing mode" testing

**How to Enable (Not Recommended):**
```bash
# Must manually edit .env - not shown in normal options
nano .env
# Change: PROFILE_TEMPLATE=degens_only
```

**Thresholds:**
- **LP Add Minimum:** 50 SOL (~$1,000)
- **Max Actions Per Day:** 10
- **Volume Spike:** 1.5x baseline
- **Trade Frequency:** 30-50+ alerts/week (mostly noise)

**Realistic Expectation:**
- 90% of alerts will be low-quality or scams
- Requires extreme discipline to not overtrade
- **Not for live trading - experimental only**

---

## 🔍 Filter Templates

Filters control **which tokens** you see (early-stage filtering).

### Default Filter

**Settings:**
- **Max Market Cap:** $8M (defensive, reduced from $20M)
- **Max Pair Age:** 24 hours (hard gate)
- **Preferred Pair Age:** 6 hours (sweet spot for early entry)
- **Legacy Memes Excluded:** BONK, WIF, DOGE, SHIB, PEPE, FLOKI, BABYDOGE, MOON, SAMO, KING, MONKY

**Hard Reject Rules (Auto-Ignore):**
```
These get logged to database but NO Telegram alert:
- Pair age > 24 hours
- Market cap ≥ $20M (too large)
- Baseline liquidity > 20 SOL (not near-zero ignition)
```

**What It Does:**
- ✅ Alerts on tokens <24h old
- ✅ Prefers tokens <6 hours old (sweet spot)
- ✅ Excludes big memes (>$20M market cap - hard reject)
- ✅ Requires near-zero ignition (≤20 SOL baseline)
- ✅ Blocks legacy memes (already pumped)

**When to Use:**
- ✅ **Always** (default is optimized for early asymmetry)
- ✅ You want early-stage opportunities
- ✅ You don't want late-stage "pumped" coins

**Example:**
```
✅ PASS: NEWTOKEN/SOL (age: 2h, baseline: 5 SOL, market cap: $500K)
❌ BLOCK: BONK/SOL (legacy meme - auto-ignored)
❌ BLOCK: OLDTOKEN/SOL (age: 48h - auto-ignored)
❌ BLOCK: BIGTOKEN/SOL (market cap: $50M - auto-ignored)
❌ BLOCK: MEDIUMTOKEN/SOL (baseline: 50 SOL - auto-ignored)
```

**Key Changes from Previous:**
1. **Stricter market cap:** $8M max (was $20M)
2. **Preferred age window:** 6 hours sweet spot
3. **Explicit hard reject rules:** Clear auto-ignore criteria
4. **Stricter baseline:** ≤20 SOL (was ≤10 SOL)

---

### Creating Custom Filters

Create `config/filters/my_filter.json`:

```json
{
  "name": "My Custom Filter",
  "description": "Stricter requirements for very early memes",
  "max_market_cap": 5000000.0,     // $5M max (stricter)
  "max_pair_age_hours": 12,          // 12h max (stricter)
  "signal_window_minutes": 20,       // 20-min window
  "legacy_memes": [
    "BONK", "WIF", "DOGE", "SHIB", "PEPE",
    "FLOKI", "BABYDOGE", "MOON", "SAMO",
    "KING", "MONKY",
    "COIN"  // Add more to exclude
  ]
}
```

Use custom filter:
```bash
FILTER_TEMPLATE=my_filter
```

---

## 🎯 Profile + Filter Combinations

### Scenario 1: Conservative Swing Trading

**Profile:** `conservative`
**Filter:** `default`

**Result:** High-quality LP adds on early-stage tokens, very low frequency.

**Best for:** Part-time traders who want only the best opportunities.

---

### Scenario 2: Balanced Day Trading

**Profile:** `balanced`
**Filter:** `default`

**Result:** Mix of quality and opportunity, 2-3 trades/day.

**Best for:** Active traders who want balance.

---

### Scenario 3: Aggressive Early Meme Hunting ⚡

**Profile:** `aggressive`
**Filter:** `default`

**Result:** Early entry on new memes, catches tokens before pump.

**Best for:** **RECOMMENDED** - Early meme hunting with discipline.

---

### Scenario 4: Ultra-Early Sniper

**Profile:** `aggressive`
**Filter:** Custom strict filter (6h max age, $5M max cap)

**Result:** Only the newest, smallest tokens.

**Best for:** Experienced traders catching launches.

---

### Scenario 5: Degen Mode

**Profile:** `degens_only`
**Filter:** `default`

**Result:** Maximum alerts, see everything.

**Best for:** Degens who want maximum information (and maximum risk).

---

## 📋 Early-Stage Filtering Rules

JournalTX uses multi-stage filtering to find early opportunities:

### 0. Auto-Ignore Rule (Critical)

**If early-stage hard rules fail → event is logged to database but NO Telegram alert is sent.**

This reduces mental load. You only see alerts that pass basic filters.

**What gets auto-ignored (silent log only):**
- Legacy memes (BONK, WIF, DOGE, etc.)
- Non-SOL pairs (USDT/USDC pairs)
- Pairs older than 24 hours
- Market cap ≥$20M (defensive filter)
- Wrong quote token

**What triggers alerts (sent to Telegram):**
- Near-zero ignition (≤10 SOL baseline)
- Significant LP addition
- Within 24h window
- Multi-signal confirmation

### 1. Hard Blocks (Auto-Reject)
- ❌ Legacy memes (BONK, WIF, DOGE, etc.)
- ❌ Non-SOL pairs (USDT/USDC pairs)
- ❌ Pairs older than 24 hours

### 2. Near-Zero Ignition
- ✅ Baseline ≤10 SOL before LP
- ✅ LP addition ≥100-300 SOL (depending on profile)

**Example:**
```
Before: 3 SOL (near-zero ✅)
Added:  500 SOL (significant ✅)
After:  503 SOL
→ PASS: Near-zero ignition detected
```

### 3. Market Cap (Defensive Only)
- ✅ Used ONLY to exclude big coins
- ❌ NOT used as entry signal
- Reject if ≥$20M market cap

**Example:**
```
$500K market cap → PASS (early stage)
$20M market cap → FAIL (too late)
```

### 4. Multi-Signal Requirement
- ✅ Need 2+ different signals within 30 minutes
- Signals: LP add, volume spike, buy pressure

**Example:**
```
Signal 1: LP Add (150 SOL added)
→ Logged to database, NO Telegram alert yet

Signal 2: Volume Spike (3x baseline, 15 min later)
→ Multi-signal confirmed!
→ Telegram alert sent ✅
```

**Why?** Prevents false positives from single events.

---

## 📊 Alert Message Format

```
🟡 JournalTX Alert [🧪 TEST MODE] [🔥 HIGH PRIORITY]

Type: LP Added
Pair: NEWCOIN / SOL
LP Added: +420 SOL (~$63,000)
Pair Age: 18 minutes (EARLY WINDOW)
Liquidity Before: 3 SOL
Liquidity After: 423 SOL
Time: 20:56 WIB
Early-Stage Check: ✅ PASSED

Reminder:
This is NOT a trade signal.
```

### Early-Window Priority Tags

The system tags alerts based on pair age to emphasize urgency:

| Tag | Pair Age | Meaning | Action |
|-----|----------|---------|--------|
| 🔥 **HIGH** | <30 min | Golden window - fresh launch | Drop everything, research NOW |
| ⚡ **MEDIUM** | 30-120 min | Early discovery | Research soon if interested |
| ✅ **LOW** | 2-24 hours | Valid but less urgent | Research when free |

**Why this matters:**
- First 30 minutes = highest asymmetric potential
- First 2 hours = still early, good opportunities
- After 2 hours = still valid (<24h) but less urgent

**What to check:**
1. **Priority Tag:** 🔥 HIGH = Act fast, ✅ LOW = Can wait
2. **Pair Age:** <6 hours is ideal (catch early)
3. **LP Added:** Higher = more commitment from dev
4. **Liquidity Before:** Lower = better (near-zero ignition)
5. **Early-Stage Check:** Must be ✅ PASSED

**What to do:**
1. Click **DexScreener** link - Check chart
2. Click **Photon** link - Check token info
3. Research: Contract, social media, holders
4. Decide: Trade or wait?

---

## 🛡️ Guardrails

### Max Actions Per Day

Each profile limits daily actions (trades + significant decisions) to prevent overtrading:

```
Conservative: 1 action/day
Balanced: 2 actions/day
Exploratory: 5 actions/day
```

**Why?** Prevents FOMO and impulsive trading.

**Note:** The system does NOT auto-trade. This limits YOUR actions, not system alerts.

### Example:

```
9:00 AM - Alert 1: TOKEN_A LP Added
→ You research and decide to trade (Action 1/2)

10:30 AM - Alert 2: TOKEN_B LP Added
→ You research and decide to trade (Action 2/2)

11:00 AM - Alert 3: TOKEN_C LP Added
→ Guardrail: MAX ACTIONS REACHED (2/2)
→ SYSTEM: "Daily action limit reached."
→ YOU: Forced to wait until tomorrow.
→ RESULT: Saved from overtrading.
```

---

## 🎮 CLI Commands

### Profile Management

```bash
# List all profiles
python scripts/profile.py list

# Show current profile
python scripts/profile.py current

# Switch profile
python scripts/profile.py switch aggressive
python scripts/profile.py switch balanced
python scripts/profile.py switch conservative

# Switch with custom filter
python scripts/profile.py switch aggressive --filter strict
```

### Testing

```bash
# Test alert (manual)
python scripts/alert.py --type lp_add --pair TEST/SOL --sol 500 --lp-before 5 --pair-age 0.5

# Test Telegram
python scripts/test_telegram.py
```

### Database

```bash
# Initialize database
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; from dotenv import load_dotenv; load_dotenv(); init_db(Config.from_env())"

# Reset database (delete and recreate)
rm -f data/journaltx.db
python -c "from journaltx.core.db import init_db; from journaltx.core.config import Config; from dotenv import load_dotenv; load_dotenv(); init_db(Config.from_env())"
```

### Trade Journaling

```bash
# Log a trade entry
python scripts/log_trade.py --pair TOKEN --entry 0.00001234

# Exit a trade
python scripts/log_trade.py exit 1 --price 0.00002400

# Weekly review
python scripts/review_week.py

# Screener - review historical alerts
python scripts/screener.py --hours 24 --type lp_add --min-sol 500

# Export data
python scripts/export_csv.py trades
python scripts/export_csv.py alerts
```

---

## 📁 Configuration Files

### `.env` (Main Configuration)

```bash
# Mode
MODE=TEST  # Change to LIVE for production

# Profile Template (EASY SETUP!)
PROFILE_TEMPLATE=aggressive  # Choose: conservative, balanced, aggressive, degens_only
FILTER_TEMPLATE=default

# Credentials
QUICKNODE_WS_URL=wss://your-quicknode-url
QUICKNODE_HTTP_URL=https://your-quicknode-url
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Timezone
TIMEZONE=Asia/Jakarta  # Options: UTC, Asia/Jakarta, America/New_York, etc.
```

### `config/profiles/{name}.json` (Profile Thresholds)

Edit these files to customize thresholds:

```bash
config/profiles/
├── conservative.json
├── balanced.json
├── aggressive.json
└── degens_only.json
```

### `config/filters/{name}.json` (Early-Stage Filters)

Edit these to customize filtering:

```bash
config/filters/
└── default.json
```

---

## 🎓 Trading Guidelines

### 1. Not All Alerts Are Trades

**Rule:** 10 alerts → 2 trades → 1 winner

```
Alert 1: Skip (liquidity too low)
Alert 2: Trade ✅ (good setup)
Alert 3: Skip (token looks suspicious)
Alert 4: Skip (chart looks weak)
Alert 5: Trade ✅ (strong momentum)
...
```

**Accept:** 80% of alerts are just information.

### 2. Always Research Before Trading

**Checklist:**
- ✅ Token contract (rugcheck)
- ✅ Holder distribution (top holder <35%)
- ✅ Social media (Twitter, Telegram)
- ✅ Liquidity locked?
- ✅ Mint authority?
- ✅ Freeze authority?

**Tools:**
- [DexScreener](https://dexscreener.com) - Charts
- [Photon](https://photon-sol.tinyastro.io) - Token info
- [Birdeye](https://birdeye.so) - Analytics
- [Solscan](https://solscan.io) - Transaction history

### 3. Define Risk Before Entry

**For Every Trade:**
```
Entry: $0.00001234
Stop Loss: $0.000011 (10% drop)
Target: $0.000024 (2x gain)
Risk/Reward: 1:2 ✅
```

**Never enter without:**
- Stop loss level
- Take profit target
- Max position size

### 4. Scale Out, Don't "All In"

**Bad:**
```
All in: 100 SOL at $0.00001
Price drops 20%
→ You panic and sell at loss
```

**Good:**
```
Entry: 30 SOL at $0.00001
Add: 30 SOL if momentum continues
Scale out: 50% at 2x
Scale out: 50% at 5x
→ You lock in profits
```

### 5. Review Weekly

```bash
# Weekly review
python scripts/review_week.py
```

**Questions to ask:**
- Did I follow my plan?
- Did I overtrade?
- What worked? What didn't?
- Any rules to adjust?

---

## 🚨 Common Mistakes

### Mistake 1: Trading Every Alert

**Wrong:** Alert received → Immediate trade
**Right:** Alert received → Research → Decide

### Mistake 2: Ignoring Pair Age

**Wrong:** Trading token with 23h age (almost expired)
**Right:** Wait for fresh tokens (<6h old)

### Mistake 3: Chasing Late Entries

**Wrong:** Token already 10x, you buy at top
**Right:** Wait for new opportunities

### Mistake 4: No Stop Loss

**Wrong:** "I'll just hold until it comes back"
**Right:** Cut losses at -10%

### Mistake 5: Switching Profiles Too Often

**Wrong:** Switching from conservative → aggressive → degen in one day
**Right:** Choose profile based on your strategy, stick to it for at least a week

**⚠️ CRITICAL RULE: Profile Lock (7-Day Minimum)**

To prevent emotional escalation:

```
Monday: Choose Aggressive profile
→ Tuesday: Bad trading day, want to switch to Conservative
→ SYSTEM: LOCKED (must wait until next Monday)
→ YOU: Forced to stick with decision
→ RESULT: Protected from emotional escalation
```

**Why this exists:**
- Prevents "revenge profile switching" after losses
- Forces discipline and commitment
- Prevents chasing different market conditions
- Protects from FOMO (switching to Degens for more action)

**How it works:**
- Profile can only be changed once every 7 days
- Calendar resets on the day you first choose a profile
- Manual override requires direct config file editing (intentionally difficult)

---

## 📈 Performance Tracking

All alerts logged to database for analysis:

```bash
# Export trades to CSV
python scripts/export_csv.py trades

# View weekly screener
python scripts/screener.py

# Run weekly review
python scripts/review_week.py
```

---

## 🔧 Troubleshooting

### Problem: No Alerts Received

**Possible Causes:**
1. Thresholds too high → Switch to more aggressive profile
2. No LP additions → Market is slow, wait
3. QuickNode connection issue → Test connection
4. Telegram bot issue → Run `python scripts/test_telegram.py`

**Solution:**
```bash
# Test with manual alert
python scripts/alert.py --type lp_add --pair TEST/SOL --sol 1000 --lp-before 5 --pair-age 0.1

# Check profile
python scripts/profile.py current

# Lower thresholds if needed
python scripts/profile.py switch aggressive
```

### Problem: Too Many Alerts

**Solution:**
```bash
# Switch to more conservative profile
python scripts/profile.py switch balanced
python scripts/profile.py switch conservative
```

### Problem: Alerts on Big Meme Coins

**Solution:**
```bash
# Create stricter filter
# config/filters/strict.json: max_market_cap = 5000000 (5M)

python scripts/profile.py switch aggressive --filter strict
```

---

## 📚 Documentation

- [JSON Configuration Guide](docs/JSON_CONFIG_GUIDE.md) - How to customize profiles/filters
- [Deployment Guide](docs/DEPLOYMENT.md) - VPS deployment (coming soon)

---

## 🔧 Technical Architecture

### Real On-Chain LP Detection

JournalTX uses **real on-chain data** from QuickNode WebSocket subscriptions - no simulations, no mocks.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QUICKNODE (PRIMARY DATA SOURCE)                  │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                     │
│  1. WebSocket → logsSubscribe(Raydium AMM Program)                  │
│     └── Subscribes to: 675kPX9MHTjS2zt1qfSiQiLpKcM8cCtKxEbZqE8qiVJ  │
│                                                                     │
│  2. HTTP RPC → getTransaction(signature, jsonParsed)                │
│     └── Fetches full transaction details                            │
│                                                                     │
│  3. Raydium Decoder → Parse instruction + account indices           │
│     └── Identifies: initialize, deposit, withdraw, swap             │
│                                                                     │
│  4. Balance Delta Analysis → preBalances vs postBalances            │
│     └── Calculates: SOL deposited, tokens added, LP minted          │
│                                                                     │
│  THIS IS REAL ON-CHAIN LP DETECTION                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     ENRICHMENT ONLY (FREE APIs)                     │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                                                     │
│  Jupiter Token API → token_mint → symbol, name (FREE)               │
│  Jupiter/CoinGecko Price API → SOL price in USD (FREE)              │
│  DexScreener API → market cap, pair age for FILTERING (FREE)        │
│                                                                     │
│  These DO NOT detect LP - they only enrich the on-chain data        │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **QuickNode WebSocket** receives Raydium AMM program logs
2. **Signature Extraction** from log notification
3. **Deduplication** prevents double-processing
4. **Transaction Fetch** via getTransaction RPC
5. **Raydium Decoder** parses instruction type and accounts
6. **Balance Delta Analysis** calculates actual liquidity change
7. **Token Resolver** enriches with symbol/name from Jupiter
8. **Early-Stage Filters** apply all rules
9. **Telegram Alert** sent only if all checks pass

### Key Detection Criteria

An LP addition is detected ONLY IF:
- ✅ Transaction involves Raydium AMM V4 program
- ✅ Instruction is `initialize`, `initialize2`, or `deposit`
- ✅ SOL balance in pool vault **INCREASED**
- ✅ Token balance in pool vault **INCREASED**
- ✅ SOL delta exceeds noise threshold (0.1 SOL)
- ✅ Not a failed transaction (err == null)

### Files Structure

```
journaltx/
├── core/
│   ├── config.py          # Configuration from JSON + .env
│   ├── db.py              # SQLite database management
│   └── models.py          # Alert, Trade, Journal models
├── ingest/
│   ├── quicknode/
│   │   ├── raydium_decoder.py      # Raydium instruction parsing
│   │   ├── raydium_subscriptions.py # WebSocket subscription format
│   │   ├── transaction_parser.py    # Full LP event parsing
│   │   ├── lp_events.py            # LP event processing
│   │   └── volume_events.py        # Volume spike detection
│   └── token_resolver.py   # Jupiter/DexScreener API integration
├── filters/
│   ├── early_meme.py      # Early-stage filtering rules
│   └── signals.py         # Multi-signal tracking
├── notify/
│   └── telegram.py        # Telegram notification formatting
└── guardrails/
    └── rules.py           # Trading discipline rules
```

---

## ⚖️ Philosophy

> **"This system exists to reduce activity, not increase it."**

Every feature is designed to:
- ✅ Reduce overtrading
- ✅ Encourage research
- ✅ Enforce discipline
- ✅ Improve decision quality
- ❌ NOT to auto-trade
- ❌ NOT to provide "hot tips"
- ❌ NOT to create urgency

**JournalTX = Information + Discipline**

---

## 🎯 Summary

### Choose Profile Based On:

| Profile | For You If... | Trade Frequency |
|---------|---------------|-----------------|
| **Conservative** | Want quality only, low time commitment | 1-3/week |
| **Balanced** | Want balance, can handle 2-3 trades/day | 3-7/week |
| **Exploratory** | Early entry, experienced, want to catch memes before pump | 5-10/week |

### Recommended Setup for Early Meme Hunting:

```bash
MODE=TEST  # Start in TEST mode
PROFILE_TEMPLATE=exploratory  # Best balance for early memes
FILTER_TEMPLATE=default

# After 1 week of testing, switch to LIVE
MODE=LIVE
```

### Key Rules:

1. **Not all alerts are trades** - 80% are just information
2. **Research before trading** - Check contract, holders, socials
3. **Define risk before entry** - Stop loss, take profit, position size
4. **Scale out, don't all in** - Lock in profits along the way
5. **Review weekly** - Learn from mistakes, improve process

---

## 📞 Support

For issues or questions:
1. Check [JSON Configuration Guide](docs/JSON_CONFIG_GUIDE.md)
2. Review troubleshooting section above
3. Check logs in `data/` directory

---

**Happy Hunting! 🚀**

*Remember: The best trade is often the one you don't make.*
