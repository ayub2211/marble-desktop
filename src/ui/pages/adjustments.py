# src/ui/pages/adjustments.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QDialog, QFormLayout, QLineEdit,
    QMessageBox, QComboBox, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt

from src.db.session import get_db
from src.db.location_repo import get_locations
from src.db.item_repo import get_items
from src.db.adjustments_repo import (
    create_adjustments_batch,
    list_adjustments
)
from src.ui.signals import signals
from src.ui.app_state import AppState


# =========================================================
# ADD ADJUSTMENT DIALOG
# =========================================================
class AddAdjustmentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Adjustment")
        self.setMinimumWidth(820)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Reason/Notes...")

        self.movement_dd = QComboBox()
        self.movement_dd.addItems([
            "ADJUST_IN",
            "ADJUST_OUT",
            "DAMAGE_OUT",
            "CORRECTION_IN",
            "CORRECTION_OUT",
        ])

        self.loc_dd = QComboBox()
        self.loc_dd.addItem("—", None)

        with get_db() as db:
            self._locations = get_locations(db)
            for l in self._locations:
                self.loc_dd.addItem(l.name, l.id)

            self._items = get_items(db, category="ALL")
            self._items_by_id = {it.id: it for it in self._items}

        form.addRow("Type", self.movement_dd)
        form.addRow("Location", self.loc_dd)
        form.addRow("Reason", self.reason)
        layout.addLayout(form)

        self.rows = QTableWidget(0, 5)
        self.rows.setHorizontalHeaderLabels(
            ["Item", "Category", "Qty Secondary", "Qty Primary", ""]
        )
        self.rows.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.rows)

        btn_row = QHBoxLayout()
        self.add_row_btn = QPushButton("+ Add Line")
        self.save_btn = QPushButton("Save Adjustment")
        btn_row.addWidget(self.add_row_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.save_btn)
        layout.addLayout(btn_row)

        self.add_row_btn.clicked.connect(self.add_line)
        self.save_btn.clicked.connect(self.on_save)

        self.add_line()

    def add_line(self):
        r = self.rows.rowCount()
        self.rows.insertRow(r)

        item_dd = QComboBox()
        item_dd.addItem("Select item...", None)
        for it in self._items:
            item_dd.addItem(f"{it.sku} — {it.name}", it.id)

        cat_lbl = QLabel("—")

        qty_sec = QSpinBox()
        qty_sec.setRange(0, 10_000_000)

        qty_pri = QDoubleSpinBox()
        qty_pri.setRange(0, 999_999_999)
        qty_pri.setDecimals(3)

        del_btn = QPushButton("Remove")

        self.rows.setCellWidget(r, 0, item_dd)
        self.rows.setCellWidget(r, 1, cat_lbl)
        self.rows.setCellWidget(r, 2, qty_sec)
        self.rows.setCellWidget(r, 3, qty_pri)
        self.rows.setCellWidget(r, 4, del_btn)

        def on_item_change():
            item_id = item_dd.currentData()
            it = self._items_by_id.get(item_id)
            if not it:
                cat_lbl.setText("—")
                qty_sec.setEnabled(True)
                return

            cat = (it.category or "").upper()
            cat_lbl.setText(cat)

            if cat in ("SLAB", "TILE"):
                qty_sec.setEnabled(True)
            else:
                qty_sec.setValue(0)
                qty_sec.setEnabled(False)

        def remove_row():
            row = self.rows.indexAt(del_btn.pos()).row()
            if row >= 0:
                self.rows.removeRow(row)

        item_dd.currentIndexChanged.connect(on_item_change)
        del_btn.clicked.connect(remove_row)

    def on_save(self):
        movement_type = self.movement_dd.currentText()
        location_id = self.loc_dd.currentData()
        notes = self.reason.text().strip() or None

        if not location_id:
            QMessageBox.warning(self, "Missing", "Select Location.")
            return

        rows_payload = []

        for r in range(self.rows.rowCount()):
            item_dd = self.rows.cellWidget(r, 0)
            qty_sec = self.rows.cellWidget(r, 2)
            qty_pri = self.rows.cellWidget(r, 3)

            item_id = item_dd.currentData()
            if not item_id:
                continue

            it = self._items_by_id.get(item_id)
            if not it:
                continue

            pri = float(qty_pri.value())
            if pri <= 0:
                continue

            cat = (it.category or "").upper()

            if cat in ("SLAB", "TILE"):
                sec = int(qty_sec.value())
                if sec <= 0:
                    continue
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": sec,
                    "qty_primary": pri
                })
            else:
                rows_payload.append({
                    "item_id": item_id,
                    "qty_secondary": None,
                    "qty_primary": pri
                })

        if not rows_payload:
            QMessageBox.warning(self, "Missing", "Add at least one valid row.")
            return

        self._data = {
            "movement_type": movement_type,
            "location_id": location_id,
            "notes": notes,
            "rows": rows_payload
        }

        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


# =========================================================
# ADJUSTMENTS PAGE
# =========================================================
class AdjustmentsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        title = QLabel("Adjustments")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        layout.addWidget(title)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search type / SKU / Name...")
        self.search.textChanged.connect(self.load_data)

        self.add_btn = QPushButton("+ Add Adjustment")
        self.add_btn.clicked.connect(self.add_adjustment)

        top.addWidget(self.search, 2)
        top.addStretch()
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Type", "Item", "Location", "Qty", "Created"]
        )
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.open_details)
        layout.addWidget(self.table)

        self.apply_permissions()
        self.load_data()

    def apply_permissions(self):
        can_add = AppState.can_add_transactions()
        self.add_btn.setEnabled(can_add)

    def load_data(self):
        self.table.setRowCount(0)

        with get_db() as db:
            rows = list_adjustments(db, self.search.text().strip())

            for r, a in enumerate(rows):
                self.table.insertRow(r)

                item_txt = ""
                if a.item:
                    item_txt = f"{a.item.sku} — {a.item.name}"

                loc_txt = a.location.name if a.location else ""
                qty_txt = f"{float(a.qty_primary or 0):.3f}"
                if a.qty_secondary is not None:
                    qty_txt += f" | {int(a.qty_secondary)}"

                self.table.setItem(r, 0, QTableWidgetItem(str(a.id)))
                self.table.setItem(r, 1, QTableWidgetItem(a.movement_type or ""))
                self.table.setItem(r, 2, QTableWidgetItem(item_txt))
                self.table.setItem(r, 3, QTableWidgetItem(loc_txt))
                self.table.setItem(r, 4, QTableWidgetItem(qty_txt))
                self.table.setItem(r, 5, QTableWidgetItem(str(a.created_at or "")))

    def open_details(self):
        row = self.table.currentRow()
        if row < 0:
            return

        adj_id = int(self.table.item(row, 0).text())

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Adjustment #{adj_id}")
        dlg.setMinimumWidth(400)

        layout = QVBoxLayout(dlg)

        for col in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(col).text()
            value = self.table.item(row, col).text()
            layout.addWidget(QLabel(f"<b>{header}:</b> {value}"))

        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)

        dlg.exec()

    def add_adjustment(self):
        if not AppState.can_add_transactions():
            QMessageBox.information(
                self,
                "Permission",
                "Viewer role can only view/export."
            )
            return

        dlg = AddAdjustmentDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_adjustments_batch(db, dlg.data)

                signals.inventory_changed.emit("all")
                self.load_data()
                QMessageBox.information(self, "Saved", "Adjustment saved ✅")

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
