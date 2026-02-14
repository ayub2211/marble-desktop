# src/db/adjustments_repo.py

from sqlalchemy.orm import joinedload
from src.db.models import Item, StockLedger
from src.db.ledger_repo import add_ledger_entry, get_stock_balance
from src.db.slab_repo import create_slab_entry
from src.db.tile_repo import create_tile_entry
from src.db.block_repo import create_block_entry
from src.db.table_repo import create_table_entry


def _neg(v):
    try:
        return -float(v)
    except Exception:
        return 0.0


# =========================================================
# SINGLE ADJUSTMENT
# =========================================================
def create_adjustment(
    db,
    *,
    location_id: int,
    movement_type: str,
    item_id: int,
    qty_primary: float,
    qty_secondary: int | None,
    notes: str | None = None,
):
    if not location_id:
        raise ValueError("Location is required.")

    item = db.query(Item).get(item_id)
    if not item:
        raise ValueError("Item not found.")

    cat = (item.category or "").upper()
    movement_type = movement_type.upper()

    allowed = (
        "ADJUST_IN",
        "ADJUST_OUT",
        "DAMAGE_OUT",
        "CORRECTION_IN",
        "CORRECTION_OUT",
    )
    if movement_type not in allowed:
        raise ValueError("Invalid movement type.")

    if qty_primary <= 0:
        raise ValueError("Primary qty must be > 0.")

    if cat in ("SLAB", "TILE"):
        if not qty_secondary or qty_secondary <= 0:
            raise ValueError("Secondary qty required.")

    is_out = movement_type.endswith("_OUT")

    if is_out:
        avail_pri, avail_sec = get_stock_balance(db, item_id, location_id)

        if qty_primary > avail_pri:
            raise ValueError("Insufficient stock.")

        if cat in ("SLAB", "TILE") and qty_secondary > avail_sec:
            raise ValueError("Insufficient secondary stock.")

    led_pri = -qty_primary if is_out else qty_primary
    led_sec = -qty_secondary if is_out and qty_secondary else qty_secondary

    add_ledger_entry(
        db=db,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        qty_primary=led_pri,
        qty_secondary=led_sec,
        unit_primary=item.unit_primary,
        unit_secondary=item.unit_secondary,
        ref_type="adjustment",
        ref_id=None
    )

    db.commit()


# =========================================================
# BATCH
# =========================================================
def create_adjustments_batch(db, payload: dict):
    movement_type = payload["movement_type"]
    location_id = payload["location_id"]
    notes = payload.get("notes")

    rows = payload.get("rows") or []

    for r in rows:
        create_adjustment(
            db,
            location_id=location_id,
            movement_type=movement_type,
            item_id=r["item_id"],
            qty_primary=r["qty_primary"],
            qty_secondary=r.get("qty_secondary"),
            notes=notes,
        )


# =========================================================
# LIST
# =========================================================
def list_adjustments(db, q_text: str = "", limit: int = 300):
    q = (
        db.query(StockLedger)
        .options(
            joinedload(StockLedger.item),
            joinedload(StockLedger.location)
        )
        .filter(StockLedger.ref_type == "adjustment")
        .order_by(StockLedger.id.desc())
    )

    if q_text:
        like = f"%{q_text}%"
        q = q.join(Item).filter(
            (StockLedger.movement_type.ilike(like)) |
            (Item.sku.ilike(like)) |
            (Item.name.ilike(like))
        )

    return q.limit(limit).all()
