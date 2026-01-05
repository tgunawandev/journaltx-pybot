# JournalTX JSON Configuration Guide

## Overview

All thresholds, filters, and parameters are now stored in JSON files. You can easily switch between different trading profiles by changing just one line in your `.env` file.

## Quick Start

### 1. Choose Your Profile

Edit `.env`:
```bash
PROFILE_TEMPLATE=aggressive  # Options: conservative, balanced, aggressive, degens_only
FILTER_TEMPLATE=default       # Or create custom filters
```

### 2. View Current Settings

```bash
source venv/bin/activate
python scripts/profile.py current
```

### 3. List All Profiles

```bash
python scripts/profile.py list
```

### 4. Switch Profiles

```bash
python scripts/profile.py switch balanced
```

### 5. Test Configuration

```bash
python scripts/alert.py --type lp_add --pair TEST/SOL --sol 500 --lp-before 5 --pair-age 0.5
```

## Built-in Profiles

### Conservative
- **LP Min:** 2,000 SOL (~$300,000)
- **Max Trades/Day:** 1
- **Best for:** High-quality LP additions only

### Balanced (Default)
- **LP Min:** 500 SOL (~$50,000)
- **Max Trades/Day:** 2
- **Best for:** Balanced alert frequency

### Aggressive
- **LP Min:** 100 SOL (~$5,000)
- **Max Trades/Day:** 5
- **Best for:** Early entry, more alerts

### Degens Only
- **LP Min:** 50 SOL (~$1,000)
- **Max Trades/Day:** 10
- **Best for:** Maximum alerts, high risk

## JSON Structure

### Profile Template: `config/profiles/{name}.json`

```json
{
  "name": "Profile Name",
  "description": "Profile description",
  "filters": {
    "lp_add_min_sol": 500.0,        # Min SOL for LP alert
    "lp_add_min_usd": 50000.0,      # Min USD for LP alert
    "lp_remove_min_pct": 50.0,      # Min % for LP removal alert
    "volume_spike_multiplier": 3.0, # Volume spike threshold
    "max_trades_per_day": 2         # Daily trade limit
  },
  "early_stage": {
    "near_zero_baseline_sol": 10.0,   # Near-zero baseline (≤X SOL before LP)
    "min_lp_ignite_sol": 300.0,       # Min SOL for LP ignition
    "signal_window_minutes": 30       # Multi-signal time window
  }
}
```

### Filter Template: `config/filters/{name}.json`

```json
{
  "name": "Filter Name",
  "description": "Filter description",
  "max_market_cap": 20000000.0,        # $20M - Defensive filter only
  "max_pair_age_hours": 24,            # 24h - Auto-reject if older
  "signal_window_minutes": 30,         # Signal time window
  "legacy_memes": [                    # Hard exclusion list
    "BONK", "WIF", "DOGE", "SHIB", "PEPE",
    "FLOKI", "BABYDOGE", "MOON", "SAMO",
    "KING", "MONKY"
  ]
}
```

## Creating Custom Profiles

### 1. Create Profile JSON

Create `config/profiles/my_custom.json`:
```json
{
  "name": "My Custom Style",
  "description": "My personal trading preferences",
  "filters": {
    "lp_add_min_sol": 800.0,
    "lp_add_min_usd": 100000.0,
    "lp_remove_min_pct": 40.0,
    "volume_spike_multiplier": 2.5,
    "max_trades_per_day": 3
  },
  "early_stage": {
    "near_zero_baseline_sol": 15.0,
    "min_lp_ignite_sol": 400.0,
    "signal_window_minutes": 25
  }
}
```

### 2. Use Custom Profile

Edit `.env`:
```bash
PROFILE_TEMPLATE=my_custom
```

### 3. Switch via CLI

```bash
python scripts/profile.py switch my_custom
```

## Creating Custom Filters

### 1. Create Filter JSON

Create `config/filters/strict.json`:
```json
{
  "name": "Strict Filters",
  "description": "Stricter early-stage requirements",
  "max_market_cap": 10000000.0,  # $10M max
  "max_pair_age_hours": 12,       # 12h max
  "signal_window_minutes": 20,
  "legacy_memes": [
    "BONK", "WIF", "DOGE", "SHIB", "PEPE",
    "FLOKI", "BABYDOGE", "MOON", "SAMO",
    "KING", "MONKY",
    "COIN"  # Add more to exclude
  ]
}
```

