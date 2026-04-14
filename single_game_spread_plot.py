import argparse
import duckdb
import pandas as pd
import matplotlib.pyplot as plt


def plot_single_game_spread(db_path='kalshi_mlb.db', event_ticker='KXMLBGAME-25SEP28TEXCLE', min_diff=0.05, min_duration=1.0, save_path=None):
    con = duckdb.connect(db_path)

    if event_ticker is None:
        event_ticker = 'KXMLBGAME-25SEP28TEXCLE'

    if event_ticker.endswith('-TEX'):
        tex_ticker = event_ticker
        cle_ticker = event_ticker[:-4] + '-CLE'
    elif event_ticker.endswith('-CLE'):
        cle_ticker = event_ticker
        tex_ticker = event_ticker[:-4] + '-TEX'
    else:
        tex_ticker = f"{event_ticker}-TEX"
        cle_ticker = f"{event_ticker}-CLE"

    df_cle = con.execute(f"""
        SELECT created_time, no_price_dollars as cle_no_price
        FROM trades
        WHERE ticker = '{cle_ticker}'
        AND taker_side = 'no'
        ORDER BY created_time
    """).df()

    df_tex = con.execute(f"""
        SELECT created_time, yes_price_dollars as tex_yes_price
        FROM trades
        WHERE ticker = '{tex_ticker}'
        AND taker_side = 'yes'
        ORDER BY created_time
    """).df()

    con.close()

    if df_cle.empty or df_tex.empty:
        print('Missing CLE NO or TEX YES trade data for this event.')
        return

    df = pd.merge(df_cle, df_tex, on='created_time', how='outer').sort_values('created_time')
    df['created_time'] = pd.to_datetime(df['created_time'])
    df['cle_no_price'] = df['cle_no_price'].ffill()
    df['tex_yes_price'] = df['tex_yes_price'].ffill()
    df = df.dropna(subset=['cle_no_price', 'tex_yes_price']).reset_index(drop=True)

    # Limit plot to the afternoon window
    start_time = pd.Timestamp('2025-09-28 12:00:00')
    end_time = pd.Timestamp('2025-09-28 15:00:00')
    df = df[(df['created_time'] >= start_time) & (df['created_time'] <= end_time)].copy()

    if df.empty:
        print('No data available in the 12:00-15:00 window for this event.')
        return

    df['price_sum'] = df['cle_no_price'] + df['tex_yes_price']
    df['price_diff'] = (df['tex_yes_price'] - df['cle_no_price']).abs()
    df['valid'] = (df['price_sum'] < 1.0) & (df['price_diff'] > min_diff)

    if not df['valid'].any():
        print('No opportunities found in the 12:00-15:00 window for this CLE/TEX pair.')
        return

    df['segment_id'] = (df['valid'] != df['valid'].shift(1)).cumsum()
    valid_segments = df[df['valid']].groupby('segment_id')

    fig, ax1 = plt.subplots(1, 1, figsize=(15, 6), sharex=True)

    highlighted_segments = []
    for _, segment in valid_segments:
        start = segment['created_time'].iloc[0]
        end = segment['created_time'].iloc[-1]
        duration = (end - start).total_seconds()
        if duration >= min_duration:
            highlighted_segments.append((start, end, duration))

    if not highlighted_segments:
        print('No sustained valid segments found for the requested minimum duration in the 12:00-15:00 window.')
        return

    for start, end, duration in highlighted_segments:
        ax1.axvspan(start, end, color='gold', alpha=0.25)

    ax1.step(df['created_time'], df['cle_no_price'], where='post', label=f'{cle_ticker} NO Price', color='#1f77b4')
    ax1.step(df['created_time'], df['tex_yes_price'], where='post', label=f'{tex_ticker} YES Price', color='#ff7f0e')
    ax1.scatter(df.loc[df['valid'], 'created_time'], df.loc[df['valid'], 'tex_yes_price'],
                s=30, c='red', marker='o', label='Valid opportunity points', edgecolors='black')

    ax1.set_ylabel('Price ($)', fontsize=12)
    ax1.set_title(f'CLE NO vs TEX YES Price Plot (12:00-15:00): {event_ticker}', fontsize=14, fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.25)
    ax1.set_xlabel('Time', fontsize=12)

    plt.tight_layout()

    if save_path is None:
        save_path = f'single_game_spread_{event_ticker}.png'

    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f'Plot saved to {save_path}')
    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Plot the CLE NO vs TEX YES spread for one game.')
    parser.add_argument('--event', default='KXMLBGAME-25SEP28TEXCLE', help='Event ticker to plot (default is TEX vs CLE)')
    parser.add_argument('--db', default='kalshi_mlb.db', help='Path to DuckDB database file')
    parser.add_argument('--diff', type=float, default=0.05, help='Minimum price difference threshold')
    parser.add_argument('--duration', type=float, default=1.0, help='Minimum sustained opportunity duration in seconds')
    parser.add_argument('--save', help='Output file path for the plot')
    args = parser.parse_args()

    plot_single_game_spread(db_path=args.db, event_ticker=args.event, min_diff=args.diff, min_duration=args.duration, save_path=args.save)