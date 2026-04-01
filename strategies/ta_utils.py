import pandas as pd
import numpy as np

def calculate_sma(series, period):
    """Simple Moving Average - Pure Python implementation"""
    return series.rolling(window=period).mean()

def calculate_ema(series, period):
    """Exponential Moving Average - Pure Python implementation"""
    return series.ewm(span=period, adjust=False).mean()

def calculate_stochastic(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3):
    """Stochastic Oscillator - Pure Python implementation"""
    lowest_low = low.rolling(window=fastk_period).min()
    highest_high = high.rolling(window=fastk_period).max()
    
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_d = stoch_k.rolling(window=slowk_period).mean()
    
    return stoch_k, stoch_d

def calculate_rsi(series, period=14):
    """RSI Indicator - Pure Python implementation"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi
