# src/db/models.py
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.db.database import Base


# ----------------------------
# MASTER TABLES
# ----------------------------

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(20), nullable=False)  # SLAB / TILE / BLOCK / TABLE

    unit_primary = Column(String(20), nullable=True)     # sqft / piece
    unit_secondary = Column(String(20), nullable=True)   # slab / box
    sqft_per_unit = Column(Numeric(10, 3), nullable=True)

    # ✅ optional product attributes
    material = Column(String(50), nullable=True)         # Marble / Travertine / Stone etc
    thickness = Column(String(20), nullable=True)        # 2cm / 3cm etc
    finish = Column(String(30), nullable=True)           # Honed / Polished etc

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

    # ✅ NEW: location FK
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")
    location = relationship("Location")


class TileInventory(Base):
    __tablename__ = "tile_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    box_count = Column(Integer, default=0)
    total_sqft = Column(Numeric(12, 3), default=0)

    # ✅ NEW: location FK
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")
    location = relationship("Location")


class BlockInventory(Base):
    __tablename__ = "block_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    piece_count = Column(Integer, default=0)

    # ✅ NEW: location FK
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")
    location = relationship("Location")


class TableInventory(Base):
    __tablename__ = "table_inventory"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    piece_count = Column(Integer, default=0)

    # ✅ NEW: location FK
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    item = relationship("Item")
    location = relationship("Location")


# ----------------------------
# PURCHASE + LEDGER (future-ready)
# ----------------------------

class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(Integer, primary_key=True)
    vendor_name = Column(String(120), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    notes = Column(String(250), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    location = relationship("Location")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(Integer, primary_key=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)

    qty_primary = Column(Numeric(12, 3), nullable=True)    # sqft OR piece (BLOCK/TABLE uses piece here)
    qty_secondary = Column(Integer, nullable=True)         # slab/box count for SLAB/TILE

    unit_primary = Column(String(20), nullable=True)       # "sqft"/"piece"
    unit_secondary = Column(String(20), nullable=True)     # "slab"/"box"

    purchase = relationship("Purchase", back_populates="items")
    item = relationship("Item")


class StockLedger(Base):
    __tablename__ = "stock_ledger"

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    movement_type = Column(String(20), nullable=False)  # PURCHASE / SALE / ADJUST / DAMAGE
    qty_primary = Column(Numeric(12, 3), nullable=True)
    qty_secondary = Column(Integer, nullable=True)

    unit_primary = Column(String(20), nullable=True)
    unit_secondary = Column(String(20), nullable=True)

    ref_type = Column(String(30), nullable=True)  # "purchase"
    ref_id = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    item = relationship("Item")
    location = relationship("Location")
