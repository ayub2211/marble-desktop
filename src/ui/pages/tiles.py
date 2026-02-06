# src/ui/pages/tiles.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox,
    QLineEdit, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.tile_repo import (
    list_tiles, create_tile_entry, update_tile_entry,
    soft_delete_tile_entry, get_tile_items, get_tile_entry
)

class AddEditTileDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Tile Stock" if entry else "Add Tile Stock")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.item_dd = QComboBox()
        self._items = []
        with get_db() as db:
            self._items = get_tile_items(db)
        for it in self._items:
            self.item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        self.qty_box = QSpinBox()
        self.qty_box.setRange(0, 10_000_000)

        self.qty_sqft = QDoubleSpinBox()
        self.qty_sqft.setRange(0, 999_999_999)
        self.qty_sqft.setDecimals(3)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes...")

        form.addRow("Tile Item (SKU)", self.item_dd)
        form.addRow("Boxes (optional)", self.qty_box)
        form.addRow("Total Sqft", self.qty_sqft)
        form.addRow("Notes", self.notes)

        layout.addLayout(form)

        # ✅ Auto-calc sqft when boxes change
        self.qty_box.valueChanged.connect(self._auto_calc_sqft)

        btns = QHBoxLayout()
        btns.addStretch()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)

        if entry:
            # prefill
            self._set_selected_item(entry["item_id"])
            self.qty_box.setValue(int(entry.get("qty_box") or 0))
            self.qty_sqft.setValue(float(entry.get("qty_sqft") or 0))
            self.notes.setText(entry.get("notes") or "")

    def _set_selected_item(self, item_id: int):
        for i in range(self.item_dd.count()):
            if self.item_dd.itemData(i) == item_id:
                self.item_dd.setCurrentIndex(i)
                break

    def _auto_calc_sqft(self):
        # boxes -> sqft via item.sqft_per_unit (if present)
        item_id = self.item_dd.currentData()
        boxes = self.qty_box.value()

        with get_db() as db:
            item = None
            for it in get_tile_items(db):
                if it.id == item_id:
                    item = it
                    break

        if not item:
            return

        if item.sqft_per_unit and boxes > 0:
            self.qty_sqft.setValue(float(item.sqft_per_unit) * boxes)

    def on_save(self):
        item_id = self.item_dd.currentData()
        qty_box = self.qty_box.value() or None
        qty_sqft = float(self.qty_sqft.value())

        if not item_id:
            QMessageBox.warning(self, "Missing", "Please select a tile item.")
            return

        data = {
            "item_id": item_id,
            "qty_box": qty_box,
            "qty_sqft": qty_sqft,
            "notes": self.notes.text().strip() or None
        }
        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class TilesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Tiles Inventory (Sqft + Box)")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Tile Stock")
        self.add_btn.clicked.connect(self.add_entry)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Name", "Boxes", "Sqft", "Notes"
        ])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_tiles(db)
            for r, row in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row.id)))
                self.table.setItem(r, 1, QTableWidgetItem(row.item.sku))
                self.table.setItem(r, 2, QTableWidgetItem(row.item.name))
                self.table.setItem(r, 3, QTableWidgetItem("" if row.qty_box is None else str(row.qty_box)))
                self.table.setItem(r, 4, QTableWidgetItem(f"{float(row.qty_sqft):.3f}"))
                self.table.setItem(r, 5, QTableWidgetItem(row.notes or ""))

    def selected_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def open_menu(self, pos):
        entry_id = self.selected_id()
        if not entry_id:
            return
        menu = QMenu(self)
        edit = menu.addAction("Edit")
        delete = menu.addAction("Delete")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit:
            self.edit_entry(entry_id)
        elif action == delete:
            self.delete_entry(entry_id)

    def add_entry(self):
        dlg = AddEditTileDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_tile_entry(db, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save:\n{e}")

    def edit_entry(self, entry_id):
        with get_db() as db:
            entry = get_tile_entry(db, entry_id)
            if not entry:
                return
            existing = {
                "item_id": entry.item_id,
                "qty_box": entry.qty_box,
                "qty_sqft": entry.qty_sqft,
                "notes": entry.notes
            }

        dlg = AddEditTileDialog(self, existing)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    update_tile_entry(db, entry_id, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update:\n{e}")

    def delete_entry(self, entry_id):
        ok = QMessageBox.question(self, "Confirm", "Delete this entry?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_tile_entry(db, entry_id)
        self.load_data()
