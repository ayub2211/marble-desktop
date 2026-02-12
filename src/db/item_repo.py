# src/db/item_repo.py
from sqlalchemy import or_
from src.db.models import Item


ALLOWED_FIELDS = {
    "sku", "name", "category",
    "unit_primary", "unit_secondary", "sqft_per_unit",
    "material", "thickness", "finish",
}


def _filtered(data: dict) -> dict:
    """Keep only allowed keys (avoid random/unwanted fields)."""
    return {k: v for k, v in (data or {}).items() if k in ALLOWED_FIELDS}


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
        # ✅ search in new fields too
        q = q.filter(or_(
            Item.sku.ilike(like),
            Item.name.ilike(like),
            Item.material.ilike(like),
            Item.thickness.ilike(like),
            Item.finish.ilike(like),
        ))

    return q.order_by(Item.id.desc()).all()


def create_item(db, data):
    data = _filtered(data)

    # normalize
    if data.get("sku"):
        data["sku"] = data["sku"].strip().upper()
    if data.get("category"):
        data["category"] = data["category"].strip().upper()

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

    data = _filtered(data)

    # normalize
    if data.get("sku"):
        data["sku"] = data["sku"].strip().upper()
    if data.get("category"):
        data["category"] = data["category"].strip().upper()

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
    Upsert rule (case-insensitive):
    - If SKU exists => update + reactivate if deleted
    - Else insert new
    Returns: "inserted" or "updated"
    NOTE: no commit here; importer commits in batches
    """
    data = _filtered(data)

    sku = (data.get("sku") or "").strip().upper()
    if not sku:
        raise ValueError("SKU is required for upsert")

    data["sku"] = sku

    if data.get("category"):
        data["category"] = data["category"].strip().upper()

    # ✅ case-insensitive match (fixes BLK-005 vs blk-005 issues)
    item = db.query(Item).filter(Item.sku.ilike(sku)).first()

    if item:
        for k, v in data.items():
            setattr(item, k, v)
        item.is_active = True
        db.add(item)
        return "updated"

    item = Item(**data)
    item.is_active = True
    db.add(item)
    return "inserted"
