import pandas as pd
import os

# --- CONFIG ---
RAW_FILE = "data/glbx-mdp3-20190414-20260205.ohlcv-1m.csv.zst"  # Make sure this path is correct
OUTPUT_FILE = "data/mnq_clean.parquet"

def fix_data():
    print(f"🚀 Reading RAW data from {RAW_FILE}...")
    print("   (This might take a minute due to decompression...)")
    
    try:
        # DataBento CSVs usually have specific headers. 
        # We try to infer, but if it fails, we might need to specify names.
        df = pd.read_csv(RAW_FILE, compression='zstd', index_col='ts_event')
        
        # DataBento uses 'ts_event' as the timestamp usually.
        # It might also just be the first column. Let's inspect index.
        df.index = pd.to_datetime(df.index)
        
        # Sort just in case
        df = df.sort_index()
        
        print("\n--- RAW DATA INSPECTION ---")
        print(f"Start: {df.index[0]} | Price: {df['close'].iloc[0]}")
        print(f"End:   {df.index[-1]} | Price: {df['close'].iloc[-1]}")
        
        # SANITY CHECK
        last_price = df['close'].iloc[-1]
        if last_price > 15000:
            print("✅ SANITY CHECK PASSED: Price is > 15,000 (Real MNQ levels).")
        else:
            print(f"⚠️ WARNING: Last price is {last_price}. This is suspiciously low for 2026.")
            
        # RENAME COLUMNS to Standard Format (Capitalized)
        # DataBento is usually lowercase: open, high, low, close, volume
        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 
            'close': 'Close', 'volume': 'Volume'
        }, inplace=True)
        
        # Keep only what we need
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        # SAVE
        print(f"\n💾 Saving Clean Parquet to {OUTPUT_FILE}...")
        df.to_parquet(OUTPUT_FILE)
        print("🎉 DONE! You can now run 'test_run.py' again.")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        print("Tip: Ensure the raw file is in the folder and 'zstandard' is installed.")

if __name__ == "__main__":
    fix_data()