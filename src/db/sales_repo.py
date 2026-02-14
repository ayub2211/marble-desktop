# src/db/sales_repo.py
from sqlalchemy.orm import joinedload

from src.db.models import Sale, SaleItem, Item
from src.db.ledger_repo import add_ledger_entry, get_stock_balance

from src.db.slab_repo import create_slab_entry
from src.db.tile_repo import create_tile_entry
from src.db.block_repo import create_block_entry
from src.db.table_repo import create_table_entry


def _neg(v):
    try:
        return -float(v or 0)
    except Exception:
        return 0.0


def _to_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default


def _to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _validate_stock_or_raise(db, item: Item, location_id: int, qty_primary, qty_secondary):
    """
    location-wise strict validation
    - BLOCK/TABLE: only primary (piece)
    - SLAB/TILE: both primary (sqft) & secondary (slab/box)
    """
    cat = (item.category or "").upper()

    avail_primary, avail_secondary = get_stock_balance(db, item.id, location_id)

    req_primary = _to_float(qty_primary, 0.0)
    req_secondary = _to_int(qty_secondary, 0) if qty_secondary is not None else 0

    # basic qty rules
    if cat in ("SLAB", "TILE"):
        if req_secondary <= 0:
            raise ValueError(f"{cat} requires secondary qty > 0 for {item.sku} — {item.name}")
        if req_primary <= 0:
            raise ValueError(f"{cat} requires primary qty (sqft) > 0 for {item.sku} — {item.name}")
    else:
        if req_primary <= 0:
            raise ValueError(f"{cat} requires piece qty > 0 for {item.sku} — {item.name}")

    # stock rules
    if cat in ("BLOCK", "TABLE"):
        if req_primary > float(avail_primary or 0):
            raise ValueError(
                f"Insufficient stock (Location-wise)\n\n"
                f"{item.sku} — {item.name}\n"
                f"Available: {float(avail_primary or 0):.3f} {item.unit_primary or 'piece'}\n"
                f"Requested: {req_primary:.3f} {item.unit_primary or 'piece'}"
            )
        return

    # SLAB/TILE => both checks
    if req_secondary > int(avail_secondary or 0):
        raise ValueError(
            f"Insufficient stock (Location-wise)\n\n"
            f"{item.sku} — {item.name}\n"
            f"Available: {int(avail_secondary or 0)} {item.unit_secondary or ''}\n"
            f"Requested: {req_secondary} {item.unit_secondary or ''}"
        )

    if req_primary > float(avail_primary or 0):
        raise ValueError(
            f"Insufficient stock (Location-wise)\n\n"
            f"{item.sku} — {item.name}\n"
            f"Available: {float(avail_primary or 0):.3f} {item.unit_primary or 'sqft'}\n"
            f"Requested: {req_primary:.3f} {item.unit_primary or 'sqft'}"
        )


def create_sale(db, payload: dict) -> Sale:
    customer = (payload.get("customer_name") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    location_id = payload.get("location_id")

    if not location_id:
        raise ValueError("Location is required for sale.")

    rows = payload.get("rows") or []
    if not rows:
        raise ValueError("No sale rows found.")

    prepared = []
    for r in rows:
        item_id = r.get("item_id")
        if not item_id:
            continue

        item = db.query(Item).get(item_id)
        if not item:
            continue

        qty_secondary = r.get("qty_secondary")
        qty_primary = r.get("qty_primary")

        # ✅ ensure numeric
        qty_primary = _to_float(qty_primary, 0.0)
        qty_secondary = None if qty_secondary is None else _to_int(qty_secondary, 0)

        _validate_stock_or_raise(db, item, int(location_id), qty_primary, qty_secondary)

        prepared.append((item, qty_primary, qty_secondary))

    if not prepared:
        raise ValueError("No valid sale lines found.")

    s = Sale(customer_name=customer, location_id=location_id, notes=notes)
    db.add(s)
    db.flush()  # s.id

    for (item, qty_primary, qty_secondary) in prepared:
        cat = (item.category or "").upper()
        unit_primary = item.unit_primary or ("piece" if cat in ("BLOCK", "TABLE") else "sqft")
        unit_secondary = item.unit_secondary

        line_qty_primary = float(qty_primary or 0)
        line_qty_secondary = None if cat in ("BLOCK", "TABLE") else (None if qty_secondary is None else int(qty_secondary))

        db.add(SaleItem(
            sale_id=s.id,
            item_id=item.id,
            qty_primary=line_qty_primary,
            qty_secondary=line_qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary
        ))

        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="SALE",
            qty_primary=_neg(line_qty_primary),
            qty_secondary=(-int(line_qty_secondary) if line_qty_secondary is not None else None),
            unit_primary=unit_primary,
            unit_secondary=unit_secondary,
            ref_type="sale",
            ref_id=s.id
        )

        note_text = f"Sale#{s.id}" + (f" — {customer}" if customer else "")

        if cat == "SLAB":
            create_slab_entry(db, {
                "item_id": item.id,
                "slab_count": -int(line_qty_secondary or 0),
                "total_sqft": _neg(line_qty_primary),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TILE":
            create_tile_entry(db, {
                "item_id": item.id,
                "box_count": -int(line_qty_secondary or 0),
                "total_sqft": _neg(line_qty_primary),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "BLOCK":
            create_block_entry(db, {
                "item_id": item.id,
                "piece_count": -int(line_qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TABLE":
            create_table_entry(db, {
                "item_id": item.id,
                "piece_count": -int(line_qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })

    db.commit()
    db.refresh(s)
    return s


def list_sales(db, q_text: str = "", limit: int = 300):
    q = (
        db.query(Sale)
        .options(joinedload(Sale.location))
        .order_by(Sale.id.desc())
    )
    if q_text:
        like = f"%{q_text}%"
        q = q.filter(Sale.customer_name.ilike(like))
    return q.limit(limit).all()


def get_sale_details(db, sale_id: int):
    return (
        db.query(Sale)
        .options(
            joinedload(Sale.location),
            joinedload(Sale.items).joinedload(SaleItem.item)
        )
        .filter(Sale.id == sale_id)
        .first()
    )
