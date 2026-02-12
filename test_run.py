# test_run.py
from backtesting import Backtest
from lib.data_loader import load_data
from strategies.god_mode import GodModeSniper # <--- Import the correct strategy
import config  # <--- Import your new config

# 1. Load Data
print(f"Loading data from {config.DATA_PATH}...")
df = load_data(config.DATA_PATH, timeframe=config.TIMEFRAME)

# 2. Init Backtest (Using Config values)
bt = Backtest(
    df, 
    GodModeSniper, 
    cash=config.INITIAL_CASH, 
    commission=config.COMMISSION, 
    margin=config.LEVERAGE
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