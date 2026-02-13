# src/db/location_repo.py
from sqlalchemy.orm import Session
from src.db.models import Location


def get_locations(db: Session):
    return (
        db.query(Location)
        .filter(Location.is_active == True)
        .order_by(Location.name.asc())
        .all()
    )


# ✅ Backward compatible alias (for older imports)
def list_locations(db: Session):
    return get_locations(db)
