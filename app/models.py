from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime
from .database import Base

class ResourcePrice(Base):
    __tablename__ = "resource_prices"
    id = Column(Integer, primary_key=True, index=True)
    resource = Column(String, index=True)
    price = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)
