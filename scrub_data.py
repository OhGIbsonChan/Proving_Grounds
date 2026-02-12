import pandas as pd
import config

OUTPUT_FILE = "data/mnq_clean.parquet"

def scrub_data():
    print(f"🧽 Loading {OUTPUT_FILE} for deep cleaning...")
    df = pd.read_parquet(OUTPUT_FILE)
    original_count = len(df)
    
    # --- 1. REMOVE ZERO/NEAR-ZERO PRICES ---
    # MNQ has never been below 1,000 since 2019. 
    # Anything below 1,000 is a data error (likely 0 or 1e-9).
    print("   Scanning for zero/low price spikes...")
    df = df[df['Low'] > 1000] # MNQ hasn't been < 1000 in decades. Safe.
    
    # --- 2. REMOVE IMPOSSIBLE VOLATILITY (DISABLED) ---
    # We commented this out to allow flash crashes/high vol events
    # df['Range'] = df['High'] - df['Low']
    # df = df[df['Range'] < 500] 
    
    # Drop the temporary column <--- COMMENT THIS OUT TOO
    # df.drop(columns=['Range'], inplace=True)
    
    removed_count = original_count - len(df)
    print(f"✨ Cleaning Complete!")
    print(f"🗑️ Removed {removed_count} corrupted bars.")
    print(f"💾 Saving scrubbed data...")
    df.to_parquet(OUTPUT_FILE)

if __name__ == "__main__":
    scrub_data()