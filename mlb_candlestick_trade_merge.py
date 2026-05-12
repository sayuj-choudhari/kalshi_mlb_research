import duckdb
import pandas as pd

def get_precision_max_definition_dataset(ticker, db_name="kalshi_mlb.db"):
    con = duckdb.connect(db_name)

    query = f"""
    -- 1. Get all actual trades with full precision
    SELECT 
        created_time AS timestamp,
        yes_price_dollars AS yes_price,
        no_price_dollars AS no_price,
        count_fp AS volume,
        'TRADE' AS source
    FROM trades
    WHERE ticker = '{ticker}'

    UNION ALL

    -- 2. Get minute snapshots only where no trades happened
    SELECT 
        end_period_ts AS timestamp,
        ask_open AS yes_price,
        (1.0 - bid_open) AS no_price,
        0 AS volume,
        'QUOTE' AS source
    FROM candlesticks c
    WHERE ticker = '{ticker}' 
      AND (volume = 0 OR volume IS NULL)
      -- Vital: Don't add a quote snapshot if a trade happened 
      -- in the exact same fractional second (unlikely, but for safety)
      AND NOT EXISTS (
          SELECT 1 FROM trades t 
          WHERE t.ticker = c.ticker 
          AND t.created_time = c.end_period_ts
      )

    ORDER BY timestamp ASC
    """
    
    df = con.execute(query).df()
    con.close()
    
    # Ensure the timestamp column is a proper datetime object with precision
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    return df

# Run and inspect
df_precision = get_precision_max_definition_dataset("KXMLBGAME-25SEP28KCATH-KC")

# Show a sample that includes fractional seconds
print(df_precision.head(300))

# To verify precision in the terminal:
# print(df_precision['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S.%f').head(10))