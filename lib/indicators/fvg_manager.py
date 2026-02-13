import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class FVG:
    index: int              # Candle index where FVG formed
    top: float              # Upper price limit of the gap
    bottom: float           # Lower price limit of the gap
    is_bullish: bool        # True = Bullish (Support), False = Bearish (Resistance)
    status: str = "ACTIVE"  # ACTIVE, MITIGATED, INVERTED
    creation_time: any = None

class FVGManager:
    def __init__(self, min_gap_points: float = 0.25):
        """
        :param min_gap_points: Minimum size of the gap to remove noise (e.g., 1 tick on ES is 0.25)
        """
        self.fvgs: List[FVG] = []
        self.min_gap_points = min_gap_points

    def scan_for_new_fvg(self, df: pd.DataFrame, i: int) -> Optional[FVG]:
        """
        Checks if a NEW FVG formed at the completed candle index 'i'.
        Logic: Gap between candle i-2 and candle i.
        """
        if i < 2: return None
        
        # Candles (0=current, 1=previous, 2=2 bars ago)
        # We look at completed sequence: i-2, i-1, i
        c_current = df.iloc[i]
        c_prev2 = df.iloc[i-2]

        new_fvg = None

        # 1. Bullish FVG (Gap between High[i-2] and Low[i])
        # Condition: Low of current > High of 2 bars ago
        if c_current['Low'] > c_prev2['High']:
            gap_size = c_current['Low'] - c_prev2['High']
            if gap_size >= self.min_gap_points:
                new_fvg = FVG(
                    index=i,
                    top=c_current['Low'],       # Top of a Bullish FVG is the current Low
                    bottom=c_prev2['High'],     # Bottom is the old High
                    is_bullish=True,
                    creation_time=c_current.name # Assuming index is datetime
                )

        # 2. Bearish FVG (Gap between Low[i-2] and High[i])
        # Condition: High of current < Low of 2 bars ago
        elif c_current['High'] < c_prev2['Low']:
            gap_size = c_prev2['Low'] - c_current['High']
            if gap_size >= self.min_gap_points:
                new_fvg = FVG(
                    index=i,
                    top=c_prev2['Low'],         # Top is the old Low
                    bottom=c_current['High'],   # Bottom is current High
                    is_bullish=False,
                    creation_time=c_current.name
                )

        if new_fvg:
            self.fvgs.append(new_fvg)
            return new_fvg
        return None

    def update_fvg_states(self, current_candle: pd.Series):
        """
        Updates the status of all existing FVGs based on current price action.
        Handles the "INVERSION" logic.
        """
        close_price = current_candle['Close']

        for fvg in self.fvgs:
            if fvg.status == "MITIGATED":
                continue # Ignore dead gaps

            # --- INVERSION LOGIC ---
            
            # Case A: Bullish FVG (Support) -> Inverted (becomes Resistance)
            # Occurs if price CLOSES below the bottom of the gap
            if fvg.is_bullish and fvg.status == "ACTIVE":
                if close_price < fvg.bottom:
                    fvg.status = "INVERTED"
            
            # Case B: Bearish FVG (Resistance) -> Inverted (becomes Support)
            # Occurs if price CLOSES above the top of the gap
            elif not fvg.is_bullish and fvg.status == "ACTIVE":
                if close_price > fvg.top:
                    fvg.status = "INVERTED"

    def check_for_signal(self, current_candle: pd.Series) -> str:
        """
        Checks if we are retesting an INVERTED FVG (Edwin's Strategy).
        Returns: 'BUY', 'SELL', or None
        """
        high = current_candle['High']
        low = current_candle['Low']
        close = current_candle['Close']

        for fvg in self.fvgs:
            # We only care about INVERTED gaps for this specific strategy
            if fvg.status != "INVERTED":
                continue

            # 1. Bullish FVG turned INVERTED (Now Resistance)
            # We want to SELL the retest of this zone
            if fvg.is_bullish: # Was bullish, now broken -> Resistance
                # Logic: Price wicked up into the gap (High > Bottom), but Closed below it (Respecting resistance)
                if high > fvg.bottom and close < fvg.bottom:
                    return "SELL"

            # 2. Bearish FVG turned INVERTED (Now Support)
            # We want to BUY the retest of this zone
            if not fvg.is_bullish: # Was bearish, now broken -> Support
                # Logic: Price wicked down into the gap (Low < Top), but Closed above it (Respecting support)
                if low < fvg.top and close > fvg.top:
                    return "BUY"

        return None