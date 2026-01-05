# Telegram Setup Guide

Telegram is **REQUIRED** for JournalTX. All alerts are sent via Telegram.

---

## Quick Setup (2 Minutes)

### Step 1: Message Your Bot

1. Open Telegram
2. Search: **@journaltx_pybot**
3. Send: `/start`

### Step 2: Get Your Chat ID

```bash
venv/bin/python scripts/get_chat_id.py
```

This will automatically:
- Fetch your Chat ID
- Save it to `.env`
- Send a test message

### Step 3: Verify

```bash
venv/bin/python scripts/test_telegram.py
```

You should receive 4 test messages.

---

## What You'll Receive

### 1. LP Addition Alerts
```
JournalTX Alert

Type: LP Added
Chain: Solana
Pair: BONK / SOL
LP Added: 1,250 SOL (~$187,500)
Time: 14:32 UTC

Reminder:
This is NOT a trade signal.
Check risk/reward and rules first.
```

### 2. Volume Spike Alerts
```
JournalTX Alert

Type: Volume Spike
Chain: Solana
Pair: WIF / SOL
Value: 5,000 SOL (~$750,000)
Time: 15:45 UTC

Reminder:
This is NOT a trade signal.
Check risk/reward and rules first.
```

### 3. LP Removal Alerts
```
JournalTX Alert

Type: LP Removed
Chain: Solana
Pair: MYRO / SOL
LP Removed: 800 SOL (~$120,000)
Time: 16:20 UTC

Reminder:
This is NOT a trade signal.
Check risk/reward and rules first.
```

### 4. Weekly Reviews
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

---

## Manual Alert Creation

You can manually create alerts that will be sent to Telegram:

```bash
# Log an LP addition alert
python scripts/alert.py --type lp_add --pair BONK/SOL --sol 1000

# Log a volume spike alert
python scripts/alert.py --type volume_spike --pair WIF/SOL --sol 5000
```

---

## Send Weekly Review to Telegram

```bash
python scripts/review_week.py --telegram
```

---

## Troubleshooting

### Bot Not Responding

1. Make sure you've started the bot with `/start`
2. Check the bot username: `@journaltx_pybot`

### Chat ID Not Found

1. You MUST message the bot first
2. Send any message (`/start` works)
3. Then run the get_chat_id script

### Test Messages Not Sending

Check your `.env` file:
```bash
TELEGRAM_BOT_TOKEN=8564945802:AAFcw3XpGSbto9oZdQUf3w-iZBwfW1j8DHc
TELEGRAM_CHAT_ID=your_actual_chat_id
```

---

## Creating Your Own Bot (Optional)

If you want to create a custom bot instead of using the provided one:

1. **Create Bot**
   - Telegram: @BotFather
   - Send: `/newbot`
   - Follow prompts
   - Copy the Bot Token

2. **Update `.env`**
   ```bash
   TELEGRAM_BOT_TOKEN=your_new_token
   ```

3. **Get Chat ID**
   ```bash
   python scripts/get_chat_id.py
   ```

---

## Alert Thresholds

Configure what triggers alerts in `.env`:

```bash
# Minimum SOL amount for LP addition alerts
LP_ADD_MIN_SOL=500.0

# Minimum USD amount for LP addition alerts
LP_ADD_MIN_USD=10000.0

# Minimum percentage for LP removal alerts
LP_REMOVE_MIN_PCT=50.0

# Volume spike multiplier (e.g., 3x baseline)
VOLUME_SPIKE_MULTIPLIER=3.0
```

---

## Summary

| Feature | Command |
|---------|---------|
| Setup | `python scripts/get_chat_id.py` |
| Test | `python scripts/test_telegram.py` |
| Manual alert | `python scripts/alert.py --type lp_add --pair TOKEN/SOL --sol 1000` |
| Weekly review | `python scripts/review_week.py --telegram` |
| Custom test | `python scripts/test_telegram.py custom --pair TOKEN/SOL --sol 1000` |
