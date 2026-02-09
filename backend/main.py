import os
import sys
import logging
from datetime import datetime, timedelta, date
from typing import List, Optional

# Ensure the root directory is in the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, and_, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Holding
from backend.schemas import (
    HoldingsResponse, Summary, TableItem, Pagination
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Holdings Analytics API")

# CORS Management
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_last_trading_day(db: AsyncSession) -> date:
    """Helper to find the most recent date in the database."""
    stmt = select(func.max(Holding.date))
    result = await db.execute(stmt)
    max_date = result.scalar()
    if max_date:
        return max_date.date() if isinstance(max_date, datetime) else max_date
    return date.today()

@app.get("/")
async def health_check():
    return {"status": "alive", "service": "Holdings Analytics API", "version": "2.0.0"}

@app.get("/api/holdings", response_model=HoldingsResponse)
async def get_holdings(
    broker_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    target_date: Optional[date] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Main analytics endpoint.
    If no target_date is provided, it defaults to the last trading day found in the DB.
    """
    try:
        # 1. Determine Date (Market Pill / Holiday Logic)
        if not target_date:
            target_date = await get_last_trading_day(db)
            
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        # 2. Base Filters
        filters = [
            Holding.qty > 0,
            Holding.date >= start_of_day,
            Holding.date <= end_of_day
        ]
        if broker_id:
            filters.append(Holding.broker_id == broker_id)
        if symbol:
            filters.append(Holding.symbol.ilike(f"%{symbol}%"))

        # 3. Summary Stats for the selected date
        summary_stmt = select(
            func.sum(Holding.qty).label("total_volume"),
            func.sum(Holding.amount).label("total_turnover"),
            func.count(func.distinct(Holding.broker_id)).label("active_brokers")
        ).where(and_(*filters))
        
        summary_res = await db.execute(summary_stmt)
        summary_row = summary_res.first()

        # 4. Fetch Raw Records
        table_stmt = select(
            Holding.date,
            Holding.broker_id,
            Holding.symbol,
            Holding.qty,
            Holding.amount
        ).where(and_(*filters)).order_by(desc(Holding.qty)).limit(limit).offset(offset)

        table_res = await db.execute(table_stmt)
        table_data = [
            TableItem(
                date=row.date.date() if isinstance(row.date, datetime) else row.date,
                broker_id=row.broker_id,
                symbol=row.symbol,
                qty=float(row.qty or 0),
                amount=float(row.amount or 0)
            )
            for row in table_res.all()
        ]

        # 5. Pagination Count
        count_stmt = select(func.count()).select_from(Holding).where(and_(*filters))
        count_res = await db.execute(count_stmt)
        total_count = count_res.scalar() or 0

        return HoldingsResponse(
            summary=Summary(
                total_volume=float(summary_row.total_volume or 0),
                total_turnover=float(summary_row.total_turnover or 0),
                active_entities=int(summary_row.active_brokers or 0)
            ),
            table_data=table_data,
            pagination=Pagination(limit=limit, offset=offset, total=total_count)
        )

    except Exception as e:
        logger.error(f"API ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
