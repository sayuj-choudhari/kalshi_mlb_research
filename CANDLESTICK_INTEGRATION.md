"""
CANDLESTICK DATA INTEGRATION GUIDE

This document explains how candlestick data has been integrated into the spread tools pipeline.
"""

# =============================================================================
# OVERVIEW
# =============================================================================

The spread tools pipeline has been enhanced to incorporate candlestick data from three 
integrated databases:

1. kalshi_candlesticks.db - OHLC candlestick data (1-minute intervals)
2. kalshi_unified_market_data.db - Unified market data (trades merged with candlesticks)
3. kalshi_event_market_map.db - Event to market ticker mapping

Candlestick data is automatically enriched into arbitrage events and can be visualized
alongside spread and volume data.


# =============================================================================
# COMPONENTS ADDED
# =============================================================================

1. candlestick_loader.py
   - CandlestickLoader class: Fetches candlestick data from kalshi_candlesticks.db
   - UnifiedMarketDataLoader class: Fetches unified market data
   - Methods to enrich arbitrage events with candlestick metrics

2. arbitrage_tracker.py (Enhanced)
   - Added candlestick_db parameter to track initialization
   - Added include_candlesticks flag to enable/disable candlestick enrichment
   - Candlestick data automatically merged into CSV output
   - New columns added to output: market1_candle_* and market2_candle_*

3. spread_visualizer.py (Enhanced)
   - Added candlestick_db parameter to visualizer initialization
   - New method: load_candlesticks_for_market() - Load candlesticks for a market
   - New method: plot_candlesticks_for_events() - Visualize candlesticks during arb events
   - New method: get_candlestick_summary() - Aggregate candlestick metrics


# =============================================================================
# CANDLESTICK DATA FIELDS
# =============================================================================

Each candlestick record includes:

OHLC Prices (midpoint):
  - open: Opening price
  - high: Highest price
  - low: Lowest price
  - close: Closing price

Ask-side OHLC:
  - ask_open, ask_high, ask_low, ask_close

Bid-side OHLC:
  - bid_open, bid_high, bid_low, bid_close

Metadata:
  - volume: Number of contracts traded in the 1-minute period
  - end_period_ts: Timestamp of the end of the candle


# =============================================================================
# ENHANCED ARBITRAGE TRACKER OUTPUT
# =============================================================================

When candlestick enrichment is enabled, the arbitrage CSV output includes new columns:

For each market (market1 and market2):
  - market1_candle_volume: Total volume during arbitrage event
  - market1_candle_open: Opening price
  - market1_candle_high: Highest price
  - market1_candle_low: Lowest price
  - market1_candle_close: Closing price
  - market1_candle_ask_open, ask_high, ask_low, ask_close: Ask-side OHLC
  - market1_candle_bid_open, bid_high, bid_low, bid_close: Bid-side OHLC
  - market1_candle_num_candles: Number of 1-minute candles in the event

This allows analysis of:
  - Price movement during arbitrage opportunities
  - Bid-ask spread behavior
  - Volume traded during specific spread conditions


# =============================================================================
# USAGE: ARBITRAGE TRACKER WITH CANDLESTICKS
# =============================================================================

Basic usage (candlesticks enabled by default):
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02

Disable candlestick enrichment:
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --no-candlesticks

Specify custom candlestick database:
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --candledb /path/to/db.db

The output CSV file will include candlestick metrics for each market pair.


# =============================================================================
# USAGE: SPREAD VISUALIZER WITH CANDLESTICKS
# =============================================================================

1. Basic spread and volume plot (no candlesticks):
   python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02

2. Timeline plot (no candlesticks):
   python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --timeline

3. CANDLESTICK VISUALIZATION (New):
   python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --candlesticks \
     --market1 KXMLBGAME-25SEP28BALNYY-BAL --market2 KXMLBGAME-25SEP28BALNYY-NYY

4. Save candlestick plot to file:
   python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --candlesticks \
     --market1 KXMLBGAME-25SEP28BALNYY-BAL --market2 KXMLBGAME-25SEP28BALNYY-NYY \
     --save candlesticks_plot.png

5. Filter by arbitrage pair and show candlesticks:
   python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --candlesticks \
     --market1 KXMLBGAME-25SEP28BALNYY-BAL --market2 KXMLBGAME-25SEP28BALNYY-NYY \
     --pair win_yes_vs_win_no

6. Disable candlestick loading (if database is unavailable):
   python spread_visualizer.py --no-candlesticks


