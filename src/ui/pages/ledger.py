# src/ui/pages/ledger.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTableWidget, QTableWidgetItem, QComboBox, QPushButton
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.ledger_repo import list_ledger


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
        self.type_dd.addItems(["PURCHASE", "SALE", "ADJUST", "DAMAGE"])
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
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)

        q = self.search.text().strip()
        type_filter = self.type_dd.currentText()
        if self.type_dd.currentData() is None:
            type_filter = None

        with get_db() as db:
            rows = list_ledger(db, q_text=q, limit=300)

        # apply type filter (simple UI side)
        if type_filter:
            rows = [r for r in rows if (r.movement_type or "").upper() == type_filter]

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
