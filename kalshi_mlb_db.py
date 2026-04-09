import requests
import time # Add this at the top
from datetime import datetime
import duckdb
import pandas as pd

# Use your working headers
headers = {"KALSHI-ACCESS-KEY": "f561daf1-9b9e-49f1-8c68-c13abddfa9f9"}
base_url = "https://api.elections.kalshi.com/trade-api/v2/events"
market_url = "https://api.elections.kalshi.com/trade-api/v2/historical/markets"
trade_url = "https://api.elections.kalshi.com/trade-api/v2/historical/trades"
cutoff_date = datetime(2025, 9, 28)
start_date = datetime(2025, 9, 28)

def fetch_all_nested_tickers():
    cursor = ""  # Start with an empty cursor
    iteration = 1
    all_market_tickers = []

    while True:
        # Define parameters for this specific 'page'
        params = {
            "limit": 200,
            "with_nested_markets": "true",
            "series_ticker": "KXMLBGAME",
            "cursor": cursor  # This is the key for pagination
        }

        print(f"--- Fetching Iteration {iteration} (Cursor: {cursor if cursor else 'Start'}) ---")
        
        response = requests.get(base_url, params=params, headers=headers)

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            break

        data = response.json()
        events = data.get('events', [])
        
        # If no events come back, we are done
        if not events:
            print("No more events found.")
            break

        

        for event in events:
            curr_event = event.get('event_ticker')

            date_str = curr_event[10:17] 
            
            # 3. Convert to a datetime object
            # %y = Year (25), %b = Month (AUG), %d = Day (09)
            event_date = datetime.strptime(date_str, '%y%b%d')

            if curr_event.startswith('KXMLBGAME-25') and event_date <= cutoff_date and event_date >= start_date:
                time.sleep(0.1) # Wait 500ms between requests to be safe

                market_params = {
                    "limit": 200,
                    "event_ticker": curr_event,
                }

                market_response = requests.get(market_url, params=market_params, headers=headers)
                market_data = market_response.json()
                
                # Add a check to prevent the crash if rate limited
                if 'markets' not in market_data:
                    print(f"Rate limited or error on {curr_event}: {market_data}")
                    continue 

                market_tickers = [m.get('ticker') for m in market_data.get('markets', [])]
                print(market_tickers)
                all_market_tickers.extend(market_tickers)



        # Update the cursor for the next loop
        cursor = data.get('cursor', '')

        # If the API returns an empty string for the cursor, there's no more data
        if not cursor:
            print("\n🏁 Reached the end of the event list.")
            break
            
        iteration += 1

    print(f"\n✅ Done. Total Markets Processed: {len(all_market_tickers)}")
    return all_market_tickers

def fetch_all_trades(market_tickers):
    trade_dict = {}
    
    for ticker in market_tickers:
        print(f"📦 Fetching trades for: {ticker}")
        cursor = ""
        market_trade_count = 0

        ticker_trades = []
        
        while True:
            
            params = {
                "limit": 1000, # Maximize limit to reduce API calls
                'ticker': ticker,
                "cursor": cursor

            }
            
            # Rate limit protection
            time.sleep(0.15) 
            
            response = requests.get(trade_url, params=params, headers=headers)
            
            if response.status_code == 429:
                print("🛑 Rate limited! Sleeping for 2 seconds...")
                time.sleep(2)
                continue
                
            if response.status_code != 200:
                print(f"❌ Error {response.status_code} for {ticker}")
                break

            data = response.json()
            trades = data.get('trades', [])
            
            if not trades:
                break
                
            ticker_trades.extend(trades)
            market_trade_count += len(trades)
            
            # Update cursor
            cursor = data.get('cursor', '')
            if not cursor:
                break

        
        
        print(f"✅ Successfully pulled {market_trade_count} trades for {ticker}")
        trade_dict[ticker] = ticker_trades

    return trade_dict

def fetch_and_store_trades(market_tickers, db_name="kalshi_mlb.db"):
    # 1. Connect to DuckDB
    con = duckdb.connect(db_name)
    
    # 2. Hard Reset: Drop the old table to ensure the new schema takes effect
    # This prevents the "Conversion Error" or silent rounding from previous runs
    con.execute("DROP TABLE IF EXISTS trades")
    
    # 3. Create schema with DOUBLE for decimal precision
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

    for ticker in market_tickers:
        print(f"📦 Fetching trades for: {ticker}")
        cursor = ""
        market_trade_count = 0
        
        while True:
            params = {
                "limit": 1000, 
                "ticker": ticker,
                "cursor": cursor
            }
            
            # Rate limit protection
            time.sleep(0.15) 
            
            response = requests.get(trade_url, params=params, headers=headers)
            
            if response.status_code == 429:
                print("🛑 Rate limited! Sleeping for 2 seconds...")
                time.sleep(2)
                continue
                
            if response.status_code != 200:
                print(f"❌ Error {response.status_code} for {ticker}")
                break

            data = response.json()
            trades = data.get('trades', [])
            
            if not trades:
                break
                
            # 4. Convert current batch to DataFrame
            df = pd.DataFrame(trades)
            
            # 5. Forced Casting to Floats
            # We explicitly use .astype(float) to ensure Pandas doesn't round
            df['created_time'] = pd.to_datetime(df['created_time'])
            df['yes_price_dollars'] = pd.to_numeric(df['yes_price_dollars']).astype(float)
            df['no_price_dollars'] = pd.to_numeric(df['no_price_dollars']).astype(float)
            df['count_fp'] = pd.to_numeric(df['count_fp']).astype(float)
            df['taker_side'] = df['taker_side'].astype(str)

            # 6. Append to DuckDB
            # We select columns explicitly to match the CREATE TABLE order
            con.append('trades', df[[
                'ticker', 'trade_id', 'yes_price_dollars', 
                'no_price_dollars', 'count_fp', 
                'taker_side', 'created_time'
            ]])
            
            market_trade_count += len(trades)
            
            # Update cursor
            cursor = data.get('cursor', '')
            if not cursor:
                break
        
        print(f"✅ Successfully stored {market_trade_count} trades for {ticker}")

    # 7. Export to Parquet
    print("\n💾 Exporting database to Parquet...")
    con.execute("COPY trades TO 'mlb_trades_2025.parquet' (FORMAT PARQUET)")
    
    # 8. Verification Summary
    total_rows = con.execute("SELECT count(*) FROM trades").fetchone()[0]
    print(f"🏁 DONE. Total trades in '{db_name}': {total_rows}")
    
    con.close()

# Execution Flow
game_market_tickers = fetch_all_nested_tickers()
fetch_and_store_trades(game_market_tickers)