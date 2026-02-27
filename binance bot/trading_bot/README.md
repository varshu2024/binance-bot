# 🤖 Binance Futures Testnet Trading Bot

A clean, production-ready Python CLI application for placing orders on the **Binance USDT-M Futures Testnet**.

---

## Features

| Feature | Included |
|---|---|
| Market orders (BUY / SELL) | YES |
| Limit orders (BUY / SELL) | YES |
| Stop-Market orders (bonus) | YES |
| Stop-Limit orders (bonus) | YES |
| Take-Profit / Take-Profit Market (bonus) | YES |
| **TWAP algorithmic order (bonus)** | YES |
| Interactive guided CLI (bonus) | YES |
| Account balance summary | YES |
| Dry-run mode (validate only) | YES |
| Structured rotating logs (file + console) | YES |
| Full input validation with clear errors | YES |

---

## Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py
│   ├── client.py          # Binance Futures Testnet REST client (HMAC signing)
│   ├── orders.py          # Order placement logic + pretty-print output
│   ├── validators.py      # Input validation helpers
│   └── logging_config.py  # Rotating file + console logging setup
├── logs/                  # Auto-created; contains trading_bot.log
├── cli.py                 # CLI entry point (argparse)
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Binance Futures Testnet Account

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com) and log in (GitHub OAuth).
2. Go to **API Management** → **Create API**.
3. Copy your **API Key** and **Secret Key**.

### 2. Clone / Download

```bash
# Clone the repo (or unzip the folder)
cd trading_bot
```

### 3. Create a Virtual Environment (recommended)

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows Command Prompt
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure API Credentials

Create a `.env` file in the `trading_bot/` directory (next to `cli.py`):

```env
BINANCE_TESTNET_API_KEY=your_api_key_here
BINANCE_TESTNET_API_SECRET=your_api_secret_here
```

> **Never commit your `.env` file to version control.**

Alternatively, set the environment variables directly:

```powershell
# Windows PowerShell
$env:BINANCE_TESTNET_API_KEY = "your_api_key"
$env:BINANCE_TESTNET_API_SECRET = "your_api_secret"
```

```bash
# macOS / Linux
export BINANCE_TESTNET_API_KEY="your_api_key"
export BINANCE_TESTNET_API_SECRET="your_api_secret"
```

---

## How to Run

All commands are run from inside the `trading_bot/` directory.

### Place a Market Order

```bash
# BUY 0.001 BTC at market price
python cli.py place-order --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001

# SELL 0.002 ETH at market price
python cli.py place-order --symbol ETHUSDT --side SELL --type MARKET --quantity 0.002
```

### Place a Limit Order

```bash
# BUY 0.001 BTC at $90,000 (GTC)
python cli.py place-order --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 90000

# SELL 0.001 BTC at $100,000 with IOC time-in-force
python cli.py place-order --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 100000 --time-in-force IOC
```

### Place a Stop-Market Order (Bonus)

```bash
# BUY 0.001 BTC if price rises above $97,000
python cli.py place-order --symbol BTCUSDT --side BUY --type STOP_MARKET --quantity 0.001 --stop-price 97000
```

### Place a Stop-Limit Order (Bonus)

```bash
# SELL 0.001 BTC when price drops to $88,000. Limit at $87,500
python cli.py place-order --symbol BTCUSDT --side SELL --type STOP --quantity 0.001 --price 87500 --stop-price 88000
```

### TWAP Order - Time Weighted Average Price (Bonus)

Splits a large order into equal-sized MARKET slices executed at fixed intervals,
reducing market impact and achieving a price closer to the time-weighted average.

```bash
# BUY 0.01 BTC in 5 equal slices every 30 seconds
python cli.py twap --symbol BTCUSDT --side BUY --quantity 0.01 --slices 5 --interval 30

# SELL 0.1 ETH in 10 slices every 60 seconds
python cli.py twap --symbol ETHUSDT --side SELL --quantity 0.1 --slices 10 --interval 60

# Preview the TWAP plan without placing orders
python cli.py twap --symbol BTCUSDT --side BUY --quantity 0.01 --slices 5 --interval 30 --dry-run
```

