from backtesting import Backtest
from lib.data_loader import load_data
from strategies.god_mode import GodModeSniper
import config
import pandas as pd

# 1. Run the Backtest
print("Running Backtest to generate trade list...")
df = load_data(config.DATA_PATH, timeframe=config.TIMEFRAME)
bt = Backtest(
    df, 
    GodModeSniper, 
    cash=config.INITIAL_CASH, 
    commission=config.COMMISSION, 
    margin=config.LEVERAGE
)
stats = bt.run()

# 2. Extract the Trade List
trades = stats['_trades']

# 3. Filter for the "Bankrupting" Trades
print("\n--- CRIME SCENE INVESTIGATION ---")
print(f"Total Trades: {len(trades)}")

# Sort by worst PnL
worst_trades = trades.sort_values(by='PnL', ascending=True).head(10)

print("\nTOP 5 WORST LOSERS:")
print(f"{'Entry Time':<20} | {'Size':<6} | {'Entry':<10} | {'Exit':<10} | {'PnL ($)':<12} | {'Return %':<10}")
print("-" * 80)

for index, t in worst_trades.iterrows():
    # Backtesting.py stores times as integers (bar index) sometimes, need to convert if needed
    # But usually .EntryTime is a timestamp
    entry_price = t.EntryPrice
    exit_price = t.ExitPrice
    pnl = t.PnL
    size = t.Size
    ret = t.ReturnPct * 100
    
    print(f"{str(t.EntryTime):<20} | {size:<6} | {entry_price:<10.2f} | {exit_price:<10.2f} | {pnl:<12.2f} | {ret:<10.2f}%")

print("\n------------------------------------------------")
print("ANALYSIS HINT:")
print("If 'Size' is 1, but 'PnL' is > $100, then your 'Stop Loss' didn't work.")
print("If 'Size' is > 1, then your config is being ignored.")