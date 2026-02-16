# src/ui/pages/sales.py
from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPdfWriter, QPainter, QFont, QPageSize

from src.db.session import get_db
from src.db.location_repo import get_locations as list_locations
from src.db.item_repo import get_items
from src.db.sales_repo import create_sale, list_sales, get_sale_details, cancel_sale
from src.ui.signals import signals
from src.ui.app_state import AppState


# -------------------- PDF (Qt Native) --------------------
def _fmt_dt(v) -> str:
    if not v:
        return ""
    return str(v)


def export_sale_pdf(parent, sale_obj, out_path: str):
    """
    Qt-native PDF export (auto-fit columns + no cutting).
    """
    writer = QPdfWriter(out_path)
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setTitle(f"Sale Invoice #{sale_obj.id}")

    p = QPainter(writer)
    try:
        page_w = writer.width()
        page_h = writer.height()
        margin = 650
        x = margin
        y = margin

        def set_font(size=12, bold=False):
            f = QFont("Arial", size)
            f.setBold(bold)
            p.setFont(f)

        def draw_text(tx, ty, text):
            p.drawText(tx, ty, text)

        # ---- Header ----
        set_font(18, True)
        draw_text(x, y, "Marble Inventory")
        set_font(12, False)
        y += 420
        draw_text(x, y, "Sales Invoice")

        # right meta
        set_font(10, False)
        right_x = page_w - margin - 3200
        draw_text(right_x, y - 200, f"Invoice #: {sale_obj.id}")
        draw_text(right_x, y + 250, f"Date: {_fmt_dt(getattr(sale_obj, 'created_at', ''))}")

        y += 650

        # Party + location + notes
        set_font(11, True)
        draw_text(x, y, f"Customer: {sale_obj.customer_name or ''}")
        y += 320
        set_font(11, False)
        draw_text(x, y, f"Location: {sale_obj.location.name if sale_obj.location else ''}")
        y += 320
        notes = getattr(sale_obj, "notes", None) or ""
        draw_text(x, y, f"Notes: {notes}")
        y += 550

        # ---- Table ----
        # IMPORTANT: widths are now "relative weights" (auto-fit to page width)
        cols = [
            ("SKU", 12),
            ("Item", 38),
            ("Cat", 12),
            ("Qty P", 10),
            ("Unit P", 8),
            ("Qty S", 10),
            ("Unit S", 10),
        ]

        available_w = page_w - (2 * margin)
        total_weight = sum(w for _, w in cols)
        col_widths = [int(available_w * (w / total_weight)) for _, w in cols]

        row_h = 420
        header_h = 430

        def draw_row(row_y, values, is_header=False):
            cx = x
            if is_header:
                set_font(10, True)
            else:
                set_font(10, False)

            for i, val in enumerate(values):
                w = col_widths[i]
                p.drawRect(cx, row_y, w, row_h)

                # text padding
                pad = 120
                text_rect_x = cx + pad
                text_rect_y = row_y + 70
                text_rect_w = max(50, w - (2 * pad))
                text_rect_h = row_h - 140

                # Elide long text (prevents cutting)
                txt = str(val)
                fm = p.fontMetrics()
                txt = fm.elidedText(txt, Qt.ElideRight, text_rect_w)

                p.drawText(text_rect_x, row_y + 280, txt)

                cx += w

        # header
        draw_row(y, [c[0] for c in cols], is_header=True)
        y += row_h

        total_primary = 0.0
        total_secondary = 0

        items = list(getattr(sale_obj, "items", []) or [])
        for it in items:
            sku = it.item.sku if it.item else ""
            name = it.item.name if it.item else ""
            cat = (it.item.category or "") if it.item else ""
            qty_p = float(it.qty_primary or 0)
            unit_p = it.unit_primary or ""
            qty_s = "" if it.qty_secondary is None else str(int(it.qty_secondary or 0))
            unit_s = it.unit_secondary or ""

            total_primary += qty_p
            if it.qty_secondary is not None:
                total_secondary += int(it.qty_secondary or 0)

            draw_row(
                y,
                [sku, name, cat, f"{qty_p:.3f}", unit_p, qty_s, unit_s],
                is_header=False
            )
            y += row_h

            # page break
            if y > page_h - margin - 1200:
                writer.newPage()
                y = margin
                draw_row(y, [c[0] for c in cols], is_header=True)
                y += row_h

        # totals
        y += 500
        set_font(11, True)
        draw_text(x, y, f"Total Primary: {total_primary:.3f}")
        y += 320
        draw_text(x, y, f"Total Secondary: {total_secondary}")

    finally:
        p.end()



