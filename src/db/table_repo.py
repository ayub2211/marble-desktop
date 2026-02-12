# src/db/table_repo.py
from sqlalchemy import desc, or_
from sqlalchemy.orm import joinedload

from src.db.models import TableInventory, Item


def list_tables(db, q_text: str = ""):
    q = (
        db.query(TableInventory)
        .options(
            joinedload(TableInventory.item),
            joinedload(TableInventory.location),
        )
        .filter(TableInventory.is_active == True)
        .order_by(desc(TableInventory.id))
    )

    if q_text:
        like = f"%{q_text}%"
        q = q.join(TableInventory.item).filter(
            or_(Item.sku.ilike(like), Item.name.ilike(like))
        )

    return q.all()


def create_table_entry(db, data: dict):
    entry = TableInventory(**data)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_table_entry(db, entry_id: int):
    return (
        db.query(TableInventory)
        .options(
            joinedload(TableInventory.item),
            joinedload(TableInventory.location),
        )
        .get(entry_id)
    )


def update_table_entry(db, entry_id: int, data: dict):
    entry = db.query(TableInventory).get(entry_id)
    if not entry:
        return None
    for k, v in data.items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


def soft_delete_table_entry(db, entry_id: int):
    entry = db.query(TableInventory).get(entry_id)
    if entry:
        entry.is_active = False
        db.commit()
        return True
    return False


def get_table_items(db):
    # dropdown me sirf TABLE items
    return (
        db.query(Item)
        .filter(Item.is_active == True, Item.category == "TABLE")
        .order_by(Item.name.asc())
        .all()
    )
