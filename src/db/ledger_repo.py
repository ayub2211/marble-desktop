# src/db/ledger_repo.py
from sqlalchemy.orm import joinedload
from sqlalchemy import func, or_

from src.db.models import StockLedger


def add_ledger_entry(
    db,
    item_id: int,
    location_id: int | None,
    movement_type: str,
    qty_primary,
    qty_secondary,
    unit_primary: str | None,
    unit_secondary: str | None,
    ref_type: str | None = None,
    ref_id: int | None = None,
):
    led = StockLedger(
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        qty_primary=qty_primary,
        qty_secondary=qty_secondary,
        unit_primary=unit_primary,
        unit_secondary=unit_secondary,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    db.add(led)
    return led


def get_stock_balance(db, item_id: int, location_id: int | None = None) -> tuple[float, int]:
    """
    Returns (primary_balance, secondary_balance)

    - primary_balance: sum(qty_primary)  (sqft OR piece)
    - secondary_balance: sum(qty_secondary) (slab/box) ; NULL treated as 0
    - If location_id is None => balance across ALL locations
    """
    q = db.query(
        func.coalesce(func.sum(StockLedger.qty_primary), 0),
        func.coalesce(func.sum(StockLedger.qty_secondary), 0),
    ).filter(StockLedger.item_id == item_id)

    if location_id is not None:
        q = q.filter(StockLedger.location_id == location_id)

    pri, sec = q.one()

    try:
        pri_val = float(pri or 0)
    except Exception:
        pri_val = 0.0

    try:
        sec_val = int(sec or 0)
    except Exception:
        sec_val = 0

    return pri_val, sec_val


def list_ledger(db, q_text: str = "", limit: int = 200):
    q = (
        db.query(StockLedger)
        .options(joinedload(StockLedger.item), joinedload(StockLedger.location))
        .order_by(StockLedger.id.desc())
    )

    if q_text:
        like = f"%{q_text}%"
        q = q.filter(
            or_(
                StockLedger.movement_type.ilike(like),
                func.coalesce(StockLedger.ref_type, "").ilike(like),
            )
        )

    return q.limit(limit).all()
