import pandas_ta_classic as ta

def get_ema(series, period):
    return ta.ema(series, length=period)