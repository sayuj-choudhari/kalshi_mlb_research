import duckdb
import pandas as pd
import numpy as np

def fetch_and_merge_event_markets(event_db="kalshi_event_market_map.db", 
                                  market_db="kalshi_unified_market_data.db"):
    con = duckdb.connect()
    con.execute(f"ATTACH '{event_db}' AS events")
    con.execute(f"ATTACH '{market_db}' AS unified")

    # 1. Find all unique events and their associated markets
    # We'll pull the mapping into a DataFrame to iterate through it easily
    mapping_df = con.execute("SELECT event_ticker, market_ticker FROM events.event_market_map").df()
    unique_events = mapping_df['event_ticker'].unique()

    event_spread_data = {}

    for event in unique_events:
        # Get the 2 (or more) markets for this specific event
        markets = mapping_df[mapping_df['event_ticker'] == event]['market_ticker'].tolist()
        
        if len(markets) < 2:
            print(f"⚠️ Skipping {event}: Found less than 2 markets.")
            continue
            
        print(f"🔄 Processing Event: {event} ({len(markets)} markets)")

        # 2. Run separate queries for each market
        market_dfs = []
        for i, ticker in enumerate(markets, 1):
            query = f"""
                SELECT 
                    timestamp,
                    yes_price AS yes_team_{i},
                    no_price AS no_team_{i},
                    source AS source_{i},
                    volume AS volume_{i}
                FROM unified.unified_market_data
                WHERE ticker = '{ticker}'
            """
            m_df = con.execute(query).df()
            market_dfs.append(m_df)

        # 3. Merge the DataFrames on 'timestamp'
        # We use an 'outer' join so we keep data even if only 1 team had an update
        if market_dfs:
            final_df = market_dfs[0]
            for next_df in market_dfs[1:]:
                final_df = pd.merge(final_df, next_df, on='timestamp', how='outer')

            # 4. Clean up the merged data
            # Sort by time and forward-fill NaNs (carries the last known price forward)
            final_df = final_df.sort_values('timestamp').reset_index(drop=True)
            final_df = final_df.ffill()

            print(f"   ✅ Merged into {final_df.shape[1]} columns and {len(final_df)} rows.")

            new_df = pd.DataFrame()
            new_df['timestamp'] = final_df['timestamp']

            # max_sell = max(1 - no_team_1, 1 - yes_team_2)
            new_df['max_sell'] = np.maximum(1 - final_df['no_team_1'], 1 - final_df['yes_team_2'])

            # min_buy = min(yes_team_1, no_team_2)
            new_df['min_buy'] = np.minimum(final_df['yes_team_1'], final_df['no_team_2'])

            # spread = max_sell - min_buy
            new_df['spread'] = new_df['max_sell'] - new_df['min_buy']

            # volume = max(min(volume_1, volume_2), 1)
            new_df['volume'] = np.maximum(np.minimum(final_df['volume_1'], final_df['volume_2']), 1)
            new_df['event'] = event
            event_spread_data[event] = new_df

    con.close()
    return event_spread_data

def save_processed_research(games_dict, output_db="kalshi_spread_data.db"):
    # 1. Combine all individual event DataFrames into one
    if not games_dict:
        print("No data to save.")
        return

    master_df = pd.concat(games_dict.values(), ignore_index=True)

    # 2. Connect to the research database
    con = duckdb.connect(output_db)

    # 3. Save the spread data
    con.execute("CREATE OR REPLACE TABLE market_spreads AS SELECT * FROM master_df")
    
    # 4. (Optional) Create an index for lightning-fast retrieval later
    con.execute("CREATE INDEX idx_event ON market_spreads (event)")

    print(f"✅ Saved {len(master_df)} rows to {output_db} in table 'market_spreads'")
    con.close()

# --- Execution ---
games_dict = fetch_and_merge_event_markets()
save_processed_research(games_dict)