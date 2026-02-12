# src/ui/pages/dashboard.py
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.db.session import get_db
from src.db.dashboard_repo import get_dashboard_totals
from src.ui.signals import signals


class ClickableCard(QFrame):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _card(title: str) -> tuple[ClickableCard, QLabel]:
    c = ClickableCard()
    c.setObjectName("dashCard")
    c.setProperty("level", "ok")  # ✅ default level (ok/low/critical/zero)

    lay = QVBoxLayout(c)
    lay.setContentsMargins(16, 14, 16, 14)

    t = QLabel(title)
    t.setObjectName("dashTitle")
    t.setStyleSheet("font-size:14px; color:#bbb;")

    v = QLabel("—")
    v.setObjectName("dashValue")
    v.setStyleSheet("font-size:26px; font-weight:800;")
    v.setAlignment(Qt.AlignLeft)

    lay.addWidget(t)
    lay.addSpacing(6)
    lay.addWidget(v)
    return c, v


class DashboardPage(QWidget):
    """
    NOTE:
    - This page emits `navigate_requested(index)` when a card is clicked.
    - MainWindow should connect it to stack.setCurrentIndex(index).
    """
    navigate_requested = Signal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size:22px;font-weight:800;")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_totals)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        layout.addLayout(header)

        # Cards row
        row = QHBoxLayout()
        row.setSpacing(12)

        self.card_slab, self.val_slab = _card("Slabs (count)")
        self.card_slab_sqft, self.val_slab_sqft = _card("Slabs (total sqft)")
        self.card_tile, self.val_tile = _card("Tiles (boxes)")
        self.card_tile_sqft, self.val_tile_sqft = _card("Tiles (total sqft)")
        self.card_block, self.val_block = _card("Blocks (pieces)")
        self.card_table, self.val_table = _card("Tables (pieces)")

        row.addWidget(self.card_slab)
        row.addWidget(self.card_slab_sqft)
        row.addWidget(self.card_tile)
        row.addWidget(self.card_tile_sqft)
        row.addWidget(self.card_block)
        row.addWidget(self.card_table)

        layout.addLayout(row)

        # Tip + last updated
        self.tip = QLabel("Tip: Click any card to open that page.")
        self.tip.setStyleSheet("color:#9a9a9a; margin-top:8px;")
        layout.addWidget(self.tip)

        self.last_updated = QLabel("Last updated: —")
        self.last_updated.setStyleSheet("color:#7f7f7f; font-size:12px;")
        layout.addWidget(self.last_updated)

        # Empty state message
        self.empty_msg = QLabel("")
        self.empty_msg.setStyleSheet("color:#9a9a9a; margin-top:14px;")
        self.empty_msg.setWordWrap(True)
        layout.addWidget(self.empty_msg)

        layout.addStretch()

        # ✅ Card styling + low stock states (level property)
        self.setStyleSheet("""
            QFrame#dashCard {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                background: rgba(255,255,255,0.03);
            }

            /* ✅ LOW */
            QFrame#dashCard[level="low"] {
                border: 1px solid rgba(255, 204, 102, 0.55);
                background: rgba(255, 204, 102, 0.07);
            }
            QFrame#dashCard[level="low"] QLabel#dashValue {
                color: #ffcc66;
            }

            /* ✅ CRITICAL */
            QFrame#dashCard[level="critical"] {
                border: 1px solid rgba(255, 107, 107, 0.60);
                background: rgba(255, 107, 107, 0.08);
            }
            QFrame#dashCard[level="critical"] QLabel#dashValue {
                color: #ff6b6b;
            }

            /* ✅ ZERO / OUT OF STOCK */
            QFrame#dashCard[level="zero"] {
                border: 1px solid rgba(160,160,160,0.25);
                background: rgba(255,255,255,0.02);
            }
            QFrame#dashCard[level="zero"] QLabel#dashValue {
                color: #9a9a9a;
            }

            QFrame#dashCard:hover {
                border: 1px solid rgba(255,255,255,0.18);
                background: rgba(255,255,255,0.05);
            }
        """)

        # ✅ auto refresh via signals
        signals.inventory_changed.connect(self.on_inventory_changed)

        # ✅ card clicks → request navigation
        # (MainWindow will map these indexes to stack)
        self.card_slab.clicked.connect(lambda: self.navigate_requested.emit(2))
        self.card_slab_sqft.clicked.connect(lambda: self.navigate_requested.emit(2))

        self.card_tile.clicked.connect(lambda: self.navigate_requested.emit(3))
        self.card_tile_sqft.clicked.connect(lambda: self.navigate_requested.emit(3))

        self.card_block.clicked.connect(lambda: self.navigate_requested.emit(4))
        self.card_table.clicked.connect(lambda: self.navigate_requested.emit(5))

        self.load_totals()

    def on_inventory_changed(self, scope: str):
        # scope: slab/tile/block/table/items/all
        self.load_totals()

    def _set_val_int(self, label: QLabel, value: int):
        label.setText(str(int(value or 0)))

    def _set_val_float(self, label: QLabel, value: float):
        label.setText(f"{float(value or 0):.3f}")

    # ✅ low-stock helpers
    def _stock_level(self, value, low, critical):
        v = float(value or 0)
        if v <= 0:
            return "zero"
        if v <= critical:
            return "critical"
        if v <= low:
            return "low"
        return "ok"

    def _apply_level(self, card: QFrame, level: str):
        card.setProperty("level", level)
        card.style().unpolish(card)
        card.style().polish(card)
        card.update()

    def load_totals(self):
        with get_db() as db:
            t = get_dashboard_totals(db)

        self._set_val_int(self.val_slab, t["slab_count"])
        self._set_val_float(self.val_slab_sqft, t["slab_sqft"])

        self._set_val_int(self.val_tile, t["tile_boxes"])
        self._set_val_float(self.val_tile_sqft, t["tile_sqft"])

        self._set_val_int(self.val_block, t["block_pieces"])
        self._set_val_int(self.val_table, t["table_pieces"])

        # ✅ thresholds (change as you want)
        SLAB_LOW, SLAB_CRIT = 3, 1
        TILE_LOW, TILE_CRIT = 5, 2
        BLOCK_LOW, BLOCK_CRIT = 10, 5
        TABLE_LOW, TABLE_CRIT = 10, 5

        # ✅ apply levels to MAIN count cards
        self._apply_level(self.card_slab, self._stock_level(t["slab_count"], SLAB_LOW, SLAB_CRIT))
        self._apply_level(self.card_tile, self._stock_level(t["tile_boxes"], TILE_LOW, TILE_CRIT))
        self._apply_level(self.card_block, self._stock_level(t["block_pieces"], BLOCK_LOW, BLOCK_CRIT))
        self._apply_level(self.card_table, self._stock_level(t["table_pieces"], TABLE_LOW, TABLE_CRIT))

        # ✅ keep sqft cards neutral (optional)
        self._apply_level(self.card_slab_sqft, "ok")
        self._apply_level(self.card_tile_sqft, "ok")

        # last updated time
        self.last_updated.setText("Last updated: " + datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"))

        # empty state
        all_zero = (
            t["slab_count"] == 0 and t["slab_sqft"] == 0 and
            t["tile_boxes"] == 0 and t["tile_sqft"] == 0 and
            t["block_pieces"] == 0 and t["table_pieces"] == 0
        )
        if all_zero:
            self.empty_msg.setText(
                "No stock yet. Start by adding Items, then add stock in Slabs/Tiles/Blocks/Tables pages."
            )
        else:
            self.empty_msg.setText("")
