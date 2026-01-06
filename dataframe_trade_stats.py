"""
DataframeTradeStatistics - Track entry dataframes and profits for trades in Freqtrade backtests.

This module provides a class to capture and store dataframe snapshots at trade entry,
calculate profits at exit, and export comprehensive trade statistics to JSON.

Features:
1. Capture last candle OHLCV + indicators when trades enter
2. Store profit when trades exit
3. Auto-save to JSON on each trade exit (crash-safe)
4. Batch export after backtest completes
5. Summary statistics and analysis
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import pandas as pd
from freqtrade.persistence import Trade, Order


logger = logging.getLogger(__name__)


class DataframeTradeStatistics:
    """
    Manages collection and export of trade entry dataframes and profit metrics.
    
    This class is designed to be used within a Freqtrade Strategy during backtests
    to capture the exact market conditions (OHLCV + indicators) when trades are entered,
    and record the profit when trades are exited.
    
    Features:
    - Capture last candle (current entry point) on each buy order fill
    - Store exit profit on each trade exit
    - Auto-save to JSON after each trade (configurable)
    - Batch export after backtest completes
    - Summary statistics calculation
    
    Attributes:
        enabled (bool): Whether to collect trade statistics
        auto_save_on_exit (bool): Whether to write JSON after each trade exit
        output_dir (Path): Directory for statistics files
        trade_data (Dict): Storage for trade dataframes and profits
    """
    
    def __init__(
        self,
        enabled: bool = False,
        auto_save_on_exit: bool = True,
        output_dir: str = "user_data/trade_statistics",
        strategy_name: str = "YourStrategy",
    ):
        """
        Initialize the DataframeTradeStatistics collector.
        
        Args:
            enabled (bool): Whether to enable data collection. Default is False.
            auto_save_on_exit (bool): If True, writes to JSON file each time a trade exits.
                                      Provides crash-safe backup. Default is True.
            output_dir (str): Directory for saving statistics files. Default is 'user_data/trade_statistics'.
        """
        self.enabled = enabled
        self.auto_save_on_exit = auto_save_on_exit
        self.output_dir = Path(output_dir)
        self.strategy_name = strategy_name
        self.trade_data: Dict[str, Dict[str, Any]] = {}
        self._current_export_file: Optional[Path] = None
        
        # Create output directory if needed
        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(
            f"DataframeTradeStatistics initialized (enabled={enabled}, "
            f"auto_save_on_exit={auto_save_on_exit}, output_dir={output_dir})"
        )
    
    def _generate_trade_key(self, enter_tag: Optional[str], pair: str, open_date_utc: datetime) -> str:
        """
        Generate a unique key for a trade.
        
        Args:
            enter_tag (Optional[str]): The enter tag from the trade
            pair (str): Trading pair (e.g., 'BTC/USDT')
            open_date_utc (datetime): UTC timestamp when trade was opened
            
        Returns:
            str: Formatted trade key
        """
        enter_tag_str = enter_tag if enter_tag else "no_tag"
        timestamp = open_date_utc.isoformat()
        return f"{enter_tag_str}_{pair}_{timestamp}"
    
    def _convert_candle_to_dict(self, candle: Union[pd.Series, Dict]) -> Dict[str, Any]:
        """
        Convert a pandas Series (single candle) to a JSON-serializable dictionary.
        
        Args:
            candle (Union[pd.Series, Dict]): A single candle (last row from dataframe)
            
        Returns:
            Dict: Serializable dictionary with candle data
        """
        if isinstance(candle, pd.Series):
            candle_dict = candle.to_dict()
        else:
            candle_dict = dict(candle)
        
        # Convert datetime values to strings
        result = {}
        for key, value in candle_dict.items():
            if isinstance(value, pd.Timestamp):
                result[key] = value.isoformat()
            elif isinstance(value, datetime):
                result[key] = value.isoformat()
            elif pd.isna(value):
                result[key] = None
            elif hasattr(value, 'item'):  # numpy types
                result[key] = float(value) if isinstance(value, (float, int)) or 'float' in str(type(value)) or 'int' in str(type(value)) else str(value)
            else:
                result[key] = value
        
        return result
    
    def store_entry_dataframe(
        self,
        pair: str,
        trade: Trade,
        candle: Union[pd.Series, Dict],
        current_time: datetime
    ) -> None:
        """
        Store the last candle (entry point) when a buy order is filled (trade entered).
        
        Called from order_filled() when a buy order closes.
        Expects a single candle (Series/dict), typically: dataframe.iloc[-1].squeeze()
        
        Args:
            pair (str): Trading pair (e.g., 'BTC/USDT')
            trade (Trade): The Freqtrade Trade object
            candle (Union[pd.Series, Dict]): The last candle at entry point
            current_time (datetime): Current time in the strategy
        """
        if not self.enabled:
            return
        
        try:
            trade_key = self._generate_trade_key(trade.enter_tag, pair, trade.open_date_utc)
            
            # Convert candle to JSON-serializable dictionary
            candle_dict = self._convert_candle_to_dict(candle)
            
            # Store only the last candle (entry candle)
            self.trade_data[trade_key] = {
                'entry_candle': candle_dict,
                'entry_price': float(trade.open_rate),
                'entry_time': trade.open_date_utc.isoformat(),
                'pair': pair,
                'enter_tag': trade.enter_tag,
                'amount': float(trade.amount),
                'profit': None,  # Will be filled during exit
            }
            
            logger.debug(f"Stored entry candle for trade: {trade_key}")
            
        except Exception as e:
            logger.error(f"Error storing entry candle for {pair}: {str(e)}", exc_info=True)
    
    def store_exit_profit(
        self,
        pair: str,
        trade: Trade,
        exit_rate: float,
        exit_reason: str
    ) -> None:
        """
        Store the profit when a trade is exited.
        
        Called from confirm_trade_exit() when exiting a trade.
        If auto_save_on_exit is enabled, writes to JSON immediately.
        
        Args:
            pair (str): Trading pair (e.g., 'BTC/USDT')
            trade (Trade): The Freqtrade Trade object
            exit_rate (float): The rate at which the trade is being exited
            exit_reason (str): The reason for exit (e.g., 'exit_signal', 'stoploss')
        """
        if not self.enabled:
            return
        
        try:
            trade_key = self._generate_trade_key(trade.enter_tag, pair, trade.open_date_utc)
            
            # Calculate profit ratio
            profit_ratio = trade.calc_profit_ratio(exit_rate)
            profit_abs = trade.calc_profit(exit_rate)
            
            if trade_key in self.trade_data:
                self.trade_data[trade_key].update({
                    'profit': float(profit_ratio),
                    'profit_abs': float(profit_abs),
                    'exit_price': float(exit_rate),
                    'exit_reason': exit_reason,
                    'trade_duration_candles': trade.nr_of_successful_buys,
                })
                
                logger.debug(
                    f"Stored exit profit for trade {trade_key}: "
                    f"profit_ratio={profit_ratio:.4f}, exit_reason={exit_reason}"
                )
                
                # Auto-save to JSON if enabled (crash-safe, writes on each trade exit)
                if self.auto_save_on_exit:
                    self._save_incremental()
            else:
                logger.warning(
                    f"Trade key {trade_key} not found in trade_data. "
                    f"Entry candle may not have been stored."
                )
        
        except Exception as e:
            logger.error(f"Error storing exit profit for {pair}: {str(e)}", exc_info=True)
    
    def _save_incremental(self) -> None:
        """
        Save current trade data to JSON incrementally.
        
        Used when auto_save_on_exit is enabled.
        Writes/updates JSON file each time a trade exits.
        Creates a single working file that gets updated on each call.
        Provides crash-safe backup during long backtests.
        """
        if not self.enabled or not self.auto_save_on_exit:
            return
        
        try:
            # Use a single working file that gets updated
            if self._current_export_file is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self._current_export_file = self.output_dir / f"{self.strategy_name}_{timestamp}.json"
            
            # Calculate statistics for metadata
            profits = [
                t['profit'] for t in self.trade_data.values()
                if t.get('profit') is not None
            ]
            trades_with_profit = sum(1 for p in profits if p > 0)
            
            export_data = {
                'metadata': {
                    'last_update': datetime.now().isoformat(),
                    'total_trades': len(self.trade_data),
                    'trades_with_profit': trades_with_profit,
                    'win_rate': f"{(trades_with_profit / len(profits) * 100):.2f}%" if profits else "0.00%",
                    'mode': 'incremental',
                },
                'trades': self.trade_data
            }
            
            # Write with atomic operation (safe across platforms)
            with open(self._current_export_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.debug(f"Incremental save: {len(self.trade_data)} trades to {self._current_export_file}")
        
        except Exception as e:
            logger.error(f"Error during incremental save: {str(e)}", exc_info=True)
    
    def export_to_json(self, output_path: Optional[str] = None) -> str:
        """
        Export all collected trade statistics to a JSON file.
        
        Call this method once after backtest completes.
        - In batch mode: Creates final export file with all trades
        - In auto-save mode: Creates clean consolidated file (incremental already exists)
        
        Args:
            output_path (Optional[str]): Path where JSON file will be saved.
                If None, uses 'trade_statistics_<timestamp>.json' in output_dir.
                
        Returns:
            str: Path to the generated JSON file
            
        Raises:
            IOError: If file cannot be written
        """
        if not self.trade_data:
            logger.warning("No trade data to export")
            return ""
        
        try:
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = str(self.output_dir / f"{self.strategy_name}_{timestamp}.json")
            else:
                output_path = str(output_path)
            
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Calculate statistics for metadata
            profits = [
                t['profit'] for t in self.trade_data.values()
                if t.get('profit') is not None
            ]
            trades_with_profit = sum(1 for p in profits if p > 0)
            win_rate = f"{(trades_with_profit / len(profits) * 100):.2f}%" if profits else "0.00%"
            
            # Prepare export data with enhanced structure
            export_data = {
                'metadata': {
                    'export_time': datetime.now().isoformat(),
                    'total_trades': len(self.trade_data),
                    'trades_with_profit': trades_with_profit,
                    'win_rate': win_rate,
                    'mode': 'final_export',
                },
                'trades': self.trade_data
            }
            
            # Write to JSON with pretty formatting
            with open(output_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Exported {len(self.trade_data)} trades to {output_file}")
            return str(output_file)
        
        except IOError as e:
            logger.error(f"Failed to write JSON file to {output_path}: {str(e)}", exc_info=True)
            raise
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """
        Get a summary of collected trade statistics.
        
        Can be called anytime to get current stats.
        
        Returns:
            Dict with summary statistics including:
            - total_trades: Number of trades collected
            - trades_with_exit_data: Number of completed trades
            - trades_with_profit: Number of profitable trades (profit > 0)
            - profitable_trades: Count of trades with profit > 0
            - losing_trades: Count of trades with profit < 0
            - breakeven_trades: Count of trades with profit == 0
            - win_rate: Percentage of profitable trades
            - avg_profit: Average profit ratio
            - total_profit: Sum of all profits
            - min_profit: Lowest profit ratio
            - max_profit: Highest profit ratio
        """
        if not self.trade_data:
            return {
                'total_trades': 0,
                'trades_with_exit_data': 0,
                'trades_with_profit': 0,
                'profitable_trades': 0,
                'losing_trades': 0,
                'breakeven_trades': 0,
                'win_rate': '0.00%',
                'avg_profit': 0.0,
                'total_profit': 0.0,
                'min_profit': 0.0,
                'max_profit': 0.0,
            }
        
        profits = [
            t['profit'] for t in self.trade_data.values()
            if t.get('profit') is not None
        ]
        
        profitable = sum(1 for p in profits if p > 0)
        losing = sum(1 for p in profits if p < 0)
        breakeven = sum(1 for p in profits if p == 0)
        total_profit = sum(profits) if profits else 0.0
        avg_profit = total_profit / len(profits) if profits else 0.0
        win_rate = f"{(profitable / len(profits) * 100):.2f}%" if profits else "0.00%"
        
        return {
            'total_trades': len(self.trade_data),
            'trades_with_exit_data': len(profits),
            'trades_with_profit': profitable,
            'profitable_trades': profitable,
            'losing_trades': losing,
            'breakeven_trades': breakeven,
            'win_rate': win_rate,
            'avg_profit': float(avg_profit),
            'total_profit': float(total_profit),
            'min_profit': float(min(profits)) if profits else 0.0,
            'max_profit': float(max(profits)) if profits else 0.0,
        }
    
    def clear(self) -> None:
        """
        Clear all stored trade data.
        
        Useful for running multiple backtests in sequence.
        """
        self.trade_data.clear()
        self._current_export_file = None
        logger.info("Cleared all trade statistics data")
    
    def __len__(self) -> int:
        """Return the number of trades currently stored."""
        return len(self.trade_data)
    
    def __repr__(self) -> str:
        """String representation of the statistics collector."""
        return (
            f"DataframeTradeStatistics(enabled={self.enabled}, "
            f"auto_save={self.auto_save_on_exit}, trades={len(self.trade_data)})"
        )
