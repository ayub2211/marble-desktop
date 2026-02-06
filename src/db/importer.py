# src/db/importer.py
import csv

from src.db.item_repo import upsert_by_sku


def _clean_row(row: dict) -> dict:
    # expected headers: sku,name,category,unit_primary,unit_secondary,sqft_per_unit
    sku = (row.get("sku") or "").strip()
    name = (row.get("name") or "").strip()
    category = (row.get("category") or "").strip().upper()

    unit_primary = (row.get("unit_primary") or "").strip().lower() or "sqft"
    unit_secondary = (row.get("unit_secondary") or "").strip().lower() or None

    sqft_per_unit_raw = (row.get("sqft_per_unit") or "").strip()
    sqft_per_unit = None
    if sqft_per_unit_raw:
        try:
            sqft_per_unit = float(sqft_per_unit_raw)
        except Exception:
            sqft_per_unit = None

    data = {
        "sku": sku,
        "name": name,
        "category": category,
        "unit_primary": unit_primary,
        "unit_secondary": unit_secondary,
        "sqft_per_unit": sqft_per_unit,
    }

    # enforce rules for BLOCK/TABLE
    if category in ("BLOCK", "TABLE"):
        data["unit_primary"] = "piece"
        data["unit_secondary"] = None
        data["sqft_per_unit"] = None

    # if no secondary unit, sqft_per_unit should be None
    if not data["unit_secondary"]:
        data["sqft_per_unit"] = None

    return data


def import_items_csv(
    db,
    file_path: str,
    mode="upsert",
    batch_size=500,
    progress_cb=None,
    stop_flag=None
):
    """
    progress_cb(percent:int, text:str)
    stop_flag: function that returns True if cancelled
    """

    inserted = 0
    updated = 0
    skipped = 0
    errors = []

    def cancelled():
        return stop_flag() if stop_flag else False

    # read all rows first (to calculate progress %)
    with open(file_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if total == 0:
        return {"inserted": 0, "updated": 0, "skipped": 0, "errors": ["CSV is empty"]}

    # IMPORTANT:
    # upsert_by_sku MUST NOT commit inside. It should only add/update and return "inserted"/"updated".
    # importer will commit in batches.

    for i, row in enumerate(rows, start=1):
        if cancelled():
            break

        try:
            data = _clean_row(row)

            # validation
            if not data["sku"] or not data["name"] or not data["category"]:
                skipped += 1
                continue

            # upsert
            res = upsert_by_sku(db, data)  # returns "inserted" or "updated"
            if res == "inserted":
                inserted += 1
            else:
                updated += 1

            # flush to catch errors early (without committing every row)
            db.flush()

            # batch commit
            if i % batch_size == 0:
                db.commit()

        except Exception as e:
            # rollback only the current failed row changes
            db.rollback()
            errors.append(f"Row {i}: {e}")

        if progress_cb:
            pct = int((i / total) * 100)
            progress_cb(
                pct,
                f"Importing {i}/{total}... Inserted: {inserted} Updated: {updated} Skipped: {skipped}"
            )

    # final commit
    try:
        db.commit()
    except Exception:
        db.rollback()

    if progress_cb:
        progress_cb(100, "Done ✅")

    # if cancelled mid-way, still return progress
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "errors": errors}
