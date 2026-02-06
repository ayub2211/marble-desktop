# src/db/slab_repo.py
from sqlalchemy.orm import joinedload
from src.db.models import SlabInventory

def list_slabs(db, item_id=None):
    q = db.query(SlabInventory).options(joinedload(SlabInventory.item)).filter(SlabInventory.is_active == True)
    if item_id:
        q = q.filter(SlabInventory.item_id == item_id)
    return q.order_by(SlabInventory.id.desc()).all()

def create_slab_entry(db, data: dict):
    row = SlabInventory(**data)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def update_slab_entry(db, row_id: int, data: dict):
    row = db.query(SlabInventory).get(row_id)
    if not row:
        return None
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row

def soft_delete_slab_entry(db, row_id: int):
    row = db.query(SlabInventory).get(row_id)
    if row:
        row.is_active = False
        db.commit()
        return True
    return False
