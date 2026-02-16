# src/ui/utils/invoice_pdf.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

def _fmt_dt(v: Any) -> str:
    if not v:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return str(v)

def _safe(v: Any) -> str:
    return "" if v is None else str(v)

def _num(v: Any, decimals: int = 3) -> str:
    try:
        return f"{float(v):.{decimals}f}"
    except Exception:
        return _safe(v)

def ensure_reportlab_or_raise():
    try:
        import reportlab  # noqa: F401
    except Exception as e:
        raise RuntimeError(
            "PDF failed: reportlab missing.\n\nRun:\n"
            "pip install reportlab\n"
        ) from e

def build_invoice_pdf(
    *,
    file_path: str,
    title: str,
    company_name: str,
    meta_lines: list[str],
    table_headers: list[str],
    table_rows: list[list[str]],
    footer_lines: list[str] | None = None,
):
    """
    Generic PDF invoice renderer (works for Sale/Purchase).
    """
    ensure_reportlab_or_raise()

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=22,
        bottomMargin=22,
        title=title,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(f"<b>{company_name}</b>", styles["Title"]))
    story.append(Paragraph(f"<b>{title}</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    for line in meta_lines:
        if line:
            story.append(Paragraph(line, styles["BodyText"]))
    story.append(Spacer(1, 12))

    data = [table_headers] + table_rows
    tbl = Table(data, hAlign="LEFT")

    tbl_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f2f2f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),

        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),

        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#444444")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f3f3f3"), colors.white]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
    tbl.setStyle(tbl_style)

    story.append(tbl)
    story.append(Spacer(1, 14))

    if footer_lines:
        for line in footer_lines:
            if line:
                story.append(Paragraph(line, styles["BodyText"]))

    doc.build(story)

def make_sale_invoice_pdf(
    *,
    sale_obj,
    file_path: str,
    company_name: str = "Marble Inventory",
):
    """
    sale_obj: Sale model with .items loaded and each item has .item relation
    """
    customer = _safe(getattr(sale_obj, "customer_name", ""))
    location = ""
    if getattr(sale_obj, "location", None):
        location = _safe(getattr(sale_obj.location, "name", ""))

    created = _fmt_dt(getattr(sale_obj, "created_at", "")) or ""
    notes = _safe(getattr(sale_obj, "notes", ""))

    meta = [
        f"<b>Invoice:</b> Sale #{sale_obj.id}",
        f"<b>Customer:</b> {customer}",
        f"<b>Location:</b> {location}",
        f"<b>Date:</b> {created}",
    ]
    if notes:
        meta.append(f"<b>Notes:</b> {notes}")

    headers = ["SKU", "Item", "Category", "Qty Primary", "Unit P", "Qty Secondary", "Unit S"]

    rows = []
    total_primary = 0.0
    total_secondary = 0

    for line in getattr(sale_obj, "items", []) or []:
        it = getattr(line, "item", None)
        sku = _safe(getattr(it, "sku", ""))
        name = _safe(getattr(it, "name", ""))
        cat = _safe(getattr(it, "category", ""))

        qp = getattr(line, "qty_primary", 0) or 0
        qs = getattr(line, "qty_secondary", None)

        up = _safe(getattr(line, "unit_primary", "")) or _safe(getattr(it, "unit_primary", ""))
        us = _safe(getattr(line, "unit_secondary", "")) or _safe(getattr(it, "unit_secondary", ""))

        rows.append([
            sku,
            name,
            cat,
            _num(qp),
            up,
            "" if qs is None else str(int(qs)),
            us,
        ])

        try:
            total_primary += float(qp or 0)
        except Exception:
            pass
        if qs is not None:
            try:
                total_secondary += int(qs or 0)
            except Exception:
                pass

    rows.append(["", "", "TOTAL", _num(total_primary), "", str(total_secondary) if total_secondary else "", ""])

    build_invoice_pdf(
        file_path=file_path,
        title="Sales Invoice",
        company_name=company_name,
        meta_lines=meta,
        table_headers=headers,
        table_rows=rows,
        footer_lines=["<i>Generated by Marble Inventory</i>"],
    )

def make_purchase_invoice_pdf(
    *,
    purchase_obj,
    file_path: str,
    company_name: str = "Marble Inventory",
):
    """
    purchase_obj: Purchase model with .items loaded and each item has .item relation
    """
    vendor = _safe(getattr(purchase_obj, "vendor_name", ""))
    location = ""
    if getattr(purchase_obj, "location", None):
        location = _safe(getattr(purchase_obj.location, "name", ""))

    created = _fmt_dt(getattr(purchase_obj, "created_at", "")) or ""
    notes = _safe(getattr(purchase_obj, "notes", ""))

    meta = [
        f"<b>Invoice:</b> Purchase #{purchase_obj.id}",
        f"<b>Vendor:</b> {vendor}",
        f"<b>Location:</b> {location}",
        f"<b>Date:</b> {created}",
    ]
    if notes:
        meta.append(f"<b>Notes:</b> {notes}")

    headers = ["SKU", "Item", "Category", "Qty Primary", "Unit P", "Qty Secondary", "Unit S"]

    rows = []
    total_primary = 0.0
    total_secondary = 0

    for line in getattr(purchase_obj, "items", []) or []:
        it = getattr(line, "item", None)
        sku = _safe(getattr(it, "sku", ""))
        name = _safe(getattr(it, "name", ""))
        cat = _safe(getattr(it, "category", ""))

        qp = getattr(line, "qty_primary", 0) or 0
        qs = getattr(line, "qty_secondary", None)

        up = _safe(getattr(line, "unit_primary", "")) or _safe(getattr(it, "unit_primary", ""))
        us = _safe(getattr(line, "unit_secondary", "")) or _safe(getattr(it, "unit_secondary", ""))

        rows.append([
            sku,
            name,
            cat,
            _num(qp),
            up,
            "" if qs is None else str(int(qs)),
            us,
        ])

        try:
            total_primary += float(qp or 0)
        except Exception:
            pass
        if qs is not None:
            try:
                total_secondary += int(qs or 0)
            except Exception:
                pass

    rows.append(["", "", "TOTAL", _num(total_primary), "", str(total_secondary) if total_secondary else "", ""])

    build_invoice_pdf(
        file_path=file_path,
        title="Purchase Invoice",
        company_name=company_name,
        meta_lines=meta,
        table_headers=headers,
        table_rows=rows,
        footer_lines=["<i>Generated by Marble Inventory</i>"],
    )
