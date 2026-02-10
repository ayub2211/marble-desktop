# src/ui/pages/blocks.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QComboBox, QSpinBox,
    QLineEdit, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.block_repo import (
    list_blocks, create_block_entry, update_block_entry,
    soft_delete_block_entry, get_block_items, get_block_entry
)


class AddEditBlockDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Block Stock" if entry else "Add Block Stock")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._items = []
        self._items_by_id = {}
        with get_db() as db:
            self._items = get_block_items(db)

        for it in self._items:
            self._items_by_id[it.id] = it

        self.item_dd = QComboBox()
        for it in self._items:
            self.item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        self.piece_count = QSpinBox()
        self.piece_count.setRange(0, 10_000_000)

        self.location = QLineEdit()
        self.location.setPlaceholderText("Optional location (e.g., Yard / Warehouse A)")

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes...")

        form.addRow("Block Item (SKU)", self.item_dd)
        form.addRow("Pieces", self.piece_count)
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
        self.save_btn.clicked.connect(self.on_save)

        if entry:
            self._set_selected_item(entry.get("item_id"))
            self.piece_count.setValue(int(entry.get("piece_count") or 0))
            self.location.setText(entry.get("location") or "")
            self.notes.setText(entry.get("notes") or "")

    def _set_selected_item(self, item_id: int):
        if not item_id:
            return
        for i in range(self.item_dd.count()):
            if self.item_dd.itemData(i) == item_id:
                self.item_dd.setCurrentIndex(i)
                break

    def on_save(self):
        item_id = self.item_dd.currentData()
        if not item_id:
            QMessageBox.warning(self, "Missing", "Please select a block item.")
            return

        data = {
            "item_id": item_id,
            "piece_count": int(self.piece_count.value()),
            "location": self.location.text().strip() or None,
            "notes": self.notes.text().strip() or None,
        }
        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class BlocksPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Blocks Inventory (Pieces)")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by SKU or Name...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Block Stock")
        self.add_btn.clicked.connect(self.add_entry)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Name", "Pieces", "Location", "Notes", "Created"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(6, True)  # created hidden (optional)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_blocks(db, self.search.text().strip())
            for r, row in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row.id)))
                self.table.setItem(r, 1, QTableWidgetItem(row.item.sku if row.item else ""))
                self.table.setItem(r, 2, QTableWidgetItem(row.item.name if row.item else ""))
                self.table.setItem(r, 3, QTableWidgetItem("" if row.piece_count is None else str(row.piece_count)))
                self.table.setItem(r, 4, QTableWidgetItem(row.location or ""))
                self.table.setItem(r, 5, QTableWidgetItem(row.notes or ""))
                self.table.setItem(r, 6, QTableWidgetItem(str(getattr(row, "created_at", ""))))

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
        dlg = AddEditBlockDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_block_entry(db, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save:\n{e}")

    def edit_entry(self, entry_id):
        with get_db() as db:
            entry = get_block_entry(db, entry_id)
            if not entry:
                return
            existing = {
                "item_id": entry.item_id,
                "piece_count": entry.piece_count,
                "location": entry.location,
                "notes": entry.notes,
            }

        dlg = AddEditBlockDialog(self, existing)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    update_block_entry(db, entry_id, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update:\n{e}")

    def delete_entry(self, entry_id):
        ok = QMessageBox.question(self, "Confirm", "Delete this entry?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_block_entry(db, entry_id)
        self.load_data()
