import pandas as pd
import numpy as np
from backtesting import Strategy
from pydantic import BaseModel
from .base import BaseStrategy
from lib.smc import FVGManager, get_po3_phase, get_swing_points, detect_mss
import config

class IFVGStrategy(BaseStrategy):
    """
    Inversion FVG Strategy (Tuned Version).
    1. Front-Runs entries.
    2. Auto-Cancels old orders.
    3. Auto-Closes 'Zombie' positions after 4 hours.
    """
    
    # --- CLASS VARS ---
    risk_reward = 2.0
    stop_loss_padding = 1.0 
    
    # EXPIRATION TUNING
    fvg_expiration = 300     # INCREASED: 5 Hours (Allows more time for setup)
    order_expiration = 120   # INCREASED: 2 Hours (Give orders time to fill)
    max_hold_bars = 240      # NEW: Force close trade after 4 hours if stuck
    
    trade_size = 1
    
    # Filters
    use_mss_filter = True    
    use_ema_filter = True
    ema_period = 200
    use_po3_filter = True
    limit_padding_atr = 0.1
    
    # NEW: Aggressive Mode
    aggressive_mode = False 
    
    class Config(BaseModel):
        risk_reward: float = 2.0
        stop_loss_padding: float = 1.0 
        fvg_expiration: int = 300
        order_expiration: int = 120
        max_hold_bars: int = 240
        trade_size: int = 1
        
        use_mss_filter: bool = True
        use_ema_filter: bool = True
        ema_period: int = 200
        use_po3_filter: bool = True
        limit_padding_atr: float = 0.1
        aggressive_mode: bool = False 

    def init(self):
        self.fvg_engine = FVGManager(expiration=self.cfg.fvg_expiration)
        self.trade_size = self.cfg.trade_size
        
        # INDICATORS
        self.atr = self.I(lambda: self.data.df.ta.atr(length=14), name="ATR")
        self.ema = self.I(lambda: self.data.df.ta.ema(length=self.cfg.ema_period), name="Trend_EMA")
        
        # STRUCTURE
        highs = pd.Series(self.data.High)
        lows = pd.Series(self.data.Low)
        self.swings_h, self.swings_l = self.I(get_swing_points, highs, lows, 5, 5)
        self.mss = self.I(detect_mss, pd.Series(self.data.Close), pd.Series(self.swings_h), pd.Series(self.swings_l))
        
        self.order_times = {}
        self.entry_times = {} # Track when we entered a position

    def next(self):
        current_idx = len(self.data)
        
        # 1. ZOMBIE TRADE KILLER (NEW)
        if self.position:
            # Check how long we've held
            # We need to find when the current position was opened.
            # Backtesting.py doesn't give 'entry_bar' easily, so we estimate or track it.
            # Simplified: We just increment a counter if we are in a position? 
            # Better: Track it in self.entry_times
            if not hasattr(self, 'pos_entry_bar') or self.pos_entry_bar is None:
                self.pos_entry_bar = current_idx
            
            bars_held = current_idx - self.pos_entry_bar
            if bars_held > self.cfg.max_hold_bars:
                self.position.close()
                self.pos_entry_bar = None
                return
        else:
            self.pos_entry_bar = None

        # 2. CLEANUP STALE ORDERS
        for order in list(self.orders):
            if order in self.order_times:
                age = current_idx - self.order_times[order]
                limit = self.cfg.order_expiration * 2 if self.cfg.aggressive_mode else self.cfg.order_expiration
                if age > limit:
                    order.cancel()
                    del self.order_times[order]
            else:
                self.order_times[order] = current_idx

        # 3. WAIT FOR DATA
        if len(self.data) < 200: return

        # 4. UPDATE ENGINE
        idx = len(self.data)
        high_s = self.data.df['High'].iloc[:idx]
        low_s = self.data.df['Low'].iloc[:idx]
        close_s = self.data.df['Close'].iloc[:idx]
        
        raw_time = self.data.index[-1]
        if raw_time.tzinfo is None:
            ny_time = raw_time.tz_localize('UTC').tz_convert('America/New_York')
        else:
            ny_time = raw_time.tz_convert('America/New_York')
        
        self.fvg_engine.update(high_s, low_s, close_s, idx-1, ny_time)
        
        # 5. ENTRY LOGIC
        if self.position or len(self.orders) > 0: return
        
        current_price = self.data.Close[-1]
        trend_ema = self.ema[-1]
        current_atr = self.atr[-1]
        current_mss = self.mss[-1]
        
        if np.isnan(current_atr) or np.isnan(trend_ema): return

        # SESSION FILTER
        if self.cfg.use_po3_filter and not self.cfg.aggressive_mode:
            phase = get_po3_phase(ny_time)
            if phase != "Distribution":
                return

        for ifvg in self.fvg_engine.inverted_fvgs:
            if ifvg.traded: continue
            
            # A. SHORT SETUP
            if ifvg.is_bullish and ifvg.inverted:
                if not self.cfg.aggressive_mode:
                    if self.cfg.use_ema_filter and current_price > trend_ema: continue
                    if self.cfg.use_mss_filter and current_mss == 1: continue
                
                self.entry_short_limit(ifvg)
                return

            # B. LONG SETUP
            if not ifvg.is_bullish and ifvg.inverted:
                if not self.cfg.aggressive_mode:
                    if self.cfg.use_ema_filter and current_price < trend_ema: continue
                    if self.cfg.use_mss_filter and current_mss == -1: continue

                self.entry_long_limit(ifvg)
                return

    def entry_short_limit(self, zone):
        current_atr = self.atr[-1]
        mult = 2.0 if self.cfg.aggressive_mode else 1.0
        padding = current_atr * self.cfg.limit_padding_atr * mult
        entry_price = zone.bottom - padding
        
        sl = zone.top + current_atr
        risk = sl - entry_price
        
        if risk < (current_atr * 0.2): return

        tp = entry_price - (risk * self.cfg.risk_reward)
        order = self.sell(limit=entry_price, sl=sl, tp=tp, size=self.trade_size)
        self.order_times[order] = len(self.data)
        zone.traded = True

    def entry_long_limit(self, zone):
        current_atr = self.atr[-1]
        mult = 2.0 if self.cfg.aggressive_mode else 1.0
        padding = current_atr * self.cfg.limit_padding_atr * mult
        entry_price = zone.top + padding
        
        sl = zone.bottom - current_atr
        risk = entry_price - sl
        
        if risk < (current_atr * 0.2): return

        tp = entry_price + (risk * self.cfg.risk_reward)
        order = self.buy(limit=entry_price, sl=sl, tp=tp, size=self.trade_size)
        self.order_times[order] = len(self.data)
        zone.traded = True