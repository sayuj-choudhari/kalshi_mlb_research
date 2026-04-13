import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import random

def plot_shadow_maker_prices(db_path='kalshi_mlb.db'):
    con = duckdb.connect(db_path)

    # 1. Randomly pick an event
    events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    if not events: return
    random_event = random.choice(events)[0]

    # 2. Get 2 markets for this event
    markets = con.execute(f"SELECT market_ticker FROM event_market_map WHERE event_ticker = '{random_event}'").fetchall()
    if len(markets) < 2: return
    m1_ticker, m2_ticker = random.sample([m[0] for m in markets], 2)

    # --- PLOT 1: Maker M1-YES and Maker M2-NO ---
    query_p1_m1 = f"""
        SELECT created_time, (yes_price_dollars - 0.01) as maker_price 
        FROM trades 
        WHERE ticker = '{m1_ticker}' AND taker_side = 'yes' 
        ORDER BY created_time
    """
    query_p1_m2 = f"""
        SELECT created_time, (no_price_dollars - 0.01) as maker_price 
        FROM trades 
        WHERE ticker = '{m2_ticker}' AND taker_side = 'no' 
        ORDER BY created_time
    """

    df1_p1 = con.execute(query_p1_m1).df()
    df2_p1 = con.execute(query_p1_m2).df()

    if not df1_p1.empty and not df2_p1.empty:
        plt.figure(figsize=(12, 6))
        plt.step(df1_p1['created_time'], df1_p1['maker_price'], where='post', 
                 label=f"Maker YES ({m1_ticker})", color='#27AE60', linewidth=2)
        plt.step(df2_p1['created_time'], df2_p1['maker_price'], where='post', 
                 label=f"Maker NO ({m2_ticker})", color='#C0392B', linewidth=2)
        
        plt.title(f"Shadow Maker Prices (Set A)\nEvent: {random_event}")
        plt.ylabel("Theoretical Maker Price ($)")
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        plt.savefig(f"shadow_maker_SET_A_{random_event}.png")
        plt.close()

    # --- PLOT 2: Maker M1-NO and Maker M2-YES ---
    query_p2_m1 = f"""
        SELECT created_time, (no_price_dollars - 0.01) as maker_price 
        FROM trades 
        WHERE ticker = '{m1_ticker}' AND taker_side = 'no' 
        ORDER BY created_time
    """
    query_p2_m2 = f"""
        SELECT created_time, (yes_price_dollars - 0.01) as maker_price 
        FROM trades 
        WHERE ticker = '{m2_ticker}' AND taker_side = 'yes' 
        ORDER BY created_time
    """

    df1_p2 = con.execute(query_p2_m1).df()
    df2_p2 = con.execute(query_p2_m2).df()

    if not df1_p2.empty and not df2_p2.empty:
        plt.figure(figsize=(12, 6))
        plt.step(df1_p2['created_time'], df1_p2['maker_price'], where='post', 
                 label=f"Maker NO ({m1_ticker})", color='#E67E22', linewidth=2)
        plt.step(df2_p2['created_time'], df2_p2['maker_price'], where='post', 
                 label=f"Maker YES ({m2_ticker})", color='#2980B9', linewidth=2)
        
        plt.title(f"Shadow Maker Prices (Set B)\nEvent: {random_event}")
        plt.ylabel("Theoretical Maker Price ($)")
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        plt.savefig(f"shadow_maker_SET_B_{random_event}.png")
        plt.close()

    print(f"✅ Success. Generated cross-market maker plots for {random_event}")
    con.close()

if __name__ == "__main__":
    plot_shadow_maker_prices()