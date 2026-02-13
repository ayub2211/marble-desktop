# src/ui/pages/returns.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTabWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QDialog, QFormLayout, QComboBox, QTextEdit,
    QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations
from src.db.models import Item
from src.db.returns_repo import (
    list_sale_returns, create_sale_return,
    list_purchase_returns, create_purchase_return
)


def _it(text, align=Qt.AlignLeft, bold=False):
    item = QTableWidgetItem(str(text if text is not None else ""))
    item.setTextAlignment(align)
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    return item


class ReturnDialog(QDialog):
    """
    Reusable dialog for:
      - Sale Return
      - Purchase Return
    """
    def __init__(self, parent=None, mode="SALE"):
        super().__init__(parent)
        self.mode = mode  # "SALE" or "PURCHASE"
        self.setWindowTitle("Add Sale Return" if mode == "SALE" else "Add Purchase Return")
        self.resize(850, 520)

        root = QVBoxLayout(self)

        form = QFormLayout()
        self.loc_dd = QComboBox()
        self.name_inp = QLineEdit()
        self.notes = QTextEdit()
        self.notes.setFixedHeight(70)

        form.addRow("Location:", self.loc_dd)
        form.addRow("Customer Name:" if mode == "SALE" else "Vendor Name:", self.name_inp)
        form.addRow("Notes:", self.notes)

        root.addLayout(form)

        # Items table
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels([
            "Item (SKU - Name)", "Category", "Qty Primary", "Qty Secondary", "Remove"
        ])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.tbl, 1)

        btn_row = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Add Line")
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")

        btn_row.addWidget(self.add_row_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.cancel_btn)
        root.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self.reject)
        self.add_row_btn.clicked.connect(self.add_line)
        self.save_btn.clicked.connect(self.on_save)

        self._load_locations()
        self._load_items_cache()

        self.add_line()

    def _load_locations(self):
        with get_db() as db:
            locs = get_locations(db)
        self.loc_dd.clear()
        self.loc_dd.addItem("Select location...", None)
        for l in locs:
            self.loc_dd.addItem(l.name, l.id)

    def _load_items_cache(self):
        with get_db() as db:
            self.items = (
                db.query(Item)
                .filter(Item.is_active == True)
                .order_by(Item.sku.asc())
                .all()
            )

    def add_line(self):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)

        item_dd = QComboBox()
        item_dd.addItem("Select item...", None)
        for it in self.items:
            item_dd.addItem(f"{it.sku} — {it.name}", it.id)
        item_dd.currentIndexChanged.connect(lambda _: self._on_item_change(r))

        cat_lbl = QTableWidgetItem("")
        cat_lbl.setFlags(cat_lbl.flags() & ~Qt.ItemIsEditable)

        qty_primary = QDoubleSpinBox()
        qty_primary.setRange(0, 9999999)
        qty_primary.setDecimals(3)
        qty_primary.setValue(0)

        qty_secondary = QSpinBox()
        qty_secondary.setRange(0, 9999999)
        qty_secondary.setValue(0)

        rm_btn = QPushButton("X")
        rm_btn.clicked.connect(lambda: self._remove_row(r))

        self.tbl.setCellWidget(r, 0, item_dd)
        self.tbl.setItem(r, 1, cat_lbl)
        self.tbl.setCellWidget(r, 2, qty_primary)
        self.tbl.setCellWidget(r, 3, qty_secondary)
        self.tbl.setCellWidget(r, 4, rm_btn)

    def _remove_row(self, row):
        # safe remove
        if 0 <= row < self.tbl.rowCount():
            self.tbl.removeRow(row)

    def _find_item(self, item_id):
        for it in self.items:
            if it.id == item_id:
                return it
        return None

    def _on_item_change(self, row):
        dd = self.tbl.cellWidget(row, 0)
        if not dd:
            return
        item_id = dd.currentData()
        it = self._find_item(item_id)
        cat = (it.category or "") if it else ""
        self.tbl.item(row, 1).setText(cat)

        # auto secondary enable/disable
        sec = self.tbl.cellWidget(row, 3)
        if sec:
            if it and (it.category or "").upper() in ("SLAB", "TILE"):
                sec.setEnabled(True)
            else:
                sec.setEnabled(False)
                sec.setValue(0)

    def _collect_payload(self):
        location_id = self.loc_dd.currentData()
        if not location_id:
            raise ValueError("Location is required.")

        name = (self.name_inp.text() or "").strip() or None
        notes = (self.notes.toPlainText() or "").strip() or None

        rows = []
        for r in range(self.tbl.rowCount()):
            dd = self.tbl.cellWidget(r, 0)
            if not dd:
                continue
            item_id = dd.currentData()
            if not item_id:
                continue

            it = self._find_item(item_id)
            if not it:
                continue

            qty_primary = self.tbl.cellWidget(r, 2).value()
            qty_secondary = self.tbl.cellWidget(r, 3).value() if self.tbl.cellWidget(r, 3).isEnabled() else None

            rows.append({
                "item_id": item_id,
                "qty_primary": qty_primary,
                "qty_secondary": qty_secondary
            })

        if not rows:
            raise ValueError("At least one valid line is required.")

        payload = {
            "location_id": location_id,
            "notes": notes,
            "rows": rows
        }
        if self.mode == "SALE":
            payload["customer_name"] = name
        else:
            payload["vendor_name"] = name

        return payload

    def on_save(self):
        try:
            payload = self._collect_payload()
        except Exception as e:
            QMessageBox.critical(self, "Validation", str(e))
            return

        try:
            with get_db() as db:
                if self.mode == "SALE":
                    create_sale_return(db, payload)
                else:
                    create_purchase_return(db, payload)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class ReturnsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Returns")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # -------------------------
        # TAB 1: Sale Returns
        # -------------------------
        t1 = QWidget()
        t1_lay = QVBoxLayout(t1)

        top1 = QHBoxLayout()
        self.sale_search = QLineEdit()
        self.sale_search.setPlaceholderText("Search customer...")
        self.btn_add_sale = QPushButton("+ Add Sale Return")
        top1.addWidget(self.sale_search, 1)
        top1.addWidget(self.btn_add_sale)
        t1_lay.addLayout(top1)

        self.sale_tbl = QTableWidget(0, 3)
        self.sale_tbl.setHorizontalHeaderLabels(["Customer", "Location", "Created"])
        self.sale_tbl.horizontalHeader().setStretchLastSection(True)
        t1_lay.addWidget(self.sale_tbl, 1)

        self.tabs.addTab(t1, "Sale Returns")

        # -------------------------
        # TAB 2: Purchase Returns
        # -------------------------
        t2 = QWidget()
        t2_lay = QVBoxLayout(t2)

        top2 = QHBoxLayout()
        self.pur_search = QLineEdit()
        self.pur_search.setPlaceholderText("Search vendor...")
        self.btn_add_pur = QPushButton("+ Add Purchase Return")
        top2.addWidget(self.pur_search, 1)
        top2.addWidget(self.btn_add_pur)
        t2_lay.addLayout(top2)

        self.pur_tbl = QTableWidget(0, 3)
        self.pur_tbl.setHorizontalHeaderLabels(["Vendor", "Location", "Created"])
        self.pur_tbl.horizontalHeader().setStretchLastSection(True)
        t2_lay.addWidget(self.pur_tbl, 1)

        self.tabs.addTab(t2, "Purchase Returns")

        # signals
        self.sale_search.textChanged.connect(self.load_sale_returns)
        self.pur_search.textChanged.connect(self.load_purchase_returns)
        self.btn_add_sale.clicked.connect(self.add_sale_return)
        self.btn_add_pur.clicked.connect(self.add_purchase_return)
        self.tabs.currentChanged.connect(self._on_tab_change)

        self._on_tab_change(0)

    def _on_tab_change(self, idx):
        if idx == 0:
            self.load_sale_returns()
        else:
            self.load_purchase_returns()

    def load_sale_returns(self):
        self.sale_tbl.setRowCount(0)
        q = (self.sale_search.text() or "").strip()

        with get_db() as db:
            rows = list_sale_returns(db, q_text=q)

        for r, row in enumerate(rows):
            self.sale_tbl.insertRow(r)
            self.sale_tbl.setItem(r, 0, _it(row.customer_name or ""))
            self.sale_tbl.setItem(r, 1, _it((row.location.name if row.location else "") or ""))
            self.sale_tbl.setItem(r, 2, _it(str(row.created_at)))

    def load_purchase_returns(self):
        self.pur_tbl.setRowCount(0)
        q = (self.pur_search.text() or "").strip()

        with get_db() as db:
            rows = list_purchase_returns(db, q_text=q)

        for r, row in enumerate(rows):
            self.pur_tbl.insertRow(r)
            self.pur_tbl.setItem(r, 0, _it(row.vendor_name or ""))
            self.pur_tbl.setItem(r, 1, _it((row.location.name if row.location else "") or ""))
            self.pur_tbl.setItem(r, 2, _it(str(row.created_at)))

    def add_sale_return(self):
        dlg = ReturnDialog(self, mode="SALE")
        if dlg.exec():
            self.load_sale_returns()

    def add_purchase_return(self):
        dlg = ReturnDialog(self, mode="PURCHASE")
        if dlg.exec():
            self.load_purchase_returns()
