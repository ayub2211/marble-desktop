# src/ui/pages/returns.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QMessageBox,
    QComboBox, QSpinBox, QDoubleSpinBox, QTabWidget
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations as list_locations
from src.db.item_repo import get_items
from src.db.returns_repo import (
    create_return,
    list_returns,
    get_sale_return_details,
    get_purchase_return_details
)
from src.ui.signals import signals
from src.ui.app_state import AppState


# ---------- helpers (dict + ORM safe) ----------
def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_location_name(ret):
    # dict forms: location_name OR location (nested) OR location_id only
    if isinstance(ret, dict):
        if ret.get("location_name"):
            return ret.get("location_name") or ""
        loc = ret.get("location")
        if isinstance(loc, dict):
            return loc.get("name") or ""
        return ""
    # ORM form
    loc = getattr(ret, "location", None)
    return (loc.name if loc else "") or ""


def _get_party(ret, rtype: str):
    # dict can have party_name, customer_name, vendor_name
    if isinstance(ret, dict):
        if ret.get("party_name"):
            return ret.get("party_name") or ""
        if rtype == "SALE_RETURN":
            return ret.get("customer_name") or ""
        return ret.get("vendor_name") or ""
    # ORM
    if rtype == "SALE_RETURN":
        return getattr(ret, "customer_name", "") or getattr(ret, "party_name", "") or ""
    return getattr(ret, "vendor_name", "") or getattr(ret, "party_name", "") or ""


def _get_created(ret):
    # dict key might be created_at / created
    if isinstance(ret, dict):
        return str(ret.get("created_at") or ret.get("created") or "")
    return str(getattr(ret, "created_at", "") or "")


# ---------- Details Dialog ----------
class ReturnDetailsDialog(QDialog):
    def __init__(self, parent=None, return_type: str = "SALE_RETURN", return_id: int | None = None):
        super().__init__(parent)
        self.return_type = (return_type or "").strip().upper()
        self.return_id = return_id

        self.setWindowTitle(f"Return Details — {self.return_type} #{return_id}" if return_id else "Return Details")
        self.setMinimumWidth(920)

        layout = QVBoxLayout(self)

        self.header = QLabel("")
        self.header.setStyleSheet("font-size:13px;font-weight:700;")
        layout.addWidget(self.header)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "SKU", "Item", "Category",
            "Qty Primary", "Unit P",
            "Qty Secondary", "Unit S"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.load()

    def load(self):
        self.table.setRowCount(0)
        if not self.return_id:
            return

        with get_db() as db:
            if self.return_type == "SALE_RETURN":
                ret = get_sale_return_details(db, int(self.return_id))
            else:
                ret = get_purchase_return_details(db, int(self.return_id))

        if not ret:
            self.header.setText("Return not found.")
            return

        loc = _get_location_name(ret)
        created = _get_created(ret)
        notes = (_get(ret, "notes", "") or "").strip()

        if self.return_type == "SALE_RETURN":
            party = _get(ret, "customer_name", "") or _get(ret, "party_name", "") or ""
        else:
            party = _get(ret, "vendor_name", "") or _get(ret, "party_name", "") or ""

        head = f"<b>Type:</b> {self.return_type} &nbsp;&nbsp; <b>Party:</b> {party} &nbsp;&nbsp; <b>Location:</b> {loc} &nbsp;&nbsp; <b>Created:</b> {created}"
        if notes:
            head += f"<br><b>Notes:</b> {notes}"
        self.header.setText(head)

        lines = _get(ret, "items", []) or []
        for r, line in enumerate(lines):
            it = _get(line, "item", None)
            sku = _get(it, "sku", "") if it else ""
            name = _get(it, "name", "") if it else ""
            cat = (_get(it, "category", "") or "").upper()

            qp = float(_get(line, "qty_primary", 0) or 0)
            qs = _get(line, "qty_secondary", None)

            up = _get(line, "unit_primary", "") or (_get(it, "unit_primary", "") if it else "")
            us = _get(line, "unit_secondary", "") or (_get(it, "unit_secondary", "") if it else "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(sku)))
            self.table.setItem(r, 1, QTableWidgetItem(str(name)))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qp:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(up or "")))
            self.table.setItem(r, 5, QTableWidgetItem("" if qs is None else str(int(qs))))
            self.table.setItem(r, 6, QTableWidgetItem(str(us or "")))


