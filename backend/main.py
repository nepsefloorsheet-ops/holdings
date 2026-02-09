import logging
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
            Holding.quantity > 0,
            Holding.trade_date >= start,
            Holding.trade_date <= end
        ]
        if broker_id:
            filters.append(Holding.broker_id == broker_id)
        if symbol:
            filters.append(Holding.symbol.ilike(f"%{symbol}%"))

        # 3. Fetch Summary Stats
        # total_volume, total_turnover, distinct entities
        entity_col = Holding.broker_id if group_by == "broker_id" else Holding.symbol
        summary_stmt = select(
            func.sum(Holding.volume).label("total_volume"),
            func.sum(Holding.turnover).label("total_turnover"),
            func.count(func.distinct(entity_col)).label("active_entities")
        ).where(and_(*filters))
        
        summary_res = await db.execute(summary_stmt)
        summary_row = summary_res.first()
        
        # 4. Fetch Chart Data (Group by date)
        chart_stmt = select(
            func.date(Holding.trade_date).label("date"),
            func.sum(Holding.volume).label("volume"),
            func.sum(Holding.turnover).label("turnover")
        ).where(and_(*filters)).group_by(func.date(Holding.trade_date)).order_by("date")
        
        chart_res = await db.execute(chart_stmt)
        chart_data = [
            ChartItem(date=str(row.date), volume=float(row.volume), turnover=float(row.turnover))
            for row in chart_res.all()
        ]

        # 5. Fetch Table Data (Grouped by entity with pagination)
        group_col = Holding.broker_id if group_by == "broker_id" else Holding.symbol
        table_stmt = select(
            group_col,
            func.sum(Holding.quantity).label("quantity"),
            func.sum(Holding.turnover).label("turnover"),
            func.sum(Holding.volume).label("volume")
        ).where(and_(*filters)).group_by(group_col).order_by(desc("quantity")).limit(limit).offset(offset)

        table_res = await db.execute(table_stmt)
        table_data = []
        for row in table_res.all():
            item_data = {
                "quantity": float(row.quantity),
                "turnover": float(row.turnover),
                "volume": float(row.volume)
            }
            if group_by == "broker_id": item_data["broker_id"] = row.broker_id
            else: item_data["symbol"] = row.symbol
            table_data.append(TableItem(**item_data))

        # 6. Pagination Count
        count_stmt = select(func.count(func.distinct(group_col))).where(and_(*filters))
        count_res = await db.execute(count_stmt)
        total_count = count_res.scalar()

        return HoldingsResponse(
            summary=Summary(
                total_volume=float(summary_row.total_volume or 0),
                total_turnover=float(summary_row.total_turnover or 0),
                active_entities=int(summary_row.active_entities or 0)
            ),
            chart_data=chart_data,
            table_data=table_data,
            pagination=Pagination(limit=limit, offset=offset, total=total_count)
        )

    except Exception as e:
        logger.error(f"Error fetching holdings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")
