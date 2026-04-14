import duckdb
import pandas as pd
import matplotlib.pyplot as plt
import random

def get_structural_arb_query(m1_ticker, m2_ticker, m1_side, m2_side, arb_type, max_bracket=30):
    """
    m1_side/m2_side: 'yes' or 'no'
    arb_type: 'parity' (m1 == m2) or 'basket' (m1 + m2 == 1)
    """
    
    # Define price columns based on side
    m1_col = "yes_price_dollars" if m1_side == 'yes' else "no_price_dollars"
    m2_col = "yes_price_dollars" if m2_side == 'yes' else "no_price_dollars"
    
    # Define the profit logic
    if arb_type == 'parity':
        # If we expect M1 == M2, profit exists if one is cheaper than the other.
        # Here we assume we buy the cheaper one and 'sell' (or take the opposite) the expensive one.
        # For simplicity, let's track the absolute spread.
        profit_calc = f"ABS(m1_pre.price - m2.price)"
        trigger_condition = f"ABS(m1_pre.price - m2.price) > 0.01"
    else:
        # Basket logic: Profit = 1.0 - (Cost of both)
        profit_calc = f"1.0 - (m1_pre.price + m2.price)"
        trigger_condition = f"(m1_pre.price + m2.price) < 1.0"

    query = f"""
        WITH M1_Tape AS (
            SELECT created_time, {m1_col} as price
            FROM trades WHERE ticker = '{m1_ticker}' AND taker_side = '{m1_side}'
        ),
        M2_Tape AS (
            SELECT created_time, {m2_col} as price
            FROM trades WHERE ticker = '{m2_ticker}' AND taker_side = '{m2_side}'
        )
        SELECT 
            '{m1_side}_{m2_side}_{arb_type}' as strategy,
            m2.created_time as signal_time,
            m1_pre.price as m1_price,
            m2.price as m2_price,
            {profit_calc} as arb_profit,
            EPOCH(m1_post.created_time - m2.created_time) as runway_seconds
        FROM M2_Tape m2
        LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time < m2.created_time ORDER BY created_time DESC LIMIT 1) m1_pre ON TRUE
        LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m1_post ON TRUE
        LEFT JOIN LATERAL (SELECT price, created_time FROM M2_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m2_post ON TRUE
        WHERE 
            -- Stability Brackets (1.5c wiggle room)
            m1_pre.price BETWEEN m1_post.price - 0.015 AND m1_post.price + 0.015
            AND m2.price BETWEEN m2_post.price - 0.015 AND m2_post.price + 0.015
            -- Temporal Brackets
            AND EPOCH(m1_post.created_time - m1_pre.created_time) <= {max_bracket}
            AND EPOCH(m2_post.created_time - m2.created_time) <= {max_bracket}
            -- Interleave Check
            AND m2.created_time < m1_post.created_time
            -- Profit Check
            AND {trigger_condition}
    """
    return query

