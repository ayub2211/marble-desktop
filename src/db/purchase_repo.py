# src/db/purchase_repo.py
from src.db.models import Purchase, PurchaseItem, StockLedger, Item, Location

# existing repos (to keep your current pages working)
from src.db.slab_repo import create_slab_entry
from src.db.tile_repo import create_tile_entry
from src.db.block_repo import create_block_entry
from src.db.table_repo import create_table_entry


def create_purchase(db, payload: dict) -> Purchase:
    """
    payload = {
      vendor_name: str|None,
      location_id: int|None,
      notes: str|None,
      rows: [
        { item_id, qty_secondary, qty_primary }  # based on category
      ]
    }
    """
    vendor_name = (payload.get("vendor_name") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    location_id = payload.get("location_id")

    loc_name = None
    if location_id:
        loc = db.query(Location).get(location_id)
        loc_name = loc.name if loc else None

    p = Purchase(vendor_name=vendor_name, location_id=location_id, notes=notes)
    db.add(p)
    db.flush()  # get p.id

    rows = payload.get("rows") or []
    for r in rows:
        item_id = r.get("item_id")
        if not item_id:
            continue

        item = db.query(Item).get(item_id)
        if not item:
            continue

        category = (item.category or "").upper()
        unit_primary = item.unit_primary or ("piece" if category in ("BLOCK", "TABLE") else "sqft")
        unit_secondary = item.unit_secondary  # slab/box or None

        qty_secondary = r.get("qty_secondary")
        qty_primary = r.get("qty_primary")

        pi = PurchaseItem(
            purchase_id=p.id,
            item_id=item_id,
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary
        )
        db.add(pi)

        # ✅ ledger entry
        led = StockLedger(
            item_id=item_id,
            location_id=location_id,
            movement_type="PURCHASE",
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary,
            ref_type="purchase",
            ref_id=p.id
        )
        db.add(led)

        # ✅ keep current stock pages accurate (update their tables)
        if category == "SLAB":
            create_slab_entry(db, {
                "item_id": item_id,
                "slab_count": int(qty_secondary or 0),
                "total_sqft": float(qty_primary or 0),
                "location": loc_name,
                "notes": f"Purchase#{p.id}" + (f" — {vendor_name}" if vendor_name else "")
            })

        elif category == "TILE":
            create_tile_entry(db, {
                "item_id": item_id,
                "box_count": int(qty_secondary or 0),
                "total_sqft": float(qty_primary or 0),
                "location": loc_name,
                "notes": f"Purchase#{p.id}" + (f" — {vendor_name}" if vendor_name else "")
            })

        elif category == "BLOCK":
            create_block_entry(db, {
                "item_id": item_id,
                "piece_count": int(qty_primary or 0),
                "location": loc_name,
                "notes": f"Purchase#{p.id}" + (f" — {vendor_name}" if vendor_name else "")
            })

        elif category == "TABLE":
            create_table_entry(db, {
                "item_id": item_id,
                "piece_count": int(qty_primary or 0),
                "location": loc_name,
                "notes": f"Purchase#{p.id}" + (f" — {vendor_name}" if vendor_name else "")
            })

    db.commit()
    db.refresh(p)
    return p


def list_purchases(db, q_text: str = ""):
    q = db.query(Purchase).order_by(Purchase.id.desc())
    if q_text:
        like = f"%{q_text}%"
        q = q.filter(Purchase.vendor_name.ilike(like))
    return q.all()
