import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

def plot_arbitrage_opportunities(db_path='kalshi_mlb.db', max_seconds=25):
    con = duckdb.connect(db_path)

    # Get all events
    events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    if not events:
        print("No events found")
        return

    print(f"Analyzing arbitrage opportunities across {len(events)} events...")

    all_opportunities = []

    for event_tuple in events:
        event_ticker = event_tuple[0]

        # Get markets for this event
        markets = con.execute(f"""
            SELECT market_ticker
            FROM event_market_map
            WHERE event_ticker = '{event_ticker}'
            LIMIT 2
        """).fetchall()

        if len(markets) < 2:
            continue

        m1_ticker, m2_ticker = markets[0][0], markets[1][0]

        # Get all M2 trades
        m2_trades = con.execute(f"""
            SELECT created_time, yes_price_dollars as m2_price
            FROM trades
            WHERE ticker = '{m2_ticker}'
            AND taker_side = 'yes'
            ORDER BY created_time
        """).df()

        if m2_trades.empty:
            continue

        # Find arbitrage opportunities
        for _, m2_trade in m2_trades.iterrows():
            m2_time = m2_trade['created_time']
            m2_price = m2_trade['m2_price']

            # Find the most recent M1 price within the time bracket
            m1_recent = con.execute(f"""
                SELECT yes_price_dollars as m1_price
                FROM trades
                WHERE ticker = '{m1_ticker}'
                AND taker_side = 'yes'
                AND created_time <= '{m2_time}'
                AND EPOCH('{m2_time}' - created_time) <= {max_seconds}
                ORDER BY created_time DESC
                LIMIT 1
            """).fetchone()

            if m1_recent:
                m1_price = m1_recent[0]
                price_sum = m1_price + m2_price
                price_diff = abs(m2_price - m1_price)
                profit = 1.0 - price_sum

                # Check arbitrage conditions
                if price_sum < 1.0 and price_diff > 0.1:
                    all_opportunities.append({
                        'event': event_ticker,
                        'time': m2_time,
                        'm1_price': m1_price,
                        'm2_price': m2_price,
                        'price_sum': price_sum,
                        'price_diff': price_diff,
                        'profit': profit
                    })

    con.close()

    if not all_opportunities:
        print("No arbitrage opportunities found!")
        return

    # Convert to DataFrame
    df = pd.DataFrame(all_opportunities)

    # Create the plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)

    # Plot 1: Profit over time
    scatter1 = ax1.scatter(df['time'], df['profit'],
                          s=df['price_diff']*500,  # Size by price difference
                          c=df['profit'],          # Color by profit amount
                          cmap='RdYlGn', alpha=0.7, edgecolors='black', linewidth=0.5)

    ax1.set_title(f'Arbitrage Opportunities Over Time (n={len(df)})', fontsize=14, fontweight='bold')
    ax1.set_ylabel('Profit ($)', fontsize=12)
    ax1.grid(True, alpha=0.3)

    # Add colorbar for profit
    cbar1 = plt.colorbar(scatter1, ax=ax1, shrink=0.8)
    cbar1.set_label('Profit Amount ($)', fontsize=10)

    # Plot 2: Price difference over time
    scatter2 = ax2.scatter(df['time'], df['price_diff'],
                          s=df['profit']*1000,    # Size by profit
                          c=df['price_sum'],      # Color by price sum (how far from 1.0)
                          cmap='coolwarm', alpha=0.7, edgecolors='black', linewidth=0.5)

    ax2.set_title('Price Differences in Arbitrage Opportunities', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Time', fontsize=12)
    ax2.set_ylabel('Price Difference (|M2 - M1|)', fontsize=12)
    ax2.grid(True, alpha=0.3)

    # Add colorbar for price sum
    cbar2 = plt.colorbar(scatter2, ax=ax2, shrink=0.8)
    cbar2.set_label('Price Sum (closer to 1.0 = tighter arb)', fontsize=10)

    plt.tight_layout()

    # Print summary statistics
    print("\n=== ARBITRAGE OPPORTUNITIES SUMMARY ===")
    print(f"Total opportunities found: {len(df)}")
    print(f"Time range: {df['time'].min()} to {df['time'].max()}")
    print(".3f")
    print(".3f")
    print(".3f")
    print(".3f")
    print(".3f")

    # Group by event
    event_counts = df.groupby('event').size().sort_values(ascending=False)
    print(f"\nTop 5 events by opportunities:")
    for event, count in event_counts.head(5).items():
        print(f"  {event}: {count}")

    plt.savefig('arbitrage_opportunities_plot.png', dpi=300, bbox_inches='tight')
    print("\nPlot saved as 'arbitrage_opportunities_plot.png'")
    plt.show()

if __name__ == "__main__":
    plot_arbitrage_opportunities(max_seconds=25)