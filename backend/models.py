from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index
from backend.database import Base

class Holding(Base):
    __tablename__ = "holdings"

    id = Column(Integer, primary_key=True, index=True)
    broker_id = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    qty = Column(Numeric, nullable=False)
    amount = Column(Numeric, nullable=False)
    date = Column(DateTime, nullable=False)

    # Performance: Crucial indexes for the analytics dashboard
    __table_args__ = (
        Index("idx_trade_date", "date"),
        Index("idx_broker_symbol", "broker_id", "symbol"),
    )
