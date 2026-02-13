# src/db/reports_repo.py
from sqlalchemy import func

from src.db.models import (
    Location, Item,
    SlabInventory, TileInventory, BlockInventory, TableInventory
)


def location_stock_summary(db):
    """
    Returns list of dict rows:
    [
      {location_id, location_name, slab_count, slab_sqft, tile_boxes, tile_sqft, block_pieces, table_pieces}
    ]
    """
    locs = (
        db.query(Location)
        .filter(Location.is_active == True)
        .order_by(Location.name.asc())
        .all()
    )

    slab_rows = (
        db.query(
            SlabInventory.location_id.label("location_id"),
            func.coalesce(func.sum(SlabInventory.slab_count), 0).label("slab_count"),
            func.coalesce(func.sum(SlabInventory.total_sqft), 0).label("slab_sqft"),
        )
        .filter(SlabInventory.is_active == True)
        .group_by(SlabInventory.location_id)
        .all()
    )
    slab_map = {r.location_id: r for r in slab_rows}

    tile_rows = (
        db.query(
            TileInventory.location_id.label("location_id"),
            func.coalesce(func.sum(TileInventory.box_count), 0).label("tile_boxes"),
            func.coalesce(func.sum(TileInventory.total_sqft), 0).label("tile_sqft"),
        )
        .filter(TileInventory.is_active == True)
        .group_by(TileInventory.location_id)
        .all()
    )
    tile_map = {r.location_id: r for r in tile_rows}

    block_rows = (
        db.query(
            BlockInventory.location_id.label("location_id"),
            func.coalesce(func.sum(BlockInventory.piece_count), 0).label("block_pieces"),
        )
        .filter(BlockInventory.is_active == True)
        .group_by(BlockInventory.location_id)
        .all()
    )
    block_map = {r.location_id: r for r in block_rows}

    table_rows = (
        db.query(
            TableInventory.location_id.label("location_id"),
            func.coalesce(func.sum(TableInventory.piece_count), 0).label("table_pieces"),
        )
        .filter(TableInventory.is_active == True)
        .group_by(TableInventory.location_id)
        .all()
    )
    table_map = {r.location_id: r for r in table_rows}

    out = []
    for loc in locs:
        slab = slab_map.get(loc.id)
        tile = tile_map.get(loc.id)
        block = block_map.get(loc.id)
        table = table_map.get(loc.id)

        out.append({
            "location_id": loc.id,
            "location_name": loc.name,

            "slab_count": int(getattr(slab, "slab_count", 0) or 0),
            "slab_sqft": float(getattr(slab, "slab_sqft", 0) or 0),

            "tile_boxes": int(getattr(tile, "tile_boxes", 0) or 0),
            "tile_sqft": float(getattr(tile, "tile_sqft", 0) or 0),

            "block_pieces": int(getattr(block, "block_pieces", 0) or 0),
            "table_pieces": int(getattr(table, "table_pieces", 0) or 0),
        })

    return out


