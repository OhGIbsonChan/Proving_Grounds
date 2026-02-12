import pandas as pd  # <--- This was missing
import numpy as np
import pandas_ta_classic as ta

def get_rolling_hurst(series: pd.Series, window: int, lags=[2, 4, 8, 16]):
    """ Vectorized Hurst Calculation """
    rolling_vars = {}
    for lag in lags:
        diffs = series.diff(lag)
        rolling_vars[lag] = diffs.rolling(window).var()
    
    x = np.log(lags)
    mean_x = np.mean(x)
    var_x = np.var(x)
    
    # Now this works because 'pd' is defined
    df_vars = pd.DataFrame(rolling_vars)
    df_log_vars = np.log(df_vars)
    
    y_bar = df_log_vars.mean(axis=1)
    
    # Note: Pandas automatically broadcasts 'x' across rows here, which is correct
    xy = df_log_vars * x 
    xy_bar = xy.mean(axis=1)
    
    slope = (xy_bar - mean_x * y_bar) / var_x
    return slope / 2