# src/ui/pages/purchases.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import list_locations
from src.db.item_repo import get_items
from src.db.purchase_repo import create_purchase, list_purchases, get_purchase_details
from src.ui.signals import signals
from src.ui.app_state import AppState


class AddPurchaseDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Purchase")
        self.setMinimumWidth(780)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.vendor = QLineEdit()
        self.vendor.setPlaceholderText("Optional vendor name...")

        self.loc_dd = QComboBox()
        self.loc_dd.addItem("—", None)

        with get_db() as db:
            self._locations = list_locations(db)
            for l in self._locations:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}

        form.addRow("Vendor", self.vendor)
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
        self.save_btn = QPushButton("Save Purchase")
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
        vendor = self.vendor.text().strip() or None
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

            if cat in ("SLAB", "TILE"):
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": int(qty_sec.value()),
                    "qty_primary": float(qty_pri.value()),
                })
            else:
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": None,
                    "qty_primary": float(qty_pri.value()),
                })

        if not rows_payload:
            QMessageBox.warning(self, "Missing", "Add at least one valid item line.")
            return

        self._data = {
            "vendor_name": vendor,
            "location_id": location_id,
            "notes": None,
            "rows": rows_payload
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class PurchasesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Purchases")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search vendor...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Purchase")
        self.add_btn.clicked.connect(self.add_purchase)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["ID", "Vendor", "Location", "Created"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        # ✅ View details
        self.table.doubleClicked.connect(self.open_details)

        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)
        self.add_btn.setToolTip("" if can_add else "Viewer role: Adding purchases is disabled.")

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_purchases(db, self.search.text().strip())
            for r, p in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(p.id)))
                self.table.setItem(r, 1, QTableWidgetItem(p.vendor_name or ""))
                self.table.setItem(r, 2, QTableWidgetItem(p.location.name if p.location else ""))
                self.table.setItem(r, 3, QTableWidgetItem(str(getattr(p, "created_at", ""))))

    def add_purchase(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(
                self,
                "Permission",
                "Viewer role: You can only view/export.\n\nPlease login as Admin/Staff."
            )
            return

        dlg = AddPurchaseDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_purchase(db, dlg.data)

                signals.inventory_changed.emit("all")
                self.load_data()
                QMessageBox.information(self, "Saved", "Purchase saved ✅")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save purchase:\n{e}")

    def open_details(self):
        row = self.table.currentRow()
        if row < 0:
            return

        try:
            pid = int(self.table.item(row, 0).text())
        except Exception:
            return

        with get_db() as db:
            p = get_purchase_details(db, pid)

        if not p:
            QMessageBox.warning(self, "Not found", "Purchase not found.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Purchase #{p.id} — Details")
        dlg.setMinimumWidth(950)
        layout = QVBoxLayout(dlg)

        vendor = p.vendor_name or "-"
        loc = p.location.name if p.location else "-"
        created = str(getattr(p, "created_at", ""))
        notes = getattr(p, "notes", None) or "-"

        header = QLabel(
            f"<b>Vendor:</b> {vendor}<br>"
            f"<b>Location:</b> {loc}<br>"
            f"<b>Created:</b> {created}<br>"
            f"<b>Notes:</b> {notes}"
        )
        header.setTextFormat(Qt.RichText)
        layout.addWidget(header)

        lines = QTableWidget(0, 7)
        lines.setHorizontalHeaderLabels(
            ["SKU", "Name", "Category", "Primary Qty", "Primary Unit", "Secondary Qty", "Secondary Unit"]
        )
        lines.horizontalHeader().setStretchLastSection(True)

        items = getattr(p, "items", []) or []
        for r, li in enumerate(items):
            it = getattr(li, "item", None)
            sku = getattr(it, "sku", "") if it else ""
            name = getattr(it, "name", "") if it else ""
            cat = getattr(it, "category", "") if it else ""

            lines.insertRow(r)
            lines.setItem(r, 0, QTableWidgetItem(sku or ""))
            lines.setItem(r, 1, QTableWidgetItem(name or ""))
            lines.setItem(r, 2, QTableWidgetItem(cat or ""))

            pri = float(getattr(li, "qty_primary", 0) or 0)
            lines.setItem(r, 3, QTableWidgetItem(f"{pri:.3f}"))
            lines.setItem(r, 4, QTableWidgetItem(getattr(li, "unit_primary", "") or ""))

            sec_qty = getattr(li, "qty_secondary", None)
            lines.setItem(r, 5, QTableWidgetItem("" if sec_qty is None else str(int(sec_qty))))
            lines.setItem(r, 6, QTableWidgetItem(getattr(li, "unit_secondary", "") or ""))

        layout.addWidget(lines)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignRight)

        dlg.exec()
