# src/db/returns_repo.py
from sqlalchemy.orm import joinedload

from src.db.models import (
    Item,
    SaleReturn, SaleReturnItem,
    PurchaseReturn, PurchaseReturnItem
)

from src.db.ledger_repo import add_ledger_entry, get_stock_balance

from src.db.slab_repo import create_slab_entry
from src.db.tile_repo import create_tile_entry
from src.db.block_repo import create_block_entry
from src.db.table_repo import create_table_entry


def _pos_float(v):
    try:
        x = float(v or 0)
        return x
    except Exception:
        return 0.0


def _pos_int(v):
    try:
        x = int(v or 0)
        return x
    except Exception:
        return 0


def _neg(v):
    try:
        return -float(v)
    except Exception:
        return 0.0


def _neg_int(v):
    try:
        return -int(v)
    except Exception:
        return 0


def _validate_return_row(item: Item, qty_primary, qty_secondary):
    cat = (item.category or "").upper()
    qp = _pos_float(qty_primary)

    if qp <= 0:
        raise ValueError(f"Invalid qty for {item.sku} — {item.name}")

    if cat in ("SLAB", "TILE"):
        qs = _pos_int(qty_secondary)
        if qs <= 0:
            raise ValueError(f"{cat} requires secondary qty (slab/box) for {item.sku} — {item.name}")


def _validate_stock_or_raise(db, item: Item, location_id: int, qty_primary, qty_secondary):
    """
    Used for PURCHASE RETURN (because it DEDUCTS stock).
    SLAB/TILE: validate both primary and secondary
    BLOCK/TABLE: validate primary only
    """
    cat = (item.category or "").upper()
    available_primary, available_secondary = get_stock_balance(db, item.id, location_id)

    req_primary = _pos_float(qty_primary)
    req_secondary = _pos_int(qty_secondary) if qty_secondary is not None else 0

    if cat in ("BLOCK", "TABLE"):
        if req_primary > float(available_primary or 0):
            raise ValueError(
                f"Insufficient stock for {item.sku} — {item.name}\n"
                f"Available: {float(available_primary or 0):.3f} {item.unit_primary or 'piece'}\n"
                f"Requested: {req_primary:.3f} {item.unit_primary or 'piece'}"
            )
        return

    if req_secondary > int(available_secondary or 0):
        raise ValueError(
            f"Insufficient stock for {item.sku} — {item.name}\n"
            f"Available: {int(available_secondary or 0)} {item.unit_secondary or ''}\n"
            f"Requested: {req_secondary} {item.unit_secondary or ''}"
        )

    if req_primary > float(available_primary or 0):
        raise ValueError(
            f"Insufficient stock for {item.sku} — {item.name}\n"
            f"Available: {float(available_primary or 0):.3f} {item.unit_primary or 'sqft'}\n"
            f"Requested: {req_primary:.3f} {item.unit_primary or 'sqft'}"
        )


# -------------------------------------------------------
# SALE RETURN  (stock ADD back, ledger POSITIVE)
# -------------------------------------------------------
def create_sale_return(db, payload: dict) -> SaleReturn:
    customer = (payload.get("customer_name") or payload.get("party_name") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    location_id = payload.get("location_id")

    if not location_id:
        raise ValueError("Location is required.")

    rows = payload.get("rows") or []
    if not rows:
        raise ValueError("At least one line is required.")

    for r in rows:
        item_id = r.get("item_id")
        if not item_id:
            raise ValueError("Invalid item.")

        item = db.query(Item).get(item_id)
        if not item:
            raise ValueError("Item not found.")

        _validate_return_row(item, r.get("qty_primary"), r.get("qty_secondary"))

    sr = SaleReturn(customer_name=customer, location_id=location_id, notes=notes)
    db.add(sr)
    db.flush()

    for r in rows:
        item = db.query(Item).get(r["item_id"])
        cat = (item.category or "").upper()

        unit_primary = item.unit_primary or ("piece" if cat in ("BLOCK", "TABLE") else "sqft")
        unit_secondary = item.unit_secondary

        qty_primary = _pos_float(r.get("qty_primary"))
        qty_secondary = _pos_int(r.get("qty_secondary")) if cat in ("SLAB", "TILE") else None

        db.add(SaleReturnItem(
            sale_return_id=sr.id,
            item_id=item.id,
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary
        ))

        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="SALE_RETURN",
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary,
            ref_type="sale_return",
            ref_id=sr.id
        )

        note_text = f"SaleReturn#{sr.id}" + (f" — {customer}" if customer else "")

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
    db.refresh(sr)
    return sr


def list_sale_returns(db, q_text: str = "", limit: int = 300):
    q = (
        db.query(SaleReturn)
        .options(joinedload(SaleReturn.location))
        .order_by(SaleReturn.id.desc())
    )
    if q_text:
        like = f"%{q_text}%"
        q = q.filter(SaleReturn.customer_name.ilike(like))
    return q.limit(limit).all()


