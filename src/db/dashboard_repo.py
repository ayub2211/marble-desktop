# src/db/dashboard_repo.py
from sqlalchemy import func

from src.db.models import (
    SlabInventory, TileInventory, BlockInventory, TableInventory,
    Purchase, Item, StockLedger
)


def get_dashboard_totals(db):
    """
    Returns dict with totals used on dashboard cards.
    NOTE: keys kept backward-compatible.
    """

    slabs_count = db.query(func.coalesce(func.sum(SlabInventory.slab_count), 0)) \
        .filter(SlabInventory.is_active == True).scalar()

    slabs_sqft = db.query(func.coalesce(func.sum(SlabInventory.total_sqft), 0)) \
        .filter(SlabInventory.is_active == True).scalar()

    tiles_boxes = db.query(func.coalesce(func.sum(TileInventory.box_count), 0)) \
        .filter(TileInventory.is_active == True).scalar()

    tiles_sqft = db.query(func.coalesce(func.sum(TileInventory.total_sqft), 0)) \
        .filter(TileInventory.is_active == True).scalar()

    blocks_pieces = db.query(func.coalesce(func.sum(BlockInventory.piece_count), 0)) \
        .filter(BlockInventory.is_active == True).scalar()

    tables_pieces = db.query(func.coalesce(func.sum(TableInventory.piece_count), 0)) \
        .filter(TableInventory.is_active == True).scalar()

    purchases_count = db.query(func.count(Purchase.id)).scalar() or 0

    return {
        # old-style keys
        "slabs_count": int(slabs_count or 0),
        "slabs_sqft": float(slabs_sqft or 0),
        "tiles_boxes": int(tiles_boxes or 0),
        "tiles_sqft": float(tiles_sqft or 0),
        "blocks_pieces": int(blocks_pieces or 0),
        "tables_pieces": int(tables_pieces or 0),
        "purchases_count": int(purchases_count or 0),

        # also provide new-style keys (optional)
        "slab_count": int(slabs_count or 0),
        "slab_sqft": float(slabs_sqft or 0),
        "tile_boxes": int(tiles_boxes or 0),
        "tile_sqft": float(tiles_sqft or 0),
        "block_pieces": int(blocks_pieces or 0),
        "table_pieces": int(tables_pieces or 0),
        "purchase_count": int(purchases_count or 0),
    }


def get_low_stock_top_items(db, limit: int = 5, location_id=None):
    """
    Low stock list (Top N) using StockLedger balances.

    SLAB/TILE -> secondary balance (slab/box)
    BLOCK/TABLE -> primary balance (piece)

    If location_id is provided -> location-wise stock.
    Returns list of dict:
    [{sku,name,category,qty,unit}]
    """

    items = db.query(Item).filter(Item.is_active == True).order_by(Item.sku.asc()).all()

    out = []
    for it in items:
        cat = (it.category or "").upper()

        q_pri = db.query(func.coalesce(func.sum(StockLedger.qty_primary), 0)) \
            .filter(StockLedger.item_id == it.id)

        q_sec = db.query(func.coalesce(func.sum(StockLedger.qty_secondary), 0)) \
            .filter(StockLedger.item_id == it.id)

        if location_id is not None:
            q_pri = q_pri.filter(StockLedger.location_id == location_id)
            q_sec = q_sec.filter(StockLedger.location_id == location_id)

        pri = q_pri.scalar() or 0
        sec = q_sec.scalar() or 0

        try:
            pri_val = float(pri or 0)
        except Exception:
            pri_val = 0.0

        try:
            sec_val = int(sec or 0)
        except Exception:
            sec_val = 0

        if cat in ("SLAB", "TILE"):
            qty = sec_val
            unit = it.unit_secondary or ("slab" if cat == "SLAB" else "box")
        else:
            qty = int(round(pri_val))
            unit = it.unit_primary or "piece"

        out.append({
            "sku": it.sku,
            "name": it.name,
            "category": cat,
            "qty": qty,
            "unit": unit,
        })

    out.sort(key=lambda x: x["qty"])
    return out[: max(1, int(limit or 5))]
