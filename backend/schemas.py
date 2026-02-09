from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

class Summary(BaseModel):
    total_volume: float
    total_turnover: float
    active_entities: int

class TableItem(BaseModel):
    broker_id: int
    symbol: str
    quantity: float
    turnover: float
    date: date

class Pagination(BaseModel):
    limit: int
    offset: int
    total: int

class HoldingsResponse(BaseModel):
    summary: Summary
    table_data: List[TableItem]
    pagination: Pagination
