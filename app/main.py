from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from .database import Base, engine, SessionLocal
from .models import ResourcePrice
from .fetcher import fetch_and_store_prices
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED
from typing import List, Dict
from pydantic import BaseModel
from datetime import datetime

# Pydantic models for API documentation
class PriceResponse(BaseModel):
    id: int
    resource: str
    price: float
    timestamp: datetime

    class Config:
        from_attributes = True

class PriceTrendPoint(BaseModel):
    price: float
    timestamp: str

class AveragePriceResponse(BaseModel):
    resource: str
    average_price: float

class HealthCheckResponse(BaseModel):
    status: str
    database: str

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Resource Price Tracker API",
    description="API for tracking and analyzing resource prices from SFL World",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI endpoint
    redoc_url="/redoc"  # ReDoc endpoint
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ptjixvwgchtj.eu-central-1.clawcloudrun.com",  # Production URL
        "http://localhost:8000",  # Local development
        "http://localhost:3000",  # Common React development port
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

scheduler = BackgroundScheduler()


# Dependency for database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Listener to catch job errors or misses and log them
def job_listener(event):
    if event.exception:
        print(f"Job {event.job_id} failed: {event.exception}")


scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_MISSED)
scheduler.add_job(fetch_and_store_prices, 'interval', minutes=15)


@app.on_event("startup")
def startup_event():
    fetch_and_store_prices()  # Immediate fetch on startup
    scheduler.start()         # Start scheduler


@app.on_event("shutdown")
def shutdown_event():
    scheduler.shutdown()      # Gracefully shutdown scheduler


@app.get("/health", response_model=HealthCheckResponse, tags=["System"])
async def health_check():
    """
    Check the health status of the API and its database connection.
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


@app.get("/prices/", response_model=List[PriceResponse], tags=["Prices"])
def get_all_prices():
    """
    Retrieve all resource prices from the database.
    Returns a list of all price records with their associated resources and timestamps.
    """
    db = SessionLocal()
    try:
        prices = db.query(ResourcePrice).all()
        return prices
    finally:
        db.close()


@app.get("/prices/{resource}", response_model=List[PriceResponse], tags=["Prices"])
def get_resource_prices(resource: str):
    """
    Retrieve all price records for a specific resource.
    
    Parameters:
    - resource: The name of the resource to get prices for
    """
    db = SessionLocal()
    try:
        data = db.query(ResourcePrice).filter(ResourcePrice.resource == resource).all()
        if not data:
            raise HTTPException(status_code=404, detail=f"No prices found for resource: {resource}")
        return data
    finally:
        db.close()


@app.get("/prices/{resource}/trend", response_model=List[PriceTrendPoint], tags=["Analytics"])
def get_price_trend(
    resource: str,
    limit: int = Query(10, description="Number of historical entries to return", ge=1, le=100)
):
    """
    Get the price trend for a specific resource.
    
    Parameters:
    - resource: The name of the resource to get the trend for
    - limit: Number of historical entries to return (default: 10, max: 100)
    """
    db = SessionLocal()
    try:
        data = (
            db.query(ResourcePrice)
            .filter(ResourcePrice.resource == resource)
            .order_by(ResourcePrice.timestamp.desc())
            .limit(limit)
            .all()
        )
        if not data:
            raise HTTPException(status_code=404, detail=f"No trend data found for resource: {resource}")
        return [
            {"price": p.price, "timestamp": p.timestamp.isoformat()}
            for p in reversed(data)
        ]
    finally:
        db.close()


@app.get("/analytics/average", response_model=List[AveragePriceResponse], tags=["Analytics"])
def get_average_prices():
    """
    Calculate and retrieve the average price for each resource.
    Returns a list of resources with their average prices.
    """
    db = SessionLocal()
    try:
        data = (
            db.query(ResourcePrice.resource, func.avg(ResourcePrice.price).label("avg_price"))
            .group_by(ResourcePrice.resource)
            .all()
        )
        return [{"resource": d[0], "average_price": d[1]} for d in data]
    finally:
        db.close()