# -------------------- UI --------------------
class AddSaleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Sale")
        self.setMinimumWidth(780)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.customer = QLineEdit()
        self.customer.setPlaceholderText("Optional customer name...")

        self.loc_dd = QComboBox()
        self.loc_dd.addItem("—", None)

        with get_db() as db:
            self._locations = list_locations(db)
            for l in self._locations:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}

        form.addRow("Customer", self.customer)
        form.addRow("Location", self.loc_dd)
        layout.addLayout(form)

        self.rows = QTableWidget(0, 5)
        self.rows.setHorizontalHeaderLabels(
            ["Item", "Category", "Qty Secondary (slab/box)", "Qty Primary (sqft/piece)", ""]
        )
        self.rows.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.rows)

        btn_row = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Add Line")
        self.save_btn = QPushButton("Save Sale")
        btn_row.addWidget(self.add_row_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.add_row_btn.clicked.connect(self.add_line)
        self.save_btn.clicked.connect(self.on_save)

        self.add_line()

    def add_line(self):
        r = self.rows.rowCount()
        self.rows.insertRow(r)

        item_dd = QComboBox()
        item_dd.addItem("Select item...", None)
        for it in self._items:
            item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        cat_lbl = QLabel("—")

        qty_sec = QSpinBox()
        qty_sec.setRange(0, 10_000_000)

        qty_pri = QDoubleSpinBox()
        qty_pri.setRange(0, 999_999_999)
        qty_pri.setDecimals(3)

        del_btn = QPushButton("Remove")

        self.rows.setCellWidget(r, 0, item_dd)
        self.rows.setCellWidget(r, 1, cat_lbl)
        self.rows.setCellWidget(r, 2, qty_sec)
        self.rows.setCellWidget(r, 3, qty_pri)
        self.rows.setCellWidget(r, 4, del_btn)

        def on_item_change():
            item_id = item_dd.currentData()
            it = self._items_by_id.get(item_id)
            if not it:
                cat_lbl.setText("—")
                qty_sec.setEnabled(True)
                qty_pri.setEnabled(True)
                return

            cat = (it.category or "").upper()
            cat_lbl.setText(cat)

            if cat in ("SLAB", "TILE"):
                qty_sec.setEnabled(True)
                qty_pri.setEnabled(True)

                def recalc():
                    if it.sqft_per_unit:
                        try:
                            qty_pri.setValue(float(it.sqft_per_unit) * float(qty_sec.value()))
                        except Exception:
                            pass

                try:
                    qty_sec.valueChanged.disconnect()
                except Exception:
                    pass
                qty_sec.valueChanged.connect(recalc)
                recalc()
            else:
                qty_sec.setValue(0)
                qty_sec.setEnabled(False)
                qty_pri.setEnabled(True)

        def remove_row():
            row_to_remove = self.rows.indexAt(del_btn.pos()).row()
            if row_to_remove >= 0:
                self.rows.removeRow(row_to_remove)

        item_dd.currentIndexChanged.connect(on_item_change)
        del_btn.clicked.connect(remove_row)

    def on_save(self):
        customer = self.customer.text().strip() or None
        location_id = self.loc_dd.currentData()

        if not location_id:
            QMessageBox.warning(self, "Missing", "Location is required.")
            return

        rows_payload = []
        for r in range(self.rows.rowCount()):
            item_dd = self.rows.cellWidget(r, 0)
            qty_sec = self.rows.cellWidget(r, 2)
            qty_pri = self.rows.cellWidget(r, 3)

            item_id = item_dd.currentData() if item_dd else None
            if not item_id:
                continue

            it = self._items_by_id.get(item_id)
            if not it:
                continue

            cat = (it.category or "").upper()
            pri = float(qty_pri.value())

            if pri <= 0:
                continue

            if cat in ("SLAB", "TILE"):
                sec = int(qty_sec.value())
                if sec <= 0:
                    continue
                rows_payload.append({"item_id": item_id, "qty_secondary": sec, "qty_primary": pri})
            else:
                rows_payload.append({"item_id": item_id, "qty_secondary": None, "qty_primary": pri})

        if not rows_payload:
            QMessageBox.warning(self, "Missing", "Add at least one valid item line (qty > 0).")
            return

        self._data = {
            "customer_name": customer,
            "location_id": location_id,
            "notes": None,
            "rows": rows_payload
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class SaleDetailsDialog(QDialog):
    def __init__(self, parent, sale_id: int):
        super().__init__(parent)
        self.sale_id = int(sale_id)
        self.setWindowTitle(f"Sale #{self.sale_id} — Details")
        self.setMinimumWidth(920)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)

        with get_db() as db:
            self.sale = get_sale_details(db, self.sale_id)

        if not self.sale:
            QMessageBox.warning(self, "Not found", "Sale not found.")
            self.reject()
            return

        header = QLabel(
            f"<b>Customer:</b> {self.sale.customer_name or ''} &nbsp;&nbsp; "
            f"<b>Location:</b> {(self.sale.location.name if self.sale.location else '')} &nbsp;&nbsp; "
            f"<b>Created:</b> {_fmt_dt(getattr(self.sale, 'created_at', ''))} &nbsp;&nbsp; "
            f"<b>Notes:</b> {getattr(self.sale, 'notes', '') or ''}"
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["SKU", "Item", "Category", "Qty Primary", "Unit P", "Qty Secondary", "Unit S"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        self._fill()

        btns = QHBoxLayout()
        self.pdf_btn = QPushButton("Save PDF")
        self.cancel_btn = QPushButton("Cancel Transaction")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.pdf_btn)
        btns.addWidget(self.cancel_btn)
        btns.addStretch()
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)

        self.close_btn.clicked.connect(self.reject)
        self.pdf_btn.clicked.connect(self.save_pdf)
        self.cancel_btn.clicked.connect(self.cancel_txn)

        # permissions
        if not AppState.can_add_transactions():
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.setToolTip("Viewer role: Cancel disabled")

    def _fill(self):
        items = list(getattr(self.sale, "items", []) or [])
        self.table.setRowCount(0)
        for r, it in enumerate(items):
            self.table.insertRow(r)
            sku = it.item.sku if it.item else ""
            name = it.item.name if it.item else ""
            cat = (it.item.category or "") if it.item else ""
            qty_p = float(it.qty_primary or 0)
            unit_p = it.unit_primary or ""
            qty_s = "" if it.qty_secondary is None else str(int(it.qty_secondary or 0))
            unit_s = it.unit_secondary or ""

            self.table.setItem(r, 0, QTableWidgetItem(sku))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qty_p:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(unit_p))
            self.table.setItem(r, 5, QTableWidgetItem(qty_s))
            self.table.setItem(r, 6, QTableWidgetItem(unit_s))

    def save_pdf(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Sale Invoice PDF", f"sale_{self.sale_id}.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return
        try:
            export_sale_pdf(self, self.sale, path)
            QMessageBox.information(self, "Saved", f"PDF saved:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"PDF failed:\n{e}")

    def cancel_txn(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(self, "Not allowed", "Viewer role: you can only view/export.")
            return

        confirm = QMessageBox.question(
            self,
            "Cancel Sale",
            "This will reverse stock using a cancellation entry.\n\nContinue?",
            QMessageBox.Yes | QMessageBox.No
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            with get_db() as db:
                cancel_sale(db, self.sale_id)

            signals.inventory_changed.emit("all")
            QMessageBox.information(self, "Done", "Sale cancelled (reversed) ✅")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Cancel failed:\n{e}")


class SalesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Sales")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search customer...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Sale")
        self.add_btn.clicked.connect(self.add_sale)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Customer", "Location", "Created"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self.open_details)
        layout.addWidget(self.table)

        self._rows = []
        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)
        self.add_btn.setToolTip("" if can_add else "Viewer role: Add Sale disabled")

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_sales(db, self.search.text().strip())
        self._rows = rows

        for r, s in enumerate(rows):
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(s.id)))
            self.table.setItem(r, 1, QTableWidgetItem(s.customer_name or ""))
            self.table.setItem(r, 2, QTableWidgetItem(s.location.name if s.location else ""))
            self.table.setItem(r, 3, QTableWidgetItem(str(getattr(s, "created_at", ""))))

    def open_details(self, row, col):
        if row < 0 or row >= len(self._rows):
            return
        s = self._rows[row]
        SaleDetailsDialog(self, int(s.id)).exec()

    def add_sale(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(
                self, "Not allowed",
                "Viewer role can only view/export.\n\nPlease login as Admin/Staff."
            )
            return

        dlg = AddSaleDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_sale(db, dlg.data)

                signals.inventory_changed.emit("all")
                self.load_data()
                QMessageBox.information(self, "Saved", "Sale saved ✅")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save sale:\n{e}")
