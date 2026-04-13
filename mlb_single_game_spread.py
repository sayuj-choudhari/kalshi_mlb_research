import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import random

def plot_taker_buy_prices(db_path='kalshi_mlb.db'):
    con = duckdb.connect(db_path)

    # 1. Randomly pick an event
    events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    if not events: return
    random_event = random.choice(events)[0]

    # 2. Get 2 markets for this event
    markets = con.execute(f"SELECT market_ticker FROM event_market_map WHERE event_ticker = '{random_event}'").fetchall()
    if len(markets) < 2: return
    m1_ticker, m2_ticker = random.sample([m[0] for m in markets], 2)

    # 3. Get Taker BUY prices for Market 1 (Price to buy YES)
    # Taker side 'buy' indicates the taker was the one initiating the purchase
    query_m1 = f"""
        SELECT created_time, yes_price_dollars 
        FROM trades 
        WHERE ticker = '{m1_ticker}' 
        AND taker_side = 'yes' 
        ORDER BY created_time
    """
    
    # 4. Get Taker BUY prices for Market 2 (Price to buy NO)
    query_m2 = f"""
        SELECT created_time, no_price_dollars 
        FROM trades 
        WHERE ticker = '{m2_ticker}' 
        AND taker_side = 'no' 
        ORDER BY created_time
    """

    df1 = con.execute(query_m1).df()
    df2 = con.execute(query_m2).df()

    if df1.empty or df2.empty:
        print(f"Skipping {random_event}: Missing taker buy data.")
        return

    # 5. Plotting
    plt.figure(figsize=(12, 6))
    
    # Using 'step' because taker prices change in discrete increments when the book is hit
    plt.step(df1['created_time'], df1['yes_price_dollars'], 
             where='post', label=f"Price to Buy YES ({m1_ticker})", color='#2ECC71', linewidth=2)
    
    plt.step(df2['created_time'], df2['no_price_dollars'], 
             where='post', label=f"Price to Buy NO ({m2_ticker})", color='#E74C3C', linewidth=2)

    plt.title(f"Taker Execution Prices (Buy)\nEvent: {random_event}")
    plt.ylabel("Execution Price ($)")
    plt.xlabel("Trade Time")
    plt.legend()
    plt.grid(True, alpha=0.2)
    plt.tight_layout()

    plt.savefig(f"taker_buy_{random_event}.png")
    print(f"✅ Success. Plotted execution costs for {random_event}")
    con.close()

if __name__ == "__main__":
    plot_taker_buy_prices()