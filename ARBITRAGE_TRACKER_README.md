# Arbitrage Tracker - Documentation

A comprehensive system for tracking arbitrage opportunities in Kalshi MLB markets. Analyzes price spreads across matched markets and records key metrics like duration, volume, and spread statistics.

## Overview

For any Kalshi MLB game (e.g., NYY vs TEX), this system tracks four primary arbitrage pairs:

1. **WIN_YES_vs_WIN_NO**: Team A WIN YES vs Team B WIN NO
   - Should theoretically sum to ~$1.00 when perfect
   - Spread = |Team A WIN YES - Team B WIN NO|

2. **LOSS_NO_vs_LOSS_YES**: Team A LOSS NO vs Team B LOSS YES
   - Should theoretically sum to ~$1.00 when perfect
   - Spread = |Team A LOSS NO - Team B LOSS YES|

3. **WIN_NO_vs_WIN_YES**: Team A WIN NO vs Team B WIN YES
   - Inverse of pair 1
   - Spread = |Team A WIN NO - Team B WIN YES|

4. **LOSS_YES_vs_LOSS_NO**: Team A LOSS YES vs Team B LOSS NO
   - Inverse of pair 2
   - Spread = |Team A LOSS YES - Team B LOSS NO|

## Files

### Core Scripts

- **arbitrage_tracker.py**: Main analysis engine
  - `ArbitrageTracker` class handles all analysis logic
  - Configurable spread threshold and game ticker
  - Outputs results to CSV with detailed metrics

- **arbitrage_runner.py**: Interactive menu-driven interface
  - Single game analysis
  - Batch analysis of all games
  - Game listing and selection

- **verify_database.py**: Database validation utility
  - Checks database structure
  - Displays available events and markets
  - Useful for troubleshooting

## Usage

### Method 1: Interactive Mode (Recommended for Single Games)

```bash
python arbitrage_runner.py
```

This launches an interactive menu where you can:
1. Select a game from a list
2. Configure the spread threshold
3. Run the analysis
4. Results are automatically saved to `arbitrage_results/` directory

### Method 2: Command Line (Best for Scripting/Batch)

```bash
# Single game analysis with default pairs (WIN YES vs WIN NO, WIN NO vs WIN YES)
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02

# Analyze all 4 pairs
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs all

# Analyze specific pairs (LOSS pairs only)
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs loss_no_vs_loss_yes loss_yes_vs_loss_no

# Custom database and output directory
python arbitrage_tracker.py \
  --event KXMLBGAME-25SEP28TEXCLE \
  --threshold 0.025 \
  --db path/to/kalshi_mlb.db \
  --output path/to/output \
  --pairs all
```

### Method 3: Python Script / Integration

```python
from arbitrage_tracker import ArbitrageTracker

# Default: analyze just the 2 WIN pairs
tracker = ArbitrageTracker(
    event_ticker='KXMLBGAME-25SEP28BALNYY',
    spread_threshold=0.02,
    db_path='kalshi_mlb.db',
    output_dir='arbitrage_results'
)
results = tracker.run_analysis()

# Or analyze all 4 pairs
tracker = ArbitrageTracker(
    event_ticker='KXMLBGAME-25SEP28BALNYY',
    spread_threshold=0.02,
    pairs_to_analyze=['win_yes_vs_win_no', 'win_no_vs_win_yes', 'loss_no_vs_loss_yes', 'loss_yes_vs_loss_no']
)
results = tracker.run_analysis()
```

## Configuration

### Key Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_ticker` | str | Required | Full event ticker (e.g., `KXMLBGAME-25SEP28BALNYY`) |
| `spread_threshold` | float | 0.02 | Minimum spread to track (in dollars) |
| `db_path` | str | `kalshi_mlb.db` | Path to DuckDB database |
| `output_dir` | str | `arbitrage_results` | Directory for CSV output |
| `pairs_to_analyze` | list | `['win_yes_vs_win_no', 'win_no_vs_win_yes']` | Which pairs to analyze |

### Pairs to Analyze

Available options:
- `win_yes_vs_win_no`: Team A WIN YES vs Team B WIN NO
- `win_no_vs_win_yes`: Team A WIN NO vs Team B WIN YES
- `loss_no_vs_loss_yes`: Team A LOSS NO vs Team B LOSS YES
- `loss_yes_vs_loss_no`: Team A LOSS YES vs Team B LOSS NO

**Default behavior** (if `--pairs` not specified): Only analyzes the 2 WIN pairs to reduce output volume.

**Command line shortcut**: Use `--pairs all` to analyze all 4 pairs.

### Spread Threshold Guidance