### 2. Use Custom Filter

Edit `.env`:
```bash
FILTER_TEMPLATE=strict
```

### 3. Switch via CLI

```bash
python scripts/profile.py switch aggressive --filter strict
```

## Environment Variables (.env)

```bash
# Database
JOURNALTX_DB_PATH=data/journaltx.db

# Mode: TEST or LIVE
MODE=TEST

# Configuration Templates (EASY SETUP!)
PROFILE_TEMPLATE=aggressive  # Just change this!
FILTER_TEMPLATE=default

# QuickNode
QUICKNODE_WS_URL=wss://your-quicknode-ws-url
QUICKNODE_HTTP_URL=https://your-quicknode-http-url

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Timezone
TIMEZONE=Asia/Jakarta
```

## Benefits of JSON Configuration

1. **Easy to Adjust:** Edit JSON files instead of Python code
2. **Version Control:** Track changes to thresholds in Git
3. **Quick Switching:** Change profiles with one command
4. **No Code Changes:** Adjust parameters without touching code
5. **Shareable:** Send your profile JSON to friends
6. **Backups:** Keep multiple profile configurations

## Migration from Old .env

If you have old `.env` with individual thresholds:

### Before (Old Way)
```bash
LP_ADD_MIN_SOL=100.0
LP_ADD_MIN_USD=5000.0
LP_REMOVE_MIN_PCT=30.0
VOLUME_SPIKE_MULTIPLIER=2.0
MAX_TRADES_PER_DAY=2
SMALL_BASELINE_SOL=10.0
MIN_LP_SOL_THRESHOLD=300.0
SIGNAL_WINDOW_MINUTES=30
```

### After (New Way)
```bash
PROFILE_TEMPLATE=aggressive  # All settings in JSON!
FILTER_TEMPLATE=default
```

The old variables are **ignored** - they're loaded from JSON instead.

## Troubleshooting

### Profile Not Found
```bash
Error: Profile 'xyz' not found!
```
**Solution:** Check available profiles with `python scripts/profile.py list`

### JSON Syntax Error
```bash
Error loading profile: Expecting property name enclosed in double quotes
```
**Solution:** Validate your JSON at https://jsonlint.com

### Settings Not Applying
```bash
# Old settings still showing
```
**Solution:** Restart your listener/reload config:
```bash
python -c "from journaltx.core.config import Config; from dotenv import load_dotenv; load_dotenv(); print(Config.from_env().get_filter_summary())"
```

## Examples

### Example 1: Early Meme Hunting
```bash
# Use aggressive profile for early memes
python scripts/profile.py switch aggressive
python scripts/listen.py
```

### Example 2: Conservative Trading
```bash
# Use conservative profile for quality only
python scripts/profile.py switch conservative
python scripts/listen.py
```

### Example 3: Custom Tight Filters
```bash
# Create custom filter for tight requirements
# config/filters/tight.json: max_pair_age_hours=6

python scripts/profile.py switch balanced --filter tight
python scripts/listen.py
```

## File Locations

```
journaltx-pybot/
├── .env                    # Template selection
├── .env.example            # Template with docs
├── config/
│   ├── profiles/           # Trading profiles
│   │   ├── conservative.json
│   │   ├── balanced.json
│   │   ├── aggressive.json
│   │   └── degens_only.json
│   └── filters/            # Early-stage filters
│       └── default.json
└── scripts/
    └── profile.py          # Profile management CLI
```

## Summary

✅ **Easy Setup:** Just change `PROFILE_TEMPLATE` in `.env`
✅ **JSON Files:** All parameters in editable JSON
✅ **Quick Switch:** `python scripts/profile.py switch aggressive`
✅ **Custom Profiles:** Create your own JSON files
✅ **Version Control:** Track changes in Git
✅ **No Code Changes:** Adjust without touching Python

**Previous:** Edit `.env` with 10+ individual parameters
**Now:** Change 1 line: `PROFILE_TEMPLATE=aggressive`

🎉 Done!
