# Candlestick Data Integration - Summary

## What's New

The Spread Tools pipeline now incorporates candlestick data from three integrated databases, enriching arbitrage analysis with market microstructure information.

### New Files

1. **candlestick_loader.py** - Utility module for loading and processing candlestick data
   - `CandlestickLoader` class: Loads OHLC data from kalshi_candlesticks.db
   - `UnifiedMarketDataLoader` class: Loads unified market data with trades and candlesticks merged

### Enhanced Files

1. **arbitrage_tracker.py**
   - Added `candlestick_db` parameter to initialization
   - Added `include_candlesticks` flag (default: True)
   - Automatic candlestick enrichment of arbitrage events
   - New columns in output CSV: market1_candle_* and market2_candle_*
   - Command-line args: `--candledb` and `--no-candlesticks`

2. **spread_visualizer.py**
   - Added `candlestick_db` and `use_candlesticks` parameters
   - New method: `plot_candlesticks_for_events()` - Visualize candlesticks during arbitrage
   - New method: `load_candlesticks_for_market()` - Load candlestick data
   - New method: `get_candlestick_summary()` - Aggregate OHLC metrics
   - Command-line args: `--candlesticks`, `--market1`, `--market2`, `--candledb`, `--no-candlesticks`

### Documentation

- **CANDLESTICK_INTEGRATION.md** - Comprehensive guide with usage examples and API reference

## Quick Start

### Analyze arbitrage with candlestick enrichment (default behavior):
```bash
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02
```
Output CSV will include candlestick metrics for each market.

### Visualize candlesticks during arbitrage events:
```bash
python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --candlesticks \
  --market1 KXMLBGAME-25SEP28BALNYY-BAL --market2 KXMLBGAME-25SEP28BALNYY-NYY
```

## Candlestick Data Included

For each arbitrage event, the following metrics are captured for both markets:
- **Volume**: Total contracts traded
- **OHLC**: Open, High, Low, Close prices (midpoint)
- **Bid-Ask OHLC**: Separate bid and ask side prices
- **Candle Count**: Number of 1-minute candles in the event

## Key Features

✅ Automatic enrichment during arbitrage analysis
✅ Optional candlestick visualization with traditional candlestick charts
✅ Seamless integration with existing tools (backward compatible)
✅ Configurable database paths
✅ Easy enable/disable with command-line flags

## Database Files Used

- **kalshi_candlesticks.db** - 1-minute OHLC candles with bid/ask data
- **kalshi_unified_market_data.db** - Unified market data (optional)
- **kalshi_event_market_map.db** - Event to market ticker mapping

## Backward Compatibility

All existing functionality remains unchanged. Candlestick enrichment is enabled by default but can be disabled with the `--no-candlesticks` flag.

See [CANDLESTICK_INTEGRATION.md](CANDLESTICK_INTEGRATION.md) for detailed documentation.
