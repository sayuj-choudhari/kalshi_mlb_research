import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import random

def plot_structural_rectangle_arb(db_path='kalshi_mlb.db', max_bracket=30):
    con = duckdb.connect(db_path)

    # 1. Setup (Random Event/Ticker selection)
    events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    if not events: return
    random_event = random.choice(events)[0]
    markets = con.execute(f"SELECT market_ticker FROM event_market_map WHERE event_ticker = '{random_event}' LIMIT 2").fetchall()
    if len(markets) < 2: return
    m1_ticker, m2_ticker = markets[0][0], markets[1][0]

    # 2. SQL: The "Rectangle of Certainty"
    query = f"""
        WITH M1_Tape AS (
            SELECT created_time, yes_price_dollars as price
            FROM trades WHERE ticker = '{m1_ticker}' AND taker_side = 'yes'
        ),
        M2_Tape AS (
            SELECT created_time, yes_price_dollars as price
            FROM trades WHERE ticker = '{m2_ticker}' AND taker_side = 'yes'
        )
        SELECT 
            m2.created_time as m2_start_time,
            m1_post.created_time as m1_end_time,
            m1_pre.price as m1_price,
            m2.price as m2_price,
            (1.0 - (m1_pre.price + m2.price)) as arb_profit,
            EPOCH(m1_post.created_time - m2.created_time) as runway_seconds
        FROM M2_Tape m2
        -- M1 Bracket
        LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time < m2.created_time ORDER BY created_time DESC LIMIT 1) m1_pre ON TRUE
        LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m1_post ON TRUE
        -- M2 Bracket (The Post-Check)
        LEFT JOIN LATERAL (SELECT price, created_time FROM M2_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m2_post ON TRUE
        WHERE 
            -- CONSTRAINT 1: M1 is stable and tight
            m1_pre.price = m1_post.price 
            AND EPOCH(m1_post.created_time - m1_pre.created_time) <= {max_bracket}
            
            -- CONSTRAINT 2: M2 is stable and tight (Post-Signal)
            AND m2.price = m2_post.price
            AND EPOCH(m2_post.created_time - m2.created_time) <= {max_bracket}

            AND m2.price + m1_pre.price < 1.0
            
        ORDER BY m2_start_time
    """
    
    df = con.execute(query).df()

    if df.empty:
        print(f"No structural rectangles found for {random_event}")
        return

    # 3. Create a specialized visualization for "Runway"
    plt.figure(figsize=(14, 7))
    
    # We plot dots where the Y-axis is profit and the color/size is the runway
    scatter = plt.scatter(df['m2_start_time'], df['arb_profit'], 
                          s=df['runway_seconds']*20, 
                          c=df['runway_seconds'], 
                          cmap='viridis', alpha=0.6, edgecolors='black')
    
    plt.colorbar(scatter, label='Guaranteed Execution Window (Seconds)')
    plt.axhline(0.01, color='red', linestyle='--', label='1c Profit Threshold')
    
    plt.title(f"Structural Arbitrage 'Rectangles': {random_event}\nInterleaved Stability (M1_start < M2_start < M1_end < M2_end)")
    plt.ylabel("Validated Arb Profit ($)")
    plt.xlabel("Time")
    plt.legend()
    plt.grid(True, alpha=0.15)
    
    plt.savefig(f"structural_rectangle_{random_event}.png")
    print(f"✅ Success. Identified {len(df)} 'Rectangle' opportunities.")
    con.close()

if __name__ == "__main__":
    plot_structural_rectangle_arb(max_bracket=25)