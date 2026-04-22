"""
Candlestick Loader - Load and merge candlestick data with arbitrage events.

Provides utilities to fetch OHLC candlestick data from the candlestick database
and enrich arbitrage events with candlestick metrics.
"""

import duckdb
import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from datetime import datetime, timedelta
import os


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    _PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return os.path.join(_PROJECT_ROOT, path)


class CandlestickLoader:
    """Load and process candlestick data from the candlestick database."""
    
    def __init__(self, candlestick_db: str = 'kalshi_candlesticks.db'):
        """
        Initialize the candlestick loader.
        
        Args:
            candlestick_db: Path to the candlestick database
        """
        self.db_path = _resolve_path(candlestick_db)
        self.con = duckdb.connect(self.db_path, read_only=True)
    
    def __del__(self):
        """Close database connection on cleanup."""
        if hasattr(self, 'con'):
            self.con.close()
    
    def get_candlesticks_for_period(self, market_ticker: str, 
                                   start_time: datetime, 
                                   end_time: datetime,
                                   lookback_minutes: int = 10) -> pd.DataFrame:
        """
        Fetch candlestick data for a market during a specific time period.
        
        Args:
            market_ticker: The market ticker (e.g., 'KXMLBGAME-25SEP28BALNYY-BAL')
            start_time: Start of the period (datetime, assumed tz-naive)
            end_time: End of the period (datetime, assumed tz-naive)
            lookback_minutes: How many minutes before start_time to include (default: 10)
            
        Returns:
            DataFrame with candlestick data: 
            - end_period_ts: timestamp of candle
            - open, high, low, close: OHLC prices
            - ask_open, ask_high, ask_low, ask_close: Ask-side OHLC
            - bid_open, bid_high, bid_low, bid_close: Bid-side OHLC
            - volume: volume in the period
        """
        # Expand the time window
        lookback_start = start_time - timedelta(minutes=lookback_minutes)
        
        try:
            query = f"""
                SELECT *
                FROM candlesticks
                WHERE ticker = '{market_ticker}'
                AND end_period_ts >= '{lookback_start.isoformat()}'
                AND end_period_ts <= '{end_time.isoformat()}'
                ORDER BY end_period_ts
            """
            
            df = self.con.execute(query).df()
            
            if not df.empty:
                df['end_period_ts'] = pd.to_datetime(df['end_period_ts'])
            
            return df
        except Exception as e:
            print(f"Error fetching candlesticks for {market_ticker}: {e}")
            return pd.DataFrame()
    
    def aggregate_candlesticks(self, df: pd.DataFrame) -> Dict[str, float]:
        """
        Aggregate candlestick data into summary statistics.
        
        Args:
            df: Candlestick DataFrame
            
        Returns:
            Dictionary with aggregated metrics
        """
        if df.empty:
            return {
                'volume': 0,
                'open': None,
                'high': None,
                'low': None,
                'close': None,
                'ask_open': None,
                'ask_high': None,
                'ask_low': None,
                'ask_close': None,
                'bid_open': None,
                'bid_high': None,
                'bid_low': None,
                'bid_close': None,
                'num_candles': 0,
            }
        
        # Get the first open and last close for proper OHLC
        first_row = df.iloc[0]
        last_row = df.iloc[-1]
        
        return {
            'volume': df['volume'].sum(),
            'open': first_row['open'],
            'high': df['high'].max(),
            'low': df['low'].min(),
            'close': last_row['close'],
            'ask_open': first_row['ask_open'],
            'ask_high': df['ask_high'].max(),
            'ask_low': df['ask_low'].min(),
            'ask_close': last_row['ask_close'],
            'bid_open': first_row['bid_open'],
            'bid_high': df['bid_high'].max(),
            'bid_low': df['bid_low'].min(),
            'bid_close': last_row['bid_close'],
            'num_candles': len(df),
        }
    
    def enrich_arbitrage_events(self, events: List[Dict], 
                                market1_ticker: str, 
                                market2_ticker: str,
                                lookback_minutes: int = 10) -> List[Dict]:
        """
        Enrich arbitrage events with candlestick data from both markets.
        
        Args:
            events: List of arbitrage event dictionaries
            market1_ticker: First market ticker
            market2_ticker: Second market ticker
            lookback_minutes: Minutes to look back before event start
            
        Returns:
            Same events list with candlestick data added
        """
        enriched_events = []
        
        for event in events:
            enriched_event = event.copy()
            
            start_time = event['start_time']
            end_time = event['end_time']
            
            # Fetch candlesticks for both markets
            candles1 = self.get_candlesticks_for_period(
                market1_ticker, start_time, end_time, lookback_minutes
            )
            candles2 = self.get_candlesticks_for_period(
                market2_ticker, start_time, end_time, lookback_minutes
            )
            
            # Aggregate candlestick data
            agg1 = self.aggregate_candlesticks(candles1)
            agg2 = self.aggregate_candlesticks(candles2)
            
            # Add to event with market1 and market2 prefix
            for key, value in agg1.items():
                enriched_event[f'market1_candle_{key}'] = value
            
            for key, value in agg2.items():
                enriched_event[f'market2_candle_{key}'] = value
            
            enriched_events.append(enriched_event)
        
        return enriched_events
    
    def get_market_candledata_summary(self, market_ticker: str, 
                                      start_time: datetime,
                                      end_time: datetime) -> pd.DataFrame:
        """
        Get a time-series of candlestick data for a market period.
        
        Useful for plotting candlesticks alongside trade data.
        
        Args:
            market_ticker: The market ticker
            start_time: Period start time
            end_time: Period end time
            
        Returns:
            DataFrame with time-indexed candlestick data
        """
        try:
            query = f"""
                SELECT *
                FROM candlesticks
                WHERE ticker = '{market_ticker}'
                AND end_period_ts >= '{start_time.isoformat()}'
                AND end_period_ts <= '{end_time.isoformat()}'
                ORDER BY end_period_ts
            """
            
            df = self.con.execute(query).df()
            
            if not df.empty:
                df['end_period_ts'] = pd.to_datetime(df['end_period_ts'])
                df = df.set_index('end_period_ts')
            
            return df
        except Exception as e:
            print(f"Error fetching candledata summary for {market_ticker}: {e}")
            return pd.DataFrame()


