import duckdb

con = duckdb.connect('kalshi_mlb.db')

# 1. Get all unique event tickers from your mapping table
events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()

for (event_ticker,) in events:
    print(f"\n🚀 PROCESSING EVENT: {event_ticker}")
    
    # 2. Find all markets belonging to THIS specific event
    markets = con.execute(f"""
        SELECT market_ticker 
        FROM event_market_map 
        WHERE event_ticker = '{event_ticker}'
    """).fetchall()
    
    # 3. Inner loop: Process each market independently
    for (m_ticker,) in markets:
        print(f"  📦 Analyzing Market: {m_ticker}")
        
        # Pull the independent trade data for this market
        query = f"""
            SELECT * FROM trades 
            WHERE ticker = '{m_ticker}' 
            ORDER BY created_time ASC
        """
        df_market = con.execute(query).df()
        
        # --- YOUR TRADING LOGIC / ANOMALY DETECTION GOES HERE ---
        if not df_market.empty:
            # Example: Calculate simple stats for this specific market
            last_price = df_market['yes_price_dollars'].iloc[-1]
            total_volume = df_market['count_fp'].sum()
            print(f"    - Last Price: ${last_price:.2f} | Volume: {total_volume}")
        else:
            print("    - No trades found for this market.")

con.close()