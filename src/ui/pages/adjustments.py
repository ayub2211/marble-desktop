# src/ui/pages/adjustments.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QFormLayout, QComboBox, QLineEdit,
    QSpinBox, QDoubleSpinBox, QMessageBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations
from src.db.item_repo import get_items
from src.db.adjustments_repo import create_adjustment
from src.ui.signals import signals


class AddAdjustmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Adjustment")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.type_dd = QComboBox()
        self.type_dd.addItem("ADJUST_IN (Add Stock)", "ADJUST_IN")
        self.type_dd.addItem("ADJUST_OUT (Deduct Stock)", "ADJUST_OUT")
        self.type_dd.addItem("DAMAGE_OUT (Damage/Waste)", "DAMAGE_OUT")

        self.loc_dd = QComboBox()
        self.loc_dd.addItem("Select location...", None)

        self.item_dd = QComboBox()
        self.item_dd.addItem("Select item...", None)

        self.primary = QDoubleSpinBox()
        self.primary.setRange(0, 999_999_999)
        self.primary.setDecimals(3)

        self.secondary = QSpinBox()
        self.secondary.setRange(0, 10_000_000)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Reason / notes (optional)")

        with get_db() as db:
            self._locs = get_locations(db)
            for l in self._locs:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}
            for it in self._items:
                self.item_dd.addItem(f"{it.sku} — {it.name} ({it.category})", it.id)

        form.addRow("Type", self.type_dd)
        form.addRow("Location", self.loc_dd)
        form.addRow("Item", self.item_dd)
        form.addRow("Primary Qty (sqft/piece)", self.primary)
        form.addRow("Secondary Qty (slab/box)", self.secondary)
        form.addRow("Notes", self.notes)
        layout.addLayout(form)

        btns = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addStretch()
        btns.addWidget(self.cancel_btn)
        btns.addWidget(self.save_btn)
        layout.addLayout(btns)

        self.cancel_btn.clicked.connect(self.reject)
        self.save_btn.clicked.connect(self.on_save)

        self.item_dd.currentIndexChanged.connect(self._toggle_secondary)
        self._toggle_secondary()

    def _toggle_secondary(self):
        item_id = self.item_dd.currentData()
        it = self._items_by_id.get(item_id)
        if not it:
            self.secondary.setEnabled(True)
            return
        cat = (it.category or "").upper()
        # only for SLAB/TILE
        self.secondary.setEnabled(cat in ("SLAB", "TILE"))

    def on_save(self):
        movement_type = self.type_dd.currentData()
        location_id = self.loc_dd.currentData()
        item_id = self.item_dd.currentData()

        if not location_id:
            QMessageBox.warning(self, "Missing", "Select a location.")
            return
        if not item_id:
            QMessageBox.warning(self, "Missing", "Select an item.")
            return

        qty_primary = float(self.primary.value() or 0)
        qty_secondary = int(self.secondary.value() or 0)
        notes = (self.notes.text() or "").strip() or None

        self._data = {
            "movement_type": movement_type,
            "location_id": location_id,
            "item_id": item_id,
            "qty_primary": qty_primary,
            "qty_secondary": qty_secondary,
            "notes": notes
        }
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


class AdjustmentsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Adjustments")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.add_btn = QPushButton("+ Add Adjustment")
        self.add_btn.clicked.connect(self.add_adjustment)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        hint = QLabel("Use adjustments to add/deduct stock with reason. (Auto ledger + inventory update)")
        hint.setStyleSheet("color:#9a9a9a;")
        layout.addWidget(hint)

        layout.addStretch()

    def add_adjustment(self):
        dlg = AddAdjustmentDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    d = dlg.data
                    create_adjustment(
                        db,
                        location_id=d["location_id"],
                        movement_type=d["movement_type"],
                        item_id=d["item_id"],
                        qty_primary=d["qty_primary"],
                        qty_secondary=d["qty_secondary"],
                        notes=d["notes"]
                    )

                signals.inventory_changed.emit("all")
                QMessageBox.information(self, "Saved", "Adjustment saved ✅")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save adjustment:\n{e}")
