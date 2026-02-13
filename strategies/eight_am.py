import pandas as pd
import numpy as np
from backtesting import Strategy
from pydantic import BaseModel
from .base import BaseStrategy
from lib.smc import get_swing_points
import config  # <--- NEW IMPORT

class EightAMStrategy(BaseStrategy):
    """
    The '8 AM Candle' Strategy (ICT/SMC).
    1. Define Range (08:00 - 09:00 ET).
    2. Wait for Sweep of Range High/Low.
    3. Wait for Market Structure Shift (MSS) on 1m chart.
    4. Enter targeting the opposing liquidity.
    """

    # --- REQUIRED FOR BACKTESTING.PY ---
    # These must exist here for the engine to "see" them
    risk_reward = 2.0
    stop_loss_padding = 2.0
    
    # OLD: swing_lookback = 5  <-- DELETE THIS
    
    # NEW: Define the split lookbacks here
    swing_lookback_left = 10 
    swing_lookback_right = 2
    # -----------------------------------
    
    class Config(BaseModel):
        risk_reward: float = 2.0
        stop_loss_padding: float = 2.0 # Points
        # Update Config to match
        swing_lookback_left: int = 10
        swing_lookback_right: int = 2

    def init(self):
        # --- 1. PRE-CALCULATE 8 AM RANGES ---
        
        # Convert index to NY time if not already
        df = self.data.df.copy()
        if df.index.tz is None:
             df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
             df.index = df.index.tz_convert('America/New_York')

        # Filter for the 8am-9am window
        mask_8am = (df.index.hour == 8) 
        
        # Calculate Daily 8am Range
        daily_groups = df[mask_8am].groupby(df[mask_8am].index.date)
        
        daily_8am_highs = daily_groups['High'].max()
        daily_8am_lows = daily_groups['Low'].min()
        
        # Map these back to the original 1m dataframe
        df['DayDate'] = df.index.date
        df['RangeHigh'] = df['DayDate'].map(daily_8am_highs)
        df['RangeLow'] = df['DayDate'].map(daily_8am_lows)
        
        # Forward fill ensures that after 9am, we still remember the values
        self.range_high = self.I(lambda: df['RangeHigh'], name='8am_High')
        self.range_low = self.I(lambda: df['RangeLow'], name='8am_Low')
        
        # --- 2. CALCULATE SWING POINTS ---
        self.swings_h, self.swings_l = self.I(
            get_swing_points, 
            pd.Series(self.data.High), 
            pd.Series(self.data.Low), 
            self.swing_lookback_left,  # Use self.var directly or self.cfg.var
            self.swing_lookback_right, 
            overlay=True
        )
        
        # State variables
        self.session_active = False
        self.sweep_high = False
        self.sweep_low = False
        self.trade_taken_today = False
        self.current_day = None

    def next(self):
        # 1. TIME CHECK (Reset daily logic)
        current_time = self.data.index[-1]
        today = current_time.date()
        
        if self.current_day != today:
            self.current_day = today
            self.sweep_high = False
            self.sweep_low = False
            self.trade_taken_today = False
            self.session_active = False

        # We only trade AFTER 9:00 AM NY Time
        ny_time = current_time 
        
        if ny_time.hour < 9:
            return 
            
        if ny_time.hour >= 16:
            if self.position:
                self.position.close()
            return

        # 2. DETECT SWEEPS
        r_high = self.range_high[-1]
        r_low = self.range_low[-1]
        
        if pd.isna(r_high): return
        
        # Check if we swept High
        if self.data.High[-1] > r_high:
            self.sweep_high = True
            
        # Check if we swept Low
        if self.data.Low[-1] < r_low:
            self.sweep_low = True
            
        # If we already took a trade, stop
        if self.trade_taken_today:
            return
        
        # 3. ENTRY LOGIC (Market Structure Shift)
        
        # --- SHORT SETUP (After High Sweep) ---
        if self.sweep_high and not self.position:
            last_swing_low = self.get_last_swing(self.swings_l)
            
            if last_swing_low and self.data.Close[-1] < last_swing_low:
                # TRIGGER SHORT
                stop_price = np.max(self.data.High[-10:]) + self.cfg.stop_loss_padding
                take_profit = r_low 
                
                risk = stop_price - self.data.Close[-1]
                reward = self.data.Close[-1] - take_profit
                
                if risk > 0 and (reward / risk) >= self.cfg.risk_reward:
                    # FIX: Explicitly use size=config.FIXED_SIZE (1 contract)
                    self.sell(sl=stop_price, tp=take_profit, size=config.FIXED_SIZE)
                    self.trade_taken_today = True

        # --- LONG SETUP (After Low Sweep) ---
        elif self.sweep_low and not self.position:
            last_swing_high = self.get_last_swing(self.swings_h)
            
            if last_swing_high and self.data.Close[-1] > last_swing_high:
                # TRIGGER LONG
                stop_price = np.min(self.data.Low[-10:]) - self.cfg.stop_loss_padding
                take_profit = r_high
                
                risk = self.data.Close[-1] - stop_price
                reward = take_profit - self.data.Close[-1]
                
                if risk > 0 and (reward / risk) >= self.cfg.risk_reward:
                    # FIX: Explicitly use size=config.FIXED_SIZE (1 contract)
                    self.buy(sl=stop_price, tp=take_profit, size=config.FIXED_SIZE)
                    self.trade_taken_today = True

    def get_last_swing(self, swing_array):
        """ Helper to find the most recent non-NaN value in the swing array """
        for val in reversed(swing_array[:-1]):
            if not np.isnan(val):
                return val
        return None