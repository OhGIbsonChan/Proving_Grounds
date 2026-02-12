# test_run.py
from backtesting import Backtest
from lib.data_loader import load_data
# from strategies.eight_am import EightAMStrategy # <--- New Strategy
from strategies.ten_am import TenAMStrategy  # <--- NEW IMPORT
import config

# 1. Load Data
# Note: Ensure config.TIMEFRAME is set to '1min'
print(f"Loading data from {config.DATA_PATH}...")
df = load_data(config.DATA_PATH, timeframe=config.TIMEFRAME)

# 2. Init Backtest
bt = Backtest(
    df, 
    TenAMStrategy, 
    cash=config.INITIAL_CASH, 
    commission=config.TOTAL_FRICTION, 
    margin=config.LEVERAGE
    trade_on_close=False # Forces entry on the NEXT candle's open
)

# 3. Run
print("Running Backtest...")
stats = bt.run()
print(stats)

# 4. Save the Chart (The Fix!)
# instead of just bt.plot(), we give it a filename.
# This saves 'report.html' in your folder and opens it.
print("Generatng Chart...")
bt.plot(filename='report.html', open_browser=True)