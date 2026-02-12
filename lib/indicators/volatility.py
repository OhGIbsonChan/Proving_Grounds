import pandas as pd
import pandas_ta_classic as ta

def get_atr(high, low, close, period=14):
    """ Simple ATR wrapper """
    return ta.atr(high, low, close, length=period)

def get_ker(close, period=20):
    """ Kaufmann Efficiency Ratio (Manual Math) """
    direction = close.diff(period).abs()
    volatility = close.diff().abs().rolling(period).sum()
    return direction / volatility