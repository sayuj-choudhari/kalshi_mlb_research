"""
Spread Stats Viewer - Display detailed statistics for each arbitrage spread event.

Shows each spread's duration, volume, and spread statistics in a readable format.
Supports both command-line arguments and an interactive menu when run with no arguments.
"""

import argparse
import os
import sys

# Resolve project root (parent of 'Spread Tools' folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECT_ROOT, path)
import pandas as pd
from pathlib import Path
from typing import List, Optional


def display_spreads(csv_file: str, sort_by: str = 'duration_seconds', reverse: bool = True, pairs_filter: List[str] = None):
    """
    Display spread statistics from a CSV file.
    
    Args:
        csv_file: Path to the CSV file
        sort_by: Column to sort by (duration_seconds, total_volume, avg_spread, etc.)
        reverse: Sort in descending order if True
        pairs_filter: List of pairs to display (e.g., ['win_yes_vs_win_no', 'win_no_vs_win_yes']).
                     If None, displays all pairs.
    """
    
    if not os.path.exists(csv_file):
        print(f"❌ File not found: {csv_file}")
        return
    
    df = pd.read_csv(csv_file)
    
    if df.empty:
        print("❌ CSV file is empty")
        return
    
    # Default to WIN pairs if no filter specified
    if pairs_filter is None:
        pairs_filter = ['win_yes_vs_win_no', 'win_no_vs_win_yes']
    
    # Map pair names to actual arbitrage type descriptions in the CSV
    # Extract unique arbitrage types to match against our filter
    all_pairs = df['arbitrage_type'].unique()
    
    # If we're filtering, only keep rows that match our filter
    if pairs_filter:
        # Check if pairs_filter contains the special names or actual descriptions
        # Try to match by checking if the arbitrage_type contains the pair name
        matching_rows = []
        for pair_name in pairs_filter:
            for idx, row in df.iterrows():
                # Match based on WIN/LOSS keywords
                arb_type = row['arbitrage_type'].lower()
                if 'win' in pair_name and 'win' in arb_type and 'loss' not in arb_type:
                    if 'yes_vs' in pair_name and 'vs' in arb_type:
                        # win_yes_vs_win_no
                        if 'yes' in arb_type and 'no' in arb_type:
                            matching_rows.append(idx)
                    elif 'no_vs' in pair_name and 'vs' in arb_type:
                        # win_no_vs_win_yes
                        if 'no' in arb_type and 'yes' in arb_type:
                            matching_rows.append(idx)
                elif 'loss' in pair_name and 'loss' in arb_type:
                    if 'no_vs' in pair_name and 'yes' in arb_type:
                        # loss_no_vs_loss_yes
                        if 'no' in arb_type and 'yes' in arb_type:
                            matching_rows.append(idx)
                    elif 'yes_vs' in pair_name and 'no' in arb_type:
                        # loss_yes_vs_loss_no
                        if 'yes' in arb_type and 'no' in arb_type:
                            matching_rows.append(idx)
        
        if matching_rows:
            df = df.loc[matching_rows].drop_duplicates().reset_index(drop=True)
    
    # Sort the dataframe
    df = df.sort_values(by=sort_by, ascending=not reverse)
    
    # Extract filename info
    filename = os.path.basename(csv_file)
    parts = filename.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
    event_ticker = parts[0] if len(parts) > 0 else "Unknown"
    threshold = parts[1] if len(parts) > 1 else "Unknown"
    
    print("\n" + "="*100)
    print(f"SPREAD STATISTICS VIEW")
    print("="*100)
    print(f"Game: {event_ticker}")
    print(f"Threshold: ${threshold}")
    print(f"Total Spreads: {len(df)}")
    print(f"Sorted by: {sort_by} (descending)" if reverse else f"Sorted by: {sort_by}")
    print("="*100 + "\n")
    
    # Group by arbitrage type
    for arb_type in df['arbitrage_type'].unique():
        subset = df[df['arbitrage_type'] == arb_type].sort_values(by=sort_by, ascending=not reverse)
        
        print(f"\n{'=' * 95}")
        print(f"  {arb_type}")
        print(f"{'=' * 95}")
        print(f"  Total events: {len(subset)}")
        print(f"  Avg duration: {subset['duration_seconds'].mean():.1f}s")
        print(f"  Total volume: {subset['total_volume'].sum():.0f}")
        print(f"  Avg spread: ${subset['avg_spread'].mean():.4f}")
        print(f"  Peak spread: ${subset['peak_spread'].max():.4f}")
        
        # Display individual spreads
        print(f"\n  {'Event':<3} | {'Duration':<10} | {'Volume':<10} | {'M1 Vol':<8} | {'M2 Vol':<8} | {'Avg Sp':<8} | {'Peak Sp':<8}")
        print(f"  {'-'*85}")
        
        for idx, (i, row) in enumerate(subset.iterrows(), 1):
            print(
                f"  {idx:<3} | "
                f"{row['duration_seconds']:>8.1f}s | "
                f"{row['total_volume']:>9.0f} | "
                f"{row['market1_volume']:>7.0f} | "
                f"{row['market2_volume']:>7.0f} | "
                f"${row['avg_spread']:>6.4f} | "
                f"${row['peak_spread']:>6.4f}"
            )
    
    # Overall summary
    print(f"\n{'='*100}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*100}")
    print(f"Total spreads analyzed: {len(df)}")
    print(f"Average duration: {df['duration_seconds'].mean():.1f} seconds")
    print(f"Median duration: {df['duration_seconds'].median():.1f} seconds")
    print(f"Longevity spread: {df['duration_seconds'].max():.1f}s")
    print(f"Total volume: {df['total_volume'].sum():.0f}")
    print(f"Average volume per spread: {df['total_volume'].mean():.0f}")
    print(f"Average spread size: ${df['avg_spread'].mean():.4f}")
    print(f"Maximum spread observed: ${df['peak_spread'].max():.4f}")
    print(f"Minimum spread observed: ${df['min_spread'].min():.4f}")
    print(f"{'='*100}\n")