# ---------- Add Dialog ----------
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
        return_type = self.return_type.currentText().strip().upper()
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

        payload = {
            "return_type": return_type,
            "location_id": location_id,
            "notes": None,
            "rows": rows_payload
        }

        # repo expects customer_name/vendor_name
        if return_type == "SALE_RETURN":
            payload["customer_name"] = party
        else:
            payload["vendor_name"] = party

        self._data = payload
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


# ---------- Page ----------
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

        # SALE_RETURN tab
        self.sale_table = QTableWidget(0, 5)
        self.sale_table.setHorizontalHeaderLabels(["ID", "Party", "Location", "Created", "Ref"])
        self.sale_table.setColumnHidden(0, True)
        self.sale_table.horizontalHeader().setStretchLastSection(True)
        self.sale_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.sale_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.sale_table.cellDoubleClicked.connect(lambda *_: self.open_details("SALE_RETURN"))
        self.tabs.addTab(self.sale_table, "Sale Returns")

        # PURCHASE_RETURN tab
        self.purchase_table = QTableWidget(0, 5)
        self.purchase_table.setHorizontalHeaderLabels(["ID", "Party", "Location", "Created", "Ref"])
        self.purchase_table.setColumnHidden(0, True)
        self.purchase_table.horizontalHeader().setStretchLastSection(True)
        self.purchase_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.purchase_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.purchase_table.cellDoubleClicked.connect(lambda *_: self.open_details("PURCHASE_RETURN"))
        self.tabs.addTab(self.purchase_table, "Purchase Returns")

        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)
        self.add_btn.setToolTip("" if can_add else "Viewer role: Add Return disabled")

    def load_data(self):
        q = self.search.text().strip()

        self.sale_table.setRowCount(0)
        self.purchase_table.setRowCount(0)

        with get_db() as db:
            sale_rows = list_returns(db, q_text=q, return_type="SALE_RETURN", limit=300) or []
            pur_rows = list_returns(db, q_text=q, return_type="PURCHASE_RETURN", limit=300) or []

        # ---- SALE_RETURN list (dict OR ORM safe) ----
        for r, ret in enumerate(sale_rows):
            rid = _get(ret, "id", None)
            party = _get_party(ret, "SALE_RETURN")
            loc = _get_location_name(ret)
            created = _get_created(ret)

            self.sale_table.insertRow(r)
            self.sale_table.setItem(r, 0, QTableWidgetItem("" if rid is None else str(rid)))
            self.sale_table.setItem(r, 1, QTableWidgetItem(party))
            self.sale_table.setItem(r, 2, QTableWidgetItem(loc))
            self.sale_table.setItem(r, 3, QTableWidgetItem(created))
            self.sale_table.setItem(r, 4, QTableWidgetItem("" if rid is None else f"sale_return#{rid}"))

        # ---- PURCHASE_RETURN list (dict OR ORM safe) ----
        for r, ret in enumerate(pur_rows):
            rid = _get(ret, "id", None)
            party = _get_party(ret, "PURCHASE_RETURN")
            loc = _get_location_name(ret)
            created = _get_created(ret)

            self.purchase_table.insertRow(r)
            self.purchase_table.setItem(r, 0, QTableWidgetItem("" if rid is None else str(rid)))
            self.purchase_table.setItem(r, 1, QTableWidgetItem(party))
            self.purchase_table.setItem(r, 2, QTableWidgetItem(loc))
            self.purchase_table.setItem(r, 3, QTableWidgetItem(created))
            self.purchase_table.setItem(r, 4, QTableWidgetItem("" if rid is None else f"purchase_return#{rid}"))

    def _selected_id(self, table: QTableWidget):
        row = table.currentRow()
        if row < 0:
            return None
        try:
            v = (table.item(row, 0).text() or "").strip()
            return int(v) if v else None
        except Exception:
            return None

    def open_details(self, rtype: str):
        table = self.sale_table if rtype == "SALE_RETURN" else self.purchase_table
        rid = self._selected_id(table)
        if not rid:
            return
        ReturnDetailsDialog(self, return_type=rtype, return_id=rid).exec()

    def add_return(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(
                self, "Permission",
                "Viewer role: You can only view/export.\n\nPlease login as Admin/Staff."
            )
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
