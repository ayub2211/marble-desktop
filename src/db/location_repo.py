# src/db/location_repo.py
from src.db.models import Location

def get_locations(db):
    return (
        db.query(Location)
        .filter(Location.is_active == True)
        .order_by(Location.name.asc())
        .all()
    )
