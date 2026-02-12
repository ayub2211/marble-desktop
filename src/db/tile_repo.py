# src/db/tile_repo.py
from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload

from src.db.models import TileInventory, Item


def list_tiles(db, q_text: str = ""):
    q = (
        db.query(TileInventory)
        .options(
            joinedload(TileInventory.item),
            joinedload(TileInventory.location),
        )
        .filter(TileInventory.is_active == True)
        .order_by(desc(TileInventory.id))
    )

    if q_text:
        like = f"%{q_text}%"
        q = q.join(TileInventory.item).filter(
            or_(Item.sku.ilike(like), Item.name.ilike(like))
        )

    return q.all()


def create_tile_entry(db, data: dict):
    entry = TileInventory(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_tile_entry(db, entry_id: int):
    return (
        db.query(TileInventory)
        .options(
            joinedload(TileInventory.item),
            joinedload(TileInventory.location),
        )
        .get(entry_id)
    )


def update_tile_entry(db, entry_id: int, data: dict):
    entry = db.query(TileInventory).get(entry_id)
    if not entry:
        return None
    for k, v in data.items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


def soft_delete_tile_entry(db, entry_id: int):
    entry = db.query(TileInventory).get(entry_id)
    if entry:
        entry.is_active = False
        db.commit()
        return True
    return False


def get_tile_items(db):
    # dropdown me sirf TILE items
    return (
        db.query(Item)
        .filter(Item.is_active == True, Item.category == "TILE")
        .order_by(Item.name.asc())
        .all()
    )
