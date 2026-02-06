# src/db/models.py
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(20), nullable=False)

    unit_primary = Column(String(20), nullable=True)     # sqft / piece
    unit_secondary = Column(String(20), nullable=True)   # slab / box
    sqft_per_unit = Column(Numeric(10, 3), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ----------------------------
# INVENTORY TABLES
# ----------------------------

class SlabInventory(Base):
    __tablename__ = "slab_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    slab_count = Column(Integer, default=0)
    total_sqft = Column(Numeric(12, 3), default=0)

    location = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")


class TileInventory(Base):
    __tablename__ = "tile_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    box_count = Column(Integer, default=0)
    total_sqft = Column(Numeric(12, 3), default=0)

    location = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")


class BlockInventory(Base):
    __tablename__ = "block_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    piece_count = Column(Integer, default=0)

    location = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")


class TableInventory(Base):
    __tablename__ = "table_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    piece_count = Column(Integer, default=0)

    location = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")