def single_arb_query(m1_ticker, m2_ticker, max_bracket):
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
            m1_pre.price < m1_post.price + .015
            AND m1_pre.price > m1_post.price - .015
            AND EPOCH(m1_post.created_time - m1_pre.created_time) <= {max_bracket}
            
            -- CONSTRAINT 2: M2 is stable and tight (Post-Signal)
            AND m2.price < m2_post.price + .015
            AND m2.price > m2_post.price - .015
            AND EPOCH(m2_post.created_time - m2.created_time) <= {max_bracket}

            AND m2.price + m1_pre.price < 1.0
            
        ORDER BY m2_start_time
    """
    
    return query

def run_all_arbitrage_checks(db_path, m1_ticker, m2_ticker):
    con = duckdb.connect(db_path)
    
    # Define the 4 Law of One Price tests
    tests = [
        ('yes', 'no',  'parity'), # m1_yes vs m2_no
        ('no',  'yes', 'parity'), # m1_no vs m2_yes
        ('yes', 'yes', 'basket'), # m1_yes + m2_yes = 1
        ('no',  'no',  'basket')  # m1_no + m2_no = 1
    ]
    
    all_results = []
    
    for m1_s, m2_s, a_type in tests:
        q = get_structural_arb_query(m1_ticker, m2_ticker, m1_s, m2_s, a_type)
        res = con.execute(q).df()
        all_results.append(res)
    
    final_df = pd.concat(all_results)
    con.close()
    return final_df


def plot_structural_rectangle_arb(db_path='kalshi_mlb.db', max_bracket=30):
    con = duckdb.connect(db_path)

    # 1. Setup (Random Event/Ticker selection)
    events = con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    if not events: return
    random_event = random.choice(events)[0]
    markets = con.execute(f"SELECT market_ticker FROM event_market_map WHERE event_ticker = '{random_event}' LIMIT 2").fetchall()
    if len(markets) < 2: return
    m1_ticker, m2_ticker = markets[0][0], markets[1][0]

    df = run_all_arbitrage_checks(db_path, m1_ticker, m2_ticker)




    if df.empty:
        print(f"No structural rectangles found for {random_event}")
        return

    tape_query = f"""
        SELECT created_time, ticker, taker_side, 
               CASE WHEN taker_side = 'yes' THEN yes_price_dollars ELSE no_price_dollars END as price
        FROM trades 
        WHERE ticker IN ('{m1_ticker}', '{m2_ticker}')
        ORDER BY created_time
    """
    df_tape = con.execute(tape_query).df()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12), sharex=True)
    
    # --- Top Plot: Arbitrage Opportunities ---
    # Removed colorbar to prevent width compression
    scatter = ax1.scatter(df['signal_time'], df['arb_profit'], 
                          s=df['runway_seconds']*25, 
                          c=df['runway_seconds'], 
                          cmap='viridis', alpha=0.6, edgecolors='black', zorder=3)
    
    ax1.axhline(0.01, color='red', linestyle='--', alpha=0.5, label='1c Profit Threshold')
    ax1.set_title(f"Structural Arbitrage: {random_event}\n{m1_ticker} vs {m2_ticker}", fontsize=14)
    ax1.set_ylabel("Validated Arb Profit ($)", fontsize=12)
    ax1.set_xlabel("Time (Arb Signal Window)", fontsize=12) # Added back x-label
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.15)

    # --- Bottom Plot: Full Market Tape ---
    colors = {
        (m1_ticker, 'yes'): ('#27AE60', 'o'), 
        (m1_ticker, 'no'):  ('#2ECC71', 'x'),
        (m2_ticker, 'yes'): ('#2980B9', 's'), 
        (m2_ticker, 'no'):  ('#3498DB', '+') 
    }

    # for (ticker, side), (color, style) in colors.items():
    #     mask = (df_tape['ticker'] == ticker) & (df_tape['taker_side'] == side)
    #     subset = df_tape[mask]
    #     if not subset.empty:
    #         ax2.step(subset['created_time'], subset['price'], where='post',
    #                  label=f"{ticker} {side.upper()}", color=color, linestyle=style, linewidth=1.5)
            
    for (ticker, side), (color, marker) in colors.items():
        mask = (df_tape['ticker'] == ticker) & (df_tape['taker_side'] == side)
        subset = df_tape[mask]
        if not subset.empty:
            # Using scatter instead of step to show every individual execution
            ax2.scatter(subset['created_time'], subset['price'],
                        label=f"{ticker} {side.upper()}", 
                        color=color, 
                        marker=marker,
                        s=30,          # Size of the tick
                        alpha=0.4,     # Transparency shows density on flat lines
                        edgecolors='none')

    ax2.set_title("Full Market Tape (Taker Prices)", fontsize=14)
    ax2.set_ylabel("Price ($)", fontsize=12)
    ax2.set_xlabel("Time", fontsize=12)
    
    # Move legend to bottom left corner inside the plot
    ax2.legend(loc='lower left', fontsize=10, frameon=True, shadow=True)
    ax2.grid(True, alpha=0.15)

    # 3. Final Formatting
    if not df.empty:
        buffer = pd.Timedelta(seconds=30)
        ax2.set_xlim(df['signal_time'].min() - buffer, df['signal_time'].max() + buffer)

    # Tight layout ensures labels don't overlap, and equalizing the width
    plt.tight_layout()
    
    filename = f"aligned_analysis_{random_event}.png"
    plt.savefig(filename)
    print(f"✅ Success. Perfectly aligned plot saved as {filename}")
    con.close()

if __name__ == "__main__":
    plot_structural_rectangle_arb(max_bracket=25)