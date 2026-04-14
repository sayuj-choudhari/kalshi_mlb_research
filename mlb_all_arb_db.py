import duckdb
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
import os

def harvest_all_arbitrages(source_db='kalshi_mlb.db', target_db='arb_research.db', max_bracket=25):
    src = duckdb.connect(source_db)
    dst = duckdb.connect(target_db)

    # 1. Initialize the Target Schema
    dst.execute("DROP TABLE IF EXISTS arb_anchors")
    dst.execute("DROP TABLE IF EXISTS arb_context_trades")
    
    # Store the core arb signal
    dst.execute("""
        CREATE TABLE arb_anchors (
            anchor_id INTEGER PRIMARY KEY,
            event_ticker VARCHAR,
            m1_ticker VARCHAR,
            m2_ticker VARCHAR,
            strategy VARCHAR,
            signal_time TIMESTAMP,
            m1_price DOUBLE,
            m2_price DOUBLE,
            arb_profit DOUBLE,
            runway_seconds DOUBLE
        )
    """)
    
    # Store the surrounding "Tape" for every signal found
    dst.execute("""
        CREATE TABLE arb_context_trades (
            anchor_id INTEGER,
            ticker VARCHAR,
            taker_side VARCHAR,
            price DOUBLE,
            created_time TIMESTAMP
        )
    """)

    # 2. Get list of all unique events
    events = src.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    print(f"🚀 Processing {len(events)} events for arbitrage discovery...")

    anchor_id_counter = 0

    for (event_ticker,) in tqdm(events):
        # Get the two tickers for this event
        markets = src.execute(f"SELECT market_ticker FROM event_market_map WHERE event_ticker = '{event_ticker}' LIMIT 2").fetchall()
        if len(markets) < 2: continue
        m1, m2 = markets[0][0], markets[1][0]

        # 3. Use your modular logic to find signals for all 4 LoOP tests
        tests = [('yes', 'no', 'parity'), ('no', 'yes', 'parity'), ('yes', 'yes', 'basket'), ('no', 'no', 'basket')]
        
        for m1_s, m2_s, a_type in tests:
            # Reusing your optimized structural query logic
            m1_col = "yes_price_dollars" if m1_s == 'yes' else "no_price_dollars"
            m2_col = "yes_price_dollars" if m2_s == 'yes' else "no_price_dollars"
            
            p_calc = f"ABS(m1_pre.price - m2.price)" if a_type == 'parity' else f"1.0 - (m1_pre.price + m2.price)"
            t_cond = f"ABS(m1_pre.price - m2.price) > 0.01" if a_type == 'parity' else f"(m1_pre.price + m2.price) < 1.0"

            query = f"""
                WITH M1_Tape AS (SELECT created_time, {m1_col} as price FROM trades WHERE ticker = '{m1}' AND taker_side = '{m1_s}'),
                     M2_Tape AS (SELECT created_time, {m2_col} as price FROM trades WHERE ticker = '{m2}' AND taker_side = '{m2_s}')
                SELECT 
                    '{m1_s}_{m2_s}_{a_type}' as strategy,
                    m2.created_time as signal_time, m1_pre.price as m1_price, m2.price as m2_price,
                    {p_calc} as arb_profit, EPOCH(m1_post.created_time - m2.created_time) as runway_seconds
                FROM M2_Tape m2
                LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time < m2.created_time ORDER BY created_time DESC LIMIT 1) m1_pre ON TRUE
                LEFT JOIN LATERAL (SELECT price, created_time FROM M1_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m1_post ON TRUE
                LEFT JOIN LATERAL (SELECT price, created_time FROM M2_Tape WHERE created_time > m2.created_time ORDER BY created_time ASC LIMIT 1) m2_post ON TRUE
                WHERE m1_pre.price BETWEEN m1_post.price - 0.015 AND m1_post.price + 0.015
                  AND m2.price BETWEEN m2_post.price - 0.015 AND m2_post.price + 0.015
                  AND EPOCH(m1_post.created_time - m1_pre.created_time) <= {max_bracket}
                  AND EPOCH(m2_post.created_time - m2.created_time) <= {max_bracket}
                  AND m2.created_time < m1_post.created_time
                  AND {t_cond}
            """
            signals = src.execute(query).df()

            if not signals.empty:
                for _, sig in signals.iterrows():
                    # a) Insert into Anchors
                    dst.execute("""
                        INSERT INTO arb_anchors VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (anchor_id_counter, event_ticker, m1, m2, sig['strategy'], 
                          sig['signal_time'], sig['m1_price'], sig['m2_price'], 
                          sig['arb_profit'], sig['runway_seconds']))

                    # b) Radius Search for Context (All 4 sides within bracket)
                    # This grabs the actual 'Tape' around the hit
                    context_query = f"""
                        SELECT ticker, taker_side, 
                               CASE WHEN taker_side = 'yes' THEN yes_price_dollars ELSE no_price_dollars END as price,
                               created_time
                        FROM trades
                        WHERE ticker IN ('{m1}', '{m2}')
                        AND created_time BETWEEN '{sig['signal_time']}'::TIMESTAMP - INTERVAL '{max_bracket} seconds'
                                             AND '{sig['signal_time']}'::TIMESTAMP + INTERVAL '{max_bracket} seconds'
                    """
                    context_df = src.execute(context_query).df()
                    context_df['anchor_id'] = anchor_id_counter
                    
                    dst.append("arb_context_trades", context_df[['anchor_id', 'ticker', 'taker_side', 'price', 'created_time']])
                    
                    anchor_id_counter += 1

    print(f"✅ Harvest Complete. Found {anchor_id_counter} structural arbitrage instances.")
    src.close()
    dst.close()

def audit_harvested_arbs(research_db='arb_research.db', num_to_audit=5, min_profit=0.02):
    """
    Picks the most profitable/stable arbs from the harvested DB 
    and generates visual proof for each.
    """
    con = duckdb.connect(research_db)
    
    # 1. Query the 'Hall of Fame' - long runway and high profit
    audit_list_query = f"""
        SELECT * FROM arb_anchors 
        WHERE arb_profit >= {min_profit}
        ORDER BY arb_profit DESC, runway_seconds DESC
        LIMIT {num_to_audit}
    """
    df_audit = con.execute(audit_list_query).df()
    
    if df_audit.empty:
        print("No arbs found matching those audit criteria.")
        return

    # Create directory for audit reports
    os.makedirs('audit_reports', exist_ok=True)

    for _, anchor in df_audit.iterrows():
        a_id = anchor['anchor_id']
        
        # 2. Fetch the Context Trades we stored for this specific ID
        context_query = f"SELECT * FROM arb_context_trades WHERE anchor_id = {a_id} ORDER BY created_time"
        df_context = con.execute(context_query).df()

        # 3. Reconstruct the Visualization
        fig, ax = plt.subplots(figsize=(12, 7))
        
        # Plot the context trades (The Evidence)
        colors = {'yes': 'tab:blue', 'no': 'tab:orange'}
        markers = {anchor['m1_ticker']: 'o', anchor['m2_ticker']: 's'}
        
        for (ticker, side), group in df_context.groupby(['ticker', 'taker_side']):
            ax.scatter(group['created_time'], group['price'], 
                       label=f"{ticker} {side.upper()}",
                       color=colors.get(side, 'gray'),
                       marker=markers.get(ticker, 'x'),
                       alpha=0.5, s=60)

        # Highlight the Anchor Trade (The Execution Point)
        ax.scatter(anchor['signal_time'], anchor['m2_price'], 
                   facecolors='none', edgecolors='red', s=200, linewidth=2, 
                   label='SIGNAL ENTRY (M2)')
        
        # Draw the "Anchor Price" for M1 as a horizontal line to show the gap
        ax.axhline(anchor['m1_price'], color='blue', linestyle=':', alpha=0.4, label='M1 ANCHOR PRICE')

        # Formatting
        ax.set_title(f"Audit ID: {a_id} | Strategy: {anchor['strategy']}\n"
                     f"Profit: ${anchor['arb_profit']:.3f} | Runway: {anchor['runway_seconds']}s", fontsize=14)
        ax.set_ylabel("Price ($)")
        ax.set_xlabel("Time (Context Window)")
        ax.legend(loc='best', frameon=True, shadow=True)
        ax.grid(True, alpha=0.2)

        # Save the audit proof
        clean_strategy = anchor['strategy'].replace('_', '-')
        filename = f"audit_reports/arb_{a_id}_{clean_strategy}.png"
        plt.tight_layout()
        plt.savefig(filename)
        plt.close()
        print(f"✅ Audit report generated for ID {a_id}: {filename}")

    con.close()

if __name__ == "__main__":
    harvest_all_arbitrages()
    audit_harvested_arbs(num_to_audit=10, min_profit=0.01)