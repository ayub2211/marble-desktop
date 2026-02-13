# src/db/purchase_repo.py
from sqlalchemy.orm import joinedload

from src.db.models import Purchase, PurchaseItem, Item
from src.db.ledger_repo import add_ledger_entry

from src.db.slab_repo import create_slab_entry
from src.db.tile_repo import create_tile_entry
from src.db.block_repo import create_block_entry
from src.db.table_repo import create_table_entry


def _clean_text(v):
    v = (v or "").strip()
    return v or None


def _validate_purchase_rows_or_raise(db, location_id: int | None, rows: list[dict]):
    """
    Purchase rules:
    - location_id REQUIRED (because you are doing location-wise stock)
    - each row must have item_id
    - qty_primary > 0 always
    - for SLAB/TILE qty_secondary > 0 required
    - for BLOCK/TABLE qty_secondary must be None
    """
    if not location_id:
        raise ValueError("Location is required for Purchase (location-wise stock).")

    if not rows:
        raise ValueError("At least one line item is required.")

    for r in rows:
        item_id = r.get("item_id")
        if not item_id:
            raise ValueError("Invalid row: item is missing.")

        item = db.query(Item).get(item_id)
        if not item:
            raise ValueError(f"Item not found (id={item_id}).")

        cat = (item.category or "").upper()

        qty_primary = r.get("qty_primary")
        qty_secondary = r.get("qty_secondary")

        try:
            pri = float(qty_primary or 0)
        except Exception:
            pri = 0.0

        if pri <= 0:
            raise ValueError(f"Invalid qty for {item.sku} — {item.name}: primary qty must be > 0")

        if cat in ("SLAB", "TILE"):
            try:
                sec = int(qty_secondary or 0)
            except Exception:
                sec = 0
            if sec <= 0:
                raise ValueError(f"{cat} requires secondary qty (slab/box) for {item.sku} — {item.name}")
        else:
            # BLOCK/TABLE
            r["qty_secondary"] = None


def create_purchase(db, payload: dict) -> Purchase:
    """
    payload = {
      vendor_name: str|None,
      location_id: int (REQUIRED),
      notes: str|None,
      rows: [
        { item_id, qty_secondary, qty_primary }
      ]
    }
    """
    vendor_name = _clean_text(payload.get("vendor_name"))
    notes = _clean_text(payload.get("notes"))
    location_id = payload.get("location_id")

    rows = payload.get("rows") or []
    _validate_purchase_rows_or_raise(db, location_id, rows)

    # ✅ create header
    p = Purchase(
        vendor_name=vendor_name,
        location_id=location_id,
        notes=notes
    )
    db.add(p)
    db.flush()  # get p.id

    # ✅ insert lines + ledger + inventory
    for r in rows:
        item = db.query(Item).get(r["item_id"])
        cat = (item.category or "").upper()

        unit_primary = item.unit_primary or ("piece" if cat in ("BLOCK", "TABLE") else "sqft")
        unit_secondary = item.unit_secondary  # slab/box or None

        qty_primary = float(r.get("qty_primary") or 0)
        qty_secondary = r.get("qty_secondary")
        if qty_secondary is not None:
            qty_secondary = int(qty_secondary or 0)

        # purchase line
        db.add(PurchaseItem(
            purchase_id=p.id,
            item_id=item.id,
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary
        ))

        # ledger entry (+)
        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="PURCHASE",
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary,
            ref_type="purchase",
            ref_id=p.id
        )

        note_text = f"Purchase#{p.id}" + (f" — {vendor_name}" if vendor_name else "")

        # inventory tables (+)
        if cat == "SLAB":
            create_slab_entry(db, {
                "item_id": item.id,
                "slab_count": int(qty_secondary or 0),
                "total_sqft": float(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TILE":
            create_tile_entry(db, {
                "item_id": item.id,
                "box_count": int(qty_secondary or 0),
                "total_sqft": float(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "BLOCK":
            create_block_entry(db, {
                "item_id": item.id,
                "piece_count": int(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TABLE":
            create_table_entry(db, {
                "item_id": item.id,
                "piece_count": int(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })

    db.commit()
    db.refresh(p)
    return p


def list_purchases(db, q_text: str = ""):
    q = (
        db.query(Purchase)
        .options(joinedload(Purchase.location))
        .order_by(Purchase.id.desc())
    )
    if q_text:
        like = f"%{q_text}%"
        q = q.filter(Purchase.vendor_name.ilike(like))
    return q.all()
