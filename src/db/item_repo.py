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
