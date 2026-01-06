"""
Example Trading Strategy with Trade Statistics Integration

This is a complete example strategy demonstrating how to integrate
the DataframeTradeStatistics module into a Freqtrade strategy.

The strategy uses simple technical indicators (RSI, Bollinger Bands, EMA)
for entry and exit signals, and captures complete trade data for analysis.

Author: Freqtrade Trade Statistics Example
License: MIT
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

import talib
from pandas import DataFrame

from freqtrade.strategy import IStrategy, informative
from freqtrade.persistence import Trade, Order
from freqtrade.exchange import Exchange

# Import the trade statistics module
from dataframe_trade_stats import DataframeTradeStatistics

# Set up logging
logger = logging.getLogger(__name__)


class ExampleStrategy(IStrategy):
    """
    Example strategy with Trade Statistics integration.
    
    Uses RSI, Bollinger Bands, and EMA for trading signals.
    Integrates with DataframeTradeStatistics to track all trades.
    """

    MINIMAL_ROI = {
        "0": 0.10  # 10% profit target
    }

    STOPLOSS = -0.05  # 5% stop loss

    TRAILING_STOP = False
    TRAILING_STOP_POSITIVE = 0.01
    TRAILING_STOP_POSITIVE_OFFSET = 0.02
    TRAILING_ONLY_OFFSET_IS_REACHED = True

    TIMEFRAME = '15m'

    CAN_SHORT = False

    def __init__(self, config: Dict) -> None:
        """Initialize the strategy and trade statistics tracker."""
        super().__init__(config)
        
        # Initialize trade statistics collector
        self.trade_stats = DataframeTradeStatistics(
            enabled=config.get("store_trade_statistics", False) if config else False,
            auto_save_on_exit=True,
            strategy_name=self.version()
        )

        logger.info(f"Strategy initialized: {self.version()}")
        logger.info(f"Trade statistics enabled: {self.trade_stats.enabled}")

    def informative_pairs(self):
        """Return list of additional dataframe to download."""
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Add technical indicators to dataframe.
        These will be captured when trades enter.
        """
        
        # RSI - Relative Strength Index
        dataframe['rsi'] = talib.RSI(dataframe['close'], timeperiod=14)

        # Bollinger Bands
        dataframe['bb_upper'], dataframe['bb_middle'], dataframe['bb_lower'] = \
            talib.BBANDS(dataframe['close'], timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)

        # EMA - Exponential Moving Average
        dataframe['ema_9'] = talib.EMA(dataframe['close'], timeperiod=9)
        dataframe['ema_21'] = talib.EMA(dataframe['close'], timeperiod=21)
        dataframe['ema_50'] = talib.EMA(dataframe['close'], timeperiod=50)

        # MACD
        dataframe['macd'], dataframe['signal'], dataframe['histogram'] = \
            talib.MACD(dataframe['close'], fastperiod=12, slowperiod=26, signalperiod=9)

        # ATR - Average True Range
        dataframe['atr'] = talib.ATR(dataframe['high'], dataframe['low'], 
                                     dataframe['close'], timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define entry conditions.
        Multiple signals with different tags for analysis.
        """

        conditions = []
        
        # Signal 1: RSI Oversold + BB Lower Band
        signal1 = (
            (dataframe['rsi'] < 30) &  # RSI below 30 = oversold
            (dataframe['close'] < dataframe['bb_lower']) &  # Price below BB lower
            (dataframe['volume'] > 0)
        )
        conditions.append(signal1)
        dataframe.loc[signal1, 'enter_tag'] = 'rsi_bb_oversold'

        # Signal 2: EMA Crossover
        signal2 = (
            (dataframe['ema_9'] > dataframe['ema_21']) &  # Short EMA above long EMA
            (dataframe['ema_21'] > dataframe['ema_50']) &  # Medium above long
            (dataframe['rsi'] > 40) &  # RSI not too low
            (dataframe['rsi'] < 80) &  # RSI not overbought
            (dataframe['volume'] > 0)
        )
        conditions.append(signal2)
        dataframe.loc[signal2, 'enter_tag'] = 'ema_crossover'

        # Signal 3: RSI Bounce
        signal3 = (
            (dataframe['rsi'] < 25) &  # Very oversold
            (dataframe['close'] > dataframe['bb_lower']) &  # Starting to recover
            (dataframe['volume'] > 0)
        )
        conditions.append(signal3)
        dataframe.loc[signal3, 'enter_tag'] = 'rsi_bounce'

        # Combine all conditions
        if conditions:
            dataframe.loc[
                dataframe.index.isin(
                    dataframe[dataframe['enter_tag'].notna()].index
                ),
                'enter'] = 1
        else:
            dataframe['enter'] = 0

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Define exit conditions.
        """

        conditions = []

        # Exit 1: RSI Overbought
        exit1 = (
            (dataframe['rsi'] > 70) &
            (dataframe['volume'] > 0)
        )
        conditions.append(exit1)
        dataframe.loc[exit1, 'exit_tag'] = 'rsi_overbought'

        # Exit 2: EMA Crossover Reversal
        exit2 = (
            (dataframe['ema_9'] < dataframe['ema_21']) &
            (dataframe['volume'] > 0)
        )
        conditions.append(exit2)
        dataframe.loc[exit2, 'exit_tag'] = 'ema_reversal'

        # Exit 3: Close below BB Middle
        exit3 = (
            (dataframe['close'] < dataframe['bb_middle']) &
            (dataframe['rsi'] < 50) &
            (dataframe['volume'] > 0)
        )
        conditions.append(exit3)
        dataframe.loc[exit3, 'exit_tag'] = 'bb_middle_reversal'

        # Combine all conditions
        if conditions:
            dataframe.loc[
                dataframe.index.isin(
                    dataframe[dataframe['exit_tag'].notna()].index
                ),
                'exit'] = 1
        else:
            dataframe['exit'] = 0

        return dataframe

    def order_filled(self, pair: str, trade: Trade, order: Order,
                     current_time: datetime, **kwargs) -> None:
        """
        Called every time an order has been fulfilled.
        Capture entry candles for statistics.
        """
        
        if order.side == 'buy' and order.status == 'closed':
            
            if self.trade_stats.enabled:
                try:
                    # Get the analyzed dataframe
                    dataframe, _ = self.dp.get_analyzed_dataframe(
                        trade.pair, self.timeframe
                    )
                    
                    # Get the last candle with all indicators
                    if len(dataframe) > 0:
                        last_candle = dataframe.iloc[-1].squeeze()
                        
                        # Store the entry candle
                        self.trade_stats.store_entry_dataframe(
                            pair=pair,
                            trade=trade,
                            candle=last_candle,
                            current_time=current_time
                        )
                        
                        logger.debug(
                            f"Captured entry for {pair}: "
                            f"RSI={last_candle.get('rsi', 'N/A'):.2f}, "
                            f"Price={last_candle.get('close', 'N/A'):.4f}"
                        )
                
                except Exception as e:
                    logger.error(f"Error capturing entry candle for {pair}: {str(e)}")

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                          amount: float, rate: float, time_in_force: str,
                          exit_reason: str, current_time: datetime,
                          **kwargs) -> bool:
        """
        Called right before a trade will be exited.
        Store exit profit for statistics.
        """
        
        if self.trade_stats.enabled:
            try:
                self.trade_stats.store_exit_profit(
                    pair=pair,
                    trade=trade,
                    exit_rate=rate,
                    exit_reason=exit_reason
                )
                
                profit = trade.calc_profit_ratio(rate)
                logger.debug(
                    f"Stored exit for {pair}: "
                    f"Profit={profit:.2%}, "
                    f"Reason={exit_reason}"
                )
            
            except Exception as e:
                logger.error(f"Error storing exit profit for {pair}: {str(e)}")
        
        return True

    def bot_loop_start(self, current_time: datetime, **kwargs) -> None:
        """
        Called at the start of every bot loop.
        Log current statistics.
        """
        
        if self.trade_stats.enabled and len(self.trade_stats) > 0:
            stats = self.trade_stats.get_statistics_summary()
            logger.info(
                f"Trade Statistics - "
                f"Total: {stats['total_trades']}, "
                f"Win Rate: {stats['win_rate']}, "
                f"Avg Profit: {stats['avg_profit']:.4f}"
            )

    def version(self) -> str:
        """Return strategy version."""
        return "ExampleStrategy_v1.0"
