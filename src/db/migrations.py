# src/db/migrations.py
from sqlalchemy import inspect, text

def ensure_items_extra_columns(engine):
    """
    Safe migration:
    - Adds nullable columns if missing
    - Won't break existing data
    Works for SQLite/Postgres/MySQL (basic ALTER TABLE ADD COLUMN)
    """
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("items")}

    alters = []
    if "material" not in cols:
        alters.append("ALTER TABLE items ADD COLUMN material VARCHAR(50)")
    if "thickness" not in cols:
        alters.append("ALTER TABLE items ADD COLUMN thickness VARCHAR(20)")
    if "finish" not in cols:
        alters.append("ALTER TABLE items ADD COLUMN finish VARCHAR(30)")

    if not alters:
        return

    with engine.begin() as conn:
        for sql in alters:
            conn.execute(text(sql))
