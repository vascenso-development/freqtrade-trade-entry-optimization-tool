# Freqtrade Trade Optimization Tool

> Track entry dataframes and profits for trades in Freqtrade backtests with comprehensive indicator analysis and visualization.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Freqtrade Compatible](https://img.shields.io/badge/Freqtrade-Compatible-brightgreen.svg)](https://www.freqtrade.io)

## 📋 Overview

**Freqtrade Trade Optimization Tool** is a comprehensive toolkit for analyzing Freqtrade trading strategies. It captures the exact market conditions (OHLCV + technical indicators) when trades are entered and records exit profits, then provides an interactive web-based dashboard for analyzing trade patterns and generating optimization recommendations.

**Use only in backtests** 

## 🎨 Live Demo Dashboard

🚀 **[Open the Trade Optimization Tool Dashboard](https://vascenso-development.github.io/freqtrade-trade-entry-optimization-tool/Trade%20Statistics%20Analysis.html)**


### Key Features

✅ **Capture Entry Candles** - Store complete OHLCV + indicators at trade entry  
✅ **Track Exit Profits** - Record profit/loss and exit reasons  
✅ **Auto-Save Protection** - Crash-safe incremental JSON saves  
✅ **Interactive Analysis** - Web-based dashboard with drag-and-drop JSON upload  
✅ **Smart Recommendations** - Identify winning indicator ranges and optimization opportunities  
✅ **Demo Mode** - Explore features without your own trade data  
✅ **Professional Exports** - Clean, structured JSON for further analysis  

## 🎯 Idea & Credits

**Original Concept**: Vascenso Development  
**Implementation**: AI assisted development  
**Community**: We welcome contributions! Found a bug? Have an idea? Please open an issue or submit a PR!


**No installation needed!** 
- Click the link above to open in your browser
- Click "⚡ Load Demo Data" to see example trades
- Or upload your own trade statistics in JSON file

### Demo Features
- View complete trade analysis
- See entry indicator values
- Analyze winning vs losing trades
- Get optimization recommendations

## 🚀 Quick Start

### Installation

1. **Copy the module to your Freqtrade strategy directory:**

```bash
cp dataframe_trade_stats.py /path/to/freqtrade/user_data/strategies/
```

2. **Import in your strategy:**

```python
from dataframe_trade_stats import DataframeTradeStatistics
```

### Basic Usage

#### 1. Initialize in `__init__`

```python
class YourStrategy(IStrategy):
    
    def __init__(self, config: Dict):
        super().__init__(config)
        
        # Initialize trade statistics tracker
        self.trade_stats = DataframeTradeStatistics(
            enabled=config.get("store_trade_statistics", False) if config else False,
            auto_save_on_exit=True,
            strategy_name=self.version()
        )
```

#### 2. Capture Entry Candles in `order_filled`

Called when a buy order is filled:

```python
def order_filled(self, pair: str, trade: Trade, order: Order, 
                 current_time: datetime, **kwargs) -> None:
    """
    Called every time an order has been fulfilled.
    """
    if order.side == 'buy' and order.status == 'closed':
        # Capture the entry candle with all indicators
        if self.trade_stats.enabled:
            dataframe, _ = self.dp.get_analyzed_dataframe(trade.pair, self.timeframe)
            last_candle = dataframe.iloc[-1].squeeze()
            self.trade_stats.store_entry_dataframe(
                pair=pair, 
                trade=trade, 
                candle=last_candle,
                current_time=current_time
            )
```

#### 3. Store Exit Profit in `confirm_trade_exit`

Called when exiting a trade:

```python
def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, 
                       amount: float, rate: float, time_in_force: str, 
                       exit_reason: str, current_time: datetime, **kwargs) -> bool:
    """
    Called right before a trade will be exited.
    """
    if self.trade_stats.enabled:
        self.trade_stats.store_exit_profit(
            pair=pair,
            trade=trade,
            exit_rate=rate,
            exit_reason=exit_reason
        )
    
    return True
```

#### 4. Enable in Backtest Config

Add to your `backtest_config.json`:

```json
{
    "store_trade_statistics": true
}
```

### Complete Example Strategy

See `examples/example_strategy.py` for a complete working example with entry/exit signals and trade statistics integration.

## 📊 Trade Statistics Output

The module generates a structured JSON file with all trade data:

```json
{
  "metadata": {
    "export_time": "2026-01-06T17:30:00.123456",
    "total_trades": 150,
    "trades_with_profit": 95,
    "win_rate": "63.33%",
    "mode": "final_export"
  },
  "trades": {
    "enter_signal_BTC/USDT_2026-01-01T12:00:00": {
      "entry_candle": {
        "open": 42500.50,
        "high": 42750.00,
        "low": 42400.00,
        "close": 42650.00,
        "volume": 250.5,
        "rsi": 65.2,
        "bb_upper": 43100.0,
        "bb_lower": 42200.0,
        "macd": 250.5
      },
      "entry_price": 42650.00,
      "entry_time": "2026-01-01T12:00:00+00:00",
      "pair": "BTC/USDT",
      "enter_tag": "enter_signal",
      "amount": 0.5,
      "profit": 0.0245,
      "profit_abs": 125.50,
      "exit_price": 43678.00,
      "exit_reason": "exit_signal",
      "trade_duration_candles": 12
    }
  }
}
```

## 🎨 Interactive Dashboard

### Using the Web Interface

1. **Open `Trade-Statistics-Analysis.html` in your browser**
2. **Choose your data source:**
   - 📤 Upload your trade statistics JSON
   - ⚡ Load demo data to explore features
3. **Analyze your trades:**
   - View winning vs losing trades
   - Identify successful indicator ranges
   - Get optimization recommendations
   - Apply recommendations to your strategy
   - See results 
   - Aim is to remove negative profit trades

### Dashboard Features

| Feature | Description |
|---------|-------------|
| **Trade Overview** | Total trades, win rate, profit distribution |
| **Winning Trades** | Filter and analyze only profitable trades |
| **Losing Trades** | Understand what went wrong |
| **Indicator Ranges** | See ranges that work for winners/losers |
| **Recommendations** | Indicators optimization suggestions |
| **Sorting** | Sort by profit, confidence, or indicator name |

## 🔧 API Reference

### DataframeTradeStatistics Class

#### Initialization

```python
DataframeTradeStatistics(
    enabled: bool = False,
    auto_save_on_exit: bool = True,
    output_dir: str = "user_data/trade_statistics",
    strategy_name: str = "YourStrategy"
)
```

**Parameters:**
- `enabled` - Enable/disable statistics collection (default: False)
- `auto_save_on_exit` - Auto-save JSON after each trade exits (default: True)
- `output_dir` - Directory for output files (default: `user_data/trade_statistics`)
- `strategy_name` - Strategy name for file naming (default: "YourStrategy")

#### Methods

##### `store_entry_dataframe(pair, trade, candle, current_time)`

Store the last candle when a buy order is filled.

```python
self.trade_stats.store_entry_dataframe(
    pair='BTC/USDT',
    trade=trade_object,
    candle=dataframe.iloc[-1].squeeze(),
    current_time=current_time
)
```

##### `store_exit_profit(pair, trade, exit_rate, exit_reason)`

Store profit when a trade is exited.

```python
self.trade_stats.store_exit_profit(
    pair='BTC/USDT',
    trade=trade_object,
    exit_rate=43678.00,
    exit_reason='exit_signal'
)
```

##### `export_to_json(output_path=None)`

Export all collected trade statistics to JSON.

```python
json_file = self.trade_stats.export_to_json(
    output_path='my_trades.json'
)
```

**Returns:** Path to the generated JSON file

##### `get_statistics_summary()`

Get a summary of collected statistics anytime.

```python
summary = self.trade_stats.get_statistics_summary()
print(f"Total Trades: {summary['total_trades']}")
print(f"Win Rate: {summary['win_rate']}")
print(f"Avg Profit: {summary['avg_profit']:.2%}")
```

**Returns:** Dictionary with statistics summary

##### `clear()`

Clear all stored trade data (useful for sequential backtests).

```python
self.trade_stats.clear()
```

## 💡 Use Cases

### 1. **Indicator Optimization**
Find the indicator ranges that correlate with winning trades. Use dashboard recommendations to refine your entry conditions.

### 2. **Strategy Backtesting**
Capture complete market conditions at entry. Replay exact scenarios to test improvements.

### 3. **Risk Analysis**
Analyze losing trades to understand failure patterns. Identify conditions to avoid.

### 4. **Performance Tracking**
Monitor strategy performance across multiple backtests. Compare win rates and profit metrics.

### 5. **Signal Validation**
Verify that your technical indicators are working as expected. See the exact values when entries occur.

## 🎓 Examples

### Example 1: Basic Strategy Integration

```python
class MyStrategy(IStrategy):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.trade_stats = DataframeTradeStatistics(
            enabled=True,
            strategy_name=self.version()
        )
    
    def order_filled(self, pair: str, trade: Trade, order: Order,
                     current_time: datetime, **kwargs) -> None:
        if order.side == 'buy' and order.status == 'closed':
            if self.trade_stats.enabled:
                dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
                last_candle = dataframe.iloc[-1].squeeze()
                self.trade_stats.store_entry_dataframe(
                    pair, trade, last_candle, current_time
                )
    
    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str,
                          amount: float, rate: float, time_in_force: str,
                          exit_reason: str, current_time: datetime,
                          **kwargs) -> bool:
        if self.trade_stats.enabled:
            self.trade_stats.store_exit_profit(pair, trade, rate, exit_reason)
        return True
```

## ⚙️ Configuration

### Strategy Configuration

Add to your strategy config:

```python
{
    "store_trade_statistics": true,
    "user_data_dir": "user_data",
}
```

### Output Directory

By default, statistics are saved to: `user_data/trade_statistics/`

Custom directory:

```python
self.trade_stats = DataframeTradeStatistics(
    enabled=True,
    output_dir="my_custom_path/trades"
)
```

## 🐛 Troubleshooting

### Issue: Trade data not being captured

**Solution:** Verify that:
1. `enabled=True` in DataframeTradeStatistics initialization
2. `store_trade_statistics: true` in config
3. `order_filled` and `confirm_trade_exit` are properly implemented

### Issue: JSON file not created

**Solution:** Check that:
1. Output directory exists or is writable
2. Strategy reaches trade exit (check backtest results)
3. Check logs for error messages

### Issue: Indicators showing as null

**Solution:**
1. Ensure indicators are calculated in `populate_indicators()`
2. Add sufficient history periods for indicator calculation
3. Use `dataframe.iloc[-1].squeeze()` to get complete last candle


## 🤝 Contributing

We welcome contributions! Whether it's:
- 🐛 Bug reports
- 💡 Feature ideas
- 📝 Documentation improvements
- 🔧 Code enhancements

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## 📋 Requirements

- **Python**: 3.8+
- **Freqtrade**: Latest stable version
- **Dependencies**:
  - pandas
  - numpy
  - freqtrade

## 📝 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.


## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/vascenso-development/freqtrade-trade-entry-optimization-tool/issues)
- **Discussions**: [GitHub Discussions](https://github.com/vascenso-development/freqtrade-trade-entry-optimization-tool/discussions)
- **Freqtrade Community**: [Freqtrade Docs](https://www.freqtrade.io)

## 🔗 Related Projects

- [Freqtrade](https://www.freqtrade.io) - Free, open source crypto trading bot

## 📊 Project Stats

- ⭐ Star the repo if you find it useful!
- 🔗 Link to us in your strategy documentation
- 📢 Share with the crypto trading community

---

**Made with ❤️ for the Freqtrade Community**
