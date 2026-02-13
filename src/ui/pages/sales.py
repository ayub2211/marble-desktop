# src/ui/pages/sales.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations   # ✅ correct import
from src.db.item_repo import get_items
from src.db.sales_repo import create_sale, list_sales
from src.ui.signals import signals


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
            self._locations = get_locations(db)  # ✅ fixed (was list_locations)
            for l in self._locations:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}

        form.addRow("Customer", self.customer)
        form.addRow("Location", self.loc_dd)
        layout.addLayout(form)

        # rows table
        self.rows = QTableWidget(0, 5)
        self.rows.setHorizontalHeaderLabels([
            "Item", "Category", "Qty Secondary (slab/box)", "Qty Primary (sqft/piece)", ""
        ])
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

        # ✅ keep one recalc handler only (prevent multi-connect issue)
        def recalc_sqft_for_item(it):
            if it and it.sqft_per_unit:
                try:
                    qty_pri.setValue(float(it.sqft_per_unit) * float(qty_sec.value()))
                except Exception:
                    pass

        def on_item_change():
            item_id = item_dd.currentData()
            it = self._items_by_id.get(item_id)

            # reset
            try:
                qty_sec.valueChanged.disconnect()
            except Exception:
                pass

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

                qty_sec.valueChanged.connect(lambda: recalc_sqft_for_item(it))
                recalc_sqft_for_item(it)

            else:
                qty_sec.setValue(0)
                qty_sec.setEnabled(False)
                qty_pri.setEnabled(True)

        def remove_row():
            # ✅ remove correct row (not the old captured index)
            row = self.rows.indexAt(del_btn.parentWidget().pos()).row()
            if row >= 0:
                self.rows.removeRow(row)

        item_dd.currentIndexChanged.connect(on_item_change)
        del_btn.clicked.connect(remove_row)

    def on_save(self):
        customer = self.customer.text().strip() or None
        location_id = self.loc_dd.currentData()

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
            "customer_name": customer,
            "location_id": location_id,
            "notes": None,
            "rows": rows_payload
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


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
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_sales(db, self.search.text().strip())
            for r, s in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(s.id)))
                self.table.setItem(r, 1, QTableWidgetItem(s.customer_name or ""))
                self.table.setItem(r, 2, QTableWidgetItem(s.location.name if s.location else ""))
                self.table.setItem(r, 3, QTableWidgetItem(str(getattr(s, "created_at", ""))))

    def add_sale(self):
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
