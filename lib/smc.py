# lib/smc.py
import pandas as pd
import numpy as np

def get_swing_points(high: pd.Series, low: pd.Series, left: int = 5, right: int = 5):
    """
    Identifies Swing Highs and Swing Lows (Pivots) WITHOUT Lookahead Bias.
    A swing is confirmed only after 'right' bars have passed.
    """
    # Window needed to verify a swing: left + 1 + right
    # At index T, we check if the bar at (T - right) was the extreme.
    window = left + right + 1
    
    # 1. Rolling Min/Max (Looking backward from T)
    # At index T, this gives max of range [T - window + 1, T]
    rolling_max = high.rolling(window=window).max()
    rolling_min = low.rolling(window=window).min()
    
    # 2. Check if the 'Candidate' (T - right) matches the rolling extreme
    # We align the candidate price to Time T using shift(right)
    candidate_high = high.shift(right)
    candidate_low = low.shift(right)
    
    # Check if the candidate was indeed the max/min of the window
    is_swing_high = (candidate_high == rolling_max)
    is_swing_low = (candidate_low == rolling_min)
    
    # 3. Output Series
    # We place the swing value at Time T (Confirmation Time).
    # This ensures the strategy only sees it when it's actually confirmed.
    swing_highs = candidate_high.where(is_swing_high, np.nan)
    swing_lows = candidate_low.where(is_swing_low, np.nan)
    
    return swing_highs, swing_lows

def detect_mss(close: pd.Series, swing_highs: pd.Series, swing_lows: pd.Series):
    """
    Detects Market Structure Shifts (Break of Structure).
    Returns +1 for Bullish MSS, -1 for Bearish MSS, 0 otherwise.
    """
    # Propagate the most recent *CONFIRMED* swing levels forward
    last_swing_high = swing_highs.ffill()
    last_swing_low = swing_lows.ffill()
    
    mss = pd.Series(0, index=close.index)
    
    # Bullish MSS: Close breaks ABOVE the last Confirmed Swing High
    bullish_break = (close > last_swing_high.shift(1)) & (close.shift(1) <= last_swing_high.shift(1))
    
    # Bearish MSS: Close breaks BELOW the last Confirmed Swing Low
    bearish_break = (close < last_swing_low.shift(1)) & (close.shift(1) >= last_swing_low.shift(1))
    
    mss[bullish_break] = 1
    mss[bearish_break] = -1
    
    return mss