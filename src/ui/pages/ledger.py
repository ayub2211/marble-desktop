# src/ui/pages/ledger.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QPushButton, QDialog, QMessageBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.ledger_repo import list_ledger
from src.db.purchase_repo import get_purchase_details
from src.db.sales_repo import get_sale_details
from src.db.returns_repo import get_sale_return_details, get_purchase_return_details


class PurchaseDetailsDialog(QDialog):
    def __init__(self, parent=None, purchase_id: int | None = None):
        super().__init__(parent)
        self.purchase_id = purchase_id
        self.setWindowTitle(f"Purchase Details #{purchase_id}" if purchase_id else "Purchase Details")
        self.setMinimumWidth(900)

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
        if not self.purchase_id:
            return

        with get_db() as db:
            p = get_purchase_details(db, int(self.purchase_id))

        if not p:
            self.header.setText("Purchase not found.")
            return

        vendor = getattr(p, "vendor_name", "") or ""
        loc = p.location.name if getattr(p, "location", None) else ""
        created = str(getattr(p, "created_at", "") or "")
        notes = (getattr(p, "notes", "") or "").strip()

        head = f"<b>Vendor:</b> {vendor} &nbsp;&nbsp; <b>Location:</b> {loc} &nbsp;&nbsp; <b>Created:</b> {created}"
        if notes:
            head += f"<br><b>Notes:</b> {notes}"
        self.header.setText(head)

        items = getattr(p, "items", []) or []
        for r, line in enumerate(items):
            it = getattr(line, "item", None)
            sku = it.sku if it else ""
            name = it.name if it else ""
            cat = (getattr(it, "category", "") or "").upper()

            qp = float(getattr(line, "qty_primary", 0) or 0)
            qs = getattr(line, "qty_secondary", None)

            up = getattr(line, "unit_primary", "") or (it.unit_primary if it else "")
            us = getattr(line, "unit_secondary", "") or (it.unit_secondary if it else "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(sku)))
            self.table.setItem(r, 1, QTableWidgetItem(str(name)))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qp:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(up or "")))
            self.table.setItem(r, 5, QTableWidgetItem("" if qs is None else str(int(qs))))
            self.table.setItem(r, 6, QTableWidgetItem(str(us or "")))


class SaleDetailsDialog(QDialog):
    def __init__(self, parent=None, sale_id: int | None = None):
        super().__init__(parent)
        self.sale_id = sale_id
        self.setWindowTitle(f"Sale Details #{sale_id}" if sale_id else "Sale Details")
        self.setMinimumWidth(900)

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
        if not self.sale_id:
            return

        with get_db() as db:
            s = get_sale_details(db, int(self.sale_id))

        if not s:
            self.header.setText("Sale not found.")
            return

        customer = getattr(s, "customer_name", "") or ""
        loc = s.location.name if getattr(s, "location", None) else ""
        created = str(getattr(s, "created_at", "") or "")
        notes = (getattr(s, "notes", "") or "").strip()

        head = f"<b>Customer:</b> {customer} &nbsp;&nbsp; <b>Location:</b> {loc} &nbsp;&nbsp; <b>Created:</b> {created}"
        if notes:
            head += f"<br><b>Notes:</b> {notes}"
        self.header.setText(head)

        items = getattr(s, "items", []) or []
        for r, line in enumerate(items):
            it = getattr(line, "item", None)
            sku = it.sku if it else ""
            name = it.name if it else ""
            cat = (getattr(it, "category", "") or "").upper()

            qp = float(getattr(line, "qty_primary", 0) or 0)
            qs = getattr(line, "qty_secondary", None)

            up = getattr(line, "unit_primary", "") or (it.unit_primary if it else "")
            us = getattr(line, "unit_secondary", "") or (it.unit_secondary if it else "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(sku)))
            self.table.setItem(r, 1, QTableWidgetItem(str(name)))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qp:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(up or "")))
            self.table.setItem(r, 5, QTableWidgetItem("" if qs is None else str(int(qs))))
            self.table.setItem(r, 6, QTableWidgetItem(str(us or "")))


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

        loc = ret.location.name if getattr(ret, "location", None) else ""
        created = str(getattr(ret, "created_at", "") or "")
        notes = (getattr(ret, "notes", "") or "").strip()

        if self.return_type == "SALE_RETURN":
            party = getattr(ret, "customer_name", "") or ""
        else:
            party = getattr(ret, "vendor_name", "") or ""

        head = f"<b>Type:</b> {self.return_type} &nbsp;&nbsp; <b>Party:</b> {party} &nbsp;&nbsp; <b>Location:</b> {loc} &nbsp;&nbsp; <b>Created:</b> {created}"
        if notes:
            head += f"<br><b>Notes:</b> {notes}"
        self.header.setText(head)

        lines = getattr(ret, "items", []) or []
        for r, line in enumerate(lines):
            it = getattr(line, "item", None)
            sku = it.sku if it else ""
            name = it.name if it else ""
            cat = (getattr(it, "category", "") or "").upper()

            qp = float(getattr(line, "qty_primary", 0) or 0)
            qs = getattr(line, "qty_secondary", None)

            up = getattr(line, "unit_primary", "") or (it.unit_primary if it else "")
            us = getattr(line, "unit_secondary", "") or (it.unit_secondary if it else "")

            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(sku)))
            self.table.setItem(r, 1, QTableWidgetItem(str(name)))
            self.table.setItem(r, 2, QTableWidgetItem(str(cat)))
            self.table.setItem(r, 3, QTableWidgetItem(f"{qp:.3f}"))
            self.table.setItem(r, 4, QTableWidgetItem(str(up or "")))
            self.table.setItem(r, 5, QTableWidgetItem("" if qs is None else str(int(qs))))
            self.table.setItem(r, 6, QTableWidgetItem(str(us or "")))


