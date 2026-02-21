# HK Stock Daily Data Fetch Script

This script fetches historical daily data for all HK stocks from Finnhub API and stores them in the ClickHouse database.

## Prerequisites

1. **Finnhub API Key**
   - Register at: https://finnhub.io/register
   - Get your free API key
   - Free tier: 60 calls/minute

2. **Database Setup**
   - Ensure ClickHouse is running
   - Ensure `ods_hk_basic` table is populated with HK stock list
   - Run: `uv run cli.py load-hk-basic` if needed

## Configuration

Add to your `.env` file:
```bash
FINNHUB_API_KEY=your_api_key_here
```

## Usage

### Fetch all HK stocks (1 year history)
```bash
uv run scripts/fetch_hk_daily_from_finnhub.py
```

### Fetch with custom date range
```bash
uv run scripts/fetch_hk_daily_from_finnhub.py --start-date 20240101 --end-date 20241231
```

### Test with limited stocks
```bash
uv run scripts/fetch_hk_daily_from_finnhub.py --max-stocks 10
```

### Dry run (test mode)
```bash
uv run scripts/fetch_hk_daily_from_finnhub.py --dry-run
```

## Features

- **Rate Limiting**: Strictly controls API calls to 60/minute
- **Error Handling**: Automatic retries (up to 3 times) with exponential backoff
- **Progress Tracking**: Real-time progress reports every 50 stocks
- **Data Quality**: Validates and maps Finnhub data to TuShare format
- **Resumable**: Can be stopped and restarted

## Output

Data is inserted into `ods_hk_daily` table with the following fields:
- ts_code: Stock code in TuShare format (e.g., 00001.HK)
- trade_date: Trading date (YYYYMMDD)
- open, high, low, close: Price data
- pre_close, change, pct_chg: Calculated fields
- vol: Volume
- amount: NULL (not available from Finnhub)

## Notes

1. **Rate Limit**: Free tier allows 60 calls/minute. The script respects this limit strictly.
2. **Time Estimate**: For ~2500 HK stocks at 60 calls/min, expect about 40-45 minutes.
3. **Missing Data**: Some stocks may not have data (newly listed, delisted, etc.)
4. **Amount Field**: Finnhub doesn't provide trading amount, so this field is NULL.

## Troubleshooting

### Error: FINNHUB_API_KEY not found
- Add `FINNHUB_API_KEY` to your `.env` file

### Error: No HK stocks found
- Run `uv run cli.py load-hk-basic` to populate stock list

### Rate limit errors
- The script automatically handles rate limits
- If errors persist, the script will retry up to 3 times

### Connection errors
- Check if ClickHouse is running
- Check database connection settings in `.env`