def get_sale_return_details(db, return_id: int):
    return (
        db.query(SaleReturn)
        .options(
            joinedload(SaleReturn.location),
            joinedload(SaleReturn.items).joinedload(SaleReturnItem.item),
        )
        .filter(SaleReturn.id == return_id)
        .first()
    )


# -------------------------------------------------------
# PURCHASE RETURN  (stock DEDUCT, ledger NEGATIVE)
# -------------------------------------------------------
def create_purchase_return(db, payload: dict) -> PurchaseReturn:
    vendor = (payload.get("vendor_name") or payload.get("party_name") or "").strip() or None
    notes = (payload.get("notes") or "").strip() or None
    location_id = payload.get("location_id")

    if not location_id:
        raise ValueError("Location is required.")

    rows = payload.get("rows") or []
    if not rows:
        raise ValueError("At least one line is required.")

    for r in rows:
        item_id = r.get("item_id")
        if not item_id:
            raise ValueError("Invalid item.")

        item = db.query(Item).get(item_id)
        if not item:
            raise ValueError("Item not found.")

        _validate_return_row(item, r.get("qty_primary"), r.get("qty_secondary"))
        _validate_stock_or_raise(db, item, location_id, r.get("qty_primary"), r.get("qty_secondary"))

    pr = PurchaseReturn(vendor_name=vendor, location_id=location_id, notes=notes)
    db.add(pr)
    db.flush()

    for r in rows:
        item = db.query(Item).get(r["item_id"])
        cat = (item.category or "").upper()

        unit_primary = item.unit_primary or ("piece" if cat in ("BLOCK", "TABLE") else "sqft")
        unit_secondary = item.unit_secondary

        qty_primary = _pos_float(r.get("qty_primary"))
        qty_secondary = _pos_int(r.get("qty_secondary")) if cat in ("SLAB", "TILE") else None

        db.add(PurchaseReturnItem(
            purchase_return_id=pr.id,
            item_id=item.id,
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary
        ))

        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="PURCHASE_RETURN",
            qty_primary=_neg(qty_primary),
            qty_secondary=_neg_int(qty_secondary) if qty_secondary is not None else None,
            unit_primary=unit_primary,
            unit_secondary=unit_secondary,
            ref_type="purchase_return",
            ref_id=pr.id
        )

        note_text = f"PurchaseReturn#{pr.id}" + (f" — {vendor}" if vendor else "")

        if cat == "SLAB":
            create_slab_entry(db, {
                "item_id": item.id,
                "slab_count": -int(qty_secondary or 0),
                "total_sqft": _neg(qty_primary) or 0,
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TILE":
            create_tile_entry(db, {
                "item_id": item.id,
                "box_count": -int(qty_secondary or 0),
                "total_sqft": _neg(qty_primary) or 0,
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "BLOCK":
            create_block_entry(db, {
                "item_id": item.id,
                "piece_count": -int(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })
        elif cat == "TABLE":
            create_table_entry(db, {
                "item_id": item.id,
                "piece_count": -int(qty_primary or 0),
                "location_id": location_id,
                "notes": note_text
            })

    db.commit()
    db.refresh(pr)
    return pr


def list_purchase_returns(db, q_text: str = "", limit: int = 300):
    q = (
        db.query(PurchaseReturn)
        .options(joinedload(PurchaseReturn.location))
        .order_by(PurchaseReturn.id.desc())
    )
    if q_text:
        like = f"%{q_text}%"
        q = q.filter(PurchaseReturn.vendor_name.ilike(like))
    return q.limit(limit).all()


def get_purchase_return_details(db, return_id: int):
    return (
        db.query(PurchaseReturn)
        .options(
            joinedload(PurchaseReturn.location),
            joinedload(PurchaseReturn.items).joinedload(PurchaseReturnItem.item),
        )
        .filter(PurchaseReturn.id == return_id)
        .first()
    )


def create_return(db, payload: dict):
    rtype = (payload.get("return_type") or payload.get("type") or "").strip().upper()

    if rtype in ("SALE_RETURN", "SALE", "SR"):
        return create_sale_return(db, payload)

    if rtype in ("PURCHASE_RETURN", "PURCHASE", "PR"):
        return create_purchase_return(db, payload)

    raise ValueError("Invalid return_type. Use SALE_RETURN or PURCHASE_RETURN.")


def list_returns(db, q_text: str = "", return_type: str = "ALL", limit: int = 300):
    rtype = (return_type or "ALL").strip().upper()

    if rtype in ("SALE_RETURN", "SALE", "SR"):
        return list_sale_returns(db, q_text=q_text, limit=limit)

    if rtype in ("PURCHASE_RETURN", "PURCHASE", "PR"):
        return list_purchase_returns(db, q_text=q_text, limit=limit)

    sale_rows = list_sale_returns(db, q_text=q_text, limit=limit) or []
    pur_rows = list_purchase_returns(db, q_text=q_text, limit=limit) or []

    def _dt(x):
        return getattr(x, "created_at", None) or getattr(x, "id", 0)

    merged = sorted([*sale_rows, *pur_rows], key=_dt, reverse=True)
    return merged[:limit]


def _is_cancelled(notes: str | None) -> bool:
    t = (notes or "").upper()
    return "[CANCELLED]" in t or "CANCELLED" in t


def cancel_sale_return(db, return_id: int, reason: str | None = None):
    sr = get_sale_return_details(db, return_id)
    if not sr:
        raise ValueError("Sale return not found.")
    if _is_cancelled(getattr(sr, "notes", None)):
        raise ValueError("This return is already cancelled.")

    location_id = getattr(sr, "location_id", None)
    party = getattr(sr, "customer_name", None)

    for li in (sr.items or []):
        item = li.item
        if not item:
            continue
        cat = (item.category or "").upper()

        qty_primary = float(li.qty_primary or 0)
        qty_secondary = (int(li.qty_secondary) if li.qty_secondary is not None else None)

        # SALE_RETURN cancel => reverse (negative)
        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="SALE_RETURN_CANCEL",
            qty_primary=_neg(qty_primary),
            qty_secondary=_neg_int(qty_secondary) if qty_secondary is not None else None,
            unit_primary=li.unit_primary,
            unit_secondary=li.unit_secondary,
            ref_type="sale_return",
            ref_id=sr.id
        )

        note_text = f"SaleReturnCancel#{sr.id}" + (f" — {party}" if party else "")
        if reason:
            note_text += f" ({reason})"

        if cat == "SLAB":
            create_slab_entry(db, {"item_id": item.id, "slab_count": -int(qty_secondary or 0), "total_sqft": _neg(qty_primary), "location_id": location_id, "notes": note_text})
        elif cat == "TILE":
            create_tile_entry(db, {"item_id": item.id, "box_count": -int(qty_secondary or 0), "total_sqft": _neg(qty_primary), "location_id": location_id, "notes": note_text})
        elif cat == "BLOCK":
            create_block_entry(db, {"item_id": item.id, "piece_count": -int(qty_primary or 0), "location_id": location_id, "notes": note_text})
        elif cat == "TABLE":
            create_table_entry(db, {"item_id": item.id, "piece_count": -int(qty_primary or 0), "location_id": location_id, "notes": note_text})

    base = (getattr(sr, "notes", None) or "").strip()
    stamp = "[CANCELLED]"
    if reason:
        stamp += f" {reason}"
    sr.notes = (base + ("\n" if base else "") + stamp).strip()

    db.commit()
    db.refresh(sr)
    return sr


def cancel_purchase_return(db, return_id: int, reason: str | None = None):
    pr = get_purchase_return_details(db, return_id)
    if not pr:
        raise ValueError("Purchase return not found.")
    if _is_cancelled(getattr(pr, "notes", None)):
        raise ValueError("This return is already cancelled.")

    location_id = getattr(pr, "location_id", None)
    party = getattr(pr, "vendor_name", None)

    for li in (pr.items or []):
        item = li.item
        if not item:
            continue
        cat = (item.category or "").upper()

        qty_primary = float(li.qty_primary or 0)
        qty_secondary = (int(li.qty_secondary) if li.qty_secondary is not None else None)

        # PURCHASE_RETURN cancel => reverse (positive)
        add_ledger_entry(
            db=db,
            item_id=item.id,
            location_id=location_id,
            movement_type="PURCHASE_RETURN_CANCEL",
            qty_primary=qty_primary,
            qty_secondary=qty_secondary,
            unit_primary=li.unit_primary,
            unit_secondary=li.unit_secondary,
            ref_type="purchase_return",
            ref_id=pr.id
        )

        note_text = f"PurchaseReturnCancel#{pr.id}" + (f" — {party}" if party else "")
        if reason:
            note_text += f" ({reason})"

        if cat == "SLAB":
            create_slab_entry(db, {"item_id": item.id, "slab_count": int(qty_secondary or 0), "total_sqft": float(qty_primary), "location_id": location_id, "notes": note_text})
        elif cat == "TILE":
            create_tile_entry(db, {"item_id": item.id, "box_count": int(qty_secondary or 0), "total_sqft": float(qty_primary), "location_id": location_id, "notes": note_text})
        elif cat == "BLOCK":
            create_block_entry(db, {"item_id": item.id, "piece_count": int(qty_primary or 0), "location_id": location_id, "notes": note_text})
        elif cat == "TABLE":
            create_table_entry(db, {"item_id": item.id, "piece_count": int(qty_primary or 0), "location_id": location_id, "notes": note_text})

    base = (getattr(pr, "notes", None) or "").strip()
    stamp = "[CANCELLED]"
    if reason:
        stamp += f" {reason}"
    pr.notes = (base + ("\n" if base else "") + stamp).strip()

    db.commit()
    db.refresh(pr)
    return pr
