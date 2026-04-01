import pandas as pd
import numpy as np
import talib
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class BinaryOptionsStrategy:
    def __init__(self, data, timeframe='5m'):
        """
        Initialize the strategy with price data
        
        Parameters:
        data: DataFrame with OHLC data
        timeframe: Timeframe of the data ('1m', '2m', '3m', '5m')
        """
        self.data = data.copy()
        self.timeframe = timeframe
        self.setup_indicators()
        
    def setup_indicators(self):
        """Calculate all required technical indicators"""
        # Alligator Indicator
        self.data['jaw'] = talib.SMA(self.data['close'], timeperiod=15)
        self.data['teeth'] = talib.SMA(self.data['close'], timeperiod=8)
        self.data['lips'] = talib.SMA(self.data['close'], timeperiod=5)
        
        # EMA-150
        self.data['ema_150'] = talib.EMA(self.data['close'], timeperiod=150)
        
        # Stochastic Oscillator
        self.data['stoch_k'], self.data['stoch_d'] = talib.STOCH(
            self.data['high'], self.data['low'], self.data['close'],
            fastk_period=14, slowk_period=3, slowk_matype=0, 
            slowd_period=3, slowd_matype=0
        )
        
        # Fractals
        self.data['fractal_high'] = self.calculate_fractals('high')
        self.data['fractal_low'] = self.calculate_fractals('low')
        
        # ATR for volatility
        self.data['atr_14'] = talib.ATR(
            self.data['high'], self.data['low'], self.data['close'], timeperiod=14
        )
        
        # Median ATR for volatility filter
        lookback = 10 if self.timeframe == '5m' else 5
        self.data['atr_median'] = self.data['atr_14'].rolling(window=lookback).median()
        
        # Historical bias - count of reversals in recent candles
        self.data['reversal_count_buy'] = self.calculate_reversal_count('buy')
        self.data['reversal_count_sell'] = self.calculate_reversal_count('sell')
        
        # EMA slope calculation
        self.data['ema_slope'] = self.calculate_ema_slope()
        
    def calculate_fractals(self, price_type='high'):
        """Calculate fractal indicators"""
        fractals = np.zeros(len(self.data))
        price_series = self.data[price_type].values
        
        for i in range(2, len(self.data)-2):
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
    
    def calculate_reversal_count(self, signal_type):
        """Calculate how many times price reversed at this level in recent history"""
        reversal_count = np.zeros(len(self.data))
        lookback = 10 if self.timeframe == '5m' else 5
        
        for i in range(lookback, len(self.data)):
            if signal_type == 'buy':
                # Count fractal lows in the recent candles near current price
                recent_lows = self.data['fractal_low'][i-lookback:i]
                current_low = self.data['low'][i]
                threshold = current_low * 0.001  # 0.1% threshold
                reversal_count[i] = sum(
                    abs(self.data['low'][j] - current_low) < threshold 
                    for j in range(i-lookback, i) if recent_lows[j] == 1
                )
            else:  # sell
                # Count fractal highs in the recent candles near current price in
                recent_highs = self.data['fractal_high'][i-lookback:i]
                current_high = self.data['high'][i]
                threshold = current_high * 0.001  # 0.1% threshold
                reversal_count[i] = sum(
                    abs(self.data['high'][j] - current_high) < threshold 
                    for j in range(i-lookback, i) if recent_highs[j] == 1
                )
                
        return reversal_count
    
    def calculate_ema_slope(self):
        """Calculate the slope of EMA-150"""
        slope = np.zeros(len(self.data))
        for i in range(1, len(self.data)):
            slope[i] = self.data['ema_150'].iloc[i] - self.data['ema_150'].iloc[i-1]
        return slope
    
    def check_three_candle_pattern(self, i, pattern_type):
        """
        Check the last 3 candles for confirmation pattern
        
        Parameters:
        i: current index
        pattern_type: 'reversal_buy', 'reversal_sell', 'trend_buy', 'trend_sell'
        """
        if i < 2:
            return False
            
        c1 = self.data.iloc[i-2]  # candle 1
        c2 = self.data.iloc[i-1]  # candle 2
        c3 = self.data.iloc[i]    # candle 3
        
        if pattern_type == 'reversal_buy':
            # Candle 1: Strong bearish candle into support
            bearish = c1['close'] < c1['open'] and (c1['open'] - c1['close']) > (0.6 * (c1['high'] - c1['low']))
            
            # Candle 2: Small-bodied candle (doji/spinning top) showing indecision
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bullish candle closing above the high of Candle 2
            bullish = c3['close'] > c3['open'] and (c3['close'] - c3['open']) > (0.6 * (c3['high'] - c3['low']))
            above_prev_high = c3['close'] > c2['high']
            
            return bearish and small_body and bullish and above_prev_high
            
        elif pattern_type == 'reversal_sell':
            # Candle 1: Strong bullish candle into resistance
            bullish_c1 = c1['close'] > c1['open'] and (c1['close'] - c1['open']) > (0.6 * (c1['high'] - c1['low']))
            
            # Candle 2: Small-bodied candle (doji/spinning top) showing indecision
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            
            # Candle 3: Strong bearish candle closing below the low of Candle 2
            bearish = c3['close'] < c3['open'] and (c3['open'] - c3['close']) > (0.6 * (c3['high'] - c3['low']))
            below_prev_low = c3['close'] < c2['low']
            
            return bullish_c1 and small_body and bearish and below_prev_low
            
        elif pattern_type == 'trend_buy':
            # Candle 1: Pullback candle (bearish) closing above EMA-150
            bearish = c1['close'] < c1['open']
            above_ema = c1['close'] > self.data['ema_150'].iloc[i-2]
            
            # Candle 2: Small indecision candle near Alligator lips
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            near_lips = abs(c2['close'] - self.data['lips'].iloc[i-1]) < (0.001 * c2['close'])
            
            # Candle 3: Strong bullish candle breaking above Candle 2's high
            bullish = c3['close'] > c3['open'] and (c3['close'] - c3['open']) > (0.6 * (c3['high'] - c3['low']))
            above_prev_high = c3['close'] > c2['high']
            
            return bearish and above_ema and small_body and near_lips and bullish and above_prev_high
            
        elif pattern_type == 'trend_sell':
            # Candle 1: Pullback candle (bullish) closing below EMA-150
            bullish_c1 = c1['close'] > c1['open']
            below_ema = c1['close'] < self.data['ema_150'].iloc[i-2]
            
            # Candle 2: Small indecision candle near Alligator lips
            small_body = abs(c2['close'] - c2['open']) < (0.3 * (c2['high'] - c2['low']))
            near_lips = abs(c2['close'] - self.data['lips'].iloc[i-1]) < (0.001 * c2['close'])
            
            # Candle 3: Strong bearish candle breaking below Candle 2's low
            bearish = c3['close'] < c3['open'] and (c3['open'] - c3['close']) > (0.6 * (c3['high'] - c3['low']))
            below_prev_low = c3['close'] < c2['low']
            
            return bullish_c1 and below_ema and small_body and near_lips and bearish and below_prev_low
            
        return False
    
    def check_alligator_condition(self, i, condition_type):
        """
        Check Alligator conditions
        
        Parameters:
        i: current index
        condition_type: 'reversal' or 'trend'
        """
        lips = self.data['lips'].iloc[i]
        teeth = self.data['teeth'].iloc[i]
        jaw = self.data['jaw'].iloc[i]
        
        if condition_type == 'reversal':
            # Alligator lines contract or cross (showing trend exhaustion)
            # Check if lines are close to each other (contracting)
            diff_lips_teeth = abs(lips - teeth)
            diff_teeth_jaw = abs(teeth - jaw)
            diff_lips_jaw = abs(lips - jaw)
            
            avg_price = (lips + teeth + jaw) / 3
            threshold = 0.002 * avg_price  # 0.2% threshold
            
            contracting = (diff_lips_teeth < threshold and 
                          diff_teeth_jaw < threshold and 
                          diff_lips_jaw < threshold)
            
            # Check if lines are crossing
            lips_prev = self.data['lips'].iloc[i-1]
            teeth_prev = self.data['teeth'].iloc[i-1]
            jaw_prev = self.data['jaw'].iloc[i-1]
            
            crossing = (
                (lips > teeth and lips_prev < teeth_prev) or
                (lips < teeth and lips_prev > teeth_prev) or
                (teeth > jaw and teeth_prev < jaw_prev) or
                (teeth < jaw and teeth_prev > jaw_prev)
            )
            
            return contracting or crossing
            
        elif condition_type == 'trend_buy':
            # Alligator lines aligned bullish (Lips above Teeth above Jaw) and expanding
            aligned = lips > teeth > jaw
            expanding = (
                lips > self.data['lips'].iloc[i-1] and
                teeth > self.data['teeth'].iloc[i-1] and
                jaw > self.data['jaw'].iloc[i-1]
            )
            return aligned and expanding
            
        elif condition_type == 'trend_sell':
            # Alligator lines aligned bearish (Lips below Teeth below Jaw) and expanding
            aligned = lips < teeth < jaw
            expanding = (
                lips < self.data['lips'].iloc[i-1] and
                teeth < self.data['teeth'].iloc[i-1] and
                jaw < self.data['jaw'].iloc[i-1]
            )
            return aligned and expanding
            
        return False
    
    def check_stochastic_condition(self, i, condition_type):
        """
        Check Stochastic conditions
        
        Parameters:
        i: current index
        condition_type: 'reversal_buy', 'reversal_sell', 'trend_buy', 'trend_sell'
        """
        stoch_k = self.data['stoch_k'].iloc[i]
        stoch_k_prev = self.data['stoch_k'].iloc[i-1] if i > 0 else 50
        
        if condition_type == 'reversal_buy':
            # Stochastic is in oversold (below 20) and crossing upward
            oversold = stoch_k < 20
            crossing_up = stoch_k > stoch_k_prev and stoch_k_prev < 20
            return oversold or crossing_up
            
        elif condition_type == 'reversal_sell':
            # Stochastic is in overbought (above 80) and crossing downward
            overbought = stoch_k > 80
            crossing_down = stoch_k < stoch_k_prev and stoch_k_prev > 80
            return overbought or crossing_down
            
        elif condition_type == 'trend_buy':
            # Stochastic drops into 40-20 zone during a pullback, then turns upward
            in_zone = 20 <= stoch_k <= 40
            turning_up = stoch_k > stoch_k_prev
            return in_zone and turning_up
            
        elif condition_type == 'trend_sell':
            # Stochastic rises into 60-80 zone during a pullback, then turns downward
            in_zone = 60 <= stoch_k <= 80
            turning_down = stoch_k < stoch_k_prev
            return in_zone and turning_down
            
        return False
    
    def check_volatility_condition(self, i):
        """Check if volatility is sufficient (ATR > median ATR)"""
        return self.data['atr_14'].iloc[i] > self.data['atr_median'].iloc[i]
    
    def check_historical_bias(self, i, signal_type):
        """Check if zone has reversed price at least 2-3 times in recent candles"""
        min_reversals = 2
        if signal_type == 'buy':
            return self.data['reversal_count_buy'].iloc[i] >= min_reversals
        else:  # sell
            return self.data['reversal_count_sell'].iloc[i] >= min_reversals
    
    def check_price_near_fractal(self, i, signal_type):
        """Check if price is near a fractal level"""
        current_price = self.data['close'].iloc[i]
        threshold = 0.002 * current_price  # 0.2% threshold
        
        if signal_type == 'buy':
            # Check if price is near a fractal low
            recent_lows = self.data['fractal_low'][max(0, i-5):i+1]
            for j in range(len(recent_lows)):
                if recent_lows.iloc[j] == 1:
                    low_price = self.data['low'].iloc[max(0, i-5)+j]
                    if abs(current_price - low_price) < threshold:
                        return True
        else:  # sell
            # Check if price is near a fractal high
            recent_highs = self.data['fractal_high'][max(0, i-5):i+1]
            for j in range(len(recent_highs)):
                if recent_highs.iloc[j] == 1:
                    high_price = self.data['high'].iloc[max(0, i-5)+j]
                    if abs(current_price - high_price) < threshold:
                        return True
        return False
    
    def check_ema_trend(self, i, signal_type):
        """Check EMA trend condition"""
        if signal_type == 'trend_buy':
            # EMA sloping upward, price above EMA
            ema_slope_positive = self.data['ema_slope'].iloc[i] > 0
            price_above_ema = self.data['close'].iloc[i] > self.data['ema_150'].iloc[i]
            return ema_slope_positive and price_above_ema
        elif signal_type == 'trend_sell':
            # EMA sloping downward, price below EMA
            ema_slope_negative = self.data['ema_slope'].iloc[i] < 0
            price_below_ema = self.data['close'].iloc[i] < self.data['ema_150'].iloc[i]
            return ema_slope_negative and price_below_ema
        elif signal_type == 'reversal_buy':
            # Price is below EMA-150 for a while but approaching support
            price_below_ema = self.data['close'].iloc[i] < self.data['ema_150'].iloc[i]
            # Check if price has been below EMA for at least 5 periods
            below_for_while = all(self.data['close'].iloc[i-j] < self.data['ema_150'].iloc[i-j] 
                                 for j in range(1, min(6, i+1))) if i >= 5 else False
            return price_below_ema and below_for_while
        elif signal_type == 'reversal_sell':
            # Price is above EMA-150 for a while but approaching resistance
            price_above_ema = self.data['close'].iloc[i] > self.data['ema_150'].iloc[i]
            # Check if price has been above EMA for at least 5 periods
            above_for_while = all(self.data['close'].iloc[i-j] > self.data['ema_150'].iloc[i-j] 
                                 for j in range(1, min(6, i+1))) if i >= 5 else False
            return price_above_ema and above_for_while
        return False
    
    def generate_signals(self):
        """Generate trading signals based on the strategy rules"""
        signals = []
        
        for i in range(len(self.data)):
            signal = {
                'timestamp': self.data.index[i],
                'price': self.data['close'].iloc[i],
                'signal': 'hold',
                'type': None,
                'expiry': None,
                'confidence': 0
            }
            
            # Skip early candles without enough data
            if i < 20:
                signals.append(signal)
                continue
            
            # Check for reversal signals (5m timeframe only)
            if self.timeframe == '5m':
                # BUY (Call) reversal signal
                if (self.check_ema_trend(i, 'reversal_buy') and
                    self.check_alligator_condition(i, 'reversal') and
                    self.check_stochastic_condition(i, 'reversal_buy') and
                    self.check_volatility_condition(i) and
                    self.check_historical_bias(i, 'buy') and
                    self.check_price_near_fractal(i, 'buy') and
                    self.check_three_candle_pattern(i, 'reversal_buy')):
                    
                    signal['signal'] = 'buy'
                    signal['type'] = 'reversal'
                    signal['expiry'] = self.data.index[i] + timedelta(minutes=5)
                    signal['confidence'] = self.calculate_confidence(i, 'reversal_buy')
                
                # SELL (Put) reversal signal
                elif (self.check_ema_trend(i, 'reversal_sell') and
                      self.check_alligator_condition(i, 'reversal') and
                      self.check_stochastic_condition(i, 'reversal_sell') and
                      self.check_volatility_condition(i) and
                      self.check_historical_bias(i, 'sell') and
                      self.check_price_near_fractal(i, 'sell') and
                      self.check_three_candle_pattern(i, 'reversal_sell')):
                    
                    signal['signal'] = 'sell'
                    signal['type'] = 'reversal'
                    signal['expiry'] = self.data.index[i] + timedelta(minutes=5)
                    signal['confidence'] = self.calculate_confidence(i, 'reversal_sell')
            
            # Check for trend-following signals (1m, 2m, 3m timeframes)
            if self.timeframe in ['1m', '2m', '3m']:
                # BUY (Call) trend-following signal
                if (self.check_ema_trend(i, 'trend_buy') and
                    self.check_alligator_condition(i, 'trend_buy') and
                    self.check_stochastic_condition(i, 'trend_buy') and
                    self.check_volatility_condition(i) and
                    self.check_price_near_fractal(i, 'buy') and
                    self.check_three_candle_pattern(i, 'trend_buy')):
                    
                    signal['signal'] = 'buy'
                    signal['type'] = 'trend'
                    # Set expiry based on timeframe
                    expiry_minutes = 2 if self.timeframe == '1m' else (3 if self.timeframe == '2m' else 4)
                    signal['expiry'] = self.data.index[i] + timedelta(minutes=expiry_minutes)
                    signal['confidence'] = self.calculate_confidence(i, 'trend_buy')
                
                # SELL (Put) trend-following signal
                elif (self.check_ema_trend(i, 'trend_sell') and
                      self.check_alligator_condition(i, 'trend_sell') and
                      self.check_stochastic_condition(i, 'trend_sell') and
                      self.check_volatility_condition(i) and
                      self.check_price_near_fractal(i, 'sell') and
                      self.check_three_candle_pattern(i, 'trend_sell')):
                    
                    signal['signal'] = 'sell'
                    signal['type'] = 'trend'
                    # Set expiry based on timeframe
                    expiry_minutes = 2 if self.timeframe == '1m' else (3 if self.timeframe == '2m' else 4)
                    signal['expiry'] = self.data.index[i] + timedelta(minutes=expiry_minutes)
                    signal['confidence'] = self.calculate_confidence(i, 'trend_sell')
            
            signals.append(signal)
        
        return signals
    
    def calculate_confidence(self, i, signal_type):
        """Calculate confidence score based on conditions met"""
        confidence = 0
        
        # Each condition contributes to confidence
        if self.check_ema_trend(i, signal_type): confidence += 20
        if self.check_alligator_condition(i, 'reversal' if 'reversal' in signal_type else signal_type): confidence += 20
        if self.check_stochastic_condition(i, signal_type): confidence += 15
        if self.check_volatility_condition(i): confidence += 10
        if self.check_historical_bias(i, 'buy' if 'buy' in signal_type else 'sell'): confidence += 15
        if self.check_price_near_fractal(i, 'buy' if 'buy' in signal_type else 'sell'): confidence += 10
        if self.check_three_candle_pattern(i, signal_type): confidence += 10
        
        return min(100, confidence)