- **0.01**: Very sensitive, captures small arbitrage opportunities
- **0.02**: Standard setting, good balance
- **0.03**: Higher threshold, filters noise, catches major spreads only
- **0.05+**: Very restrictive, only extreme opportunities

## Output

### CSV Format

Results are saved to: `arbitrage_results/arbitrage_{EVENT_TICKER}_{THRESHOLD}.csv`

**Columns:**
- `arbitrage_type`: Which pair (e.g., "NYY WIN YES vs TEX WIN NO")
- `market1`: First market identifier
- `market2`: Second market identifier
- `start_time`: When spread exceeded threshold
- `end_time`: When spread dropped below threshold
- `duration_seconds`: Total duration of spread event
- `market1_volume`: Total trades in market1 during event (count_fp)
- `market2_volume`: Total trades in market2 during event (count_fp)
- `total_volume`: Combined volume from both markets
- `avg_spread`: Average spread during event
- `peak_spread`: Maximum spread during event
- `min_spread`: Minimum spread during event (just above threshold)
- `num_trades`: Number of trades recorded during event

### Example Output

```
arbitrage_type,market1,market2,start_time,end_time,duration_seconds,market1_volume,market2_volume,total_volume,avg_spread,peak_spread,min_spread,num_trades
NYY WIN YES vs TEX WIN NO,NYY_Y,TEX_N,2025-09-28 14:30:45.123456,2025-09-28 14:31:02.456789,17.333333,245.0,189.0,434.0,0.0342,0.0567,0.0201,42
```

## Common Use Cases

### Analyze Last Day of Season (All Games)

```bash
python arbitrage_runner.py
# Select option 2, enter threshold 0.02
```

### Analyze Just WIN Pairs (Default, Quick Scan)

```bash
# Default behavior - analyzes 2 WIN pairs only
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02
```

### Analyze All 4 Pairs (Comprehensive Scan)

```bash
# Use --pairs all to analyze WIN and LOSS pairs
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs all
```

### Analyze Only LOSS Pairs

```bash
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs loss_no_vs_loss_yes loss_yes_vs_loss_no
```

### Find Longest Arbitrage Opportunities

After running analysis:
```bash
# Load CSV and sort by duration_seconds descending
```

### Compare Thresholds

```bash
# Run with 0.02 threshold
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.02 --pairs all

# Run with 0.03 threshold
python arbitrage_tracker.py --event KXMLBGAME-25SEP28BALNYY --threshold 0.03 --pairs all

# Compare results in arbitrage_results/ directory
```

### Volume Analysis During Spreads

The CSV includes volume data for each market independently, allowing you to:
- Identify which market is more active during spreads
- Correlate volume spikes with arbitrage opportunities
- Analyze market microstructure

## Database Requirements

The script expects a DuckDB database with:

**Table 1: `event_market_map`**
```
event_ticker VARCHAR
market_ticker VARCHAR
```

**Table 2: `trades`**
```
ticker VARCHAR
trade_id VARCHAR
yes_price_dollars DOUBLE
no_price_dollars DOUBLE
count_fp DOUBLE
taker_side VARCHAR ('yes' or 'no')
created_time TIMESTAMP
```

Use `verify_database.py` to check your database:

```bash
python verify_database.py
# or with custom path:
python verify_database.py path/to/kalshi_mlb.db
```

## Troubleshooting

### "No markets found for event"
- Verify the event ticker spelling
- Use `verify_database.py` to list available events
- Check that the event is in the database

### "Missing data for one or both markets"
- The game may not have trades recorded for that market
- Try a different threshold
- Check database contents with `verify_database.py`

### Empty results
- Try lowering the spread threshold
- Verify the game has sufficient trading volume
- Check that trade data was properly loaded to database

## Performance Notes

- Single game analysis: typically <5 seconds
- Batch analysis of ~20 games: ~1-2 minutes
- Output files are relatively small (<100KB per game)

## Advanced: Analyzing Specific Pairs

If you only want to analyze specific arbitrage pairs, you can modify the script or use the Python API:

```python
from arbitrage_tracker import ArbitrageTracker

tracker = ArbitrageTracker(event_ticker='KXMLBGAME-25SEP28BALNYY', spread_threshold=0.02)

# Manually analyze just one pair
events, df = tracker.analyze_arbitrage_pair(
    market1_ticker='KXMLBGAME-25SEP28BALNYY-NYY',
    market1_side='yes',
    market2_ticker='KXMLBGAME-25SEP28BALNYY-TEX',
    market2_side='no',
    arbitrage_type='WIN_YES_vs_WIN_NO'
)
```

## Contact & Support

For issues with:
- Database connectivity: Check `verify_database.py` output
- Missing data: Review database contents and trade volume
- Script bugs: Review error messages and traceback details
