# src/ui/pages/slabs.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.item_repo import search_items
from src.db.slab_repo import list_slabs, create_slab_entry, update_slab_entry, soft_delete_slab_entry


class SlabEntryDialog(QDialog):
    def __init__(self, parent=None, existing=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Slab Entry" if existing else "Add Slab Entry")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.slab_count = QSpinBox()
        self.slab_count.setRange(0, 999999)

        self.total_sqft = QDoubleSpinBox()
        self.total_sqft.setRange(0, 999999999)
        self.total_sqft.setDecimals(3)

        self.location = QLineEdit()
        self.notes = QLineEdit()

        form.addRow("Slab Count", self.slab_count)
        form.addRow("Total Sqft", self.total_sqft)
        form.addRow("Location", self.location)
        form.addRow("Notes", self.notes)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self._save)

        if existing:
            self.slab_count.setValue(int(existing.get("slab_count") or 0))
            self.total_sqft.setValue(float(existing.get("total_sqft") or 0))
            self.location.setText(existing.get("location") or "")
            self.notes.setText(existing.get("notes") or "")

    def _save(self):
        self._data = {
            "slab_count": int(self.slab_count.value()),
            "total_sqft": float(self.total_sqft.value()),
            "location": self.location.text().strip() or None,
            "notes": self.notes.text().strip() or None,
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class SlabsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Slabs Inventory (Sqft + Slab Count)")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        # top controls
        top = QHBoxLayout()

        self.item_dd = QComboBox()
        self.item_dd.currentIndexChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Slab Stock")
        self.add_btn.clicked.connect(self.add_entry)

        top.addWidget(QLabel("Item:"))
        top.addWidget(self.item_dd, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        # table
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "ItemID", "SKU", "Name", "Slab Count", "Total Sqft", "Location"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(1, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        self._load_items()
        self.load_data()

    def _load_items(self):
        self.item_dd.blockSignals(True)
        self.item_dd.clear()
        self.item_dd.addItem("ALL SLABS", None)

        with get_db() as db:
            slabs = search_items(db, q_text="", category="SLAB")
            for it in slabs:
                self.item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        self.item_dd.blockSignals(False)

    def _selected_item_id(self):
        return self.item_dd.currentData()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_slabs(db, item_id=self._selected_item_id())

            for r, row in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row.id)))
                self.table.setItem(r, 1, QTableWidgetItem(str(row.item_id)))
                self.table.setItem(r, 2, QTableWidgetItem(row.item.sku))
                self.table.setItem(r, 3, QTableWidgetItem(row.item.name))
                self.table.setItem(r, 4, QTableWidgetItem(str(row.slab_count or 0)))
                self.table.setItem(r, 5, QTableWidgetItem(f"{float(row.total_sqft or 0):.3f}"))
                self.table.setItem(r, 6, QTableWidgetItem(row.location or ""))

    def _selected_row_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def open_menu(self, pos):
        row_id = self._selected_row_id()
        if not row_id:
            return
        menu = QMenu(self)
        edit = menu.addAction("Edit")
        delete = menu.addAction("Delete")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit:
            self.edit_entry(row_id)
        elif action == delete:
            self.delete_entry(row_id)

    def add_entry(self):
        item_id = self._selected_item_id()
        if item_id is None:
            QMessageBox.warning(self, "Select Item", "Please select a SLAB item first (not ALL).")
            return

        dlg = SlabEntryDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.data
            data["item_id"] = int(item_id)

            with get_db() as db:
                create_slab_entry(db, data)

            self.load_data()

    def edit_entry(self, row_id: int):
        # pull existing row values from table (fast)
        row = self.table.currentRow()
        existing = {
            "slab_count": self.table.item(row, 4).text(),
            "total_sqft": self.table.item(row, 5).text(),
            "location": self.table.item(row, 6).text(),
            "notes": "",
        }

        dlg = SlabEntryDialog(self, existing=existing)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.data
            with get_db() as db:
                update_slab_entry(db, row_id, data)
            self.load_data()

    def delete_entry(self, row_id: int):
        ok = QMessageBox.question(self, "Confirm", "Delete this slab entry?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_slab_entry(db, row_id)
        self.load_data()
