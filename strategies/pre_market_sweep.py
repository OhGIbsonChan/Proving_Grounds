import pandas as pd
import numpy as np
from backtesting import Strategy
from pydantic import BaseModel
from .base import BaseStrategy
from lib.smc import FVGManager
import config

class PreMarketSweepStrategy(BaseStrategy):
    """
    Edwin's Pre-Market Sweep Strategy (Scalp Version).
    1. Tracks Asian Low, London Low, and Previous Day Low (PDL).
    2. Entry Window: 05:00 - 08:00 EST.
    3. Setup: Sweep -> Reclaim -> Bullish Inversion FVG.
    4. Hard Exit: 09:30 EST (NY Open) to avoid open volatility/overnight risk.
    """
    
    # --- REQUIRED FOR BACKTESTING.PY ENGINE ---
    risk_reward = 2.0
    stop_loss_padding = 1.0
    trade_size = 1
    fvg_expiration = 60
    strict_reclaim = True 
    exit_hour = 9
    exit_minute = 30
    
    class Config(BaseModel):
        risk_reward: float = 2.0
        stop_loss_padding: float = 1.0
        trade_size: int = 1
        fvg_expiration: int = 60
        strict_reclaim: bool = True
        # Hard Exit Settings (NY Time)
        exit_hour: int = 9
        exit_minute: int = 30

    def init(self):
        self.fvg_engine = FVGManager(expiration=self.cfg.fvg_expiration)
        self.trade_size = self.cfg.trade_size
        self.atr = self.I(lambda: self.data.df.ta.atr(length=14), name="ATR")
        
        # --- PRE-CALCULATE LEVELS ---
        df = self.data.df.copy()
        
        # Ensure NY Timezone for session logic
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('America/New_York')
        else:
            df.index = df.index.tz_convert('America/New_York')

        # 1. Previous Day Low (PDL) - Static Daily Low
        daily_lows = df['Low'].resample('D').min()
        pdl_series = daily_lows.shift(1)
        df['PDL'] = df.index.normalize().map(pdl_series)
        self.pdl = self.I(lambda: df['PDL'].ffill(), name="PDL")

        # 2. Asian Low (19:00 - 00:00 EST Previous Day)
        asia_mask = (df.index.hour >= 19) | (df.index.hour < 0)
        df['AsiaLow'] = df['Low'].where(asia_mask).groupby(df.index.date).transform('min').ffill()
        self.asia_low = self.I(lambda: df['AsiaLow'], name="Asia_Low")

        # 3. London Low (02:00 - 05:00 EST Current Day)
        lon_mask = (df.index.hour >= 2) & (df.index.hour < 5)
        df['LonLow'] = df['Low'].where(lon_mask).groupby(df.index.date).transform('min').ffill()
        self.london_low = self.I(lambda: df['LonLow'], name="London_Low")
        
        self.session_start_day = None
        self.session_min_low = float('inf')

    def next(self):
        # 1. TIMEZONE CHECK
        current_time = self.data.index[-1]
        ny_time = current_time.tz_convert('America/New_York') if current_time.tzinfo else current_time.tz_localize('UTC').tz_convert('America/New_York')
        
        # --- HARD EXIT LOGIC (09:30 EST) ---
        # If we are in a position and it's time to exit
        if self.position:
            if (ny_time.hour > self.cfg.exit_hour) or \
               (ny_time.hour == self.cfg.exit_hour and ny_time.minute >= self.cfg.exit_minute):
                self.position.close()
                return

        # Trade Window: 5am - 8am EST
        is_entry_window = (ny_time.hour >= 5 and ny_time.hour < 8)
        
        # Reset Session Tracker at 5am
        if ny_time.hour == 5 and ny_time.minute == 0:
            self.session_min_low = float('inf')

        # 2. UPDATE FVG ENGINE
        idx = len(self.data)
        self.fvg_engine.update(
            self.data.df['High'].iloc[:idx], 
            self.data.df['Low'].iloc[:idx], 
            self.data.df['Close'].iloc[:idx], 
            idx-1, ny_time
        )

        if not is_entry_window:
            return

        if self.position: return

        # 3. SWEEP DETECTION LOGIC
        current_low = self.data.Low[-1]
        current_close = self.data.Close[-1]
        
        # Track lowest low in session
        self.session_min_low = min(self.session_min_low, current_low)
        
        levels_map = {
            'Asia': self.asia_low[-1], 
            'London': self.london_low[-1], 
            'PDL': self.pdl[-1]
        }
        
        swept_levels = [lvl for name, lvl in levels_map.items() 
                        if not np.isnan(lvl) and self.session_min_low < lvl]
        
        if not swept_levels:
            return 
            
        # 4. ENTRY ON BULLISH INVERSION FVG
        for ifvg in self.fvg_engine.inverted_fvgs:
            if ifvg.traded: continue
            
            # Look for Resistance -> Support Flip (Bullish Inversion)
            if not ifvg.is_bullish and ifvg.inverted:
                
                # Strict Reclaim: Close > Highest Swept Level
                highest_swept_level = max(swept_levels)
                
                if current_close > highest_swept_level:
                    self.entry_long(ifvg)
                    ifvg.traded = True
                    break

    def entry_long(self, zone):
        current_atr = self.atr[-1]
        entry_price = self.data.Close[-1]
        
        sl = zone.bottom - (current_atr * self.cfg.stop_loss_padding)
        risk = entry_price - sl
        
        if risk <= 0: return

        tp = entry_price + (risk * self.cfg.risk_reward)
        self.buy(sl=sl, tp=tp, size=self.trade_size)