def find_csv_file(event_ticker: str = None, threshold: float = None, results_dir: str = 'arbitrage_results'):
    """
    Find a CSV file in the results directory based on event and threshold.
    
    Args:
        event_ticker: Event ticker to search for
        threshold: Threshold value to search for
        results_dir: Directory containing CSV files
        
    Returns:
        Path to the CSV file, or None if not found
    """
    results_dir = _resolve_path(results_dir)
    
    if not os.path.exists(results_dir):
        print(f"❌ Results directory not found: {results_dir}")
        return None
    
    files = list(Path(results_dir).glob('arbitrage_*.csv'))
    
    if not files:
        print(f"❌ No CSV files found in {results_dir}")
        return None
    
    # If both event and threshold specified, find exact match
    if event_ticker and threshold is not None:
        target_filename = f"arbitrage_{event_ticker}_{threshold}.csv"
        for f in files:
            if f.name == target_filename:
                return str(f)
        print(f"❌ File not found: {target_filename}")
        return None
    
    # If only event specified, find first match
    if event_ticker:
        for f in files:
            if event_ticker in f.name:
                return str(f)
        print(f"❌ No files found for event: {event_ticker}")
        return None
    
    # List available files
    print(f"📁 Available CSV files in {results_dir}:")
    for i, f in enumerate(files, 1):
        print(f"   {i}. {f.name}")
    
    return None


def get_available_games(results_dir: str = 'arbitrage_results') -> dict:
    """Get available games and their thresholds from CSV files."""
    results_dir = _resolve_path(results_dir)
    games = {}
    if not os.path.exists(results_dir):
        return games
    for f in Path(results_dir).glob('arbitrage_*.csv'):
        parts = f.name.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
        if len(parts) == 2:
            event, thresh = parts[0], parts[1]
            try:
                thresh_val = float(thresh)
            except ValueError:
                continue
            if event not in games:
                games[event] = []
            games[event].append(thresh_val)
    for event in games:
        games[event] = sorted(set(games[event]))
    return games


