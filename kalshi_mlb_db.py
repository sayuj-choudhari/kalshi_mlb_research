import requests
import time
import pandas as pd
import duckdb
import base64
from datetime import datetime
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization

# API Config
headers = {"KALSHI-ACCESS-KEY": "f561daf1-9b9e-49f1-8c68-c13abddfa9f9"}
base_url = "https://api.elections.kalshi.com/trade-api/v2/events"
market_url = "https://api.elections.kalshi.com/trade-api/v2/historical/markets"
trade_url = "https://api.elections.kalshi.com/trade-api/v2/historical/trades"

# Filtering
cutoff_date = datetime(2025, 9, 28)
start_date = datetime(2025, 9, 28)

def fetch_market_hierarchy():
    cursor = ""
    iteration = 1
    # This will store a list of dicts: {'event_ticker': '...', 'market_ticker': '...'}
    hierarchy_data = []

    while True:
        params = {
            "limit": 200,
            "with_nested_markets": "true",
            "series_ticker": "KXMLBGAME",
            "cursor": cursor
        }

        print(f"--- Fetching Events Iteration {iteration} ---")
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code != 200:
            break

        data = response.json()
        events = data.get('events', [])
        if not events:
            break

        for event in events:
            curr_event = event.get('event_ticker')
            
            # Date filtering logic
            try:
                date_str = curr_event[10:17] 
                event_date = datetime.strptime(date_str, '%y%b%d')
            except:
                continue

            if curr_event.startswith('KXMLBGAME-25') and start_date <= event_date <= cutoff_date:
                time.sleep(0.1) 
                
                m_params = {"limit": 200, "event_ticker": curr_event}
                m_res = requests.get(market_url, params=m_params, headers=headers)
                m_data = m_res.json()
                
                if 'markets' in m_data:
                    for m in m_data['markets']:
                        hierarchy_data.append({
                            "event_ticker": curr_event,
                            "market_ticker": m.get('ticker')
                        })
                        print(f"Mapped {curr_event} -> {m.get('ticker')}")

        cursor = data.get('cursor', '')
        if not cursor:
            break
        iteration += 1

    return hierarchy_data

def fetch_and_store_all(hierarchy_data, db_name="kalshi_mlb.db"):
    con = duckdb.connect(db_name)
    
    # Clean setup
    con.execute("DROP TABLE IF EXISTS trades")
    con.execute("DROP TABLE IF EXISTS event_market_map")
    
    # Table 1: The Map
    con.execute("CREATE TABLE event_market_map (event_ticker VARCHAR, market_ticker VARCHAR)")
    map_df = pd.DataFrame(hierarchy_data)
    con.append('event_market_map', map_df)

    # Table 2: The Trades
    con.execute("""
        CREATE TABLE trades (
            ticker VARCHAR,
            trade_id VARCHAR,
            yes_price_dollars DOUBLE,
            no_price_dollars DOUBLE,
            count_fp DOUBLE,
            taker_side VARCHAR,
            created_time TIMESTAMP
        )
    """)

    # Get unique market tickers to avoid redundant API calls
    unique_markets = map_df['market_ticker'].unique()

    for ticker in unique_markets:
        print(f"📦 Fetching trades for: {ticker}")
        cursor = ""
        while True:
            params = {"limit": 1000, "ticker": ticker, "cursor": cursor}
            time.sleep(0.15) 
            res = requests.get(trade_url, params=params, headers=headers)
            
            if res.status_code == 429:
                time.sleep(2)
                continue
            if res.status_code != 200:
                break

            data = res.json()
            trades = data.get('trades', [])
            if not trades:
                break
                
            df = pd.DataFrame(trades)
            df['created_time'] = pd.to_datetime(df['created_time'])
            df['yes_price_dollars'] = pd.to_numeric(df['yes_price_dollars']).astype(float)
            df['no_price_dollars'] = pd.to_numeric(df['no_price_dollars']).astype(float)
            df['count_fp'] = pd.to_numeric(df['count_fp']).astype(float)

            con.append('trades', df[['ticker', 'trade_id', 'yes_price_dollars', 'no_price_dollars', 'count_fp', 'taker_side', 'created_time']])
            
            cursor = data.get('cursor', '')
            if not cursor:
                break
    
    con.close()
    print("🏁 Done mapping and storing.")

# Run
mapping = fetch_market_hierarchy()
fetch_and_store_all(mapping)