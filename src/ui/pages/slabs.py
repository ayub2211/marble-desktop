# src/ui/pages/slabs.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QDialog,
    QFormLayout, QComboBox, QDoubleSpinBox, QSpinBox,
    QLineEdit, QMessageBox, QMenu
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.slab_repo import (
    list_slabs, create_slab_entry, update_slab_entry,
    soft_delete_slab_entry, get_slab_items, get_slab_entry
)
from src.db.location_repo import get_locations
from src.ui.signals import signals


class AddEditSlabDialog(QDialog):
    def __init__(self, parent=None, entry=None):
        super().__init__(parent)
        self.entry = entry
        self.setWindowTitle("Edit Slab Stock" if entry else "Add Slab Stock")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # ---- load items once ----
        self._items = []
        self._items_by_id = {}
        with get_db() as db:
            self._items = get_slab_items(db)
        for it in self._items:
            self._items_by_id[it.id] = it

        self.item_dd = QComboBox()
        for it in self._items:
            self.item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        self.slab_count = QSpinBox()
        self.slab_count.setRange(0, 10_000_000)

        self.total_sqft = QDoubleSpinBox()
        self.total_sqft.setRange(0, 999_999_999)
        self.total_sqft.setDecimals(3)

        # ---- locations dropdown ----
        self.location_cb = QComboBox()
        self.location_cb.addItem("Select Location...", None)
        with get_db() as db:
            locs = get_locations(db)
        for loc in locs:
            self.location_cb.addItem(loc.name, loc.id)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional notes...")

        form.addRow("Slab Item (SKU)", self.item_dd)
        form.addRow("Slab Count", self.slab_count)
        form.addRow("Total Sqft", self.total_sqft)
        form.addRow("Location", self.location_cb)
        form.addRow("Notes", self.notes)

        layout.addLayout(form)

        # auto calc hooks
        self.item_dd.currentIndexChanged.connect(self._auto_calc_sqft)
        self.slab_count.valueChanged.connect(self._auto_calc_sqft)

        btns = QHBoxLayout()
        btns.addStretch()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)

        # ---- prefill (edit) ----
        if entry:
            self._set_selected_item(entry.get("item_id"))
            self.slab_count.setValue(int(entry.get("slab_count") or 0))
            self.total_sqft.setValue(float(entry.get("total_sqft") or 0))
            self._set_selected_location(entry.get("location_id"))
            self.notes.setText(entry.get("notes") or "")

        self._auto_calc_sqft()

    def _set_selected_item(self, item_id: int):
        if not item_id:
            return
        for i in range(self.item_dd.count()):
            if self.item_dd.itemData(i) == item_id:
                self.item_dd.setCurrentIndex(i)
                break

    def _set_selected_location(self, loc_id: int):
        if loc_id is None:
            self.location_cb.setCurrentIndex(0)
            return
        for i in range(self.location_cb.count()):
            if self.location_cb.itemData(i) == loc_id:
                self.location_cb.setCurrentIndex(i)
                break

    def _auto_calc_sqft(self):
        item_id = self.item_dd.currentData()
        slabs = self.slab_count.value()
        item = self._items_by_id.get(item_id)
        if not item:
            return

        # slab_count -> total_sqft using item.sqft_per_unit (if present)
        if item.sqft_per_unit and slabs > 0:
            try:
                per = float(item.sqft_per_unit)
                self.total_sqft.setValue(per * slabs)
            except Exception:
                pass
        # else: user can manually type total_sqft (we don't block)

    def on_save(self):
        item_id = self.item_dd.currentData()
        if not item_id:
            QMessageBox.warning(self, "Missing", "Please select a slab item.")
            return

        data = {
            "item_id": item_id,
            "slab_count": int(self.slab_count.value()),
            "total_sqft": float(self.total_sqft.value()),
            "location_id": self.location_cb.currentData(),
            "notes": self.notes.text().strip() or None,
        }
        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class SlabsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Slabs Inventory (Slab Count + Sqft)")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by SKU or Name...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Slab Stock")
        self.add_btn.clicked.connect(self.add_entry)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Name", "Slab Count", "Sqft", "Location", "Notes", "Created"
        ])
        self.table.setColumnHidden(0, True)
        self.table.setColumnHidden(7, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        self.load_data()

    def load_data(self):
        self.table.setRowCount(0)
        with get_db() as db:
            rows = list_slabs(db, self.search.text().strip())
            for r, row in enumerate(rows):
                self.table.insertRow(r)
                self.table.setItem(r, 0, QTableWidgetItem(str(row.id)))
                self.table.setItem(r, 1, QTableWidgetItem(row.item.sku if row.item else ""))
                self.table.setItem(r, 2, QTableWidgetItem(row.item.name if row.item else ""))

                slab_txt = "" if row.slab_count is None else str(row.slab_count)
                sqft_txt = "" if row.total_sqft is None else f"{float(row.total_sqft):.3f}"
                loc_txt = row.location.name if getattr(row, "location", None) else ""

                self.table.setItem(r, 3, QTableWidgetItem(slab_txt))
                self.table.setItem(r, 4, QTableWidgetItem(sqft_txt))
                self.table.setItem(r, 5, QTableWidgetItem(loc_txt))
                self.table.setItem(r, 6, QTableWidgetItem(row.notes or ""))
                self.table.setItem(r, 7, QTableWidgetItem(str(getattr(row, "created_at", ""))))

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
        dlg = AddEditSlabDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_slab_entry(db, dlg.data)
                self.load_data()
                signals.inventory_changed.emit("slab")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save:\n{e}")

    def edit_entry(self, entry_id):
        with get_db() as db:
            entry = get_slab_entry(db, entry_id)
            if not entry:
                return
            existing = {
                "item_id": entry.item_id,
                "slab_count": entry.slab_count,
                "total_sqft": entry.total_sqft,
                "location_id": entry.location_id,
                "notes": entry.notes,
            }

        dlg = AddEditSlabDialog(self, existing)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    update_slab_entry(db, entry_id, dlg.data)
                self.load_data()
                signals.inventory_changed.emit("slab")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not update:\n{e}")

    def delete_entry(self, entry_id):
        ok = QMessageBox.question(self, "Confirm", "Delete this entry?") == QMessageBox.Yes
        if not ok:
            return
        with get_db() as db:
            soft_delete_slab_entry(db, entry_id)
        self.load_data()
        signals.inventory_changed.emit("slab")