def interactive_mode(results_dir: str = 'arbitrage_results'):
    """Run an interactive menu for exploring spread statistics."""
    sort_by = 'duration_seconds'
    reverse = True
    pairs_filter = ['win_yes_vs_win_no', 'win_no_vs_win_yes']

    while True:
        print("\n" + "=" * 60)
        print("  SPREAD STATS VIEWER - Interactive Mode")
        print("=" * 60)
        print(f"  Sort: {sort_by} ({'desc' if reverse else 'asc'})")
        pairs_display = ', '.join(pairs_filter) if pairs_filter else 'all pairs'
        print(f"  Pairs: {pairs_display}")
        print("-" * 60)
        print("  1. View spread stats for a game")
        print("  2. Change sort options")
        print("  3. Change pair filter")
        print("  4. List available games")
        print("  5. Exit")
        print("-" * 60)

        choice = input("\nSelect (1-5): ").strip()

        if choice == '1':
            games = get_available_games(results_dir)
            if not games:
                print("\n❌ No CSV files found in", results_dir)
                continue

            print("\n" + "-" * 60)
            print("  AVAILABLE GAMES")
            print("-" * 60)
            game_list = sorted(games.keys())
            for i, game in enumerate(game_list, 1):
                thresholds_str = ", ".join(f"${t}" for t in games[game])
                print(f"  {i:2}. {game}")
                print(f"      Thresholds: {thresholds_str}")
            print(f"\n   0. Back")

            try:
                game_choice = input("\nSelect game (0 to cancel): ").strip()
                if game_choice == '0':
                    continue
                game_idx = int(game_choice) - 1
                if not (0 <= game_idx < len(game_list)):
                    print("❌ Invalid selection")
                    continue
            except ValueError:
                print("❌ Invalid input")
                continue

            selected_game = game_list[game_idx]
            available_thresholds = games[selected_game]

            print(f"\n  Thresholds for {selected_game}:")
            for i, t in enumerate(available_thresholds, 1):
                print(f"  {i}. ${t}")
            print(f"  C. Enter custom threshold")
            print(f"  0. Back")

            thresh_choice = input("\nSelect threshold: ").strip().upper()
            if thresh_choice == '0':
                continue
            elif thresh_choice == 'C':
                try:
                    threshold = float(input("Enter threshold (e.g., 0.02): ").strip())
                except ValueError:
                    print("❌ Invalid number")
                    continue
            else:
                try:
                    thresh_idx = int(thresh_choice) - 1
                    if not (0 <= thresh_idx < len(available_thresholds)):
                        print("❌ Invalid selection")
                        continue
                    threshold = available_thresholds[thresh_idx]
                except ValueError:
                    print("❌ Invalid input")
                    continue

            csv_file = find_csv_file(selected_game, threshold, results_dir)
            if csv_file:
                display_spreads(csv_file, sort_by=sort_by, reverse=reverse, pairs_filter=pairs_filter)
                input("\nPress Enter to continue...")
            else:
                print(f"\n❌ No CSV found for {selected_game} with threshold ${threshold}")

        elif choice == '2':
            print("\n" + "-" * 60)
            print("  SORT OPTIONS")
            print("-" * 60)
            print(f"  Current: {sort_by} ({'desc' if reverse else 'asc'})")
            sort_options = {
                '1': 'duration_seconds',
                '2': 'total_volume',
                '3': 'avg_spread',
                '4': 'peak_spread',
                '5': 'num_trades'
            }
            for key, opt in sort_options.items():
                marker = "✓" if opt == sort_by else " "
                print(f"  {key}. [{marker}] {opt}")
            print(f"  6. Toggle order (currently {'desc' if reverse else 'asc'})")
            print(f"  0. Back")

            sort_choice = input("\nSelect (0-6): ").strip()
            if sort_choice in sort_options:
                sort_by = sort_options[sort_choice]
                print(f"  ✅ Sort by: {sort_by}")
            elif sort_choice == '6':
                reverse = not reverse
                print(f"  ✅ Order: {'descending' if reverse else 'ascending'}")

        elif choice == '3':
            print("\n" + "-" * 60)
            print("  PAIR FILTER")
            print("-" * 60)
            print(f"  Current: {pairs_display}")
            filter_options = {
                '1': (['win_yes_vs_win_no', 'win_no_vs_win_yes'], '2 WIN pairs (default)'),
                '2': (['loss_no_vs_loss_yes', 'loss_yes_vs_loss_no'], '2 LOSS pairs'),
                '3': (None, 'All 4 pairs'),
            }
            for key, (_, name) in filter_options.items():
                current = pairs_filter == filter_options[key][0]
                marker = "✓" if current else " "
                print(f"  {key}. [{marker}] {name}")
            print(f"  0. Back")

            filter_choice = input("\nSelect (0-3): ").strip()
            if filter_choice in filter_options:
                pairs_filter = filter_options[filter_choice][0]
                display = ', '.join(pairs_filter) if pairs_filter else 'all pairs'
                print(f"  ✅ Pairs: {display}")

        elif choice == '4':
            games = get_available_games(results_dir)
            if not games:
                print("\n❌ No CSV files found in", results_dir)
            else:
                print("\n" + "-" * 60)
                print("  AVAILABLE GAMES")
                print("-" * 60)
                for game in sorted(games.keys()):
                    thresholds_str = ", ".join(f"${t}" for t in games[game])
                    print(f"  {game}")
                    print(f"    Thresholds: {thresholds_str}")

        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice")


