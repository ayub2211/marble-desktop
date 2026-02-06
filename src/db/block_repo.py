# src/db/block_repo.py
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from src.db.models import BlockInventory, Item


def list_blocks(db, item_id=None):
    q = (
        db.query(BlockInventory)
        .options(joinedload(BlockInventory.item))
        .filter(BlockInventory.is_active == True)
    )
    if item_id:
        q = q.filter(BlockInventory.item_id == item_id)

    return q.order_by(desc(BlockInventory.id)).all()


def create_block_entry(db, data: dict):
    entry = BlockInventory(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_block_entry(db, entry_id: int):
    return db.query(BlockInventory).get(entry_id)


def update_block_entry(db, entry_id: int, data: dict):
    entry = db.query(BlockInventory).get(entry_id)
    if not entry:
        return None
    for k, v in data.items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


def soft_delete_block_entry(db, entry_id: int):
    entry = db.query(BlockInventory).get(entry_id)
    if entry:
        entry.is_active = False
        db.commit()
        return True
    return False


def get_block_items(db):
    # dropdown ke liye sirf BLOCK items
    return (
        db.query(Item)
        .filter(Item.is_active == True, Item.category == "BLOCK")
        .order_by(Item.name.asc())
        .all()
    )
