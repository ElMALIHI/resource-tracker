import httpx
import os
from datetime import datetime
from .database import SessionLocal
from .models import ResourcePrice

API_URL = os.getenv("API_URL", "https://sfl.world/api/v1/prices")

# Define which categories to keep (example: only crops and ores)
CROP_NAMES = {"Sunflower", "Potato", "Pumpkin", "Carrot", "Cabbage", "Beetroot",
              "Cauliflower", "Parsnip", "Radish", "Wheat", "Kale", "Apple", "Blueberry",
              "Orange", "Eggplant", "Corn", "Banana", "Soybean", "Grape", "Rice", "Olive",
              "Tomato", "Lemon", "Barley", "Rhubarb", "Zucchini", "Yam", "Broccoli", "Pepper",
              "Onion", "Turnip", "Artichoke", "Duskberry", "Lunara", "Celestine"}
ORE_NAMES = {"Wood", "Stone", "Iron", "Gold", "Obsidian", "Crimstone"}

ALLOWED_RESOURCES = CROP_NAMES.union(ORE_NAMES)

def fetch_and_store_prices():
    try:
        response = httpx.get(API_URL)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {}).get("p2p", {})
        timestamp_ms = payload.get("updatedAt")
        if not timestamp_ms:
            raise ValueError("Missing timestamp from API response")

        timestamp = datetime.utcfromtimestamp(timestamp_ms / 1000.0)

        db = SessionLocal()
        for resource, price in data.items():
            if resource not in ALLOWED_RESOURCES:
                continue
            db.add(ResourcePrice(resource=resource, price=price, timestamp=timestamp))
        db.commit()
        db.close()
        print(f"[{timestamp}] Filtered prices fetched and stored.")
    except Exception as e:
        print(f"Error fetching data: {e}")
