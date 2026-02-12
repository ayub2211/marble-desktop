# src/db/dashboard_repo.py
from sqlalchemy import func
from src.db.models import SlabInventory, TileInventory, BlockInventory, TableInventory


def get_dashboard_totals(db) -> dict:
    slab_count = db.query(func.coalesce(func.sum(SlabInventory.slab_count), 0)).filter(
        SlabInventory.is_active == True
    ).scalar()

    slab_sqft = db.query(func.coalesce(func.sum(SlabInventory.total_sqft), 0)).filter(
        SlabInventory.is_active == True
    ).scalar()

    tile_boxes = db.query(func.coalesce(func.sum(TileInventory.box_count), 0)).filter(
        TileInventory.is_active == True
    ).scalar()

    tile_sqft = db.query(func.coalesce(func.sum(TileInventory.total_sqft), 0)).filter(
        TileInventory.is_active == True
    ).scalar()

    block_pieces = db.query(func.coalesce(func.sum(BlockInventory.piece_count), 0)).filter(
        BlockInventory.is_active == True
    ).scalar()

    table_pieces = db.query(func.coalesce(func.sum(TableInventory.piece_count), 0)).filter(
        TableInventory.is_active == True
    ).scalar()

    return {
        "slab_count": int(slab_count or 0),
        "slab_sqft": float(slab_sqft or 0),
        "tile_boxes": int(tile_boxes or 0),
        "tile_sqft": float(tile_sqft or 0),
        "block_pieces": int(block_pieces or 0),
        "table_pieces": int(table_pieces or 0),
    }
