import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Literal, Optional

# ==========================================
# MODULE 1: SWING POINTS & MARKET STRUCTURE
# ==========================================

def get_swing_points(high: pd.Series, low: pd.Series, left: int = 5, right: int = 5):
    """
    Identifies Swing Highs and Swing Lows (Pivots) WITHOUT Lookahead Bias.
    """
    window = left + right + 1
    rolling_max = high.rolling(window=window).max()
    rolling_min = low.rolling(window=window).min()
    
    candidate_high = high.shift(right)
    candidate_low = low.shift(right)
    
    is_swing_high = (candidate_high == rolling_max)
    is_swing_low = (candidate_low == rolling_min)
    
    swing_highs = candidate_high.where(is_swing_high, np.nan)
    swing_lows = candidate_low.where(is_swing_low, np.nan)
    
    return swing_highs, swing_lows

def detect_mss(close: pd.Series, swing_highs: pd.Series, swing_lows: pd.Series):
    """
    Detects Market Structure Shifts.
    """
    last_swing_high = swing_highs.ffill()
    last_swing_low = swing_lows.ffill()
    mss = pd.Series(0, index=close.index)
    
    bullish_break = (close > last_swing_high.shift(1)) & (close.shift(1) <= last_swing_high.shift(1))
    bearish_break = (close < last_swing_low.shift(1)) & (close.shift(1) >= last_swing_low.shift(1))
    
    mss[bullish_break] = 1
    mss[bearish_break] = -1
    return mss

# ==========================================
# MODULE 2: FAIR VALUE GAPS (FVG) MANAGER
# ==========================================

@dataclass
class FVG:
    top: float
    bottom: float
    is_bullish: bool
    created_at: int
    created_time: pd.Timestamp
    inverted: bool = False
    traded: bool = False  # <--- CRITICAL: Prevents duplicate trades
    
    @property
    def mid(self):
        return (self.top + self.bottom) / 2

class FVGManager:
    """
    Universal FVG Tracker.
    Handles Detection, Expiration, and Inversion automatically.
    """
    def __init__(self, expiration: int = 120):
        self.expiration = expiration
        self.active_fvgs: List[FVG] = []
        self.inverted_fvgs: List[FVG] = []

    def update(self, data_high, data_low, data_close, current_idx, current_time):
        # 1. CLEANUP (Expire old zones)
        self.active_fvgs = [f for f in self.active_fvgs if (current_idx - f.created_at) <= self.expiration]
        
        # Filter Inverted Fvgs: Expire OLD ones AND Invalid ones
        valid_inversions = []
        price_close = data_close.iloc[-1]

        for f in self.inverted_fvgs:
            # A. Expiration Check
            if (current_idx - f.created_at) > self.expiration:
                continue
            
            # B. Invalidation Check (Kill Zone)
            # If Bearish IFVG (Resistance) is broken to the UPSIDE, delete it.
            if f.inverted and f.is_bullish and price_close > f.top:
                continue # Killed
            
            # If Bullish IFVG (Support) is broken to the DOWNSIDE, delete it.
            if f.inverted and not f.is_bullish and price_close < f.bottom:
                continue # Killed

            valid_inversions.append(f)
            
        self.inverted_fvgs = valid_inversions

        # 2. DETECT NEW FVG (Looking at candles -1, -2, -3)
        # Check Bullish FVG
        if data_low.iloc[-1] > data_high.iloc[-3]:
            gap = data_low.iloc[-1] - data_high.iloc[-3]
            if gap > 0:
                self.active_fvgs.append(FVG(
                    top=data_low.iloc[-1], bottom=data_high.iloc[-3], is_bullish=True, 
                    created_at=current_idx, created_time=current_time
                ))

        # Check Bearish FVG
        if data_high.iloc[-1] < data_low.iloc[-3]:
            gap = data_low.iloc[-3] - data_high.iloc[-1]
            if gap > 0:
                self.active_fvgs.append(FVG(
                    top=data_low.iloc[-3], bottom=data_high.iloc[-1], is_bullish=False, 
                    created_at=current_idx, created_time=current_time
                ))

        # 3. CHECK FOR INVERSIONS
        still_active = []
        
        for f in self.active_fvgs:
            inverted = False
            
            if f.is_bullish:
                # Bullish Support Broken -> Becomes Bearish Resistance
                if price_close < f.bottom:
                    f.inverted = True
                    self.inverted_fvgs.append(f)
                    inverted = True
            else:
                # Bearish Resistance Broken -> Becomes Bullish Support
                if price_close > f.top:
                    f.inverted = True
                    self.inverted_fvgs.append(f)
                    inverted = True
            
            if not inverted:
                still_active.append(f)
                
        self.active_fvgs = still_active

# ==========================================
# MODULE 3: PO3 / SESSION LOGIC
# ==========================================

def get_po3_phase(timestamp: pd.Timestamp, 
                  asia_start=19, asia_end=0,      # Accumulation (EST PM)
                  london_start=2, london_end=5,   # Manipulation (EST AM)
                  ny_start=7, ny_end=11):         # Distribution (EST AM)
    
    h = timestamp.hour
    is_asia = False
    if asia_start > asia_end:
        if h >= asia_start or h < asia_end: is_asia = True
    else:
        if asia_start <= h < asia_end: is_asia = True
        
    if is_asia: return "Accumulation"
    if london_start <= h < london_end: return "Manipulation"
    if ny_start <= h < ny_end: return "Distribution"
    return None