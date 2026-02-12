# src/db/slab_repo.py
from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload

from src.db.models import SlabInventory, Item


def list_slabs(db, q_text: str = ""):
    q = (
        db.query(SlabInventory)
        .options(
            joinedload(SlabInventory.item),
            joinedload(SlabInventory.location),
        )
        .filter(SlabInventory.is_active == True)
        .order_by(desc(SlabInventory.id))
    )

    if q_text:
        like = f"%{q_text}%"
        q = q.join(SlabInventory.item).filter(
            or_(Item.sku.ilike(like), Item.name.ilike(like))
        )

    return q.all()


def create_slab_entry(db, data: dict):
    entry = SlabInventory(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_slab_entry(db, entry_id: int):
    return (
        db.query(SlabInventory)
        .options(
            joinedload(SlabInventory.item),
            joinedload(SlabInventory.location),
        )
        .get(entry_id)
    )


def update_slab_entry(db, entry_id: int, data: dict):
    entry = db.query(SlabInventory).get(entry_id)
    if not entry:
        return None
    for k, v in data.items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


def soft_delete_slab_entry(db, entry_id: int):
    entry = db.query(SlabInventory).get(entry_id)
    if entry:
        entry.is_active = False
        db.commit()
        return True
    return False


def get_slab_items(db):
    # dropdown me sirf SLAB items
    return (
        db.query(Item)
        .filter(Item.is_active == True, Item.category == "SLAB")
        .order_by(Item.name.asc())
        .all()
    )
