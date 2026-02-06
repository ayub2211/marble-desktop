# src/ui/pages/tables.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem,
    QDialog, QFormLayout, QComboBox, QSpinBox, QLineEdit,
    QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.table_repo import (
    list_tables, create_table_entry, update_table_entry,
    soft_delete_table_entry, get_table_items, get_table_entry
)


class AddEditTableDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Table Stock" if entry else "Add Table Stock")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # Items dropdown (TABLE only)
        self.item_dd = QComboBox()
        self._items = []
        with get_db() as db:
            self._items = get_table_items(db)

        for it in self._items:
            self.item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        self.piece_count = QSpinBox()
        self.piece_count.setRange(0, 10_000_000)

        self.location = QLineEdit()
        self.location.setPlaceholderText("e.g. Showroom / Rack 1")

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes...")

        form.addRow("Table Item (SKU)", self.item_dd)
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

    def _set_selected_item(self, item_id):
        if not item_id:
            return
        for i in range(self.item_dd.count()):
            if self.item_dd.itemData(i) == item_id:
                self.item_dd.setCurrentIndex(i)
                break

    def on_save(self):
        item_id = self.item_dd.currentData()
        if not item_id:
            QMessageBox.warning(self, "Missing", "Please select a table item.")
            return

        data = {
            "item_id": int(item_id),
            "piece_count": int(self.piece_count.value()),
            "location": self.location.text().strip() or None,
            "notes": self.notes.text().strip() or None,
        }
        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class TablesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Tables Inventory (Pieces)")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Table Stock")
        self.add_btn.clicked.connect(self.add_entry)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Name", "Pieces", "Location", "Notes"
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
            rows = list_tables(db)
            for r, row in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row.id)))
                self.table.setItem(r, 1, QTableWidgetItem(row.item.sku))
                self.table.setItem(r, 2, QTableWidgetItem(row.item.name))
                self.table.setItem(r, 3, QTableWidgetItem(str(row.piece_count or 0)))
                self.table.setItem(r, 4, QTableWidgetItem(row.location or ""))
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
        dlg = AddEditTableDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_table_entry(db, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save:\n{e}")

    def edit_entry(self, entry_id):
        with get_db() as db:
            entry = get_table_entry(db, entry_id)
            if not entry:
                return
            existing = {
                "item_id": entry.item_id,
                "piece_count": entry.piece_count,
                "location": entry.location,
                "notes": entry.notes,
            }

        dlg = AddEditTableDialog(self, existing)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    update_table_entry(db, entry_id, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update:\n{e}")

    def delete_entry(self, entry_id):
        ok = QMessageBox.question(self, "Confirm", "Delete this entry?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_table_entry(db, entry_id)
        self.load_data()
