from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.item_repo import search_items, create_item, update_item, soft_delete_item


class AddEditItemDialog(QDialog):
    def __init__(self, parent=None, item=None):
        super().__init__(parent)
        self.item = item
        self.setWindowTitle("Edit Item" if item else "Add Item")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.sku = QLineEdit()
        self.name = QLineEdit()

        self.category = QComboBox()
        self.category.addItems(["SLAB", "TILE", "BLOCK", "TABLE"])

        self.unit_primary = QComboBox()
        self.unit_primary.addItems(["sqft", "piece"])

        self.unit_secondary = QComboBox()
        self.unit_secondary.addItems(["", "slab", "box"])

        self.sqft_per_unit = QDoubleSpinBox()
        self.sqft_per_unit.setRange(0, 999999)
        self.sqft_per_unit.setDecimals(3)
        self.sqft_per_unit.setValue(0)

        form.addRow("SKU", self.sku)
        form.addRow("Name", self.name)
        form.addRow("Category", self.category)
        form.addRow("Primary Unit", self.unit_primary)
        form.addRow("Secondary Unit", self.unit_secondary)
        form.addRow("Sqft per Secondary Unit", self.sqft_per_unit)

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

        if item:
            self.sku.setText(item["sku"])
            self.name.setText(item["name"])
            self.category.setCurrentText(item["category"])
            self.unit_primary.setCurrentText(item["unit_primary"])
            self.unit_secondary.setCurrentText(item["unit_secondary"] or "")
            self.sqft_per_unit.setValue(float(item["sqft_per_unit"] or 0))

    def on_save(self):
        sku = self.sku.text().strip()
        name = self.name.text().strip()

        if not sku or not name:
            QMessageBox.warning(self, "Missing", "SKU and Name are required.")
            return

        data = {
            "sku": sku,
            "name": name,
            "category": self.category.currentText(),
            "unit_primary": self.unit_primary.currentText(),
            "unit_secondary": self.unit_secondary.currentText() or None,
            "sqft_per_unit": None
        }

        if data["unit_secondary"]:
            val = float(self.sqft_per_unit.value())
            data["sqft_per_unit"] = val if val > 0 else None

        if data["category"] in ("BLOCK", "TABLE"):
            data["unit_primary"] = "piece"
            data["unit_secondary"] = None
            data["sqft_per_unit"] = None

        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class ItemsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Items / Products")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        # Top bar
        top = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by SKU or Name...")
        self.search.textChanged.connect(self.load_data)

        self.category = QComboBox()
        self.category.addItems(["ALL", "SLAB", "TILE", "BLOCK", "TABLE"])
        self.category.currentTextChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Item")
        self.add_btn.clicked.connect(self.add_item)

        top.addWidget(self.search, 2)
        top.addWidget(QLabel("Category:"))
        top.addWidget(self.category, 1)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        # Table
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "SKU", "Name", "Category", "Unit"])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            items = search_items(db, self.search.text().strip(), self.category.currentText())
            for row, item in enumerate(items):
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(item.id)))
                self.table.setItem(row, 1, QTableWidgetItem(item.sku))
                self.table.setItem(row, 2, QTableWidgetItem(item.name))
                self.table.setItem(row, 3, QTableWidgetItem(item.category))
                self.table.setItem(row, 4, QTableWidgetItem(item.unit_primary))

    def selected_item_id(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        return int(self.table.item(row, 0).text())

    def open_menu(self, pos):
        item_id = self.selected_item_id()
        if not item_id:
            return
        menu = QMenu(self)
        edit = menu.addAction("Edit")
        delete = menu.addAction("Delete")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit:
            self.edit_item(item_id)
        elif action == delete:
            self.delete_item(item_id)

    def add_item(self):
        dlg = AddEditItemDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.data
            try:
                with get_db() as db:
                    create_item(db, data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save item:\n{e}")

    def edit_item(self, item_id):
        with get_db() as db:
            item = db.query(__import__("src.db.models", fromlist=["Item"]).Item).get(item_id)
            if not item:
                return

            existing = {
                "sku": item.sku,
                "name": item.name,
                "category": item.category,
                "unit_primary": item.unit_primary,
                "unit_secondary": item.unit_secondary,
                "sqft_per_unit": item.sqft_per_unit,
            }

        dlg = AddEditItemDialog(self, existing)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.data
            try:
                with get_db() as db:
                    update_item(db, item_id, data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update item:\n{e}")

    def delete_item(self, item_id):
        ok = QMessageBox.question(self, "Confirm", "Delete this item?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_item(db, item_id)
        self.load_data()
