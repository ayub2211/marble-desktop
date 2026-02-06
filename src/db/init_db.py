from src.db.database import Base, engine
import src.db.models  # loads all models into Base metadata

def init():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init()
    print("DB tables ensured ✅")
