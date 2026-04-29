import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import random

# Connect to your existing database
con = duckdb.connect("kalshi_spread_data.db")

# Use the COPY command to export the table directly to Parquet
# 'compression snappy' is the standard balance of speed and size
con.execute("COPY market_spreads TO 'kalshi_spread_data.parquet' (FORMAT PARQUET, COMPRESSION 'SNAPPY')")

con.close()
print("Conversion complete: kalshi_spread_data.parquet created.")

# Configuration
EVENT_DB = "kalshi_event_market_map.db"
MARKET_DB = "kalshi_unified_market_data.db"
RESEARCH_DB = "kalshi_spread_data.db"

def analyze_spreads(mode="summary", event_ticker=None, threshold=0.03, random_event=False):
    """Step 2: Analyzes or Visualizes the processed research data."""
    con = duckdb.connect(RESEARCH_DB)
    
    if random_event:
        available_events = con.execute("SELECT DISTINCT event FROM market_spreads").fetchall()
        if available_events:
            event_ticker = random.choice(available_events)[0]
            mode = "visualize"
            print(f"🎲 Randomly selected event: {event_ticker}")
        else:
            print("⚠️ No data in research DB. Run fetch_and_process_spreads() first.")
            return

    if mode == "visualize" and event_ticker:
        df = con.execute(f"SELECT * FROM market_spreads WHERE event = '{event_ticker}'").df()
        
        plt.figure(figsize=(14, 7))
        sns.lineplot(data=df, x='timestamp', y='spread', label='Synthetic Spread', color='#1f77b4')
        plt.axhline(y=threshold, color='red', linestyle='--', label=f'Threshold ({threshold})')
        plt.fill_between(df['timestamp'], df['spread'], threshold, 
                         where=(df['spread'] > threshold), color='red', alpha=0.15)
        
        plt.title(f"Market Microstructure: {event_ticker}", fontsize=14)
        plt.ylabel("Spread ($)")
        plt.grid(True, alpha=0.2)
        plt.legend()
        plt.show()

    elif mode == "summary":
        df = con.execute("SELECT * FROM market_spreads").df()
        
        # Duration Analysis
        df['above_thresh'] = df['spread'] > threshold
        df['segment_id'] = (df['above_thresh'] != df['above_thresh'].shift(1)).cumsum()
        
        streaks = df[df['above_thresh'] == True].copy()
        streak_stats = streaks.groupby(['event', 'segment_id']).agg(
            start=('timestamp', 'min'), end=('timestamp', 'max'), avg_spread=('spread', 'mean')
        )
        streak_stats['duration_sec'] = (streak_stats['end'] - streak_stats['start']).dt.total_seconds()

        print(f"\n--- 📊 MLB Spread Research Summary (Threshold: {threshold}) ---")
        print(f"Games Analyzed:     {df['event'].nunique()}")
        print(f"Total Wide Events:  {len(streak_stats)}")
        print(f"Avg Wide Duration:  {streak_stats['duration_sec'].mean():.2f}s")
        print(f"Median Wide Spread: ${streak_stats['avg_spread'].median():.4f}")
        
        # Inefficiency Ranking
        top_inefficient = streak_stats.groupby('event')['duration_sec'].sum().sort_values(ascending=False).head(5)
        print("\n🔥 Top 5 Most Inefficient Games (Total time > threshold):")
        print(top_inefficient)

    con.close()

analyze_spreads(random_event=False, threshold=0.03)