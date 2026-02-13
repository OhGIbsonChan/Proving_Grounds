from strategies.base import BaseStrategy
from lib.indicators import get_rolling_hurst, get_ker, get_atr
from pydantic import BaseModel, Field
import pandas_ta_classic as ta
import config

class FractalSniperV4(BaseStrategy):
    # --- 1. PARAMETERS (Must be Class Variables for Backtesting.py) ---
    # We define the DEFAULTS here so the optimizer can see them.
    hurst_window = 100
    hurst_threshold = 0.60
    ker_period = 20
    ker_threshold = 0.40
    vol_ma_period = 50
    ema_period = 50
    stop_atr = 2.0
    trail_atr = 3.0

    # --- 2. UI METADATA (The "Magic" for later) ---
    # This tells our future WebUI what sliders to draw
    class Config(BaseModel):
        hurst_window: int = Field(100, ge=50, le=300, title="Hurst Window")
        hurst_threshold: float = Field(0.60, ge=0.0, le=1.0, title="Hurst Threshold")
        ker_period: int = Field(20, title="Efficiency Period")
        ker_threshold: float = Field(0.40, title="Efficiency Threshold")
        vol_ma_period: int = Field(50, title="Volume MA Period")
        ema_period: int = Field(50, title="EMA Trend Filter")
        stop_atr: float = Field(2.0, title="Initial Stop ATR")
        trail_atr: float = Field(3.0, title="Trailing Stop ATR")

    def init(self):
        # 1. Indicators
        # NOTICE: We now access params via 'self.hurst_window', NOT 'self.cfg'
        self.hurst = self.I(get_rolling_hurst, self.data.Close.s, self.hurst_window)
        self.ker = self.I(get_ker, self.data.Close.s, self.ker_period)
        
        # 2. Volume & Trend
        self.vol_sma = self.I(ta.sma, self.data.Volume.s, self.vol_ma_period)
        self.ema = self.I(ta.ema, self.data.Close.s, self.ema_period)
        self.atr = self.I(get_atr, self.data.High.s, self.data.Low.s, self.data.Close.s, 14)

        # Variables for Trailing Stop logic
        self.stop_loss_price = None
        self.highest_high = 0
        self.lowest_low = 999999

    def next(self):
        price = self.data.Close[-1]
        high = self.data.High[-1]
        low = self.data.Low[-1]
        vol = self.data.Volume[-1]
        
        # --- TRAILING STOP LOGIC ---
        if self.position:
            if self.position.is_long:
                self.highest_high = max(self.highest_high, high)
                new_stop = self.highest_high - (self.atr[-1] * self.trail_atr)
                self.stop_loss_price = max(self.stop_loss_price, new_stop) if self.stop_loss_price else new_stop
                
                if low <= self.stop_loss_price:
                    self.position.close()
                    return

            elif self.position.is_short:
                self.lowest_low = min(self.lowest_low, low)
                new_stop = self.lowest_low + (self.atr[-1] * self.trail_atr)
                self.stop_loss_price = min(self.stop_loss_price, new_stop) if self.stop_loss_price else new_stop

                if high >= self.stop_loss_price:
                    self.position.close()
                    return

            # Panic Exit
            if self.hurst[-1] < 0.50:
                self.position.close()
                return

        # --- ENTRY LOGIC ---
        if not self.position:
            is_fractal = self.hurst[-1] > self.hurst_threshold
            is_efficient = self.ker[-1] > self.ker_threshold
            is_volume = vol > self.vol_sma[-1]

            if is_fractal and is_efficient and is_volume:
                if price > self.ema[-1]:
                    # Reduced size to 0.5 (50% of equity) to survive longer
                    self.buy(size=config.FIXED_SIZE) 
                    self.stop_loss_price = price - (self.atr[-1] * self.stop_atr)
                    self.highest_high = price 

                elif price < self.ema[-1]:
                    self.sell(size=config.FIXED_SIZE)
                    self.stop_loss_price = price + (self.atr[-1] * self.stop_atr)
                    self.lowest_low = price