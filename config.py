# config.py

# --- ACCOUNT SETTINGS ---
INITIAL_CASH = 100_000       # Realistically, what you'd trade with
LEVERAGE = 1.0 / 20.0       # 1:20 Leverage (Margin = 0.05)

# --- REALITY CHECK ---
# TradingView uses a "Flat Fee". Backtesting.py uses %.
# $1.25 fee on a ~$30k contract value is roughly 0.00004
COMMISSION = 0.00004         # NQ/MNQ fees are usually around $0.60 per side per contract (adjust as needed)
SLIPPAGE = 0.00010    # Added friction (approx. 1 tick on NQ/MNQ)
TOTAL_FRICTION = COMMISSION + SLIPPAGE

# --- DATA SETTINGS ---
DATA_PATH = "data/mnq_clean.parquet" # Ensure we load the parquet now
TIMEFRAME = "1min"

# --- BACKTEST DEFAULTS ---
# If you want to default to 50% equity per trade to avoid ruin
DEFAULT_TRADE_SIZE = 1

# --- POSITION SIZING ---
# CRITICAL: We want to trade 1 Contract, not "95% of Account".
# In Backtesting.py, if size is > 1, it treats it as UNITS (Contracts).
FIXED_SIZE = 10
