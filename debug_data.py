from lib.data_loader import load_data
import config

# Load the data
print(f"Inspecting {config.DATA_PATH}...")
df = load_data(config.DATA_PATH)

# 1. Check Date Order
print(f"\n--- TIMESTAMPS ---")
print(f"Start Date: {df.index[0]}")
print(f"End Date:   {df.index[-1]}")
if df.index[0] > df.index[-1]:
    print("❌ ALARM: Data is sorted backwards (Newest -> Oldest)!")
else:
    print("✅ Order looks correct (Oldest -> Newest)")

# 2. Check Price Reality
print(f"\n--- PRICES ---")
print(f"First Close: {df['Close'].iloc[0]}")
print(f"Last Close:  {df['Close'].iloc[-1]}")
print(f"Min Close:   {df['Close'].min()}")
print(f"Max Close:   {df['Close'].max()}")

if df['Close'].iloc[-1] < df['Close'].iloc[0]:
    print("❌ ALARM: Data shows MNQ crashed, but real MNQ went up. Data is inverted or corrupted.")

if df['Close'].min() < 0:
    print("❌ CRITICAL: You have negative prices! Back-adjustment logic is broken.")