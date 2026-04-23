"""
Arbitrage Results Summary - Analyze spread data across all games.

Provides overall statistics and breakdowns by MLB division.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Resolve project root (parent of 'Spread Tools' folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECT_ROOT, path)


# MLB Team to Division Mapping
TEAM_DIVISIONS = {
    # AL East
    'BAL': 'AL East', 'BOS': 'AL East', 'NYY': 'AL East', 'TB': 'AL East', 'TOR': 'AL East',
    # AL Central
    'CWS': 'AL Central', 'CLE': 'AL Central', 'DET': 'AL Central', 'KC': 'AL Central', 'MIN': 'AL Central',
    # AL West
    'HOU': 'AL West', 'LAA': 'AL West', 'OAK': 'AL West', 'SEA': 'AL West', 'TEX': 'AL West',
    # NL East
    'ATH': 'NL East', 'ATL': 'NL East',  # ATL is alias for ATH
    'MIA': 'NL East', 'NYM': 'NL East', 'PHI': 'NL East', 'WSH': 'NL East',
    # NL Central
    'CHC': 'NL Central', 'CIN': 'NL Central', 'MIL': 'NL Central', 'PIT': 'NL Central', 'STL': 'NL Central',
    # NL West
    'AZ': 'NL West', 'ARI': 'NL West',  # ARI is alias for AZ
    'COL': 'NL West', 'LAD': 'NL West', 'SD': 'NL West', 'SF': 'NL West',
}


def extract_teams_from_ticker(event_ticker: str):
    """Extract team codes from event ticker (e.g., KXMLBGAME-25APR16ATHCWS -> ATH, CWS)"""
    # Format: KXMLBGAME-25APR16TEAM1TEAM2
    # Find where the date ends (format 25APR16)
    import re
    match = re.search(r'\d{2}[A-Z]{3}\d{2}', event_ticker)
    if match:
        date_end = match.end()
        team_part = event_ticker[date_end:]
        
        # Try to split - teams can be 2-3 characters each
        if len(team_part) == 5:
            return team_part[:3], team_part[3:]
        elif len(team_part) == 6:
            return team_part[:3], team_part[3:6]
    
    return None, None


def get_division(team_code: str) -> str:
    """Get division for a team code."""
    return TEAM_DIVISIONS.get(team_code, 'Unknown')


class ArbitrageResultsSummary:
    """Summarize arbitrage results across all games."""
    
    def __init__(self, results_dir: str = 'arbitrage_results', threshold: float = None):
        self.results_dir = _resolve_path(results_dir)
        self.threshold = threshold  # None means load all, or specify like 0.03
        self.df_all = None
        self.load_results()
    
    def load_results(self):
        """Load and combine all arbitrage result CSV files."""
        csv_files = list(Path(self.results_dir).glob('arbitrage_*.csv'))
        
        if not csv_files:
            print(f"[ERROR] No CSV files found in {self.results_dir}")
            return
        
        # Filter by threshold if specified
        if self.threshold is not None:
            threshold_str = f"_{self.threshold}.csv"
            csv_files = [f for f in csv_files if threshold_str in f.name]
            print(f"[...] Loading files with threshold {self.threshold}...")
        
        if not csv_files:
            print(f"[ERROR] No CSV files found with threshold {self.threshold}")
            return
        
        print(f"[...] Loading {len(csv_files)} result files...")
        
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(csv_file)
                # Extract event ticker from filename (arbitrage_TICKER_THRESHOLD.csv)
                filename = csv_file.name.replace('arbitrage_', '').replace('.csv', '')
                parts = filename.rsplit('_', 1)
                if len(parts) == 2:
                    df['event_ticker'] = parts[0]
                    df['threshold'] = float(parts[1])
                dfs.append(df)
            except Exception as e:
                print(f"[WARNING] Error loading {csv_file.name}: {e}")
        
        if dfs:
            self.df_all = pd.concat(dfs, ignore_index=True)
            num_games = len(self.df_all['event_ticker'].unique())
            print(f"[OK] Loaded {len(self.df_all)} total spread events from {num_games} games")
        else:
            print("[ERROR] No data loaded")
    
    def add_divisions(self):
        """Add division columns based on team codes in arbitrage_type."""
        if self.df_all is None or self.df_all.empty:
            return
        
        team1_list = []
        team2_list = []
        div1_list = []
        div2_list = []
        
        # Extract teams from arbitrage_type (e.g., "AZ WIN YES vs MIA WIN NO" -> AZ, MIA)
        for arb_type in self.df_all['arbitrage_type']:
            parts = arb_type.split(' vs ')
            if len(parts) == 2:
                # Extract team code from first part (e.g., "AZ WIN YES" -> "AZ")
                team1 = parts[0].split()[0]
                # Extract team code from second part (e.g., "MIA WIN NO" -> "MIA")
                team2 = parts[1].split()[0]
            else:
                team1, team2 = None, None
            
            team1_list.append(team1 if team1 else 'Unknown')
            team2_list.append(team2 if team2 else 'Unknown')
            div1_list.append(get_division(team1) if team1 else 'Unknown')
            div2_list.append(get_division(team2) if team2 else 'Unknown')
        
        self.df_all['team1'] = team1_list
        self.df_all['team2'] = team2_list
        self.df_all['division1'] = div1_list
        self.df_all['division2'] = div2_list
        
        # Create a combined division identifier
        def get_matchup_division(div1, div2):
            if div1 == div2:
                return div1
            else:
                divs = sorted([div1, div2])
                return f"{divs[0]} vs {divs[1]}"
        
        self.df_all['matchup_type'] = [
            get_matchup_division(d1, d2) 
            for d1, d2 in zip(div1_list, div2_list)
        ]
    
    def calculate_overall_summary(self) -> pd.DataFrame:
        """Calculate overall summary statistics."""
        if self.df_all is None or self.df_all.empty:
            return None
        
        summary = {
            'Total Games': len(self.df_all['event_ticker'].unique()),
            'Total Spread Events': len(self.df_all),
            'Avg Events per Game': len(self.df_all) / len(self.df_all['event_ticker'].unique()),
            'Avg Duration (seconds)': self.df_all['duration_seconds'].mean(),
            'Median Duration (seconds)': self.df_all['duration_seconds'].median(),
            'Avg Peak Spread': self.df_all['peak_spread'].mean(),
            'Median Peak Spread': self.df_all['peak_spread'].median(),
            'Avg Spread': self.df_all['avg_spread'].mean(),
            'Avg Total Volume': self.df_all['total_volume'].mean(),
            'Total Volume (all events)': self.df_all['total_volume'].sum(),
        }
        
        return pd.Series(summary)
    
    def calculate_by_arbitrage_type(self) -> pd.DataFrame:
        """Calculate summary by arbitrage type."""
        if self.df_all is None or self.df_all.empty:
            return None
        
        summary_data = []
        for arb_type in self.df_all['arbitrage_type'].unique():
            subset = self.df_all[self.df_all['arbitrage_type'] == arb_type]
            num_games = len(subset['event_ticker'].unique())
            summary_data.append({
                'Arbitrage Type': arb_type,
                'Games': num_games,
                'Total Events': len(subset),
                'Avg Events/Game': len(subset) / num_games if num_games > 0 else 0,
                'Avg Duration (s)': subset['duration_seconds'].mean(),
                'Avg Peak Spread': subset['peak_spread'].mean(),
                'Avg Spread': subset['avg_spread'].mean(),
                'Total Volume': subset['total_volume'].sum(),
            })
        
        return pd.DataFrame(summary_data)
    
    def calculate_by_division_summary(self) -> pd.DataFrame:
        """Calculate summary statistics for each division."""
        if self.df_all is None or self.df_all.empty:
            return None
        
        divisions = [
            'AL East', 'AL Central', 'AL West',
            'NL East', 'NL Central', 'NL West'
        ]
        
        summary_data = []
        for div in divisions:
            # Get all events where this division is involved (either team is from this division)
            subset = self.df_all[
                (self.df_all['division1'] == div) | (self.df_all['division2'] == div)
            ]
            
            if len(subset) == 0:
                continue
            
            num_games = len(subset['event_ticker'].unique())
            summary_data.append({
                'Division': div,
                'Games': num_games,
                'Events': len(subset),
                'Avg Events/Game': len(subset) / num_games if num_games > 0 else 0,
                'Avg Duration (s)': subset['duration_seconds'].mean(),
                'Median Duration (s)': subset['duration_seconds'].median(),
                'Avg Peak Spread': subset['peak_spread'].mean(),
                'Median Peak Spread': subset['peak_spread'].median(),
            })
        
        return pd.DataFrame(summary_data)
    
    def print_summary(self):
        """Print condensed summary in a formatted way."""
        if self.df_all is None or self.df_all.empty:
            print("[ERROR] No data to summarize")
            return
        
        print("\n" + "="*80)
        print("ARBITRAGE ANALYSIS SUMMARY")
        print("="*80)
        
        # Overall summary - condensed
        overall = self.calculate_overall_summary()
        print("\n[MLB OVERALL]")
        print(f"Total Games: {overall['Total Games']:.0f}")
        print(f"Total Events: {overall['Total Spread Events']:.0f}")
        print(f"Avg Events per Game: {overall['Avg Events per Game']:.2f}")
        print(f"Median Duration: {overall['Median Duration (seconds)']:.2f}s")
        print(f"Median Peak Spread: {overall['Median Peak Spread']:.6f}")
        print(f"Total Volume: {overall['Total Volume (all events)']:.0f}")
        
        # By division
        by_div = self.calculate_by_division_summary()
        print("\n[BY DIVISION]")
        print(by_div.to_string(index=False))
        
        print("\n" + "="*80)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Summarize arbitrage results')
    parser.add_argument('--threshold', type=float, default=0.02,
                        help='Spread threshold to analyze (default: 0.02)')
    parser.add_argument('--all-thresholds', action='store_true',
                        help='Include all thresholds instead of just one')
    
    args = parser.parse_args()
    
    threshold = None if args.all_thresholds else args.threshold
    
    summary = ArbitrageResultsSummary(threshold=threshold)
    if summary.df_all is not None:
        summary.add_divisions()
        summary.print_summary()
    else:
        print("[ERROR] Failed to load results")


if __name__ == '__main__':
    main()
