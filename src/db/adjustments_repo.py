# src/db/adjustments_repo.py
from src.db.models import Item
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


def create_adjustment(
    db,
    *,
    location_id: int,
    movement_type: str,   # ADJUST_IN / ADJUST_OUT / DAMAGE_OUT
    item_id: int,
    qty_primary: float,
    qty_secondary: int | None,
    notes: str | None = None
):
    """
    Creates a stock adjustment:
    - Adds ledger entry
    - Updates inventory tables
    Enforces no negative stock for OUT movements.
    """
    if not location_id:
        raise ValueError("Location is required.")

    item = db.query(Item).get(item_id)
    if not item:
        raise ValueError("Item not found.")

    cat = (item.category or "").upper()
    unit_primary = item.unit_primary or ("piece" if cat in ("BLOCK", "TABLE") else "sqft")
    unit_secondary = item.unit_secondary

    if not qty_primary or float(qty_primary) <= 0:
        raise ValueError("Primary quantity must be > 0.")

    if cat in ("SLAB", "TILE"):
        if qty_secondary is None or int(qty_secondary) <= 0:
            raise ValueError(f"{cat} requires secondary qty (slab/box).")
        qty_secondary = int(qty_secondary)
    else:
        qty_secondary = None

    # OUT movements => validate stock
    is_out = movement_type in ("ADJUST_OUT", "DAMAGE_OUT")
    if is_out:
        avail_primary, avail_secondary = get_stock_balance(db, item_id, location_id)
        req_primary = float(qty_primary)
        req_secondary = int(qty_secondary or 0)

        if cat in ("BLOCK", "TABLE"):
            if req_primary > avail_primary:
                raise ValueError(
                    f"Insufficient stock.\n"
                    f"{item.sku} — {item.name}\n"
                    f"Available: {avail_primary:.3f} {unit_primary}\n"
                    f"Requested: {req_primary:.3f} {unit_primary}"
                )
        else:
            if req_secondary > avail_secondary:
                raise ValueError(
                    f"Insufficient secondary stock.\n"
                    f"{item.sku} — {item.name}\n"
                    f"Available: {avail_secondary} {unit_secondary}\n"
                    f"Requested: {req_secondary} {unit_secondary}"
                )
            if req_primary > avail_primary:
                raise ValueError(
                    f"Insufficient primary stock.\n"
                    f"{item.sku} — {item.name}\n"
                    f"Available: {avail_primary:.3f} {unit_primary}\n"
                    f"Requested: {req_primary:.3f} {unit_primary}"
                )

    # ledger qty sign
    led_qty_primary = float(qty_primary)
    led_qty_secondary = qty_secondary

    inv_primary = float(qty_primary)
    inv_secondary = qty_secondary

    if is_out:
        led_qty_primary = _neg(qty_primary)
        led_qty_secondary = -int(qty_secondary) if qty_secondary is not None else None
        inv_primary = _neg(qty_primary)
        inv_secondary = -int(qty_secondary) if qty_secondary is not None else None

    # ledger
    add_ledger_entry(
        db=db,
        item_id=item_id,
        location_id=location_id,
        movement_type=movement_type,
        qty_primary=led_qty_primary,
        qty_secondary=led_qty_secondary,
        unit_primary=unit_primary,
        unit_secondary=unit_secondary,
        ref_type="adjustment",
        ref_id=None
    )

    note_text = (notes or "").strip() or movement_type

    # inventory tables
    if cat == "SLAB":
        create_slab_entry(db, {
            "item_id": item_id,
            "slab_count": int(inv_secondary or 0),
            "total_sqft": float(inv_primary or 0),
            "location_id": location_id,
            "notes": note_text
        })
    elif cat == "TILE":
        create_tile_entry(db, {
            "item_id": item_id,
            "box_count": int(inv_secondary or 0),
            "total_sqft": float(inv_primary or 0),
            "location_id": location_id,
            "notes": note_text
        })
    elif cat == "BLOCK":
        create_block_entry(db, {
            "item_id": item_id,
            "piece_count": int(inv_primary or 0),
            "location_id": location_id,
            "notes": note_text
        })
    elif cat == "TABLE":
        create_table_entry(db, {
            "item_id": item_id,
            "piece_count": int(inv_primary or 0),
            "location_id": location_id,
            "notes": note_text
        })

    db.commit()
