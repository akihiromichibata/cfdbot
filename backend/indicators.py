import numpy as np
import pandas as pd

def bollinger_bands(close: pd.Series, period=20, sigma=2.0):
    ma = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = ma + sigma * std
    lower = ma - sigma * std
    return ma, upper, lower

def rsi(close: pd.Series, period=14):
    delta = close.diff()
    up = np.where(delta > 0, delta, 0.0)
    down = np.where(delta < 0, -delta, 0.0)
    roll_up = pd.Series(up).rolling(period).mean()
    roll_down = pd.Series(down).rolling(period).mean()
    rs = roll_up / (roll_down + 1e-9)
    return 100.0 - (100.0 / (1.0 + rs))

def volume_spike(volume: pd.Series, ma_period=20, mult=1.5):
    vma = volume.rolling(ma_period).mean()
    return (volume.tail(1).iloc[0] > mult * vma.tail(1).iloc[0])
