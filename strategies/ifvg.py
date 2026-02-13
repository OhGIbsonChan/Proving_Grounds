import pandas as pd
import numpy as np
from backtesting import Strategy
from pydantic import BaseModel
from .base import BaseStrategy
from lib.smc import FVGManager, get_po3_phase
import config

class IFVGStrategy(BaseStrategy):
    """
    Inversion FVG Strategy (Modular Version).
    1. Uses FVGManager to track zones.
    2. Uses PO3 Filter (Optional).
    3. Entries on 'Wick' retest of Inverted Zones.
    """
    
    # --- CLASS VARS FOR BACKTESTING ---
    risk_reward = 2.0
    stop_loss_padding = 2.0
    fvg_expiration = 120
    use_po3_filter = True  # New switch
    
    class Config(BaseModel):
        risk_reward: float = 2.0
        stop_loss_padding: float = 2.0 
        fvg_expiration: int = 120
        use_po3_filter: bool = True

    def init(self):
        # 1. Initialize the Brain
        self.fvg_engine = FVGManager(expiration=self.cfg.fvg_expiration)
        self.trade_size = config.FIXED_SIZE
        # 2. Add ATR for smart Stop Losses (14 period)
        self.atr = self.I(lambda: self.data.df.ta.atr(length=14), name="ATR")

    def next(self):
        # --- FIX: WAIT FOR ENOUGH DATA ---
        # We need at least 3 bars to define an FVG (Candle 1, 2, 3)
        # If we are on bar 0, 1, or 2, we skip.
        if len(self.data) < 3:
            return
        # 1. DATA SLICING (Required because lib/smc.py uses .iloc)
        # We pass the data up to the current candle
        idx = len(self.data)
        # Note: self.data.df gives us the full dataframe, we slice up to 'now'
        # This is safe because 'idx' corresponds to the current simulation step
        high_s = self.data.df['High'].iloc[:idx]
        low_s = self.data.df['Low'].iloc[:idx]
        close_s = self.data.df['Close'].iloc[:idx]
        
        current_time = self.data.index[-1]
        
        # 2. UPDATE THE ENGINE
        self.fvg_engine.update(high_s, low_s, close_s, idx-1, current_time)
        
        # 3. PO3 FILTER (Optional)
        # "Distribution" is usually the best phase for IFVG reversals/continuations
        if self.cfg.use_po3_filter:
            phase = get_po3_phase(current_time)
            # If we are NOT in Distribution (NY Session), skip.
            # You can adjust this to include "Manipulation" (London) if you want.
            if phase != "Distribution":
                return

        # 4. ENTRY LOGIC
        if self.position: return
        
        # Iterate through INVERTED zones only
        for ifvg in self.fvg_engine.inverted_fvgs:
            
            # A. SHORT SETUP (Bearish IFVG)
            # Logic: It was Bullish (Support) -> Broke -> Now Resistance
            if ifvg.is_bullish and ifvg.inverted:
                # 1. Did we poke up into it?
                poked = self.data.High[-1] > ifvg.bottom
                # 2. Did we reject it? (Close < Top)
                rejected = self.data.Close[-1] < ifvg.top
                # 3. Edwin's "Wick" rule: Close should be in the lower half or below
                valid_close = self.data.Close[-1] < ifvg.mid
                
                if poked and rejected and valid_close:
                    self.entry_short(ifvg)
                    return

            # B. LONG SETUP (Bullish IFVG)
            # Logic: It was Bearish (Resistance) -> Broke -> Now Support
            if not ifvg.is_bullish and ifvg.inverted:
                # 1. Did we poke down into it?
                poked = self.data.Low[-1] < ifvg.top
                # 2. Did we reject it? (Close > Bottom)
                rejected = self.data.Close[-1] > ifvg.bottom
                # 3. Wick rule: Close should be in the upper half or above
                valid_close = self.data.Close[-1] > ifvg.mid
                
                if poked and rejected and valid_close:
                    self.entry_long(ifvg)
                    return

    def entry_short(self, zone):
        # FIX: Use ATR for padding instead of fixed 2.0
        # If ATR is 20 points, we give it 20 points of room, not 2.
        current_atr = self.atr[-1]
        
        # Stop Loss = Top of Zone + 1x ATR (Safe)
        sl = zone.top + current_atr
        
        risk = sl - self.data.Close[-1]
        
        # FILTER: If the zone is too tight, don't take it (Commission saver)
        if risk < (current_atr * 0.5): 
            return
        
        tp = self.data.Close[-1] - (risk * self.cfg.risk_reward)
        self.sell(sl=sl, tp=tp, size=self.trade_size)

    def entry_long(self, zone):
        # FIX: Use ATR for padding
        current_atr = self.atr[-1]
        
        # Stop Loss = Bottom of Zone - 1x ATR
        sl = zone.bottom - current_atr
        
        risk = self.data.Close[-1] - sl
        
        # FILTER: Minimum risk required
        if risk < (current_atr * 0.5):
            return

        tp = self.data.Close[-1] + (risk * self.cfg.risk_reward)
        self.buy(sl=sl, tp=tp, size=self.trade_size)