# =============================================================================
# CANDLESTICK VISUALIZATION
# =============================================================================

The candlestick plots show:
  - One subplot per arbitrage pair
  - Two columns per subplot: one for each market
  - Traditional candlestick bars (green=up, red=down)
  - Summary statistics: Open, High, Low, Close for each market

This visualization helps understand:
  - Market price action during arbitrage events
  - Directional movement and volatility
  - Volume traded during spread anomalies


# =============================================================================
# PYTHON API USAGE
# =============================================================================

1. Using CandlestickLoader directly:

   from candlestick_loader import CandlestickLoader
   from datetime import datetime
   
   loader = CandlestickLoader('kalshi_candlesticks.db')
   
   # Load candlesticks for a market and time period
   candles = loader.get_candlesticks_for_period(
       market_ticker='KXMLBGAME-25SEP28BALNYY-BAL',
       start_time=datetime(2025, 9, 28, 13, 0),
       end_time=datetime(2025, 9, 28, 14, 0),
       lookback_minutes=10
   )
   
   # Enrich arbitrage events with candlestick data
   enriched_events = loader.enrich_arbitrage_events(
       events=[event1, event2, ...],
       market1_ticker='KXMLBGAME-25SEP28BALNYY-BAL',
       market2_ticker='KXMLBGAME-25SEP28BALNYY-NYY'
   )


2. Using UnifiedMarketDataLoader:

   from candlestick_loader import UnifiedMarketDataLoader
   
   loader = UnifiedMarketDataLoader('kalshi_unified_market_data.db')
   
   # Get unified data (trades + candlesticks merged)
   df = loader.get_market_data_for_period(
       market_ticker='KXMLBGAME-25SEP28BALNYY-BAL',
       start_time=datetime(2025, 9, 28, 13, 0),
       end_time=datetime(2025, 9, 28, 14, 0)
   )


# =============================================================================
# DATABASE SCHEMAS
# =============================================================================

kalshi_candlesticks.db - candlesticks table:
  - ticker (VARCHAR): Market ticker
  - end_period_ts (TIMESTAMP): End time of the 1-minute candle
  - open, high, low, close (DOUBLE): Midpoint OHLC
  - ask_open, ask_high, ask_low, ask_close (DOUBLE): Ask-side OHLC
  - bid_open, bid_high, bid_low, bid_close (DOUBLE): Bid-side OHLC
  - volume (INTEGER): Contracts traded in the period

kalshi_unified_market_data.db - unified_market_data table:
  - timestamp (TIMESTAMP): Time of the data point
  - ticker (VARCHAR): Market ticker
  - yes_price (DOUBLE): YES outcome price
  - no_price (DOUBLE): NO outcome price
  - volume (DOUBLE): Trading volume
  - source (VARCHAR): Data source (trade or candlestick)

kalshi_event_market_map.db - event_market_map table:
  - event_ticker (VARCHAR): Event ticker
  - market_ticker (VARCHAR): Market ticker


# =============================================================================
# TROUBLESHOOTING
# =============================================================================

Issue: "Could not initialize candlestick loader"
Solution: Check that kalshi_candlesticks.db exists in the project root or specify
          the correct path with --candledb parameter

Issue: "No candlestick data" for candlestick plot
Solution: The market and time period may not have candlestick data. Verify the
          market tickers are correct and the time period is within available data.

Issue: Candlestick enrichment is slow
Solution: The enrichment happens during arbitrage analysis. For large datasets,
          use --no-candlesticks to disable it if not needed.

Issue: UnicodeEncodeError with emoji characters
Solution: This is a terminal encoding issue. The code will work fine, but emojis
          may not display on Windows systems with certain encodings.


# =============================================================================
# PERFORMANCE NOTES
# =============================================================================

- Candlestick loading is performed on-demand during analysis
- Lookback period is 10 minutes by default (configurable)
- Database queries are indexed by ticker and timestamp for efficiency
- Memory usage scales with the number of arbitrage events and candlesticks

For large analyses (100+ events), consider:
  1. Filtering to specific arbitrage pairs
  2. Using time windows instead of full game analysis
  3. Caching results if re-analyzing the same events


# =============================================================================
# FUTURE ENHANCEMENTS
# =============================================================================

Potential improvements:
  1. Real-time candlestick updates
  2. Configurable candlestick intervals (currently 1-minute only)
  3. Technical indicators (moving averages, RSI, etc.) based on candlesticks
  4. Pattern recognition for candlestick formations
  5. Volume profile analysis during spread events
