import duckdb
import pandas as pd
import numpy as np
from tqdm import tqdm
import matplotlib.pyplot as plt

class MLBBacktestEngine:
    def __init__(self, db_path='kalshi_mlb.db'):
        self.db_path = db_path
        self.con = duckdb.connect(self.db_path)

    def get_validated_tape(self, ticker, max_gap=15):
        """
        Ingests trades, converts sides to numerical, and applies 
        Post-Corroboration filtering to ensure actionability.
        """
        query = f"""
            WITH Raw AS (
                SELECT 
                    created_time, 
                    -- 1 for YES taker, 0 for NO taker
                    CASE WHEN taker_side = 'yes' THEN 1 ELSE 0 END as side_num,
                    -- The actual price paid by the taker
                    CASE WHEN taker_side = 'yes' THEN yes_price_dollars 
                         ELSE no_price_dollars END as price,
                    -- Available liquidity
                    count_fp as quantity, 
                    ticker
                FROM trades 
                WHERE ticker = '{ticker}'
            ),
            PostCheck AS (
                SELECT *,
                    LEAD(price) OVER (ORDER BY created_time) as next_price,
                    LEAD(created_time) OVER (ORDER BY created_time) as next_time
                FROM Raw
            )
            SELECT 
                created_time,
                side_num,
                price,
                quantity,
                ticker
            FROM PostCheck
            WHERE 
                -- Post-Corroboration: Price level must survive the next trade
                ABS(price - next_price) <= 0.015 
                AND (next_time - created_time) <= INTERVAL '{max_gap} seconds'
        """
        return self.con.execute(query).df()

    def run_strategy(self, m1_df, m2_df, event_ticker):
        if m1_df.empty or m2_df.empty:
            return pd.DataFrame()

        # 1. Perform a standard outer join on timestamps
        # This keeps every trade from both sides, but leaves NaNs where they don't align
        tape = pd.merge(
            m1_df.sort_values('created_time'), 
            m2_df.sort_values('created_time'), 
            on='created_time', 
            how='outer',
            suffixes=('_m1', '_m2')
        ).sort_values('created_time')

        # 2. Zero out the NaN values
        # Instead of backfilling (carrying forward), we treat missing data as 0 liquidity/price
        cols_to_fix = ['price_m1', 'quantity_m1', 'price_m2', 'quantity_m2', 'side_num_m1', 'side_num_m2']
        tape[cols_to_fix] = tape[cols_to_fix].fillna(0)

        print(tape)

        # 3. Arbitrage Logic
        # NOTE: With 0-filling, 'arb_sum' will be very low (e.g., 0.45 + 0.00) 
        # unless BOTH markets printed a trade at the exact same timestamp.
        tape['arb_sum'] = tape['price_m1'] + tape['price_m2']
        
        # We check for signals where BOTH prices are non-zero (proving simultaneous prints)
        tape['is_arb'] = (tape['price_m1'] > 0) & (tape['price_m2'] > 0) & (tape['arb_sum'] < 0.985)
        
        # 4. Volume and PnL
        tape['trade_volume'] = tape[['quantity_m1', 'quantity_m2']].min(axis=1)
        fee_per_contract = 0.01
        tape['net_profit_per_contract'] = 1.0 - tape['arb_sum'] - fee_per_contract
        tape['trade_pnl'] = np.where(tape['is_arb'], 
                                     tape['net_profit_per_contract'] * tape['trade_volume'], 
                                     0)
        
        trades = tape[tape['is_arb']].copy()
        if not trades.empty:
            trades['event'] = event_ticker
            
        return trades

def main():
    engine = MLBBacktestEngine('kalshi_mlb.db')
    
    print("🔍 Fetching event list from database...")
    events = engine.con.execute("SELECT DISTINCT event_ticker FROM event_market_map").fetchall()
    
    all_trades = []

    print(f"🚀 Running backtest across {len(events)} events...")
    for (event_ticker,) in tqdm(events, desc="Processing Games"):
        # Get the two market tickers for the event
        markets = engine.con.execute(f"""
            SELECT market_ticker FROM event_market_map 
            WHERE event_ticker = '{event_ticker}' LIMIT 2
        """).fetchall()
        
        if len(markets) < 2:
            continue
            
        m1_ticker, m2_ticker = markets[0][0], markets[1][0]
        
        # 1. Data Ingestion & Post-Corroboration Validation
        m1_tape = engine.get_validated_tape(m1_ticker)
        m2_tape = engine.get_validated_tape(m2_ticker)
        
        # 2. Strategy Simulation
        game_trades = engine.run_strategy(m1_tape, m2_tape, event_ticker)
        
        if not game_trades.empty:
            all_trades.append(game_trades)

    # 3. Performance Analysis
    if all_trades:
        final_df = pd.concat(all_trades).sort_values('created_time')
        final_df['cum_pnl'] = final_df['trade_pnl'].cumsum()

        print("\n" + "="*30)
        print("📊 BACKTEST PERFORMANCE SUMMARY")
        print("="*30)
        print(f"Total Events Processed: {len(events)}")
        print(f"Total Profitable Signals: {len(final_df)}")
        print(f"Total Realized PnL: ${final_df['trade_pnl'].sum():.2f}")
        print(f"Avg PnL per Signal: ${final_df['trade_pnl'].mean():.4f}")
        print(f"Max Single Trade Win: ${final_df['trade_pnl'].max():.2f}")
        print("="*30)
        
        # Visualizing the Equity Curve
        plt.figure(figsize=(12, 6))
        plt.plot(final_df['created_time'], final_df['cum_pnl'], color='#2ecc71', linewidth=2)
        plt.fill_between(final_df['created_time'], final_df['cum_pnl'], color='#2ecc71', alpha=0.1)
        plt.title(f"MLB 2025 Strategy Equity Curve\n(Bracket Validated Taker Prices)", fontsize=14)
        plt.ylabel("Cumulative Net PnL ($)")
        plt.xlabel("Date")
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        
        plt.savefig('mlb_backtest_equity_curve.png')
        print("📈 Performance chart saved to 'mlb_backtest_equity_curve.png'")
    else:
        print("\n⚠️ No trades were executed. Consider adjusting the arb_sum threshold or max_gap.")

if __name__ == "__main__":
    main()