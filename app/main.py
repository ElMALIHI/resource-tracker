from fastapi import FastAPI, Query, HTTPException, Depends
from sqlalchemy.exc import SQLAlchemyError
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func
from .database import Base, engine, SessionLocal
from .models import ResourcePrice
from .fetcher import fetch_and_store_prices
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED

Base.metadata.create_all(bind=engine)

app = FastAPI()
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


@app.get("/health")
async def health_check():
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


@app.get("/prices/")
def get_all_prices():
    db = SessionLocal()
    prices = db.query(ResourcePrice).all()
    db.close()
    return prices


@app.get("/prices/{resource}")
def get_resource_prices(resource: str):
    db = SessionLocal()
    data = db.query(ResourcePrice).filter(ResourcePrice.resource == resource).all()
    db.close()
    return data


@app.get("/prices/{resource}/trend")
def get_price_trend(resource: str,
                    limit: int = Query(10, description="Limit number of historical entries")):
    db = SessionLocal()
    data = (
        db.query(ResourcePrice)
        .filter(ResourcePrice.resource == resource)
        .order_by(ResourcePrice.timestamp.desc())
        .limit(limit)
        .all()
    )
    db.close()
    return [
        {"price": p.price, "timestamp": p.timestamp.isoformat()}
        for p in reversed(data)
    ]


@app.get("/analytics/average")
def get_average_prices():
    db = SessionLocal()
    data = (
        db.query(ResourcePrice.resource, func.avg(ResourcePrice.price).label("avg_price"))
        .group_by(ResourcePrice.resource)
        .all()
    )
    db.close()
    return [{"resource": d[0], "average_price": d[1]} for d in data]