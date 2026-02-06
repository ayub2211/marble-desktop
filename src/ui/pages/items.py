# src/ui/pages/items.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QDialog, QFormLayout, QLineEdit, QDoubleSpinBox, QMessageBox, QMenu,
    QFileDialog
)
from PySide6.QtCore import Qt, QObject, QThread, Signal

from src.db.session import get_db
from src.db.item_repo import search_items, create_item, update_item, soft_delete_item
from src.db.importer import import_items_csv
from src.ui.widgets.progress_dialog import ImportProgressDialog


class AddEditItemDialog(QDialog):
    def __init__(self, parent=None, item=None, lock_category="ALL"):
        super().__init__(parent)
        self.item = item
        self.lock_category = lock_category

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

        # ✅ dynamic rules
        self.category.currentTextChanged.connect(self._apply_rules)
        self.unit_secondary.currentTextChanged.connect(self._apply_rules)

        # ✅ load existing
        if item:
            self.sku.setText(item.get("sku", ""))
            self.name.setText(item.get("name", ""))
            self.category.setCurrentText(item.get("category", "SLAB"))
            self.unit_primary.setCurrentText(item.get("unit_primary", "sqft"))
            self.unit_secondary.setCurrentText(item.get("unit_secondary") or "")
            self.sqft_per_unit.setValue(float(item.get("sqft_per_unit") or 0))

        # ✅ lock category if page is SLAB/TILE/BLOCK/TABLE
        if self.lock_category and self.lock_category != "ALL":
            self.category.setCurrentText(self.lock_category)
            self.category.setEnabled(False)

        self._apply_rules()

    def _apply_rules(self):
        cat = self.category.currentText()
        sec = self.unit_secondary.currentText().strip()

        if cat in ("BLOCK", "TABLE"):
            self.unit_primary.setCurrentText("piece")
            self.unit_primary.setEnabled(False)

            self.unit_secondary.setCurrentText("")
            self.unit_secondary.setEnabled(False)

            self.sqft_per_unit.setValue(0)
            self.sqft_per_unit.setEnabled(False)
        else:
            # SLAB/TILE
            self.unit_primary.setEnabled(True)

            # if category is locked, still allow primary edits (optional)
            if self.lock_category and self.lock_category != "ALL":
                # category locked only; units still editable
                pass

            self.unit_secondary.setEnabled(True)

            if not sec:
                self.sqft_per_unit.setValue(0)
                self.sqft_per_unit.setEnabled(False)
            else:
                self.sqft_per_unit.setEnabled(True)

    def on_save(self):
        sku = self.sku.text().strip()
        name = self.name.text().strip()

        if not sku or not name:
            QMessageBox.warning(self, "Missing", "SKU and Name are required.")
            return

        category = self.category.currentText()
        unit_primary = self.unit_primary.currentText()
        unit_secondary = self.unit_secondary.currentText().strip() or None

        data = {
            "sku": sku,
            "name": name,
            "category": category,
            "unit_primary": unit_primary,
            "unit_secondary": unit_secondary,
            "sqft_per_unit": None
        }

        if unit_secondary:
            val = float(self.sqft_per_unit.value())
            data["sqft_per_unit"] = val if val > 0 else None

        if category in ("BLOCK", "TABLE"):
            data["unit_primary"] = "piece"
            data["unit_secondary"] = None
            data["sqft_per_unit"] = None

        self._data = data
        self.accept()

    @property
    def data(self):
        return getattr(self, "_data", None)


# ---------------------------
# Worker (runs in QThread)
# ---------------------------
class ImportWorker(QObject):
    progress = Signal(int, str)     # percent, text
    done = Signal(dict)            # result dict
    failed = Signal(str)           # error message

    def __init__(self, file_path: str, batch_size: int = 500):
        super().__init__()
        self.file_path = file_path
        self.batch_size = batch_size
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def is_cancelled(self):
        return self._cancel

    def run(self):
        try:
            with get_db() as db:
                result = import_items_csv(
                    db,
                    self.file_path,
                    mode="upsert",
                    batch_size=self.batch_size,
                    progress_cb=lambda p, t: self.progress.emit(p, t),
                    stop_flag=self.is_cancelled
                )
            self.done.emit(result)
        except Exception as e:
            self.failed.emit(str(e))