TWAP output example:
```
========================================================
  TWAP ORDER PLAN
========================================================
  Symbol          : BTCUSDT
  Side            : BUY
  Total Quantity  : 0.01
  Slices          : 5
  Qty per Slice   : 0.002
  Interval        : 30s
  Total Duration  : ~120s (2.0 min)
========================================================

  Executing 5 slices every 30s. Press Ctrl+C to abort.

  [1/5] Placing MARKET BUY 0.002 BTCUSDT ... OK  orderId=3801813500 avgPrice=95410.2000 execQty=0.002
  [2/5] Placing MARKET BUY 0.002 BTCUSDT ... OK  orderId=3801813501 avgPrice=95422.1000 execQty=0.002
  ...

  Slices Filled    : 5
  Avg Fill Price   : 95404.5800
  Total Cost       : 954.045800 USDT

[SUCCESS] TWAP order fully executed!
```

### Dry Run (validate only, no order sent)

```bash
python cli.py place-order --symbol BTCUSDT --side BUY --type LIMIT --quantity 0.001 --price 90000 --dry-run
```

### Interactive (Guided) Mode

```bash
python cli.py interactive
```

Prompts you through all fields step-by-step with validation at each stage.

### Account Balance Summary

```bash
python cli.py account
```

---

## Output Example

```
==================================================
  ORDER REQUEST SUMMARY
==================================================
  Symbol     : BTCUSDT
  Side       : BUY
  Type       : MARKET
  Quantity   : 0.001
==================================================

==================================================
  ORDER RESPONSE
==================================================
  Order ID     : 3801813348
  Client OID   : web_abc123
  Symbol       : BTCUSDT
  Status       : FILLED
  Side         : BUY
  Type         : MARKET
  Orig Qty     : 0.001
  Executed Qty : 0.001
  Avg Price    : 95432.10
  ...
==================================================

[SUCCESS] Order placed successfully!
```

---

## Logging

Logs are written to:

```
trading_bot/logs/trading_bot.log
```

- **Console** → INFO level and above (human readable)
- **Log file** → DEBUG level and above (full request/response detail)
- Log files rotate automatically at 5 MB (last 5 files kept)

Sample log entries:

```
2025-01-15 10:23:44 | INFO     | bot.orders | Placing order → symbol=BTCUSDT side=BUY type=MARKET qty=0.001 price=None stopPrice=None
2025-01-15 10:23:45 | INFO     | bot.client | Order placed successfully: orderId=3801813348 status=FILLED
```

---

## All CLI Options

```
python cli.py place-order --help

options:
  --symbol     / -s   Trading pair (e.g. BTCUSDT)          [required]
  --side              BUY or SELL                            [required]
  --type       / -t   MARKET / LIMIT / STOP_MARKET / STOP
                       TAKE_PROFIT / TAKE_PROFIT_MARKET      [required]
  --quantity   / -q   Order quantity in base asset           [required]
  --price      / -p   Limit price (required for LIMIT/STOP)
  --stop-price        Trigger price (required for STOP*)
  --time-in-force     GTC / IOC / FOK (default: GTC)
  --reduce-only       Make order reduce-only
  --dry-run           Validate inputs only, do not send order

python cli.py twap --help  (BONUS)

options:
  --symbol     / -s   Trading pair (e.g. BTCUSDT)     [required]
  --side              BUY or SELL                       [required]
  --quantity   / -q   Total quantity across all slices [required]
  --slices            Number of child orders (2-100)   [required]
  --interval          Seconds between slices (1-3600)  [required]
  --dry-run           Show TWAP plan, do not execute
```

---

## Assumptions

1. **Testnet only** – base URL is hardcoded to `https://testnet.binancefuture.com`. Change `BASE_URL` in `bot/client.py` to switch to mainnet.
2. **Quantity precision** – the bot sends `quantity` as provided. If Binance rejects the order due to precision rules, reduce decimal places.
3. **Leverage** – uses whatever leverage is currently set on your testnet account. Adjust via the Testnet UI or add a `client.change_leverage()` method.
4. **No position management** – this bot only *places* orders; it does not track open positions.
5. **REST only** – no WebSocket streaming.

---

## Requirements

```
requests>=2.31.0
python-dotenv>=1.0.0
```

Python 3.8+ required.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Missing API keys | Prints config error + exits 1 |
| Invalid symbol / side / type | Prints validation error + exits 1 |
| Price missing for LIMIT order | Prints validation error + exits 1 |
| TWAP slices out of range (1 or >100) | Prints validation error + exits 1 |
| TWAP interval out of range | Prints validation error + exits 1 |
| TWAP slice fails mid-execution | Logs error, continues remaining slices |
| Ctrl+C during TWAP | Prints partial fill summary + exits cleanly |
| Binance API error (e.g. -2019) | Prints Binance error code + message + exits 1 |
| Network / timeout failure | Logs and prints error + exits 1 |
| Ctrl+C | Prints "Aborted by user." + exits 0 |
