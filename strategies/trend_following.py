import pandas as pd
import numpy as np
from typing import Dict, Any

def calculate_sma(series, period):
    return series.rolling(window=period).mean()

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low = low.rolling(window=k_period).min()
    highest_high = high.rolling(window=k_period).max()
    
    stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    stoch_d = stoch_k.rolling(window=d_period).mean()
    
    return stoch_k, stoch_d

class TrendFollowingStrategy:
    def __init__(self, timeframe='1m'):
        self.timeframe = timeframe
        self.name = f"TrendFollowing_{timeframe}"
        
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate indicators for trend following strategy"""
        df = data.copy()
        
        # Alligator Indicator
        df['jaw'] = calculate_sma(df['close'], 15)
        df['teeth'] = calculate_sma(df['close'], 8)
        df['lips'] = calculate_sma(df['close'], 5)
        
        # EMA-150
        df['ema_150'] = calculate_ema(df['close'], 150)
        
        # Stochastic Oscillator
        df['stoch_k'], df['stoch_d'] = calculate_stochastic(
            df['high'], df['low'], df['close'], 14, 3
        )
        
        # ATR for volatility
        df['atr_14'] = self._calculate_atr(df['high'], df['low'], df['close'], 14)
        
        return df
    
    def _calculate_atr(self, high, low, close, period=14):
        """Calculate Average True Range"""
        tr = np.maximum(high - low, 
                       np.maximum(abs(high - close.shift()), 
                                 abs(low - close.shift())))
        return tr.rolling(window=period).mean()
    
    def analyze(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Trend Following Strategy Analysis"""
        if len(data) < 20:
            return {'signal': 'hold', 'confidence': 0}
        
        df = self.calculate_indicators(data)
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check for BUY (Call) trend following signal
        buy_signal = self._check_buy_conditions(current, prev, df)
        
        # Check for SELL (Put) trend following signal
        sell_signal = self._check_sell_conditions(current, prev, df)
        
        if buy_signal['signal'] == 'buy':
            return buy_signal
        elif sell_signal['signal'] == 'sell':
            return sell_signal
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_buy_conditions(self, current, prev, df):
        """Check BUY trend following conditions"""
        # EMA trending up
        ema_slope_positive = current['ema_150'] > df['ema_150'].iloc[-5]
        
        # Price above EMA
        price_above_ema = current['close'] > current['ema_150']
        
        # Alligator aligned bullish (Lips > Teeth > Jaw)
        alligator_bullish = (current['lips'] > current['teeth'] > current['jaw'])
        
        # Stochastic in oversold zone and turning up
        stoch_cond = (20 <= current['stoch_k'] <= 40 and 
                     current['stoch_k'] > prev['stoch_k'])
        
        # Check 3-candle pattern for trend following
        pattern_cond = self._check_three_candle_pattern(df, 'trend_buy')
        
        if (ema_slope_positive and price_above_ema and alligator_bullish and 
            stoch_cond and pattern_cond):
            
            confidence = self._calculate_confidence(
                ema_slope_positive, price_above_ema, alligator_bullish,
                stoch_cond, pattern_cond
            )
            
            return {'signal': 'buy', 'confidence': confidence, 'type': 'trend_following'}
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_sell_conditions(self, current, prev, df):
        """Check SELL trend following conditions"""
        # EMA trending down
        ema_slope_negative = current['ema_150'] < df['ema_150'].iloc[-5]
        
        # Price below EMA
        price_below_ema = current['close'] < current['ema_150']
        
        # Alligator aligned bearish (Lips < Teeth < Jaw)
        alligator_bearish = (current['lips'] < current['teeth'] < current['jaw'])
        
        # Stochastic in overbought zone and turning down
        stoch_cond = (60 <= current['stoch_k'] <= 80 and 
                     current['stoch_k'] < prev['stoch_k'])
        
        # Check 3-candle pattern for trend following
        pattern_cond = self._check_three_candle_pattern(df, 'trend_sell')
        
        if (ema_slope_negative and price_below_ema and alligator_bearish and 
            stoch_cond and pattern_cond):
            
            confidence = self._calculate_confidence(
                ema_slope_negative, price_below_ema, alligator_bearish,
                stoch_cond, pattern_cond
            )
            
            return {'signal': 'sell', 'confidence': confidence, 'type': 'trend_following'}
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_three_candle_pattern(self, df, pattern_type):
        """Check 3-candle pattern for trend following"""
        if len(df) < 3:
            return False
            
        c1 = df.iloc[-3]  # candle 1
        c2 = df.iloc[-2]  # candle 2
        c3 = df.iloc[-1]  # candle 3
        
        if pattern_type == 'trend_buy':
            # Candle 1: Pullback candle (bearish) closing above EMA-150
            bearish = c1['close'] < c1['open']
            above_ema = c1['close'] > df['ema_150'].iloc[-3]
            
            # Candle 2: Small indecision candle
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bullish candle breaking above Candle 2's high
            bullish = c3['close'] > c3['open'] and (c3['close'] - c3['open']) > (0.6 * (c3['high'] - c3['low']))
            above_prev_high = c3['close'] > c2['high']
            
            return bearish and above_ema and small_body and bullish and above_prev_high
            
        elif pattern_type == 'trend_sell':
            # Candle 1: Pullback candle (bullish) closing below EMA-150
            bullish_c1 = c1['close'] > c1['open']
            below_ema = c1['close'] < df['ema_150'].iloc[-3]
            
            # Candle 2: Small indecision candle
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bearish candle breaking below Candle 2's low
            bearish = c3['close'] < c3['open'] and (c3['open'] - c3['close']) > (0.6 * (c3['high'] - c3['low']))
            below_prev_low = c3['close'] < c2['low']
            
            return bullish_c1 and below_ema and small_body and bearish and below_prev_low
            
        return False
    
    def _calculate_confidence(self, *conditions):
        """Calculate signal confidence score"""
        confidence = sum(20 for condition in conditions if condition)
        return min(100, confidence)
