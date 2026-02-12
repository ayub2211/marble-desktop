# src/db/init_db.py
from src.db.database import Base, engine, SessionLocal
import src.db.models  # loads all models into Base metadata

from src.db.models import Location


def init():
    # 1) Create all tables from models
    Base.metadata.create_all(bind=engine)

    # 2) Seed default locations (safe)
    db = SessionLocal()
    try:
        for name in ["Showroom", "Warehouse"]:
            exists = db.query(Location).filter(Location.name == name).first()
            if not exists:
                db.add(Location(name=name, is_active=True))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    init()
    print("DB tables ensured ✅")
