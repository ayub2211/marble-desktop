# Marble Inventory Desktop App

A desktop-based inventory management system for marble businesses.  
Built with **Python (PySide6)** and **PostgreSQL**.

---

## Features
- Product master (Slabs, Tiles, Blocks, Tables)
- Dual unit handling (sqft + slab / box)
- Category-wise inventory
- Soft delete (safe records)
- PostgreSQL database backend
- Clean modular architecture

---

## Modules
- Dashboard (quick overview & alerts)
- Items / Products master
- Slabs inventory (sqft + slab count)
- Tiles inventory
- Blocks inventory
- Tables inventory

---

## Database
- PostgreSQL
- SQLAlchemy ORM
- Soft delete supported (`is_active` flag)

**Items table includes:**
- SKU
- Name
- Category
- Primary unit (sqft)
- Secondary unit (slab / box)

---

## Environment Variables

Create a `.env` file (use `.env.example` as reference):

```env
DATABASE_URL=postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/marble_db
