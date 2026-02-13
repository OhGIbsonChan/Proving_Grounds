import pandas as pd
import numpy as np
from backtesting import Strategy
from pydantic import BaseModel
from .base import BaseStrategy
from lib.smc import FVGManager, get_po3_phase
import config

class PreMarketSweepStrategy(BaseStrategy):
    """
    Edwin's Pre-Market Sweep Strategy.
    1. Tracks Asian Low, London Low, and Previous Day Low (PDL).
    2. Window: 05:00 - 08:00 EST (6pm-9pm SGT).
    3. Setup: Sweep of a key low + Inversion FVG Reversal.
    """
    
    # --- REQUIRED FOR ENGINE ---
    risk_reward = 2.0
    stop_loss_padding = 1.0
    trade_size = 1
    
    class Config(BaseModel):
        risk_reward: float = 2.0
        stop_loss_padding: float = 1.0
        trade_size: int = 1
        fvg_expiration: int = 60

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

        # Previous Day Low (PDL)
        self.pdl = self.I(lambda: df['Low'].shift(1).rolling(window='24h').min(), name="PDL")

        # Asian Low (19:00 - 00:00 EST)
        asia_mask = (df.index.hour >= 19) | (df.index.hour < 0)
        df['AsiaLow'] = df['Low'].where(asia_mask).groupby(df.index.date).transform('min').ffill()
        self.asia_low = self.I(lambda: df['AsiaLow'], name="Asia_Low")

        # London Low (02:00 - 05:00 EST)
        lon_mask = (df.index.hour >= 2) & (df.index.hour < 5)
        df['LonLow'] = df['Low'].where(lon_mask).groupby(df.index.date).transform('min').ffill()
        self.london_low = self.I(lambda: df['LonLow'], name="London_Low")

    def next(self):
        if len(self.data) < 20: return

        # 1. TIMEZONE & WINDOW CHECK
        raw_time = self.data.index[-1]
        ny_time = raw_time.tz_convert('America/New_York') if raw_time.tzinfo else raw_time.tz_localize('UTC').tz_convert('America/New_York')
        
        # Trade Window: 5am - 8am EST (6pm - 9pm SGT)
        is_trade_window = (ny_time.hour >= 5 and ny_time.hour < 8)
        
        # 2. UPDATE FVG ENGINE
        idx = len(self.data)
        self.fvg_engine.update(
            self.data.df['High'].iloc[:idx], 
            self.data.df['Low'].iloc[:idx], 
            self.data.df['Close'].iloc[:idx], 
            idx-1, ny_time
        )

        if not is_trade_window:
            return

        if self.position: return

        # 3. SWEEP DETECTION
        # Levels to monitor
        levels = [self.asia_low[-1], self.london_low[-1], self.pdl[-1]]
        current_low = self.data.Low[-1]
        current_close = self.data.Close[-1]
        
        # Did we poke below any level?
        swept = any(current_low < lvl for lvl in levels if not np.isnan(lvl))
        
        if swept:
            # 4. ENTRY ON INVERSION FVG (UPWARD)
            # Look for Bullish IFVGs (Was Resistance -> Now Support)
            for ifvg in self.fvg_engine.inverted_fvgs:
                if ifvg.traded: continue
                
                # If it's a Bullish Inversion (Price broke ABOVE a Bearish FVG)
                if not ifvg.is_bullish and ifvg.inverted:
                    # Confirm we are trading ABOVE the swept level (Reclaim)
                    if current_close > max(levels):
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