import os
import sys
import logging

# Ensure the root directory is in the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta, date
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import Holding
from backend.schemas import (
    HoldingsResponse, Summary, ChartItem, TableItem, Pagination
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Holdings Analytics API")

@app.get("/")
async def health_check():
    return {"status": "alive", "service": "Holdings Analytics API", "version": "1.0.0"}

# CORS Management
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_timeframe_dates(timeframe: Optional[str], start_date: Optional[date], end_date: Optional[date]):
    """Calculates start and end dates based on timeframe shortcuts or manual input."""
    now = datetime.now()
    
    if timeframe:
        if timeframe == "1D": start = now - timedelta(days=1)
        elif timeframe == "1W": start = now - timedelta(weeks=1)
        elif timeframe == "1M": start = now - timedelta(days=30)
        elif timeframe == "3M": start = now - timedelta(days=90)
        elif timeframe == "6M": start = now - timedelta(days=180)
        elif timeframe == "1Y": start = now - timedelta(days=365)
        else:
            raise HTTPException(status_code=400, detail="Invalid timeframe shortcut")
        return start, now
    
    if not start_date or not end_date:
        # Default fallback: 1 month
        start = now - timedelta(days=30)
        return start, now
        
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())
    
    # Validation: 1 year limit
    if (end - start).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 1 year")
        
    return start, end

@app.get("/api/holdings", response_model=HoldingsResponse)
async def get_holdings(
    broker_id: Optional[int] = Query(None),
    symbol: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    timeframe: Optional[str] = Query(None, regex="^(1D|1W|1M|3M|6M|1Y)$"),
    group_by: str = Query("broker_id", regex="^(broker_id|symbol)$"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        # 1. Date Calculation & Validation
        start, end = get_timeframe_dates(timeframe, start_date, end_date)
        
        # 2. Base Filter Criteria
        filters = [
            Holding.qty > 0,
            Holding.date >= start,
            Holding.date <= end
        ]
        if broker_id:
            filters.append(Holding.broker_id == broker_id)
        if symbol:
            filters.append(Holding.symbol.ilike(f"%{symbol}%"))

        # 3. Fetch Summary Stats
        summary_stmt = select(
            func.sum(Holding.qty).label("total_volume"),
            func.sum(Holding.amount).label("total_turnover"),
            func.count(func.distinct(Holding.broker_id)).label("active_entities")
        ).where(and_(*filters))
        
        summary_res = await db.execute(summary_stmt)
        summary_row = summary_res.first()
        
        # 4. Fetch Raw Table Data (No grouping)
        table_stmt = select(
            Holding.broker_id,
            Holding.symbol,
            Holding.qty,
            Holding.amount,
            Holding.date
        ).where(and_(*filters)).order_by(desc(Holding.date)).limit(limit).offset(offset)

        table_res = await db.execute(table_stmt)
        table_data = [
            TableItem(
                broker_id=row.broker_id,
                symbol=row.symbol,
                quantity=float(row.qty or 0),
                turnover=float(row.amount or 0),
                date=row.date.date() if isinstance(row.date, datetime) else row.date
            )
            for row in table_res.all()
        ]

        # 5. Pagination Count (Total raw records)
        count_stmt = select(func.count()).select_from(Holding).where(and_(*filters))
        count_res = await db.execute(count_stmt)
        total_count = count_res.scalar() or 0

        return HoldingsResponse(
            summary=Summary(
                total_volume=float(summary_row.total_volume or 0),
                total_turnover=float(summary_row.total_turnover or 0),
                active_entities=int(summary_row.active_entities or 0)
            ),
            table_data=table_data,
            pagination=Pagination(limit=limit, offset=offset, total=total_count)
        )

    except Exception as e:
        logger.error(f"DATABASE ERROR: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