def main():
    # If no arguments provided, launch interactive mode
    if len(sys.argv) == 1:
        interactive_mode()
        return

    parser = argparse.ArgumentParser(
        description='Display detailed spread statistics from arbitrage analysis CSV files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch interactive mode
  python spread_stats_viewer.py
  
  # View a specific CSV file (default: 2 WIN pairs)
  python spread_stats_viewer.py --csv arbitrage_results/arbitrage_KXMLBGAME-25SEP28BALNYY_0.02.csv
  
  # Find and view by event and threshold (default: 2 WIN pairs)
  python spread_stats_viewer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02
  
  # View all 4 pairs
  python spread_stats_viewer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs all
  
  # Sort by volume instead of duration
  python spread_stats_viewer.py --csv arbitrage_results/arbitrage_KXMLBGAME-25SEP28BALNYY_0.02.csv --sort total_volume
  
  # List available CSV files
  python spread_stats_viewer.py --list
        """
    )
    
    parser.add_argument('--csv', help='Path to CSV file to view')
    parser.add_argument('--event', help='Event ticker to search for (e.g., KXMLBGAME-25SEP28BALNYY)')
    parser.add_argument('--threshold', type=float, help='Threshold value (e.g., 0.02)')
    parser.add_argument('--sort', default='duration_seconds', 
                        help='Column to sort by (default: duration_seconds). Options: duration_seconds, total_volume, avg_spread, peak_spread, num_trades')
    parser.add_argument('--ascending', action='store_true', help='Sort in ascending order')
    parser.add_argument('--pairs', nargs='+', default=['win_yes_vs_win_no', 'win_no_vs_win_yes'],
                        help='Which pairs to display (default: win_yes_vs_win_no win_no_vs_win_yes). Options: win_yes_vs_win_no, win_no_vs_win_yes, loss_no_vs_loss_yes, loss_yes_vs_loss_no, all')
    parser.add_argument('--results-dir', default='arbitrage_results', help='Results directory (default: arbitrage_results)')
    parser.add_argument('--list', action='store_true', help='List available CSV files')
    parser.add_argument('--interactive', '-i', action='store_true', help='Launch interactive mode')
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_mode(results_dir=args.results_dir)
        return
    
    # Handle 'all' keyword
    if args.pairs == ['all']:
        pairs = None  # None means show all pairs
    else:
        pairs = args.pairs
    
    # Handle list command
    if args.list:
        find_csv_file(results_dir=args.results_dir)
        return
    
    # Determine which CSV to use
    csv_file = None
    
    if args.csv:
        csv_file = args.csv
    elif args.event and args.threshold is not None:
        csv_file = find_csv_file(args.event, args.threshold, args.results_dir)
    elif args.event:
        csv_file = find_csv_file(args.event, results_dir=args.results_dir)
    else:
        interactive_mode(results_dir=args.results_dir)
        return
    
    if csv_file:
        display_spreads(csv_file, sort_by=args.sort, reverse=not args.ascending, pairs_filter=pairs)


if __name__ == '__main__':
    main()