class LedgerEntryDialog(QDialog):
    def __init__(self, parent=None, led=None):
        super().__init__(parent)
        self.led = led
        self.setWindowTitle(f"Ledger Entry #{getattr(led, 'id', '')}")
        self.setMinimumWidth(780)

        layout = QVBoxLayout(self)

        info = QLabel("")
        info.setStyleSheet("font-size:13px;font-weight:700;")
        layout.addWidget(info)

        ref_type = (getattr(led, "ref_type", None) or "").strip()
        ref_id = getattr(led, "ref_id", None)

        sku = led.item.sku if getattr(led, "item", None) else ""
        name = led.item.name if getattr(led, "item", None) else ""
        loc = led.location.name if getattr(led, "location", None) else ""
        mt = getattr(led, "movement_type", "") or ""
        dt = str(getattr(led, "created_at", "") or "")

        ref_txt = ""
        if ref_type or ref_id:
            ref_txt = f"{ref_type}#{ref_id}"

        qp = getattr(led, "qty_primary", None)
        qs = getattr(led, "qty_secondary", None)

        info.setText(
            f"<b>Type:</b> {mt} &nbsp;&nbsp; <b>SKU:</b> {sku} &nbsp;&nbsp; <b>Item:</b> {name}<br>"
            f"<b>Location:</b> {loc} &nbsp;&nbsp; <b>Qty Primary:</b> {qp} &nbsp;&nbsp; <b>Qty Secondary:</b> {qs}<br>"
            f"<b>Ref:</b> {ref_txt} &nbsp;&nbsp; <b>Date:</b> {dt}"
        )

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.open_ref_btn = QPushButton("Open Source (Ref)")
        self.open_ref_btn.clicked.connect(self.open_source)
        btn_row.addWidget(self.open_ref_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        can_open = bool(ref_type) and bool(ref_id)
        self.open_ref_btn.setEnabled(can_open)
        if not can_open:
            self.open_ref_btn.setToolTip("No ref_type/ref_id for this ledger row.")

    def open_source(self):
        ref_type = (getattr(self.led, "ref_type", None) or "").strip().lower()
        ref_id = getattr(self.led, "ref_id", None)

        if not ref_type or not ref_id:
            QMessageBox.information(self, "No Ref", "This ledger entry has no source reference.")
            return

        if ref_type == "purchase":
            PurchaseDetailsDialog(self, purchase_id=int(ref_id)).exec()
            return

        if ref_type == "sale":
            SaleDetailsDialog(self, sale_id=int(ref_id)).exec()
            return

        if ref_type == "sale_return":
            ReturnDetailsDialog(self, return_type="SALE_RETURN", return_id=int(ref_id)).exec()
            return

        if ref_type == "purchase_return":
            ReturnDetailsDialog(self, return_type="PURCHASE_RETURN", return_id=int(ref_id)).exec()
            return

        QMessageBox.information(self, "Unsupported", f"Open Ref not supported for ref_type: {ref_type}")


class LedgerPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Stock Ledger")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search: PURCHASE / SALE / ADJUST / DAMAGE / ref_type ...")
        self.search.textChanged.connect(self.load_data)

        self.type_dd = QComboBox()
        self.type_dd.addItem("ALL", None)
        self.type_dd.addItems(["PURCHASE", "SALE", "SALE_RETURN", "PURCHASE_RETURN", "ADJUST", "DAMAGE"])
        self.type_dd.currentIndexChanged.connect(self.load_data)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_data)

        top.addWidget(self.search, 2)
        top.addWidget(QLabel("Type:"))
        top.addWidget(self.type_dd)
        top.addStretch()
        top.addWidget(self.refresh_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "ID", "When", "Type", "SKU", "Item",
            "Location", "Qty Primary", "Qty Secondary", "Ref"
        ])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.open_ledger_popup)
        layout.addWidget(self.table)

        self._rows_cache = []
        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)

        q = self.search.text().strip()
        type_filter = self.type_dd.currentText()
        if self.type_dd.currentData() is None:
            type_filter = None

        with get_db() as db:
            rows = list_ledger(db, q_text=q, limit=400)

        if type_filter:
            rows = [r for r in rows if (r.movement_type or "").upper() == type_filter]

        self._rows_cache = rows

        for r, led in enumerate(rows):
            self.table.insertRow(r)

            sku = led.item.sku if led.item else ""
            name = led.item.name if led.item else ""
            loc = led.location.name if led.location else ""

            ref_txt = ""
            if led.ref_type or led.ref_id:
                ref_txt = f"{led.ref_type or ''}#{led.ref_id or ''}".strip()

            self.table.setItem(r, 0, QTableWidgetItem(str(led.id)))
            self.table.setItem(r, 1, QTableWidgetItem(str(getattr(led, "created_at", ""))))
            self.table.setItem(r, 2, QTableWidgetItem(led.movement_type or ""))
            self.table.setItem(r, 3, QTableWidgetItem(sku))
            self.table.setItem(r, 4, QTableWidgetItem(name))
            self.table.setItem(r, 5, QTableWidgetItem(loc))
            self.table.setItem(r, 6, QTableWidgetItem(str(led.qty_primary or "")))
            self.table.setItem(r, 7, QTableWidgetItem(str(led.qty_secondary or "")))
            self.table.setItem(r, 8, QTableWidgetItem(ref_txt))

    def open_ledger_popup(self, row, _col):
        if row < 0 or row >= len(self._rows_cache):
            return
        led = self._rows_cache[row]
        LedgerEntryDialog(self, led=led).exec()
