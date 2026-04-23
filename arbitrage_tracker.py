import argparse
import duckdb
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Tuple
import os
from candlestick_loader import CandlestickLoader

# Resolve project root (parent of 'Spread Tools' folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECT_ROOT, path)


class ArbitrageTracker:
    """
    Tracks arbitrage opportunities between matched markets in a Kalshi MLB game.
    
    For a game like NYY vs TEX, tracks four arbitrage pairs:
    1. WIN_YES_vs_WIN_NO: NYY WIN YES vs TEX WIN NO (should sum to ~1.0)
    2. LOSS_NO_vs_LOSS_YES: NYY LOSS NO vs TEX LOSS YES (should sum to ~1.0)
    3. WIN_NO_vs_WIN_YES: NYY WIN NO vs TEX WIN YES (should sum to ~1.0)
    4. LOSS_YES_vs_LOSS_NO: NYY LOSS YES vs TEX LOSS NO (should sum to ~1.0)
    """
    
    def __init__(self, db_path: str = 'kalshi_unified_market_data.db', event_ticker: str = None, 
                 spread_threshold: float = 0.02, output_dir: str = 'arbitrage_results',
                 pairs_to_analyze: List[str] = None, candlestick_db: str = 'kalshi_candlesticks.db',
                 include_candlesticks: bool = False, mapping_db_path: str = 'kalshi_event_market_map.db'):
        """
        Initialize the tracker.
        
        Args:
            db_path: Path to the unified market data database (kalshi_unified_market_data.db)
            event_ticker: Full event ticker (e.g., 'KXMLBGAME-25SEP28BALNYY')
            spread_threshold: Minimum spread (price difference) to trigger tracking
            output_dir: Directory to save results
            pairs_to_analyze: List of pairs to analyze. Options: 'win_yes_vs_win_no', 'win_no_vs_win_yes', 
                            'loss_no_vs_loss_yes', 'loss_yes_vs_loss_no'. Default: ['win_yes_vs_win_no', 'win_no_vs_win_yes']
            candlestick_db: Path to the candlestick database
            include_candlesticks: Whether to enrich results with candlestick data
            mapping_db_path: Path to the event-market mapping database (kalshi_event_market_map.db)
        """
        self.db_path = _resolve_path(db_path)
        self.mapping_db_path = _resolve_path(mapping_db_path)
        self.event_ticker = event_ticker
        self.spread_threshold = spread_threshold
        self.output_dir = _resolve_path(output_dir)
        self.con = duckdb.connect(self.db_path)
        self.mapping_con = duckdb.connect(self.mapping_db_path)
        self.include_candlesticks = include_candlesticks
        self.candlestick_loader = CandlestickLoader(candlestick_db) if include_candlesticks else None
        self.market1_ticker = None
        self.market2_ticker = None
        
        # Default to just the WIN pairs if not specified
        if pairs_to_analyze is None:
            pairs_to_analyze = ['win_yes_vs_win_no', 'win_no_vs_win_yes']
        self.pairs_to_analyze = pairs_to_analyze
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Parse the event ticker to get base event and team codes
        self._parse_event_ticker()
    
    def __del__(self):
        """Clean up database connections."""
        try:
            if hasattr(self, 'con') and self.con is not None:
                self.con.close()
            if hasattr(self, 'mapping_con') and self.mapping_con is not None:
                self.mapping_con.close()
        except:
            pass
        
    def _parse_event_ticker(self):
        """Extract base event and team codes from event ticker."""
        # Event ticker format: KXMLBGAME-25SEP28BALNYY or KXMLBGAME-25SEP28COLSF
        # Market tickers: KXMLBGAME-25SEP28BALNYY-BAL, KXMLBGAME-25SEP28BALNYY-NYY
        # Teams can be 2 or 3 characters (COL vs SF, not always 3-3 split)
        
        if not self.event_ticker:
            raise ValueError("event_ticker is required")
        
        # Query the database to find actual team codes from market tickers
        try:
            markets = self.mapping_con.execute(f"""
                SELECT DISTINCT market_ticker 
                FROM event_market_map 
                WHERE event_ticker = '{self.event_ticker}'
                ORDER BY market_ticker
            """).fetchall()
            
            if len(markets) >= 2:
                # Extract team codes from market tickers (the part after the last dash)
                self.team1 = markets[0][0].split('-')[-1]
                self.team2 = markets[1][0].split('-')[-1]
                self.base_event = self.event_ticker
                
                print(f"Parsed event ticker: {self.event_ticker}")
                print(f"  Base event: {self.base_event}")
                print(f"  Team 1: {self.team1}")
                print(f"  Team 2: {self.team2}\n")
                return
        except:
            pass
        
        # Fallback: Try to parse from event ticker directly
        # Assume format: KXMLBGAME-25SEP28[TEAM1][TEAM2]
        # where date is always 6 characters
        
        # Find the date part (format: 25SEP28)
        import re
        match = re.search(r'\d{2}[A-Z]{3}\d{2}', self.event_ticker)
        if match:
            date_end = match.end()
            team_part = self.event_ticker[date_end:]
            
            # Try common team code lengths
            # First try: COL+SF pattern (3+2)
            if len(team_part) == 5:
                self.team1 = team_part[:3]
                self.team2 = team_part[3:]
            # Otherwise assume 3+3
            elif len(team_part) == 6:
                self.team1 = team_part[:3]
                self.team2 = team_part[3:6]
            else:
                # Try to split in half
                mid = len(team_part) // 2
                self.team1 = team_part[:mid]
                self.team2 = team_part[mid:]
        else:
            # Last resort: take last 6 chars, assume 3+3
            self.team1 = self.event_ticker[-6:-3]
            self.team2 = self.event_ticker[-3:]
        
        self.base_event = self.event_ticker
        
        print(f"Parsed event ticker: {self.event_ticker}")
        print(f"  Base event: {self.base_event}")
        print(f"  Team 1: {self.team1}")
        print(f"  Team 2: {self.team2}\n")
        
    def _get_market_data(self, market_ticker: str, side: str) -> pd.DataFrame:
        """
        Fetch trade data for a specific market and side (yes/no).
        
        Args:
            market_ticker: The market ticker
            side: 'yes' or 'no' (corresponds to taker_side)
            
        Returns:
            DataFrame with columns: created_time, price, volume
        """
        query = f"""
            SELECT timestamp as created_time, 
                   CASE WHEN '{side}' = 'yes' THEN yes_price 
                        ELSE no_price END as price,
                   1 as volume
            FROM unified_market_data
            WHERE ticker = '{market_ticker}'
            ORDER BY timestamp
        """
        
        df = self.con.execute(query).df()
        if not df.empty:
            df['created_time'] = pd.to_datetime(df['created_time'])
        return df
    
    def _merge_on_time(self, df1: pd.DataFrame, df2: pd.DataFrame, 
                      market1_name: str, market2_name: str) -> pd.DataFrame:
        """
        Merge two market dataframes on time, forward-filling prices.
        
        Args:
            df1: First market data
            df2: Second market data
            market1_name: Name for first market (for column naming)
            market2_name: Name for second market (for column naming)
            
        Returns:
            Merged dataframe with both market prices and volumes
        """
        if df1.empty or df2.empty:
            return pd.DataFrame()
        
        # Rename columns to distinguish markets
        df1 = df1.rename(columns={
            'price': f'{market1_name}_price',
            'volume': f'{market1_name}_volume'
        })
        df2 = df2.rename(columns={
            'price': f'{market2_name}_price',
            'volume': f'{market2_name}_volume'
        })
        
        # Merge on time
        df = pd.merge(df1, df2, on='created_time', how='outer').sort_values('created_time')
        
        # Forward fill prices to handle moments where only one market traded
        df[f'{market1_name}_price'] = df[f'{market1_name}_price'].ffill()
        df[f'{market2_name}_price'] = df[f'{market2_name}_price'].ffill()
        
        # Keep volume as-is (0 or NaN for non-trades)
        df[f'{market1_name}_volume'] = df[f'{market1_name}_volume'].fillna(0)
        df[f'{market2_name}_volume'] = df[f'{market2_name}_volume'].fillna(0)
        
        # Drop rows where we don't have both prices yet
        df = df.dropna(subset=[f'{market1_name}_price', f'{market2_name}_price']).reset_index(drop=True)
        
        return df
    
    def _track_spread_events(self, df: pd.DataFrame, 
                            market1_col: str, market2_col: str,
                            vol1_col: str, vol2_col: str,
                            arbitrage_type: str) -> List[Dict]:
        """
        Track periods when the spread exceeds the threshold.
        
        Args:
            df: Merged market data
            market1_col: Column name for market1 price
            market2_col: Column name for market2 price
            vol1_col: Column name for market1 volume
            vol2_col: Column name for market2 volume
            arbitrage_type: Name of this arbitrage pair
            
        Returns:
            List of dicts with spread event details
        """
        if df.empty:
            return []
        
        # Calculate spread and identify when it exceeds threshold
        df['spread'] = (df[market1_col] - df[market2_col]).abs()
        df['above_threshold'] = df['spread'] > self.spread_threshold
        
        # Identify continuous segments where spread exceeds threshold
        df['segment_id'] = (df['above_threshold'] != df['above_threshold'].shift(1)).cumsum()
        
        events = []
        
        for segment_id, segment in df[df['above_threshold']].groupby('segment_id'):
            if len(segment) < 1:
                continue
            
            start_time = segment['created_time'].iloc[0]
            end_time = segment['created_time'].iloc[-1]
            duration_seconds = (end_time - start_time).total_seconds()
            
            # Skip very short spurious events (less than 1 second)
            if duration_seconds < 1.0:
                continue
            
            # Aggregate volume data
            vol1_total = segment[vol1_col].sum()
            vol2_total = segment[vol2_col].sum()
            
            # Spread statistics
            avg_spread = segment['spread'].mean()
            peak_spread = segment['spread'].max()
            min_spread = segment['spread'].min()
            
            events.append({
                'arbitrage_type': arbitrage_type,
                'market1': market1_col.replace('_price', ''),
                'market2': market2_col.replace('_price', ''),
                'start_time': start_time,
                'end_time': end_time,
                'duration_seconds': duration_seconds,
                'market1_volume': vol1_total,
                'market2_volume': vol2_total,
                'total_volume': vol1_total + vol2_total,
                'avg_spread': avg_spread,
                'peak_spread': peak_spread,
                'min_spread': min_spread,
                'num_trades': len(segment),
            })
        
        return events
    
    def analyze_arbitrage_pair(self, market1_ticker: str, market1_side: str,
                               market2_ticker: str, market2_side: str,
                               arbitrage_type: str) -> Tuple[List[Dict], pd.DataFrame]:
        """
        Analyze one arbitrage pair.
        
        Args:
            market1_ticker: First market ticker
            market1_side: Side for first market ('yes' or 'no')
            market2_ticker: Second market ticker
            market2_side: Side for second market ('yes' or 'no')
            arbitrage_type: Description of this arbitrage pair
            
        Returns:
            Tuple of (events list, merged dataframe)
        """
        print(f"Analyzing: {arbitrage_type}")
        print(f"  {market1_ticker} ({market1_side}) vs {market2_ticker} ({market2_side})")
        
        # Fetch data
        df1 = self._get_market_data(market1_ticker, market1_side)
        df2 = self._get_market_data(market2_ticker, market2_side)
        
        if df1.empty or df2.empty:
            print(f"  ⚠️  Missing data for one or both markets")
            return [], pd.DataFrame()
        
        # Create market descriptors for column names
        m1_desc = f"{market1_ticker.split('-')[-1]}_{market1_side[:1].upper()}"
        m2_desc = f"{market2_ticker.split('-')[-1]}_{market2_side[:1].upper()}"
        
        # Merge
        df = self._merge_on_time(df1, df2, m1_desc, m2_desc)
        
        if df.empty:
            print(f"  ⚠️  No merged data available")
            return [], pd.DataFrame()
        
        # Track spread events
        vol1_col = f'{m1_desc}_volume'
        vol2_col = f'{m2_desc}_volume'
        events = self._track_spread_events(df, f'{m1_desc}_price', f'{m2_desc}_price',
                                          vol1_col, vol2_col, arbitrage_type)
        
        print(f"  [OK] Found {len(events)} spread events")
        
        return events, df
    
    def run_analysis(self) -> Dict:
        """
        Run the arbitrage analysis for specified pairs.
        
        Returns:
            Dictionary with results for each arbitrage pair
        """
        results = {
            'game_ticker': self.event_ticker,
            'spread_threshold': self.spread_threshold,
            'analysis_timestamp': datetime.now().isoformat(),
            'arbitrage_pairs': {}
        }
        
        all_events = []
        
        # Build market tickers
        market1_ticker = f"{self.base_event}-{self.team1}"
        market2_ticker = f"{self.base_event}-{self.team2}"
        
        # Store for use in _save_results
        self.market1_ticker = market1_ticker
        self.market2_ticker = market2_ticker
        
        # Analyze selected pairs
        if 'win_yes_vs_win_no' in self.pairs_to_analyze:
            events, df = self.analyze_arbitrage_pair(
                market1_ticker, 'yes',
                market2_ticker, 'no',
                f"{self.team1} WIN YES vs {self.team2} WIN NO"
            )
            results['arbitrage_pairs']['win_yes_vs_win_no'] = {
                'events': events,
                'dataframe': df
            }
            all_events.extend(events)
            print()
        
        if 'win_no_vs_win_yes' in self.pairs_to_analyze:
            events, df = self.analyze_arbitrage_pair(
                market1_ticker, 'no',
                market2_ticker, 'yes',
                f"{self.team1} WIN NO vs {self.team2} WIN YES"
            )
            results['arbitrage_pairs']['win_no_vs_win_yes'] = {
                'events': events,
                'dataframe': df
            }
            all_events.extend(events)
            print()
        
        if 'loss_no_vs_loss_yes' in self.pairs_to_analyze:
            events, df = self.analyze_arbitrage_pair(
                market1_ticker, 'no',
                market2_ticker, 'yes',
                f"{self.team1} LOSS NO vs {self.team2} LOSS YES"
            )
            results['arbitrage_pairs']['loss_no_vs_loss_yes'] = {
                'events': events,
                'dataframe': df
            }
            all_events.extend(events)
            print()
        
        if 'loss_yes_vs_loss_no' in self.pairs_to_analyze:
            events, df = self.analyze_arbitrage_pair(
                market1_ticker, 'yes',
                market2_ticker, 'no',
                f"{self.team1} LOSS YES vs {self.team2} LOSS NO"
            )
            results['arbitrage_pairs']['loss_yes_vs_loss_no'] = {
                'events': events,
                'dataframe': df
            }
            all_events.extend(events)
            print()
        
        # Save results
        self._save_results(all_events)
        
        return results
    
    def _save_results(self, all_events: List[Dict]):
        """Save results to CSV file."""
        if not all_events:
            print("[WARNING] No arbitrage events found to save.")
            return
        
        # Enrich events with candlestick data if available
        if self.include_candlesticks and self.candlestick_loader and self.market1_ticker and self.market2_ticker:
            print("[...] Enriching events with candlestick data...")
            try:
                all_events = self.candlestick_loader.enrich_arbitrage_events(
                    all_events,
                    self.market1_ticker,
                    self.market2_ticker,
                    lookback_minutes=10
                )
                print("[OK] Candlestick enrichment completed")
            except Exception as e:
                print(f"[WARNING] Could not enrich with candlesticks: {e}")
        
        # Create DataFrame from events
        df_results = pd.DataFrame(all_events)
        
        # Format timestamps for readability
        df_results['start_time'] = df_results['start_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        df_results['end_time'] = df_results['end_time'].dt.strftime('%Y-%m-%d %H:%M:%S.%f')
        
        # Save to CSV
        output_file = os.path.join(self.output_dir, f"arbitrage_{self.event_ticker}_{self.spread_threshold}.csv")
        df_results.to_csv(output_file, index=False)
        
        print(f"[OK] Results saved to: {output_file}")
        print(f"   Total events found: {len(all_events)}")
        
        # Print summary stats
        print("\n" + "="*70)
        print("ARBITRAGE SUMMARY")
        print("="*70)
        print(f"Game: {self.event_ticker}")
        print(f"Spread Threshold: ${self.spread_threshold:.4f}")
        print(f"Total Arbitrage Events: {len(all_events)}\n")
        
        # Group by arbitrage type
        for arb_type in df_results['arbitrage_type'].unique():
            subset = df_results[df_results['arbitrage_type'] == arb_type]
            print(f"{arb_type}")
            print(f"  Events: {len(subset)}")
            print(f"  Avg Duration: {subset['duration_seconds'].mean():.2f}s")
            print(f"  Total Volume: {subset['total_volume'].sum():.0f}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description='Track arbitrage opportunities in Kalshi MLB games.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28TEXCLE --threshold 0.03 --pairs win_yes_vs_win_no win_no_vs_win_yes
  python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs all
        """
    )
    
    parser.add_argument('--event', required=True, 
                        help='Event ticker (e.g., KXMLBGAME-25SEP28BALNYY)')
    parser.add_argument('--threshold', type=float, default=0.02,
                        help='Minimum spread threshold to track (default: 0.02)')
    parser.add_argument('--db', default='kalshi_unified_market_data.db',
                        help='Path to DuckDB database (default: kalshi_unified_market_data.db)')
    parser.add_argument('--candledb', default='kalshi_candlesticks.db',
                        help='Path to candlestick database (default: kalshi_candlesticks.db)')
    parser.add_argument('--output', default='arbitrage_results',
                        help='Output directory for results (default: arbitrage_results)')
    parser.add_argument('--pairs', nargs='+', default=['win_yes_vs_win_no', 'win_no_vs_win_yes'],
                        help='Which pairs to analyze. Options: win_yes_vs_win_no, win_no_vs_win_yes, loss_no_vs_loss_yes, loss_yes_vs_loss_no, all (default: win_yes_vs_win_no win_no_vs_win_yes)')
    parser.add_argument('--no-candlesticks', action='store_true',
                        help='Disable candlestick data enrichment (default: enabled)')
    
    args = parser.parse_args()
    
    # Handle 'all' keyword
    if args.pairs == ['all']:
        pairs = ['win_yes_vs_win_no', 'win_no_vs_win_yes', 'loss_no_vs_loss_yes', 'loss_yes_vs_loss_no']
    else:
        pairs = args.pairs
    
    # Run analysis
    tracker = ArbitrageTracker(
        db_path=args.db,
        event_ticker=args.event,
        spread_threshold=args.threshold,
        output_dir=args.output,
        pairs_to_analyze=pairs,
        candlestick_db=args.candledb,
        include_candlesticks=not args.no_candlesticks
    )
    
    tracker.run_analysis()


if __name__ == '__main__':
    main()
