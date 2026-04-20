"""
Spread Visualizer - Create visualizations of arbitrage spread data.

Plots spreads and market volumes over time to help analyze arbitrage opportunities.
"""

import argparse
import os
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import matplotlib.dates as mdates
from pathlib import Path
from typing import Optional
import numpy as np
from datetime import datetime

# Resolve project root (parent of 'Spread Tools' folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECT_ROOT, path)


class SpreadVisualizer:
    """Visualize arbitrage spread data with plots."""
    
    def __init__(self, results_dir: str = 'arbitrage_results', verbose: bool = True):
        self.results_dir = _resolve_path(results_dir)
        self.verbose = verbose
        
        if not os.path.exists(results_dir):
            print(f"❌ Results directory not found: {results_dir}")
            exit(1)
    
    def get_available_games(self):
        """Get list of unique games from available CSV files."""
        files = list(Path(self.results_dir).glob('arbitrage_*.csv'))
        
        if not files:
            return []
        
        games = {}
        for f in files:
            parts = f.name.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
            event_ticker = parts[0] if len(parts) > 0 else None
            threshold = parts[1] if len(parts) > 1 else None
            
            if event_ticker:
                if event_ticker not in games:
                    games[event_ticker] = []
                if threshold:
                    games[event_ticker].append(float(threshold))
        
        return sorted(games.keys())
    
    def find_csv_file(self, event: str, threshold: float) -> Optional[str]:
        """Find CSV file for given event and threshold."""
        filename = f"arbitrage_{event}_{threshold}.csv"
        filepath = os.path.join(self.results_dir, filename)
        
        if os.path.exists(filepath):
            return filepath
        return None
    
    def load_spread_data(self, csv_file: str) -> pd.DataFrame:
        """Load spread data from CSV file."""
        try:
            df = pd.read_csv(csv_file)
            # Convert timestamp columns to datetime
            df['start_time'] = pd.to_datetime(df['start_time'])
            df['end_time'] = pd.to_datetime(df['end_time'])
            return df
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return None
    
    def get_game_start_time(self, event_ticker: str, games_csv: str = 'games.csv') -> Optional[datetime]:
        """
        Get the game start time from games.csv based on event ticker.
        
        Args:
            event_ticker: Event ticker (e.g., 'KXMLBGAME-25SEP28BALNYY')
            games_csv: Path to games.csv file
            
        Returns:
            Game start time as datetime, or None if not found
        """
        # Try multiple possible paths
        possible_paths = [
            games_csv,
            _resolve_path(games_csv),
            os.path.join('..', games_csv),
            os.path.join(os.path.dirname(__file__), '..', games_csv),
        ]
        
        games_csv_path = None
        for path in possible_paths:
            if os.path.exists(path):
                games_csv_path = path
                if self.verbose:
                    print(f"Found games.csv at: {games_csv_path}")
                break
        
        if games_csv_path is None:
            if self.verbose:
                print(f"Could not find games.csv in: {possible_paths}")
            return None
        
        try:
            df = pd.read_csv(games_csv_path)
            
            # Convert game_datetime to datetime
            df['game_datetime'] = pd.to_datetime(df['game_datetime'], errors='coerce')
            
            # Extract date from event ticker (e.g., '25SEP28' from 'KXMLBGAME-25SEP28BALNYY')
            # Format: KXMLBGAME-YYMMDDTEAMS where MMM is month abbreviation (3 letters)
            parts = event_ticker.split('-')
            if len(parts) < 2:
                if self.verbose:
                    print(f"Could not parse event ticker: {event_ticker}")
                return None
            
            # Date format is YYMMMDD (2 + 3 + 2 = 7 characters), e.g., '25SEP28'
            date_part = parts[1][:7]
            
            if len(date_part) >= 6:
                try:
                    # Parse as YYMMMDD (e.g., 25SEP28)
                    game_date = pd.to_datetime(date_part, format='%y%b%d')
                    if self.verbose:
                        print(f"Looking for games on: {game_date.date()}")
                    
                    # Find games from that date
                    df['game_date'] = df['game_datetime'].dt.date
                    matching_games = df[df['game_date'] == game_date.date()]
                    
                    if self.verbose:
                        print(f"Found {len(matching_games)} games on that date")
                    
                    if not matching_games.empty:
                        # Return the first game's start time from game_datetime
                        game_start = matching_games.iloc[0]['game_datetime']
                        # Remove timezone info to match tz-naive spread data
                        if hasattr(game_start, 'tz_localize'):
                            game_start = game_start.tz_localize(None)
                        elif hasattr(game_start, 'replace'):
                            game_start = game_start.replace(tzinfo=None)
                        if self.verbose:
                            print(f"Game start time: {game_start}")
                        return game_start
                    else:
                        if self.verbose:
                            print(f"No games found for date {game_date.date()}")
                except Exception as e:
                    if self.verbose:
                        print(f"Error parsing date from ticker: {e}")
                    pass
            
            return None
        except Exception as e:
            if self.verbose:
                print(f"Error reading games.csv: {e}")
            return None
    
    def plot_spread_and_volume(self, csv_file: str, pair_filter: Optional[str] = None, save_path: Optional[str] = None, show_all_pairs: bool = False):
        """
        Plot spread and volume data for each arbitrage pair.
        
        Args:
            csv_file: Path to CSV file
            pair_filter: Specific pair to plot (e.g., 'win_yes_vs_win_no'). If None, uses default (2 WIN pairs).
            save_path: Path to save the plot. If None, displays interactively.
            show_all_pairs: If True, shows all 4 pairs. If False (default), shows only 2 WIN pairs.
        """
        df = self.load_spread_data(csv_file)
        if df is None:
            return
        
        # Filter by pair if specified
        if pair_filter:
            df = df[df['arbitrage_type'].str.contains(pair_filter, case=False, na=False)]
            if df.empty:
                print(f"❌ No data found for pair: {pair_filter}")
                return
        elif not show_all_pairs:
            # Default: filter to 2 WIN pairs only
            df_filtered = df[df['arbitrage_type'].str.contains('WIN', case=False, na=False)]
            if not df_filtered.empty:
                df = df_filtered
        
        # Get unique arbitrage types
        arb_types = df['arbitrage_type'].unique()
        
        # Extract filename info
        filename = os.path.basename(csv_file)
        parts = filename.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
        game = parts[0] if len(parts) > 0 else "Unknown"
        threshold = parts[1] if len(parts) > 1 else "Unknown"
        
        # Get game start time - convert from UTC to US/Pacific (naive) to match arbitrage data
        game_start_time_raw = self.get_game_start_time(game)
        game_start_time = None
        if game_start_time_raw is not None:
            ts = pd.Timestamp(game_start_time_raw)
            # The raw value is UTC (from games.csv). Convert to Pacific to match arbitrage CSV times.
            if ts.tzinfo is not None:
                game_start_time = ts.tz_convert('US/Pacific').tz_localize(None)
            else:
                game_start_time = ts.tz_localize('UTC').tz_convert('US/Pacific').tz_localize(None)
        if self.verbose and game_start_time is not None:
            print(f"📍 Game start time (PT, naive): {game_start_time}")
        elif self.verbose:
            print(f"⚠️  Could not find game start time for {game}")
        
        # Create subplots for each arbitrage type
        num_pairs = len(arb_types)
        fig, axes = plt.subplots(num_pairs, 1, figsize=(14, 5 * num_pairs))
        
        # Handle single plot case
        if num_pairs == 1:
            axes = [axes]
        
        fig.suptitle(f'{game} | Threshold: ${threshold}\nSpread and Volume Analysis', 
                     fontsize=16, fontweight='bold', y=0.995)
        
        for idx, arb_type in enumerate(sorted(arb_types)):
            ax = axes[idx]
            subset = df[df['arbitrage_type'] == arb_type].copy().sort_values('start_time').reset_index(drop=True)
            # Ensure all timestamps are tz-naive
            subset['start_time'] = pd.to_datetime(subset['start_time'])
            subset['end_time'] = pd.to_datetime(subset['end_time'])
            # Strip any timezone info (data is already in Eastern time)
            if subset['start_time'].dt.tz is not None:
                subset['start_time'] = subset['start_time'].dt.tz_localize(None)
                subset['end_time'] = subset['end_time'].dt.tz_localize(None)
            if self.verbose and len(subset) > 0:
                print("First 3 spread event start times (ET, naive):")
                print(subset['start_time'].head(3))
            
            if subset.empty:
                continue
            
            # Find where game start time falls relative to events using time interpolation
            game_start_index = None
            if game_start_time is not None and len(subset) > 0:
                first_time = subset.iloc[0]['start_time']
                last_time = subset.iloc[-1]['end_time']
                
                if game_start_time < first_time:
                    # Before all events - extrapolate left
                    if len(subset) > 1:
                        time_per_event = (last_time - first_time).total_seconds() / (len(subset) - 1)
                        offset = (first_time - game_start_time).total_seconds() / max(time_per_event, 1)
                        game_start_index = -offset
                    else:
                        game_start_index = -1
                elif game_start_time > last_time:
                    # After all events - extrapolate right
                    if len(subset) > 1:
                        time_per_event = (last_time - first_time).total_seconds() / (len(subset) - 1)
                        offset = (game_start_time - last_time).total_seconds() / max(time_per_event, 1)
                        game_start_index = len(subset) - 1 + offset
                    else:
                        game_start_index = 1
                else:
                    # Within data range - interpolate between events
                    for i in range(len(subset)):
                        event_start = subset.iloc[i]['start_time']
                        event_end = subset.iloc[i]['end_time']
                        if event_start <= game_start_time <= event_end:
                            game_start_index = float(i)
                            break
                        elif i < len(subset) - 1:
                            next_start = subset.iloc[i + 1]['start_time']
                            if event_end <= game_start_time <= next_start:
                                gap_total = (next_start - event_end).total_seconds()
                                gap_elapsed = (game_start_time - event_end).total_seconds()
                                frac = gap_elapsed / max(gap_total, 1)
                                game_start_index = i + frac
                                break
                    if game_start_index is None:
                        game_start_index = len(subset) - 0.5
            if self.verbose:
                print(f"[DEBUG] Spread/Volume plot: game_start_index = {game_start_index}")
            
            # Create dual-axis plot
            ax1 = ax
            ax2 = ax1.twinx()
            
            # Plot absolute spread as bars on primary axis
            color_spread = '#2E86AB'
            event_indices = np.arange(len(subset))
            bar_width = 0.35
            
            # Plot peak spread bars
            bars = ax1.bar(event_indices - bar_width/2, subset['peak_spread'].values, 
                   width=bar_width, color=color_spread, alpha=0.8, label='Peak Spread', zorder=3)
            
            # Add duration labels on spread bars
            for bar, duration in zip(bars, subset['duration_seconds'].values):
                height = bar.get_height()
                # Format duration nicely
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                if minutes > 0:
                    duration_str = f"{minutes}m{seconds}s"
                else:
                    duration_str = f"{seconds}s"
                
                # Place text at center of bar
                ax1.text(bar.get_x() + bar.get_width()/2, height/2, duration_str,
                        ha='center', va='center', fontsize=9, fontweight='bold',
                        color='white', bbox=dict(boxstyle='round,pad=0.3', 
                        facecolor='black', alpha=0.7, edgecolor='white', linewidth=0.5))
            
            ax1.set_ylabel('Spread ($)', fontsize=11, fontweight='bold', color=color_spread)
            ax1.tick_params(axis='y', labelcolor=color_spread)
            ax1.grid(True, alpha=0.3, linestyle='--', axis='y')
            
            # Plot volumes on secondary axis
            color_vol1 = '#A23B72'
            color_vol2 = '#F18F01'
            
            # Get market labels
            market1_label = subset.iloc[0]['market1'] if 'market1' in subset.columns else 'Market 1'
            market2_label = subset.iloc[0]['market2'] if 'market2' in subset.columns else 'Market 2'
            
            # Plot volume bars with offset
            volume_bar_width = 0.15
            ax2.bar(event_indices + volume_bar_width/2, subset['market1_volume'].values, 
                   width=volume_bar_width, alpha=0.6, color=color_vol1, label=f'{market1_label} Volume')
            
            ax2.bar(event_indices + volume_bar_width/2 + volume_bar_width, subset['market2_volume'].values, 
                   width=volume_bar_width, alpha=0.6, color=color_vol2, label=f'{market2_label} Volume')
            
            ax2.set_ylabel('Volume (Contracts)', fontsize=11, fontweight='bold')
            ax2.tick_params(axis='y')
            
            # Add game start line BEFORE creating legend
            if game_start_index is not None:
                ax1.axvline(x=game_start_index, color='green', linestyle='--', linewidth=2.5, 
                           label='Game Start (1st Pitch)', alpha=0.8, zorder=5)
                # Add time label at top of the line
                if game_start_time is not None:
                    time_str = game_start_time.strftime('%I:%M %p')
                    ax1.annotate(time_str, xy=(game_start_index, 1), xycoords=('data', 'axes fraction'),
                                ha='center', va='bottom', fontsize=9, fontweight='bold', color='green',
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='green', alpha=0.8))
                # Always extend x-axis to show the line
                current_xlim = ax1.get_xlim()
                min_x = min(current_xlim[0], game_start_index - 1)
                max_x = max(current_xlim[1], game_start_index + 1)
                ax1.set_xlim(min_x, max_x)
            
            # Set labels and title
            ax.set_title(arb_type, fontsize=12, fontweight='bold', pad=10)
            ax.set_xlabel('Spread Event #', fontsize=11, fontweight='bold')
            ax.set_xticks(event_indices)
            ax.set_xticklabels([f'{i+1}' for i in event_indices])
            
            # Add legends - get after adding game start line
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)
            
            # Extend x-axis to ensure game start line is visible
            if game_start_index is not None:
                current_xlim = ax1.get_xlim()
                new_xlim = (min(current_xlim[0], game_start_index - 0.5), 
                           max(current_xlim[1], game_start_index + len(subset) + 0.5))
                ax1.set_xlim(new_xlim)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\n✅ Plot saved to: {save_path}")
        else:
            plt.show()
    
    def plot_all_spreads_timeline(self, csv_file: str, pair_filter: Optional[str] = None, 
                                 save_path: Optional[str] = None, show_all_pairs: bool = False):
        """
        Create spread vs time plots for each arbitrage pair with threshold line.
        
        Shows how spread evolved over time with threshold marked as reference.
        
        Args:
            csv_file: Path to CSV file
            pair_filter: Specific pair to plot (e.g., 'win_yes_vs_win_no'). If None, uses default (2 WIN pairs).
            save_path: Path to save the plot. If None, displays interactively.
            show_all_pairs: If True, shows all 4 pairs. If False (default), shows only 2 WIN pairs.
        """
        df = self.load_spread_data(csv_file)
        if df is None:
            return
        
        # Filter by pair if specified
        if pair_filter:
            df = df[df['arbitrage_type'].str.contains(pair_filter, case=False, na=False)]
            if df.empty:
                print(f"❌ No data found for pair: {pair_filter}")
                return
        elif not show_all_pairs:
            # Default: filter to 2 WIN pairs only
            df_filtered = df[df['arbitrage_type'].str.contains('WIN', case=False, na=False)]
            if not df_filtered.empty:
                df = df_filtered
        
        # Extract filename info
        filename = os.path.basename(csv_file)
        parts = filename.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
        game = parts[0] if len(parts) > 0 else "Unknown"
        threshold_str = parts[1] if len(parts) > 1 else "Unknown"
        threshold_val = float(threshold_str) if threshold_str != "Unknown" else 0
        
        # Get game start time - convert from UTC to US/Pacific (naive) to match arbitrage data
        game_start_time_raw = self.get_game_start_time(game)
        game_start_time = None
        if game_start_time_raw is not None:
            ts = pd.Timestamp(game_start_time_raw)
            if ts.tzinfo is not None:
                game_start_time = ts.tz_convert('US/Pacific').tz_localize(None)
            else:
                game_start_time = ts.tz_localize('UTC').tz_convert('US/Pacific').tz_localize(None)
        if self.verbose and game_start_time is not None:
            print(f"📍 Timeline plot - Game start time (PT, naive): {game_start_time}")
        
        # Sort by start time and ensure tz-naive (data is already in Eastern time)
        df = df.copy()
        df['start_time'] = pd.to_datetime(df['start_time'])
        df['end_time'] = pd.to_datetime(df['end_time'])
        if df['start_time'].dt.tz is not None:
            df['start_time'] = df['start_time'].dt.tz_localize(None)
            df['end_time'] = df['end_time'].dt.tz_localize(None)
        df = df.sort_values('start_time')
        
        # Get unique arbitrage types
        arb_types = sorted(df['arbitrage_type'].unique())
        
        # Create subplots for each arbitrage type
        num_pairs = len(arb_types)
        fig, axes = plt.subplots(num_pairs, 1, figsize=(14, 4 * num_pairs))
        
        # Handle single plot case
        if num_pairs == 1:
            axes = [axes]
        
        fig.suptitle(f'{game} | Threshold: ${threshold_str}\nSpread vs Time', 
                     fontsize=16, fontweight='bold', y=0.995)
        
        # Compute global time range across all arb types for consistent x-axes
        global_min_time = df['start_time'].min()
        global_max_time = df['end_time'].max()
        if game_start_time is not None:
            global_min_time = min(global_min_time, game_start_time)
            global_max_time = max(global_max_time, game_start_time)
        global_time_range = global_max_time - global_min_time
        global_xlim = (global_min_time - global_time_range * 0.05, global_max_time + global_time_range * 0.05)
        
        for idx, arb_type in enumerate(arb_types):
            ax = axes[idx]
            subset = df[df['arbitrage_type'] == arb_type].copy().sort_values('start_time')
            subset['start_time'] = pd.to_datetime(subset['start_time'])
            subset['end_time'] = pd.to_datetime(subset['end_time'])
            if subset['start_time'].dt.tz is not None:
                subset['start_time'] = subset['start_time'].dt.tz_localize(None)
                subset['end_time'] = subset['end_time'].dt.tz_localize(None)
            
            if subset.empty:
                continue
            
            # Plot spread values over time for each event
            color_avg = '#2E86AB'
            color_peak = '#A23B72'
            color_min = '#F18F01'
            
            for _, row in subset.iterrows():
                start = row['start_time']
                end = row['end_time']
                
                # Create time array for this event
                times = [start, end]
                
                # Plot average spread as line
                avg_values = [row['avg_spread'], row['avg_spread']]
                ax.plot(times, avg_values, color=color_avg, linewidth=2.5, alpha=0.7, zorder=2)
                
                # Plot peak spread dashed line
                peak_values = [row['peak_spread'], row['peak_spread']]
                ax.plot(times, peak_values, color=color_peak, linewidth=2, linestyle='--', 
                       alpha=0.6, zorder=2)
                
                # Plot min spread dashed line
                min_values = [row['min_spread'], row['min_spread']]
                ax.plot(times, min_values, color=color_min, linewidth=1.5, linestyle=':', 
                       alpha=0.5, zorder=1)
                
                # Fill area between min and peak spread
                ax.fill_between(times, min_values, peak_values, alpha=0.15, color=color_avg, zorder=0)
            
            # Add threshold line
            all_times = [pd.to_datetime(t) for t in df['start_time'].unique()]
            if all_times:
                min_time = min(all_times)
                max_time = max(subset['end_time'])
                ax.axhline(y=threshold_val, color='red', linestyle='-', linewidth=2.5, 
                          label=f'Threshold: ${threshold_val}', zorder=4, alpha=0.8)
            
            # Add game start time vertical line
            if game_start_time is not None:
                ax.axvline(x=game_start_time, color='green', linestyle='--', linewidth=2.5, 
                          label='Game Start (1st Pitch)', zorder=5, alpha=0.8)
            
            # Use global x-axis limits so all subplots are aligned
            ax.set_xlim(global_xlim)
            
            # Set labels and styling
            ax.set_ylabel('Spread ($)', fontsize=11, fontweight='bold')
            ax.set_xlabel('Time', fontsize=11, fontweight='bold')
            ax.set_title(arb_type, fontsize=12, fontweight='bold', pad=10)
            
            # Format x-axis
            ax.xaxis.set_major_formatter(DateFormatter('%H:%M:%S'))
            fig.autofmt_xdate(rotation=45, ha='right')
            
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.set_axisbelow(True)
            
            # Add legend - reconstruct to include all elements
            legend_lines = [
                plt.Line2D([0], [0], color=color_avg, linewidth=2.5, alpha=0.7, label='Avg Spread'),
                plt.Line2D([0], [0], color=color_peak, linewidth=2, linestyle='--', alpha=0.6, label='Peak Spread'),
                plt.Line2D([0], [0], color=color_min, linewidth=1.5, linestyle=':', alpha=0.5, label='Min Spread'),
                plt.Line2D([0], [0], color='red', linewidth=2.5, label=f'Threshold: ${threshold_str}'),
            ]
            
            # Add game start line to legend if it exists
            if game_start_time is not None:
                legend_lines.append(plt.Line2D([0], [0], color='green', linewidth=2.5, linestyle='--', 
                                               label='Game Start (1st Pitch)'))
            
            ax.legend(handles=legend_lines, loc='upper left', fontsize=10)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\n✅ Spread vs time plot saved to: {save_path}")
        else:
            plt.show()
    
    def interactive_menu(self):
        """Show interactive menu for visualization."""
        while True:
            print("\n" + "="*70)
            print("SPREAD VISUALIZER - Interactive Menu")
            print("="*70)
            
            games = self.get_available_games()
            
            if not games:
                print("❌ No games found in results directory")
                return
            
            print("\nAvailable Games:")
            for i, game in enumerate(games, 1):
                print(f"{i}. {game}")
            
            print("\n0. Exit")
            
            try:
                choice = int(input("\nSelect game (0 to exit): ")) - 1
                
                if choice == -1:
                    break
                
                if 0 <= choice < len(games):
                    selected_game = games[choice]
                    self._select_threshold_and_visualize(selected_game)
                else:
                    print("❌ Invalid selection")
            
            except ValueError:
                print("❌ Invalid input")
    
    def _select_threshold_and_visualize(self, game: str):
        """Select threshold and visualization type for a game."""
        thresholds = []
        files = list(Path(self.results_dir).glob(f'arbitrage_{game}_*.csv'))
        
        for f in files:
            parts = f.name.replace('arbitrage_', '').replace('.csv', '').rsplit('_', 1)
            if len(parts) > 1:
                try:
                    thresholds.append(float(parts[1]))
                except ValueError:
                    pass
        
        if not thresholds:
            print(f"❌ No thresholds found for {game}")
            return
        
        print(f"\n{'='*70}")
        print(f"THRESHOLDS FOR {game}")
        print(f"{'='*70}")
        
        for i, t in enumerate(sorted(thresholds), 1):
            print(f"{i}. ${t}")
        
        print("\n0. Back")
        
        try:
            choice = int(input("\nSelect threshold (0 to cancel): ")) - 1
            
            if choice == -1:
                return
            
            if 0 <= choice < len(thresholds):
                threshold = sorted(thresholds)[choice]
                self._visualization_options(game, threshold)
            else:
                print("❌ Invalid selection")
        
        except ValueError:
            print("❌ Invalid input")
    
    def _visualization_options(self, game: str, threshold: float):
        """Show visualization options."""
        csv_file = self.find_csv_file(game, threshold)
        
        if not csv_file:
            print(f"❌ CSV file not found")
            return
        
        print(f"\n{'='*70}")
        print(f"VISUALIZATION OPTIONS")
        print(f"{'='*70}")
        print("1. Spread & Volume Plot (2 WIN pairs - default)")
        print("2. Spread Timeline (2 WIN pairs - default)")
        print("3. Both plots (2 WIN pairs)")
        print("4. Spread & Volume Plot (all 4 pairs)")
        print("5. Spread Timeline (all 4 pairs)")
        print("6. Both plots (all 4 pairs)")
        print("0. Back")
        
        try:
            choice = input("\nSelect visualization (0-6): ").strip()
            
            if choice == '1':
                self.plot_spread_and_volume(csv_file)
            elif choice == '2':
                self.plot_all_spreads_timeline(csv_file)
            elif choice == '3':
                self.plot_spread_and_volume(csv_file)
                self.plot_all_spreads_timeline(csv_file)
            elif choice == '4':
                self.plot_spread_and_volume(csv_file, show_all_pairs=True)
            elif choice == '5':
                self.plot_all_spreads_timeline(csv_file, show_all_pairs=True)
            elif choice == '6':
                self.plot_spread_and_volume(csv_file, show_all_pairs=True)
                self.plot_all_spreads_timeline(csv_file, show_all_pairs=True)
            elif choice != '0':
                print("❌ Invalid selection")
        
        except Exception as e:
            print(f"❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Visualize arbitrage spread data with plots',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python spread_visualizer.py
  
  # Plot specific game and threshold
  python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02
  
  # Plot timeline view
  python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --timeline
  
  # Save to file
  python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --save plot.png
  
  # Filter by pair
  python spread_visualizer.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pair win_yes_vs_win_no
        """
    )
    
    parser.add_argument('--event', help='Event ticker (e.g., KXMLBGAME-25SEP28BALNYY)')
    parser.add_argument('--threshold', type=float, help='Spread threshold')
    parser.add_argument('--timeline', action='store_true', help='Show timeline view instead of spread/volume plot')
    parser.add_argument('--pair', help='Filter by arbitrage pair (e.g., win_yes_vs_win_no)')
    parser.add_argument('--all-pairs', action='store_true', help='Show all 4 pairs instead of default 2 WIN pairs')
    parser.add_argument('--save', help='Save plot to file instead of displaying')
    parser.add_argument('--results-dir', default='arbitrage_results', help='Results directory')
    
    args = parser.parse_args()
    
    visualizer = SpreadVisualizer(results_dir=args.results_dir)
    
    if args.event and args.threshold is not None:
        csv_file = visualizer.find_csv_file(args.event, args.threshold)
        
        if not csv_file:
            print(f"❌ CSV file not found for {args.event} with threshold {args.threshold}")
            return
        
        if args.timeline:
            visualizer.plot_all_spreads_timeline(csv_file, pair_filter=args.pair, save_path=args.save, show_all_pairs=args.all_pairs)
        else:
            visualizer.plot_spread_and_volume(csv_file, pair_filter=args.pair, save_path=args.save, show_all_pairs=args.all_pairs)
    else:
        visualizer.interactive_menu()


if __name__ == '__main__':
    main()
