import duckdb
import os

# Get the directory of the current script
script_dir = os.path.dirname(os.path.abspath(__file__))
parquet_file = os.path.join(script_dir, 'mlb_trades_2025.parquet')

# 1. Connect (in-memory is fine for reading Parquet)
con = duckdb.connect()

print("--- 🔍 SCHEMA CHECK ---")
# This tells us exactly what data types are stored in the file
schema = con.execute(f"DESCRIBE SELECT * FROM '{parquet_file}'").df()
print(schema[['column_name', 'column_type']])

print("\n--- 📈 DECIMAL PRECISION CHECK ---")
# We want to find trades where the price is between 0 and 1 (not just settlement 0 or 1)
decimal_check = con.execute(f"""
    SELECT 
        ticker, 
        yes_price_dollars, 
        no_price_dollars, 
        taker_side, 
        created_time 
    FROM '{parquet_file}' 
    WHERE yes_price_dollars > 0 AND yes_price_dollars < 1
    LIMIT 10
""").df()

if decimal_check.empty:
    print("❌ NO DECIMALS FOUND: All prices are currently 0.0 or 1.0.")
    print("This likely means the Kalshi 2025 archive only stores settlement values.")
else:
    print(f"✅ SUCCESS: Found {len(decimal_check)} sample trades with decimal precision!")
    print(decimal_check)

print("\n--- 📊 VOLUME SUMMARY ---")
# Let's see which game had the most activity
volume_summary = con.execute(f"""
    SELECT 
        ticker, 
        COUNT(*) as trade_count, 
        SUM(count_fp) as total_contracts
    FROM '{parquet_file}'
    GROUP BY ticker
    ORDER BY trade_count DESC
    LIMIT 5
""").df()
print(volume_summary)