# lib/data_loader.py
import pandas as pd
import os

def load_data(file_path: str, timeframe: str = None) -> pd.DataFrame:
    """
    Loads MNQ data from CSV. 
    1. Checks if a fast .parquet version exists.
    2. If not, loads CSV, cleans it, and saves .parquet for next time.
    3. Resamples to the requested timeframe.
    """
    
    # Define parquet filename based on the original CSV
    file_name = os.path.splitext(os.path.basename(file_path))[0]
    parquet_path = os.path.join(os.path.dirname(file_path), f"{file_name}.parquet")

    # 1. Try Loading Parquet (Fast Lane)
    if os.path.exists(parquet_path):
        print(f"⚡ Loading cached data from {parquet_path}...")
        df = pd.read_parquet(parquet_path)
    
    # 2. Else Load CSV (Slow Lane)
    else:
        print(f"🐢 Parsing CSV from {file_path} (One-time setup)...")
        # Using your specific column names
        df = pd.read_csv(file_path, header=None, names=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        
        # Standardize Timezone (Safe approach)
        try:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        except TypeError:
            # Already tz-aware
            df.index = df.index.tz_convert('America/New_York')
            
        # Ensure numeric types
        cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        df[cols] = df[cols].apply(pd.to_numeric, errors='coerce')
        
        # Save for next time
        print(f"💾 Saving to Parquet for future speed...")
        df.to_parquet(parquet_path)

    # 3. Resample if needed
    if timeframe:
        print(f"⏱️ Resampling to {timeframe}...")
        agg_dict = {
            'Open': 'first', 
            'High': 'max', 
            'Low': 'min', 
            'Close': 'last', 
            'Volume': 'sum'
        }
        df = df.resample(timeframe).agg(agg_dict).dropna()

    return df