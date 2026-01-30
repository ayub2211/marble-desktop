from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, func
from src.db.database import Base

class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(20), nullable=False)  # SLAB/TILE/BLOCK/TABLE

    unit_primary = Column(String(20), nullable=False, default="sqft")   # sqft/piece
    unit_secondary = Column(String(20), nullable=True)                  # slab/box (optional)
    sqft_per_unit = Column(Numeric(10, 3), nullable=True)               # sqft per slab/box

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