class UnifiedMarketDataLoader:
    """Load unified market data (trades merged with candlesticks)."""
    
    def __init__(self, unified_db: str = 'kalshi_unified_market_data.db'):
        """
        Initialize the unified market data loader.
        
        Args:
            unified_db: Path to the unified market data database
        """
        self.db_path = _resolve_path(unified_db)
        self.con = duckdb.connect(self.db_path, read_only=True)
    
    def __del__(self):
        """Close database connection on cleanup."""
        if hasattr(self, 'con'):
            self.con.close()
    
    def get_market_data_for_period(self, market_ticker: str,
                                   start_time: datetime,
                                   end_time: datetime) -> pd.DataFrame:
        """
        Fetch unified market data (trades + candlesticks) for a period.
        
        Args:
            market_ticker: The market ticker
            start_time: Period start time
            end_time: Period end time
            
        Returns:
            DataFrame with columns: timestamp, yes_price, no_price, volume, source
        """
        try:
            query = f"""
                SELECT *
                FROM unified_market_data
                WHERE ticker = '{market_ticker}'
                AND timestamp >= '{start_time.isoformat()}'
                AND timestamp <= '{end_time.isoformat()}'
                ORDER BY timestamp
            """
            
            df = self.con.execute(query).df()
            
            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            return df
        except Exception as e:
            print(f"Error fetching unified market data for {market_ticker}: {e}")
            return pd.DataFrame()


if __name__ == '__main__':
    # Quick test
    loader = CandlestickLoader()
    print("✅ Candlestick loader initialized successfully")