def location_stock_by_item(db, location_id=None, category="ALL", q_text=""):
    """
    Item-wise per-location stock list.
    Returns list of dict:
    { sku, name, category, primary_qty, secondary_qty, location_name, primary_unit, secondary_unit }
    - SLAB/TILE: primary=total_sqft, secondary=slab_count/box_count
    - BLOCK/TABLE: primary=piece_count, secondary=None
    """
    q_text = (q_text or "").strip()
    cat = (category or "ALL").upper()

    def apply_item_filter(query):
        query = query.filter(Item.is_active == True)

        if cat and cat != "ALL":
            query = query.filter(Item.category == cat)

        if q_text:
            like = f"%{q_text}%"
            query = query.filter((Item.sku.ilike(like)) | (Item.name.ilike(like)))

        return query

    results = []

    # SLABS
    if cat in ("ALL", "SLAB"):
        slab_q = (
            db.query(
                Item.sku, Item.name, Item.category,
                Location.name.label("location_name"),
                func.coalesce(func.sum(SlabInventory.total_sqft), 0).label("primary_qty"),
                func.coalesce(func.sum(SlabInventory.slab_count), 0).label("secondary_qty"),
            )
            .join(SlabInventory, SlabInventory.item_id == Item.id)
            .outerjoin(Location, Location.id == SlabInventory.location_id)
            .filter(SlabInventory.is_active == True)
            .group_by(Item.sku, Item.name, Item.category, Location.name)
        )
        slab_q = apply_item_filter(slab_q)
        if location_id is not None:
            slab_q = slab_q.filter(SlabInventory.location_id == location_id)

        for r in slab_q.all():
            results.append({
                "sku": r.sku,
                "name": r.name,
                "category": r.category,
                "location_name": r.location_name or "",
                "primary_qty": float(r.primary_qty or 0),
                "secondary_qty": int(r.secondary_qty or 0),
                "primary_unit": "sqft",
                "secondary_unit": "slab",
            })

    # TILES
    if cat in ("ALL", "TILE"):
        tile_q = (
            db.query(
                Item.sku, Item.name, Item.category,
                Location.name.label("location_name"),
                func.coalesce(func.sum(TileInventory.total_sqft), 0).label("primary_qty"),
                func.coalesce(func.sum(TileInventory.box_count), 0).label("secondary_qty"),
            )
            .join(TileInventory, TileInventory.item_id == Item.id)
            .outerjoin(Location, Location.id == TileInventory.location_id)
            .filter(TileInventory.is_active == True)
            .group_by(Item.sku, Item.name, Item.category, Location.name)
        )
        tile_q = apply_item_filter(tile_q)
        if location_id is not None:
            tile_q = tile_q.filter(TileInventory.location_id == location_id)

        for r in tile_q.all():
            results.append({
                "sku": r.sku,
                "name": r.name,
                "category": r.category,
                "location_name": r.location_name or "",
                "primary_qty": float(r.primary_qty or 0),
                "secondary_qty": int(r.secondary_qty or 0),
                "primary_unit": "sqft",
                "secondary_unit": "box",
            })

    # BLOCKS
    if cat in ("ALL", "BLOCK"):
        block_q = (
            db.query(
                Item.sku, Item.name, Item.category,
                Location.name.label("location_name"),
                func.coalesce(func.sum(BlockInventory.piece_count), 0).label("primary_qty"),
            )
            .join(BlockInventory, BlockInventory.item_id == Item.id)
            .outerjoin(Location, Location.id == BlockInventory.location_id)
            .filter(BlockInventory.is_active == True)
            .group_by(Item.sku, Item.name, Item.category, Location.name)
        )
        block_q = apply_item_filter(block_q)
        if location_id is not None:
            block_q = block_q.filter(BlockInventory.location_id == location_id)

        for r in block_q.all():
            results.append({
                "sku": r.sku,
                "name": r.name,
                "category": r.category,
                "location_name": r.location_name or "",
                "primary_qty": float(r.primary_qty or 0),
                "secondary_qty": None,
                "primary_unit": "piece",
                "secondary_unit": None,
            })

    # TABLES
    if cat in ("ALL", "TABLE"):
        table_q = (
            db.query(
                Item.sku, Item.name, Item.category,
                Location.name.label("location_name"),
                func.coalesce(func.sum(TableInventory.piece_count), 0).label("primary_qty"),
            )
            .join(TableInventory, TableInventory.item_id == Item.id)
            .outerjoin(Location, Location.id == TableInventory.location_id)
            .filter(TableInventory.is_active == True)
            .group_by(Item.sku, Item.name, Item.category, Location.name)
        )
        table_q = apply_item_filter(table_q)
        if location_id is not None:
            table_q = table_q.filter(TableInventory.location_id == location_id)

        for r in table_q.all():
            results.append({
                "sku": r.sku,
                "name": r.name,
                "category": r.category,
                "location_name": r.location_name or "",
                "primary_qty": float(r.primary_qty or 0),
                "secondary_qty": None,
                "primary_unit": "piece",
                "secondary_unit": None,
            })

    results.sort(key=lambda x: (x["location_name"], x["category"], x["sku"]))
    return results
