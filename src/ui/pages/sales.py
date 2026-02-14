# src/ui/pages/sales.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations as list_locations
from src.db.item_repo import get_items
from src.db.sales_repo import create_sale, list_sales, get_sale_details
from src.ui.signals import signals
from src.ui.app_state import AppState


class SaleDetailsDialog(QDialog):
    def __init__(self, parent=None, sale_id: int | None = None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.setWindowTitle(f"Sale Details #{sale_id}")
        self.setMinimumWidth(900)
        self.setMinimumHeight(420)

        layout = QVBoxLayout(self)

        self.meta = QLabel("")
        self.meta.setStyleSheet("font-size:13px;")
        layout.addWidget(self.meta)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "SKU", "Name", "Category",
            "Qty Primary", "Unit P",
            "Qty Secondary", "Unit S"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.load()

    def load(self):
        with get_db() as db:
            s = get_sale_details(db, int(self.sale_id))

        if not s:
            self.meta.setText("Not found.")
            return

        customer = s.customer_name or ""
        loc = s.location.name if s.location else ""
        created = str(getattr(s, "created_at", "") or "")
        notes = getattr(s, "notes", "") or ""

        self.meta.setText(
            f"<b>Customer:</b> {customer} &nbsp;&nbsp; "
            f"<b>Location:</b> {loc} &nbsp;&nbsp; "
            f"<b>Created:</b> {created} &nbsp;&nbsp; "
            f"<b>Notes:</b> {notes}"
        )

        self.table.setRowCount(0)
        items = list(getattr(s, "items", []) or [])
        for r, ln in enumerate(items):
            it = ln.item
            sku = it.sku if it else ""
            name = it.name if it else ""
            cat = (it.category if it else "") or ""

            qp = float(ln.qty_primary or 0)
            up = (ln.unit_primary or (it.unit_primary if it else "") or "")
            qs = "" if ln.qty_secondary is None else str(int(ln.qty_secondary or 0))
            us = (ln.unit_secondary or (it.unit_secondary if it else "") or "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(sku))
            self.table.setItem(r, 1, QTableWidgetItem(name))
            self.table.setItem(r, 2, QTableWidgetItem(cat))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qp:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(up))
            self.table.setItem(r, 5, QTableWidgetItem(qs))
            self.table.setItem(r, 6, QTableWidgetItem(us))


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

                # avoid stacking signals too much: disconnect safe
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
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": sec,
                    "qty_primary": pri,
                })
            else:
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": None,
                    "qty_primary": pri,
                })

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

        # ✅ View Details on double click
        self.table.cellDoubleClicked.connect(self.open_details)

        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)
        self.add_btn.setToolTip("" if can_add else "Viewer role: Add Sale disabled")

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_sales(db, self.search.text().strip(), limit=300)

        for r, s in enumerate(rows):
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(s.id)))
            self.table.setItem(r, 1, QTableWidgetItem(s.customer_name or ""))
            self.table.setItem(r, 2, QTableWidgetItem(s.location.name if s.location else ""))
            self.table.setItem(r, 3, QTableWidgetItem(str(getattr(s, "created_at", ""))))

    def selected_sale_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        try:
            return int(self.table.item(row, 0).text())
        except Exception:
            return None

    def open_details(self):
        sale_id = self.selected_sale_id()
        if not sale_id:
            return
        dlg = SaleDetailsDialog(self, sale_id=sale_id)
        dlg.exec()

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
