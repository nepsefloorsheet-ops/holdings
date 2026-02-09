# Holdings Analytics API

A high-performance FastAPI back-end for processing large datasets of financial holdings.

## Features

- **SQL-side aggregation**: Efficiently handles millions of rows using PostgreSQL grouping.
- **Shortcut support**: Automatic date calculation for `1D`, `1W`, `1M`, `3M`, `6M`, `1Y`.
- **Async DB operations**: Optimized for concurrent requests.
- **Safety checks**: Prevents date ranges exceeding 1 year to ensure database stability.

## Prerequisites

- Python 3.9+
- A Supabase Project (PostgreSQL)

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment:
   - Rename `.env.example` to `.env`
   - Update `DATABASE_URL` with your Supabase credentials.

## Setup Supabase (PostgreSQL)

You need your **Database Connection string** from Supabase.

1. Go to **Project Settings** -> **Database**.
2. Look for the **Connection string** section.
3. Use the **URI** format: `postgresql://postgres:[YOUR-PASSWORD]@[HOST]:5432/postgres`
4. **IMPORTANT**: For FastAPI (SQLAlchemy), use `postgresql+asyncpg://` as the prefix.

### Required Database Key

The "API Key" from Supabase is **not** used for this direct database connection. Instead, you need:

- **Database Password**: The one you set when creating the project.
- **Database Host**: e.g., `db.xxxxxxxx.supabase.co`

## Running the API

```bash
uvicorn backend.main:app --reload
```

The API will be available at `http://localhost:8000/docs`.

## Database Schema (SQL)

Run this in your Supabase SQL Editor:

```sql
CREATE TABLE holdings (
    id SERIAL PRIMARY KEY,
    broker_id INTEGER NOT NULL,
    symbol TEXT NOT NULL,
    quantity NUMERIC NOT NULL,
    turnover NUMERIC NOT NULL,
    volume NUMERIC NOT NULL,
    trade_date TIMESTAMP WITH TIME ZONE NOT NULL
);

-- Essential Performance Indexes
CREATE INDEX idx_trade_date ON holdings(trade_date);
CREATE INDEX idx_broker_id ON holdings(broker_id);
CREATE INDEX idx_symbol ON holdings(symbol);
```
