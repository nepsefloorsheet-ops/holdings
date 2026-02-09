from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class Summary(BaseModel):
    total_volume: float
    total_turnover: float
    active_entities: int

class ChartItem(BaseModel):
    date: str
    volume: float
    turnover: float

class TableItem(BaseModel):
    broker_id: Optional[int] = None
    symbol: Optional[str] = None
    quantity: float
    turnover: float
    volume: float

class Pagination(BaseModel):
    limit: int
    offset: int
    total: int

class HoldingsResponse(BaseModel):
    summary: Summary
    chart_data: List[ChartItem]
    table_data: List[TableItem]
    pagination: Pagination
