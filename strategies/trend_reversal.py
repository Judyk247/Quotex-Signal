import pandas as pd
import numpy as np
from typing import Dict, Any

# Try to import TA-Lib, fallback to pure Python implementations
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
    # Pure Python technical analysis implementations
    def calculate_sma(series, period):
        return series.rolling(window=period).mean()

    def calculate_ema(series, period):
        return series.ewm(span=period, adjust=False).mean()

    def calculate_stochastic(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3):
        lowest_low = low.rolling(window=fastk_period).min()
        highest_high = high.rolling(window=fastk_period).max()
        
        stoch_k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        stoch_d = stoch_k.rolling(window=slowk_period).mean()
        
        return stoch_k, stoch_d

    def calculate_atr(high, low, close, period=14):
        tr = np.maximum(high - low, 
                       np.maximum(abs(high - close.shift()), 
                                 abs(low - close.shift())))
        return tr.rolling(window=period).mean()

class TrendReversalStrategy:
    def __init__(self, timeframe='5m'):
        self.timeframe = timeframe
        self.name = f"TrendReversal_{timeframe}"
        
    def calculate_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate all required technical indicators"""
        df = data.copy()
        
        # Alligator Indicator
        if HAS_TALIB:
            df['jaw'] = talib.SMA(df['close'], timeperiod=15)
            df['teeth'] = talib.SMA(df['close'], timeperiod=8)
            df['lips'] = talib.SMA(df['close'], timeperiod=5)
        else:
            df['jaw'] = calculate_sma(df['close'], 15)
            df['teeth'] = calculate_sma(df['close'], 8)
            df['lips'] = calculate_sma(df['close'], 5)
        
        # EMA-150
        if HAS_TALIB:
            df['ema_150'] = talib.EMA(df['close'], timeperiod=150)
        else:
            df['ema_150'] = calculate_ema(df['close'], 150)
        
        # Stochastic Oscillator
        if HAS_TALIB:
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowk_matype=0, 
                slowd_period=3, slowd_matype=0
            )
        else:
            df['stoch_k'], df['stoch_d'] = calculate_stochastic(
                df['high'], df['low'], df['close'], 14, 3, 3
            )
        
        # Fractals
        df['fractal_high'] = self._calculate_fractals(df, 'high')
        df['fractal_low'] = self._calculate_fractals(df, 'low')
        
        # ATR for volatility
        if HAS_TALIB:
            df['atr_14'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
        else:
            df['atr_14'] = calculate_atr(df['high'], df['low'], df['close'], 14)
        
        # Median ATR for volatility filter
        lookback = 10
        df['atr_median'] = df['atr_14'].rolling(window=lookback).median()
        
        # Historical bias
        df['reversal_count_buy'] = self._calculate_reversal_count(df, 'buy')
        df['reversal_count_sell'] = self._calculate_reversal_count(df, 'sell')
        
        # EMA slope
        df['ema_slope'] = df['ema_150'].diff()
        
        return df
    
    def _calculate_fractals(self, df: pd.DataFrame, price_type: str) -> np.array:
        """Calculate fractal indicators"""
        fractals = np.zeros(len(df))
        price_series = df[price_type].values
        
        for i in range(2, len(df)-2):
            if price_type == 'high':
                if (price_series[i] > price_series[i-2] and 
                    price_series[i] > price_series[i-1] and 
                    price_series[i] > price_series[i+1] and 
                    price_series[i] > price_series[i+2]):
                    fractals[i] = 1
            else:  # low
                if (price_series[i] < price_series[i-2] and 
                    price_series[i] < price_series[i-1] and 
                    price_series[i] < price_series[i+1] and 
                    price_series[i] < price_series[i+2]):
                    fractals[i] = 1
        return fractals
    
    def _calculate_reversal_count(self, df: pd.DataFrame, signal_type: str) -> np.array:
        """Calculate historical reversal count"""
        reversal_count = np.zeros(len(df))
        lookback = 10
        
        for i in range(lookback, len(df)):
            if signal_type == 'buy':
                recent_lows = df['fractal_low'].iloc[i-lookback:i]
                current_low = df['low'].iloc[i]
                threshold = current_low * 0.001
                reversal_count[i] = sum(
                    abs(df['low'].iloc[j] - current_low) < threshold 
                    for j in range(i-lookback, i) if recent_lows.iloc[j] == 1
                )
            else:  # sell
                recent_highs = df['fractal_high'].iloc[i-lookback:i]
                current_high = df['high'].iloc[i]
                threshold = current_high * 0.001
                reversal_count[i] = sum(
                    abs(df['high'].iloc[j] - current_high) < threshold 
                    for j in range(i-lookback, i) if recent_highs.iloc[j] == 1
                )
        return reversal_count
    
    def analyze(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Analyze data and generate signals"""
        if len(data) < 20:
            return {'signal': 'hold', 'confidence': 0}
        
        df = self.calculate_indicators(data)
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Check for BUY (Call) reversal signal
        buy_signal = self._check_buy_conditions(current, prev, df)
        
        # Check for SELL (Put) reversal signal
        sell_signal = self._check_sell_conditions(current, prev, df)
        
        if buy_signal['signal'] == 'buy':
            return buy_signal
        elif sell_signal['signal'] == 'sell':
            return sell_signal
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_buy_conditions(self, current, prev, df):
        """Check BUY reversal conditions"""
        # Trend context
        price_below_ema = current['close'] < current['ema_150']
        below_for_while = all(df['close'].iloc[-i] < df['ema_150'].iloc[-i] for i in range(2, min(7, len(df))))
        
        # Alligator condition
        alligator_cond = self._check_alligator_reversal(current, prev)
        
        # Stochastic condition
        stoch_cond = current['stoch_k'] < 20 and current['stoch_k'] > prev['stoch_k']
        
        # Volatility filter
        volatility_cond = current['atr_14'] > current['atr_median']
        
        # Historical bias
        historical_cond = current['reversal_count_buy'] >= 2
        
        # Price near fractal support
        price_cond = self._check_price_near_fractal(df, 'buy')
        
        # 3-candle pattern
        pattern_cond = self._check_three_candle_pattern(df, 'reversal_buy')
        
        if (price_below_ema and below_for_while and alligator_cond and stoch_cond and 
            volatility_cond and historical_cond and price_cond and pattern_cond):
            
            confidence = self._calculate_confidence(
                stoch_cond, alligator_cond, volatility_cond, 
                historical_cond, price_cond, pattern_cond
            )
            
            return {'signal': 'buy', 'confidence': confidence, 'type': 'reversal'}
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_sell_conditions(self, current, prev, df):
        """Check SELL reversal conditions"""
        # Trend context
        price_above_ema = current['close'] > current['ema_150']
        above_for_while = all(df['close'].iloc[-i] > df['ema_150'].iloc[-i] for i in range(2, min(7, len(df))))
        
        # Alligator condition
        alligator_cond = self._check_alligator_reversal(current, prev)
        
        # Stochastic condition
        stoch_cond = current['stoch_k'] > 80 and current['stoch_k'] < prev['stoch_k']
        
        # Volatility filter
        volatility_cond = current['atr_14'] > current['atr_median']
        
        # Historical bias
        historical_cond = current['reversal_count_sell'] >= 2
        
        # Price near fractal resistance
        price_cond = self._check_price_near_fractal(df, 'sell')
        
        # 3-candle pattern
        pattern_cond = self._check_three_candle_pattern(df, 'reversal_sell')
        
        if (price_above_ema and above_for_while and alligator_cond and stoch_cond and 
            volatility_cond and historical_cond and price_cond and pattern_cond):
            
            confidence = self._calculate_confidence(
                stoch_cond, alligator_cond, volatility_cond, 
                historical_cond, price_cond, pattern_cond
            )
            
            return {'signal': 'sell', 'confidence': confidence, 'type': 'reversal'}
        
        return {'signal': 'hold', 'confidence': 0}
    
    def _check_alligator_reversal(self, current, prev):
        """Check Alligator reversal condition"""
        lips, teeth, jaw = current['lips'], current['teeth'], current['jaw']
        lips_prev, teeth_prev, jaw_prev = prev['lips'], prev['teeth'], prev['jaw']
        
        # Check if lines are contracting
        diff_current = max(abs(lips - teeth), abs(teeth - jaw), abs(lips - jaw))
        diff_prev = max(abs(lips_prev - teeth_prev), abs(teeth_prev - jaw_prev), abs(lips_prev - jaw_prev))
        contracting = diff_current < diff_prev
        
        # Check if lines are crossing
        crossing = (
            (lips > teeth and lips_prev < teeth_prev) or
            (lips < teeth and lips_prev > teeth_prev) or
            (teeth > jaw and teeth_prev < jaw_prev) or
            (teeth < jaw and teeth_prev > jaw_prev)
        )
        
        return contracting or crossing
    
    def _check_price_near_fractal(self, df, signal_type):
        """Check if price is near fractal level"""
        current_price = df['close'].iloc[-1]
        threshold = current_price * 0.002
        
        if signal_type == 'buy':
            recent_lows = df['fractal_low'].iloc[-10:-1]
            for i in range(len(recent_lows)):
                if recent_lows.iloc[i] == 1:
                    low_price = df['low'].iloc[-10+i]
                    if abs(current_price - low_price) < threshold:
                        return True
        else:  # sell
            recent_highs = df['fractal_high'].iloc[-10:-1]
            for i in range(len(recent_highs)):
                if recent_highs.iloc[i] == 1:
                    high_price = df['high'].iloc[-10+i]
                    if abs(current_price - high_price) < threshold:
                        return True
        return False
    
    def _check_three_candle_pattern(self, df, pattern_type):
        """Check 3-candle pattern"""
        if len(df) < 3:
            return False
            
        c1 = df.iloc[-3]  # candle 1
        c2 = df.iloc[-2]  # candle 2
        c3 = df.iloc[-1]  # candle 3
        
        if pattern_type == 'reversal_buy':
            # Candle 1: Strong bearish candle
            bearish = c1['close'] < c1['open'] and (c1['open'] - c1['close']) > (0.6 * (c1['high'] - c1['low']))
            
            # Candle 2: Small-bodied candle
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bullish candle closing above Candle 2's high
            bullish = c3['close'] > c3['open'] and (c3['close'] - c3['open']) > (0.6 * (c3['high'] - c3['low']))
            above_prev_high = c3['close'] > c2['high']
            
            return bearish and small_body and bullish and above_prev_high
            
        elif pattern_type == 'reversal_sell':
            # Candle 1: Strong bullish candle
            bullish_c1 = c1['close'] > c1['open'] and (c1['close'] - c1['open']) > (0.6 * (c1['high'] - c1['low']))
            
            # Candle 2: Small-bodied candle
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bearish candle closing below Candle 2's low
            bearish = c3['close'] < c3['open'] and (c3['open'] - c3['close']) > (0.6 * (c3['high'] - c3['low']))
            below_prev_low = c3['close'] < c2['low']
            
            return bullish_c1 and small_body and bearish and below_prev_low
            
        return False
    
    def _calculate_confidence(self, stoch, alligator, volatility, historical, price, pattern):
        """Calculate signal confidence score"""
        confidence = 0
        
        if stoch: confidence += 15
        if alligator: confidence += 15
        if volatility: confidence += 10
        if historical: confidence += 15
        if price: confidence += 15
        if pattern: confidence += 30
        
        return min(100, confidence)
