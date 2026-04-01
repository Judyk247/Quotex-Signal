import pandas as pd
from datetime import datetime
import logging
from strategies.base_strategy import BinaryOptionsStrategy

logger = logging.getLogger(__name__)

class StrategyWrapper:
    """
    Feeds live candle data into your BinaryOptionsStrategy.
    Maintains rolling DataFrames per asset and triggers signals when they occur.
    """
    def __init__(self, timeframe, on_signal_callback, max_history=200):
        self.timeframe = timeframe
        self.on_signal = on_signal_callback
        self.max_history = max_history
        self.data = {}          # asset -> DataFrame
        self.strategies = {}    # asset -> BinaryOptionsStrategy instance

    def _get_strategy(self, asset):
        if asset not in self.strategies:
            # Create an empty DataFrame with the required columns
            df = pd.DataFrame(columns=['open','high','low','close','volume'])
            self.strategies[asset] = BinaryOptionsStrategy(df, self.timeframe)
        return self.strategies[asset]

    def _append_candle(self, asset, candle):
        """Append a new candle to the asset's DataFrame and trim."""
        if asset not in self.data:
            self.data[asset] = pd.DataFrame(columns=['open','high','low','close','volume'])
        new_row = pd.Series({
            'open': candle['open'],
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'volume': candle.get('volume', 0)
        }, name=candle['time'])
        self.data[asset] = pd.concat([self.data[asset], new_row.to_frame().T])
        # Keep only last max_history candles
        if len(self.data[asset]) > self.max_history:
            self.data[asset] = self.data[asset].iloc[-self.max_history:]

    def on_candle(self, asset, candle):
        """Called from the WebSocket client when a new candle arrives."""
        self._append_candle(asset, candle)
        if len(self.data[asset]) < 20:
            return   # not enough data yet

        # Update the strategy's internal data and recalculate indicators
        strat = self._get_strategy(asset)
        strat.data = self.data[asset].copy()
        strat.setup_indicators()

        # Generate signals for all candles, take the last one
        all_signals = strat.generate_signals()
        if all_signals and all_signals[-1]['signal'] != 'hold':
            sig = all_signals[-1]
            direction = 'call' if sig['signal'] == 'buy' else 'put'
            signal_dict = {
                'asset': asset,
                'direction': direction,
                'type': sig.get('type', 'unknown'),
                'expiry': sig['expiry'].timestamp() if hasattr(sig['expiry'], 'timestamp') else None,
                'timestamp': datetime.now().isoformat(),
                'price': sig['price'],
                'confidence': sig['confidence']
            }
            self.on_signal(signal_dict)
            logger.info(f"Signal: {signal_dict}")
