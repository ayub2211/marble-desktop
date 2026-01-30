from src.db.database import engine, Base
from src.db import models  # noqa: F401

def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created")

if __name__ == "__main__":
    init_db()
