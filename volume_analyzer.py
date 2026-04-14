import argparse
import duckdb
import pandas as pd
import matplotlib.pyplot as plt


def plot_trade_volume(db_path='kalshi_mlb.db', event_ticker='KXMLBGAME-25SEP28BALNYY', save_path=None):
    con = duckdb.connect(db_path)

    # Get market tickers for this event
    markets = con.execute(f"""
        SELECT market_ticker
        FROM event_market_map
        WHERE event_ticker = '{event_ticker}'
    """).fetchall()

    if not markets:
        print(f'No markets found for event {event_ticker}')
        return

    market_tickers = [m[0] for m in markets]
    print(f'Found markets: {market_tickers}')

    # Find BAL and NYY tickers
    bal_ticker = next((t for t in market_tickers if t.endswith('-BAL')), None)
    nyy_ticker = next((t for t in market_tickers if t.endswith('-NYY')), None)

    if not bal_ticker or not nyy_ticker:
        print('BAL or NYY market not found.')
        return

    # Query BAL NO trades
    df_bal_no = con.execute(f"""
        SELECT created_time, count_fp
        FROM trades
        WHERE ticker = '{bal_ticker}' AND taker_side = 'no'
        ORDER BY created_time
    """).df()

    # Query NYY YES trades
    df_nyy_yes = con.execute(f"""
        SELECT created_time, count_fp
        FROM trades
        WHERE ticker = '{nyy_ticker}' AND taker_side = 'yes'
        ORDER BY created_time
    """).df()

    con.close()

    if df_bal_no.empty and df_nyy_yes.empty:
        print('No trade data found for BAL NO or NYY YES.')
        return

    # Process BAL NO
    if not df_bal_no.empty:
        df_bal_no['created_time'] = pd.to_datetime(df_bal_no['created_time'])
        df_bal_no.set_index('created_time', inplace=True)
        start_time = pd.Timestamp('2025-09-28 12:00:00')
        end_time = pd.Timestamp('2025-09-28 16:00:00')
        df_bal_no = df_bal_no[(df_bal_no.index >= start_time) & (df_bal_no.index <= end_time)]
        bal_volume = df_bal_no['count_fp'].resample('1min').sum()
    else:
        bal_volume = pd.Series(dtype=float)

    # Process NYY YES
    if not df_nyy_yes.empty:
        df_nyy_yes['created_time'] = pd.to_datetime(df_nyy_yes['created_time'])
        df_nyy_yes.set_index('created_time', inplace=True)
        df_nyy_yes = df_nyy_yes[(df_nyy_yes.index >= start_time) & (df_nyy_yes.index <= end_time)]
        nyy_volume = df_nyy_yes['count_fp'].resample('1min').sum()
    else:
        nyy_volume = pd.Series(dtype=float)

    # Plot
    fig, ax = plt.subplots(figsize=(15, 6))
    if not bal_volume.empty:
        ax.plot(bal_volume.index, bal_volume.values, linewidth=2, label='BAL NO Volume', color='#1f77b4')
        ax.fill_between(bal_volume.index, bal_volume.values, alpha=0.3, color='#1f77b4')
    if not nyy_volume.empty:
        ax.plot(nyy_volume.index, nyy_volume.values, linewidth=2, label='NYY YES Volume', color='#ff7f0e')
        ax.fill_between(nyy_volume.index, nyy_volume.values, alpha=0.3, color='#ff7f0e')

    ax.set_title(f'Trade Volume Over Time (12:00-16:00): BAL NO vs NYY YES - {event_ticker}', fontsize=14, fontweight='bold')
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Volume (count_fp)', fontsize=12)
    ax.legend()
    ax.grid(True, alpha=0.25)

    plt.tight_layout()

    if save_path is None:
        save_path = f'volume_plot_{event_ticker}.png'

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f'Plot saved to {save_path}')
    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot trade volume over time for a Kalshi MLB game.')
    parser.add_argument('--event', default='KXMLBGAME-25SEP28BALNYY', help='Event ticker to analyze')
    parser.add_argument('--db', default='kalshi_mlb.db', help='Path to DuckDB database file')
    parser.add_argument('--save', help='Output file path for the plot')
    args = parser.parse_args()

    plot_trade_volume(db_path=args.db, event_ticker=args.event, save_path=args.save)
