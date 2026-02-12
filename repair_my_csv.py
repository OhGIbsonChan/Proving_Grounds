import pandas as pd
import numpy as np
import os

# --- CONFIG ---
INPUT_CSV = "data/mnq_clean.csv"
OUTPUT_PARQUET = "data/mnq_clean.parquet" # We overwrite the bad parquet
TIMEFRAME = "5min"

def repair_data():
    print(f"🔧 Repairing {INPUT_CSV}...")
    
    # 1. Load the User's Original CSV
    # We assume standard columns. If your CSV has no headers, use 'header=None'
    try:
        df = pd.read_csv(INPUT_CSV)
        
        # Auto-detect Date column
        date_col = [c for c in df.columns if 'date' in c.lower() or 'time' in c.lower()][0]
        df[date_col] = pd.to_datetime(df[date_col])
        df.set_index(date_col, inplace=True)
        
    except Exception as e:
        # Fallback for headerless CSV (common in data exports)
        print("   (Header detection failed, trying default columns...)")
        df = pd.read_csv(INPUT_CSV, header=None, names=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)

    # 2. FIX: Sort Order
    df = df.sort_index()
    print(f"   Sorted: {df.index[0]} to {df.index[-1]}")

    # 3. FIX: Gap Filling (The "TradingView" Effect)
    # We create a perfect 5-minute grid from start to end
    print("   Filling gaps (Making 17:00 guaranteed)...")
    full_idx = pd.date_range(start=df.index[0], end=df.index[-1], freq=TIMEFRAME)
    
    # Reindex forces missing bars to exist (as NaNs)
    df = df.reindex(full_idx)
    
    # Forward Fill: Copy previous close to current open/high/low/close
    # This simulates a "flat" market instead of a broken one
    df['Close'] = df['Close'].ffill()
    df['Open'] = df['Open'].fillna(df['Close'])
    df['High'] = df['High'].fillna(df['Close'])
    df['Low'] = df['Low'].fillna(df['Close'])
    df['Volume'] = df['Volume'].fillna(0) # No volume on filled bars

    # 4. FIX: Negative Prices (The "Crash" Preventer)
    min_price = df['Low'].min()
    if min_price <= 0:
        shift_val = abs(min_price) + 2000
        print(f"   ⚠️ Found negative prices (Min: {min_price}). Shifting all data up by +{shift_val}...")
        df['Open'] += shift_val
        df['High'] += shift_val
        df['Low'] += shift_val
        df['Close'] += shift_val
    
    # 5. Save
    print(f"💾 Saving repaired data to {OUTPUT_PARQUET}")
    df.to_parquet(OUTPUT_PARQUET)
    print("✅ Ready for Backtest.")

if __name__ == "__main__":
    repair_data()