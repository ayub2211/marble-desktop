from sqlalchemy import or_
from src.db.models import Item


def get_items(db, category=None):
    q = db.query(Item).filter(Item.is_active == True)
    if category and category != "ALL":
        q = q.filter(Item.category == category)
    return q.order_by(Item.id.desc()).all()


def search_items(db, q_text="", category=None):
    q = db.query(Item).filter(Item.is_active == True)
    if category and category != "ALL":
        q = q.filter(Item.category == category)

    if q_text:
        like = f"%{q_text}%"
        q = q.filter(or_(Item.sku.ilike(like), Item.name.ilike(like)))

    return q.order_by(Item.id.desc()).all()


def create_item(db, data):
    item = Item(**data)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_item(db, item_id: int):
    return db.query(Item).get(item_id)


def update_item(db, item_id: int, data: dict):
    item = db.query(Item).get(item_id)
    if not item:
        return None
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


def soft_delete_item(db, item_id: int):
    item = db.query(Item).get(item_id)
    if item:
        item.is_active = False
        db.commit()
        return True
    return False

def upsert_by_sku(db, data: dict):
    """
    Upsert rule:
    - If SKU exists => update fields
    - If item is soft-deleted => reactivate (is_active=True)
    Returns: ("inserted" | "updated", Item)
    """
    sku = (data.get("sku") or "").strip()
    if not sku:
        raise ValueError("SKU is required for upsert")

    # case-insensitive match
    item = db.query(Item).filter(Item.sku.ilike(sku)).first()

    if item:
        # Update existing
        for k, v in data.items():
            setattr(item, k, v)

        # reactivate if deleted
        item.is_active = True

        db.add(item)
        return "updated", item

    # Insert new
    item = Item(**data)
    item.is_active = True
    db.add(item)
    return "inserted", item
# add into src/db/item_repo.py
from src.db.models import Item


def upsert_by_sku(db, data: dict):
    """
    Same SKU => update
    If item exists but is_active=False => reactivate + update
    Returns: "inserted" or "updated"
    """
    sku = data.get("sku")
    if not sku:
        raise ValueError("SKU missing")

    item = db.query(Item).filter(Item.sku == sku).first()

    if item:
        # reactivate + update
        item.is_active = True
        for k, v in data.items():
            setattr(item, k, v)
        db.add(item)
        return "updated"

    # insert
    item = Item(**data)
    item.is_active = True
    db.add(item)
    return "inserted"
