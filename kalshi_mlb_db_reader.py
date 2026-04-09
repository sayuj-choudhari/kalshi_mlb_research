import duckdb

# Connect to your DB
con = duckdb.connect('kalshi_mlb.db')

# USE THESE EXACT COLUMN NAMES
query = """
    SELECT 
        ticker, 
        trade_id, 
        yes_price_dollars,
        no_price_dollars, 
        count_fp, 
        taker_side, 
        created_time 
    FROM 'mlb_trades_2025.parquet'
    WHERE ticker = 'KXMLBGAME-25SEP28STLCHC-STL'
    ORDER BY created_time ASC
"""

df = con.execute(query).df()
print(df.head())
print(df)