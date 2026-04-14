import duckdb
import pandas as pd


def analyze_tex_cle_spread(db_path='kalshi_mlb.db', event_ticker='KXMLBGAME-25SEP28TEXCLE', brackets=(5, 10, 15, 20, 25)):
    con = duckdb.connect(db_path)

    print("=== CLE NO vs TEX YES SUSTAINED SPREAD ANALYSIS ===")
    print(f"Event: {event_ticker}")
    print("Counting sustained windows where:")
    print("  1. CLE NO + TEX YES < 1.0")
    print("  2. |TEX YES - CLE NO| > 0.05")
    print("For sustained durations of 5, 10, 15, 20, and 25 seconds\n")

    if event_ticker.endswith('-CLE'):
        base_event = event_ticker[:-4]
        cle_ticker = event_ticker
        tex_ticker = f"{base_event}-TEX"
    elif event_ticker.endswith('-TEX'):
        base_event = event_ticker[:-4]
        tex_ticker = event_ticker
        cle_ticker = f"{base_event}-CLE"
    else:
        base_event = event_ticker
        cle_ticker = f"{event_ticker}-CLE"
        tex_ticker = f"{event_ticker}-TEX"

    print(f"Using CLE ticker: {cle_ticker}")
    print(f"Using TEX ticker: {tex_ticker}\n")

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
        print('Missing data for CLE NO or TEX YES.')
        return

    df = pd.merge(df_cle, df_tex, on='created_time', how='outer').sort_values('created_time')
    df['created_time'] = pd.to_datetime(df['created_time'])
    df['cle_no_price'] = df['cle_no_price'].ffill()
    df['tex_yes_price'] = df['tex_yes_price'].ffill()
    df = df.dropna(subset=['cle_no_price', 'tex_yes_price']).reset_index(drop=True)

    df['price_sum'] = df['cle_no_price'] + df['tex_yes_price']
    df['price_diff'] = (df['tex_yes_price'] - df['cle_no_price']).abs()
    df['valid'] = (df['price_sum'] < 1.0) & (df['price_diff'] > 0.05)

    if not df['valid'].any():
        print('No valid spread opportunities found for this pair.')
        return

    df['segment_id'] = (df['valid'] != df['valid'].shift(1)).cumsum()

    sustained_counts = {bracket: 0 for bracket in brackets}
    total_segments = 0

    for segment_id, segment in df[df['valid']].groupby('segment_id'):
        segment_duration = (segment['created_time'].iloc[-1] - segment['created_time'].iloc[0]).total_seconds()
        if segment_duration < 1.0:
            continue
        total_segments += 1
        for bracket in brackets:
            if segment_duration >= bracket:
                sustained_counts[bracket] += 1

    print('RESULTS:')
    print('-' * 50)
    print(f'Total sustained valid segments found: {total_segments}')
    print(f'Time range: {df["created_time"].min()} to {df["created_time"].max()}')
    print()
    for bracket in brackets:
        print(f"{bracket:2d} seconds: {sustained_counts[bracket]:4d} sustained segments")

    print('\nNotes:')
    print('- Each segment is a contiguous period where the condition stays true')
    print('- A segment can count for multiple brackets if it lasts long enough')
    print('- This only checks TEX YES vs CLE NO for the specified event')


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Analyze sustained TEX YES vs CLE NO spread for a single game.')
    parser.add_argument('--event', default='KXMLBGAME-25SEP28TEXCLE', help='Event ticker to analyze. Can be base event or full market ticker ending in -TEX or -CLE.')
    parser.add_argument('--db', default='kalshi_mlb.db', help='Path to DuckDB database file')
    parser.add_argument('--brackets', nargs='+', type=int, default=[5, 10, 15, 20, 25], help='Sustained duration brackets in seconds')
    args = parser.parse_args()

    analyze_tex_cle_spread(db_path=args.db, event_ticker=args.event, brackets=tuple(args.brackets))