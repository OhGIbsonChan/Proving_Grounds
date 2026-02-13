from strategies.base import BaseStrategy
from pydantic import BaseModel, Field
import pandas_ta_classic as ta
import pytz 
import config # Add import

class Config(BaseModel):
    # The "God Mode" Settings
    atr_period: int = Field(14, title="ATR Period")
    stop_mult: float = Field(1.2, title="Stop Loss Multiplier")
    target_mult: float = Field(8.0, title="Take Profit Multiplier")
    vol_filter_len: int = Field(20, title="Volume Filter Length")

class GodModeSniper(BaseStrategy):
    Config = Config

    def init(self):
        # 1. Indicators
        self.atr = self.I(ta.atr, self.data.High.s, self.data.Low.s, self.data.Close.s, self.cfg.atr_period)
        self.vol_sma = self.I(ta.sma, self.data.Volume.s, self.cfg.vol_filter_len)
        
        # 2. Session High/Low Trackers
        self.asia_high = 0.0
        self.asia_low = 999999.0
        self.london_high = 0.0
        self.london_low = 999999.0
        self.current_trading_day = None

    def next(self):
        # --- 1. ROBUST TIMEZONE LOGIC ---
        utc_time = self.data.index[-1]
        if utc_time.tzinfo is None:
            utc_time = utc_time.replace(tzinfo=pytz.utc)
        ny_time = utc_time.astimezone(pytz.timezone('America/New_York'))
        
        hour = ny_time.hour
        minute = ny_time.minute
        day_of_week = ny_time.dayofweek 
        date = ny_time.date()
        price = self.data.Close[-1]

        # --- 2. ROBUST RESET LOGIC (Fixes the "Bad Highs") ---
        # Reset if the DATE changed. This handles data gaps where 17:00 doesn't exist.
        if self.current_trading_day != date:
            if hour >= 17 or hour < 9: 
                self.asia_high = 0.0
                self.asia_low = 999999.0
                self.london_high = 0.0
                self.london_low = 999999.0
                self.current_trading_day = date
        # Fallback for perfect data
        elif hour == 17 and minute == 0:
             self.asia_high = 0.0
             self.asia_low = 999999.0
             self.london_high = 0.0
             self.london_low = 999999.0

        # --- 3. SESSION RECORDING ---
        if hour >= 18 or hour < 2:
            self.asia_high = max(self.asia_high, self.data.High[-1])
            self.asia_low = min(self.asia_low, self.data.Low[-1])
        elif 2 <= hour < 5:
            self.london_high = max(self.london_high, self.data.High[-1])
            self.london_low = min(self.london_low, self.data.Low[-1])

        # --- 4. TRADE EXECUTION ---
        if not self.position:
            if day_of_week in [3, 4]: # Thu/Fri
                if self.data.Volume[-1] > self.vol_sma[-1]:
                    if hour in [9, 10, 12, 14]:
                        
                        trig_h = max(self.asia_high, self.london_high)
                        trig_l = min(self.asia_low, self.london_low)
                        
                        # --- SAFETY: ATR CHECK ---
                        # If ATR is suspiciously huge (e.g. > 2% of price), cap it or skip
                        current_atr = self.atr[-1]
                        if current_atr > (price * 0.02):
                             return # Skip trade, market is broken/gapping

                        # Long Entry
                        if trig_h > 0 and price > trig_h:
                            dist_sl = current_atr * self.cfg.stop_mult
                            dist_tp = current_atr * self.cfg.target_mult
                            
                            sl_price = price - dist_sl
                            tp_price = price + dist_tp
                            
                            # SAFETY: Ensure positive prices
                            if sl_price > 0:
                                self.buy(sl=sl_price, tp=tp_price, size=config.FIXED_SIZE)

                        # Short Entry
                        elif trig_l < 999999 and price < trig_l:
                            dist_sl = current_atr * self.cfg.stop_mult
                            dist_tp = current_atr * self.cfg.target_mult
                            
                            sl_price = price + dist_sl
                            tp_price = price - dist_tp
                            
                            # SAFETY: Ensure positive prices (Fixes the crash!)
                            if tp_price > 0: 
                                self.sell(sl=sl_price, tp=tp_price, size=config.FIXED_SIZE)

        # --- 5. HARD EXIT ---
        if self.position and hour == 15 and minute >= 45:
            self.position.close()