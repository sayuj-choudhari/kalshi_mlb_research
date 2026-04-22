"""
Interactive runner for the arbitrage tracker.

Provides convenient ways to analyze one game or batch analyze multiple games.
"""

import os
import sys

# Resolve project root (parent of 'Spread Tools' folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Add this folder to sys.path so sibling imports work
if os.path.dirname(__file__) not in sys.path:
    sys.path.insert(0, os.path.dirname(__file__))

from arbitrage_tracker import ArbitrageTracker
import duckdb
import pandas as pd


def _resolve_path(path: str) -> str:
    """Resolve a relative path against the project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_PROJECT_ROOT, path)


def list_available_games(db_path='kalshi_event_market_map.db'):
    """List all available games in the database."""
    db_path = _resolve_path(db_path)
    try:
        con = duckdb.connect(db_path)
        events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map ORDER BY event_ticker").fetchall()
        con.close()
        
        if not events:
            print("No games found in database.")
            return []
        
        game_list = [e[0] for e in events]
        print(f"\nFound {len(game_list)} games in database:")
        print("="*70)
        for i, game in enumerate(game_list, 1):
            print(f"{i:2d}. {game}")
        print("="*70)
        return game_list
    except Exception as e:
        print(f"Error reading database: {e}")
        return []


def analyze_single_game():
    """Interactive single game analysis."""
    print("\n" + "="*70)
    print("SINGLE GAME ANALYSIS")
    print("="*70)
    
    # List available games
    games = list_available_games()
    if not games:
        print("No games available to analyze.")
        return
    
    # Get user input
    while True:
        try:
            game_choice = input("\nEnter game number or full ticker (or 'q' to quit): ").strip()
            
            if game_choice.lower() == 'q':
                return
            
            # Check if it's a number
            if game_choice.isdigit():
                idx = int(game_choice) - 1
                if 0 <= idx < len(games):
                    event_ticker = games[idx]
                else:
                    print("Invalid selection. Please try again.")
                    continue
            else:
                # Use as-is (assumed to be full ticker)
                event_ticker = game_choice
            
            break
        except ValueError:
            print("Invalid input. Please enter a number or game ticker.")
    
    # Get threshold
    while True:
        try:
            threshold_input = input("Enter spread threshold (default 0.02, range 0.01-0.10): ").strip()
            if not threshold_input:
                threshold = 0.02
            else:
                threshold = float(threshold_input)
                if not (0.01 <= threshold <= 0.10):
                    print("Threshold should be between 0.01 and 0.10")
                    continue
            break
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    # Run analysis
    print(f"\nAnalyzing {event_ticker} with threshold ${threshold:.4f}...")
    try:
        tracker = ArbitrageTracker(
            event_ticker=event_ticker,
            spread_threshold=threshold
        )
        tracker.run_analysis()
    except Exception as e:
        print(f"[ERROR] Error during analysis: {e}")


def analyze_all_games():
    """Batch analyze all games with a given threshold."""
    print("\n" + "="*70)
    print("BATCH ANALYSIS - ALL GAMES")
    print("="*70)
    
    games = list_available_games()
    if not games:
        return
    
    # Get threshold
    while True:
        try:
            threshold_input = input("\nEnter spread threshold for all games (default 0.02): ").strip()
            if not threshold_input:
                threshold = 0.02
            else:
                threshold = float(threshold_input)
            break
        except ValueError:
            print("Invalid input.")
    
    print(f"\nAnalyzing {len(games)} games with threshold ${threshold:.4f}...\n")
    
    successful = 0
    failed = 0
    
    for i, event_ticker in enumerate(games, 1):
        print(f"\n[{i}/{len(games)}] {event_ticker}")
        try:
            tracker = ArbitrageTracker(
                event_ticker=event_ticker,
                spread_threshold=threshold
            )
            tracker.run_analysis()
            successful += 1
        except Exception as e:
            print(f"  ❌ Failed: {e}")
            failed += 1
    
    print(f"\n" + "="*70)
    print(f"BATCH COMPLETE: {successful} successful, {failed} failed")
    print("="*70)


def main():
    """Main menu."""
    db_path = _resolve_path('kalshi_unified_market_data.db')
    if not os.path.exists(db_path):
        print(f"[ERROR] Error: kalshi_unified_market_data.db not found at {db_path}")
        print("   Make sure the database exists in the project root directory.")
        return
    
    while True:
        print("\n" + "="*70)
        print("ARBITRAGE TRACKER - MAIN MENU")
        print("="*70)
        print("1. Analyze single game")
        print("2. Batch analyze all games")
        print("3. List available games")
        print("4. Exit")
        print("-"*70)
        
        choice = input("Select option (1-4): ").strip()
        
        if choice == '1':
            analyze_single_game()
        elif choice == '2':
            confirm = input("\nThis will analyze all games. Continue? (y/n): ").strip().lower()
            if confirm == 'y':
                analyze_all_games()
        elif choice == '3':
            list_available_games()
        elif choice == '4':
            print("Exiting...")
            break
        else:
            print("Invalid option. Please try again.")


if __name__ == '__main__':
    main()