class ItemsPage(QWidget):
    """
    default_category:
      - "ALL" -> dropdown enabled
      - "SLAB"/"TILE"/"BLOCK"/"TABLE" -> dropdown locked
    """
    def __init__(self, default_category="ALL"):
        super().__init__()
        self.default_category = default_category

        layout = QVBoxLayout(self)

        title = QLabel("Items / Products")
        title.setStyleSheet("font-size:22px;font-weight:700;")
        layout.addWidget(title)

        # ---------- Top bar (NO signals yet) ----------
        top = QHBoxLayout()

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by SKU or Name...")

        self.category = QComboBox()
        self.category.addItems(["ALL", "SLAB", "TILE", "BLOCK", "TABLE"])
        self.category.setCurrentText(default_category)

        # lock dropdown if specific page
        if default_category != "ALL":
            self.category.setEnabled(False)

        self.import_btn = QPushButton("Import CSV")
        self.add_btn = QPushButton("+ Add Item")

        top.addWidget(self.search, 2)
        top.addWidget(QLabel("Category:"))
        top.addWidget(self.category, 1)
        top.addStretch()
        top.addWidget(self.import_btn)
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        # ---------- Table (create BEFORE connecting signals) ----------
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "ID", "SKU", "Name", "Category", "Primary Unit", "Secondary Unit", "Sqft/Unit"
        ])
        self.table.setColumnHidden(0, True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.open_menu)
        layout.addWidget(self.table)

        # thread refs
        self._thread = None
        self._worker = None
        self._progress_dialog = None

        # ---------- NOW connect signals ----------
        self.search.textChanged.connect(self.load_data)
        self.category.currentTextChanged.connect(self.load_data)
        self.import_btn.clicked.connect(self.import_csv)
        self.add_btn.clicked.connect(self.add_item)

        # ---------- Initial load ----------
        self.load_data()

    def load_data(self):
        # safety guard (in case signal fires early)
        if not hasattr(self, "table") or self.table is None:
            return

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
                self.table.setItem(row, 5, QTableWidgetItem(item.unit_secondary or ""))

                sqft_txt = ""
                if item.sqft_per_unit is not None:
                    try:
                        sqft_txt = f"{float(item.sqft_per_unit):.3f}"
                    except Exception:
                        sqft_txt = str(item.sqft_per_unit)

                self.table.setItem(row, 6, QTableWidgetItem(sqft_txt))

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

    # ---------------------------
    # CSV Import with Progress
    # ---------------------------
    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select CSV file", "", "CSV Files (*.csv)")
        if not file_path:
            return

        ok = QMessageBox.question(
            self,
            "Confirm Import",
            "CSV import will UPSERT by SKU (same SKU => update + reactivate if deleted).\nContinue?"
        ) == QMessageBox.Yes
        if not ok:
            return

        self.import_btn.setEnabled(False)

        dlg = ImportProgressDialog(self, title="Importing CSV")
        self._progress_dialog = dlg

        thread = QThread(self)
        worker = ImportWorker(file_path=file_path, batch_size=500)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.progress.connect(self._on_import_progress)
        worker.done.connect(self._on_import_done)
        worker.failed.connect(self._on_import_failed)

        dlg.cancelled.connect(worker.cancel)

        worker.done.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker

        thread.start()
        dlg.exec()

    def _on_import_progress(self, percent: int, text: str):
        if self._progress_dialog:
            self._progress_dialog.set_progress(percent, text)

    def _on_import_done(self, result: dict):
        if self._progress_dialog:
            self._progress_dialog.accept()
            self._progress_dialog = None

        self.import_btn.setEnabled(True)
        self.load_data()

        inserted = result.get("inserted", 0)
        updated = result.get("updated", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", [])

        msg = (
            f"Import complete ✅\n\n"
            f"Inserted: {inserted}\n"
            f"Updated: {updated}\n"
            f"Skipped: {skipped}\n"
            f"Errors: {len(errors)}"
        )
        if errors:
            preview = "\n".join(errors[:15])
            msg += f"\n\nFirst errors:\n{preview}"
            if len(errors) > 15:
                msg += f"\n...and {len(errors)-15} more."

        QMessageBox.information(self, "CSV Import", msg)

    def _on_import_failed(self, err: str):
        if self._progress_dialog:
            self._progress_dialog.reject()
            self._progress_dialog = None

        self.import_btn.setEnabled(True)
        QMessageBox.critical(self, "Import Error", f"CSV import failed:\n{err}")

    # ---------------------------
    # CRUD
    # ---------------------------
    def add_item(self):
        dlg = AddEditItemDialog(self, lock_category=self.default_category)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    create_item(db, dlg.data)
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not save item:\n{e}")

    def edit_item(self, item_id):
        with get_db() as db:
            ItemModel = __import__("src.db.models", fromlist=["Item"]).Item
            item = db.query(ItemModel).get(item_id)
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

        dlg = AddEditItemDialog(self, existing, lock_category=self.default_category)
        if dlg.exec() == QDialog.Accepted:
            try:
                with get_db() as db:
                    update_item(db, item_id, dlg.data)
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
