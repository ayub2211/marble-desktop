# src/ui/pages/returns.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QMessageBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import list_locations
from src.db.item_repo import get_items
from src.db.returns_repo import (
    create_return,
    list_sale_returns, list_purchase_returns,
    get_sale_return_details, get_purchase_return_details,
    cancel_sale_return, cancel_purchase_return,
)
from src.ui.signals import signals
from src.ui.app_state import AppState


def _get(obj, key, default=None):
    # supports ORM + dict mixed
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class AddReturnDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Return")
        self.setMinimumWidth(820)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.return_type = QComboBox()
        self.return_type.addItems(["SALE_RETURN", "PURCHASE_RETURN"])

        self.party = QLineEdit()
        self.party.setPlaceholderText("Customer/Vendor (optional)...")

        self.loc_dd = QComboBox()
        self.loc_dd.addItem("—", None)

        with get_db() as db:
            self._locations = list_locations(db)
            for l in self._locations:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}

        form.addRow("Return Type", self.return_type)
        form.addRow("Customer/Vendor", self.party)
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
        self.save_btn = QPushButton("Save Return")
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
        return_type = self.return_type.currentText()
        party = self.party.text().strip() or None
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
                rows_payload.append({"item_id": item_id, "qty_secondary": int(qty_sec.value()), "qty_primary": float(qty_pri.value())})
            else:
                rows_payload.append({"item_id": item_id, "qty_secondary": None, "qty_primary": float(qty_pri.value())})

        if not rows_payload:
            QMessageBox.warning(self, "Missing", "Add at least one valid item line.")
            return

        self._data = {
            "return_type": return_type,
            "party_name": party,
            "location_id": location_id,
            "notes": None,
            "rows": rows_payload
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class ReturnDetailsDialog(QDialog):
    def __init__(self, parent, return_type: str, return_id: int):
        super().__init__(parent)
        self.return_type = (return_type or "").upper()
        self.return_id = int(return_id)

        self.setWindowTitle(f"Return Details — {self.return_type} #{self.return_id}")
        self.setMinimumWidth(940)
        self.setMinimumHeight(520)

        layout = QVBoxLayout(self)

        self.header = QLabel("")
        self.header.setStyleSheet("font-size:13px;font-weight:700;")
        layout.addWidget(self.header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["SKU", "Item", "Category", "Qty Primary", "Unit P", "Qty Secondary", "Unit S"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        btns = QHBoxLayout()
        self.cancel_btn = QPushButton("Cancel Transaction")
        self.close_btn = QPushButton("Close")
        btns.addWidget(self.cancel_btn)
        btns.addStretch()
        btns.addWidget(self.close_btn)
        layout.addLayout(btns)

        self.close_btn.clicked.connect(self.reject)
        self.cancel_btn.clicked.connect(self.cancel_txn)

        self.cancel_btn.setEnabled(AppState.can_add_transactions())
        self._ret = None
        self.load()

    def load(self):
        with get_db() as db:
            if self.return_type == "SALE_RETURN":
                ret = get_sale_return_details(db, self.return_id)
                party = _get(ret, "customer_name", "")
            else:
                ret = get_purchase_return_details(db, self.return_id)
                party = _get(ret, "vendor_name", "")

        if not ret:
            QMessageBox.warning(self, "Missing", "Return not found.")
            self.reject()
            return

        self._ret = ret
        loc = _get(ret, "location", None)
        self.header.setText(
            f"Type: {self.return_type}    "
            f"Party: {party or ''}    "
            f"Location: {(loc.name if loc else '')}    "
            f"Created: {_get(ret, 'created_at', '')}    "
            f"Notes: {_get(ret, 'notes', '') or ''}"
        )

        self.table.setRowCount(0)
        for r, li in enumerate(_get(ret, "items", []) or []):
            it = _get(li, "item", None)
            sku = _get(it, "sku", "")
            name = _get(it, "name", "")
            cat = (_get(it, "category", "") or "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(sku)))
            self.table.setItem(r, 1, QTableWidgetItem(str(name)))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{float(_get(li,'qty_primary',0) or 0):.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(_get(li,'unit_primary','') or "")))
            self.table.setItem(r, 5, QTableWidgetItem("" if _get(li,'qty_secondary',None) is None else str(int(_get(li,'qty_secondary',0) or 0))))
            self.table.setItem(r, 6, QTableWidgetItem(str(_get(li,'unit_secondary','') or "")))

    def cancel_txn(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(self, "Permission", "Viewer cannot cancel.")
            return

        ok = QMessageBox.question(self, "Confirm", "Cancel this Return? Stock will be reversed.") == QMessageBox.Yes
        if not ok:
            return

        try:
            with get_db() as db:
                if self.return_type == "SALE_RETURN":
                    cancel_sale_return(db, self.return_id, reason="UI Cancel")
                else:
                    cancel_purchase_return(db, self.return_id, reason="UI Cancel")

            signals.inventory_changed.emit("all")
            QMessageBox.information(self, "Done", "Return cancelled ✅")
            self.load()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class ReturnsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Returns")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search party (customer/vendor)...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Return")
        self.add_btn.clicked.connect(self.add_return)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # Sale Returns
        self.sale_table = QTableWidget(0, 5)
        self.sale_table.setHorizontalHeaderLabels(["ID", "Party", "Location", "Created", "Ref"])
        self.sale_table.setColumnHidden(0, True)
        self.sale_table.horizontalHeader().setStretchLastSection(True)
        self.sale_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sale_table.customContextMenuRequested.connect(lambda pos: self.open_menu(self.sale_table, "SALE_RETURN", pos))
        self.sale_table.cellDoubleClicked.connect(lambda *_: self.open_details("SALE_RETURN"))
        self.tabs.addTab(self.sale_table, "Sale Returns")

        # Purchase Returns
        self.pur_table = QTableWidget(0, 5)
        self.pur_table.setHorizontalHeaderLabels(["ID", "Party", "Location", "Created", "Ref"])
        self.pur_table.setColumnHidden(0, True)
        self.pur_table.horizontalHeader().setStretchLastSection(True)
        self.pur_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pur_table.customContextMenuRequested.connect(lambda pos: self.open_menu(self.pur_table, "PURCHASE_RETURN", pos))
        self.pur_table.cellDoubleClicked.connect(lambda *_: self.open_details("PURCHASE_RETURN"))
        self.tabs.addTab(self.pur_table, "Purchase Returns")

        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)
        self.add_btn.setToolTip("" if can_add else "Viewer role: Adding returns is disabled.")

    def load_data(self):
        q = self.search.text().strip()

        self.sale_table.setRowCount(0)
        self.pur_table.setRowCount(0)

        with get_db() as db:
            sale_rows = list_sale_returns(db, q_text=q) or []
            pur_rows = list_purchase_returns(db, q_text=q) or []

        for r, ret in enumerate(sale_rows):
            self.sale_table.insertRow(r)
            self.sale_table.setItem(r, 0, QTableWidgetItem(str(_get(ret, "id", ""))))
            self.sale_table.setItem(r, 1, QTableWidgetItem(str(_get(ret, "customer_name", "") or "")))
            loc = _get(ret, "location", None)
            self.sale_table.setItem(r, 2, QTableWidgetItem(loc.name if loc else ""))
            self.sale_table.setItem(r, 3, QTableWidgetItem(str(_get(ret, "created_at", "") or "")))
            self.sale_table.setItem(r, 4, QTableWidgetItem(f"sale_return#{_get(ret,'id','')}"))

        for r, ret in enumerate(pur_rows):
            self.pur_table.insertRow(r)
            self.pur_table.setItem(r, 0, QTableWidgetItem(str(_get(ret, "id", ""))))
            self.pur_table.setItem(r, 1, QTableWidgetItem(str(_get(ret, "vendor_name", "") or "")))
            loc = _get(ret, "location", None)
            self.pur_table.setItem(r, 2, QTableWidgetItem(loc.name if loc else ""))
            self.pur_table.setItem(r, 3, QTableWidgetItem(str(_get(ret, "created_at", "") or "")))
            self.pur_table.setItem(r, 4, QTableWidgetItem(f"purchase_return#{_get(ret,'id','')}"))

    def selected_id(self, table: QTableWidget):
        row = table.currentRow()
        if row < 0:
            return None
        return int(table.item(row, 0).text())

    def open_details(self, return_type: str):
        table = self.sale_table if return_type == "SALE_RETURN" else self.pur_table
        rid = self.selected_id(table)
        if not rid:
            return
        dlg = ReturnDetailsDialog(self, return_type, rid)
        dlg.exec()

    def open_menu(self, table: QTableWidget, return_type: str, pos):
        rid = self.selected_id(table)
        if not rid:
            return

        menu = QMenu(self)
        view = menu.addAction("View Details")

        cancel_action = None
        if AppState.can_add_transactions():
            cancel_action = menu.addAction("Cancel Transaction")

        action = menu.exec(table.mapToGlobal(pos))
        if action == view:
            self.open_details(return_type)
        elif cancel_action and action == cancel_action:
            dlg = ReturnDetailsDialog(self, return_type, rid)
            dlg.cancel_txn()

    def add_return(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(self, "Permission", "Viewer role: You can only view/export.")
            return

        dlg = AddReturnDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_return(db, dlg.data)

                signals.inventory_changed.emit("all")
                self.load_data()
                QMessageBox.information(self, "Saved", "Return saved ✅")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save return:\n{e}")
