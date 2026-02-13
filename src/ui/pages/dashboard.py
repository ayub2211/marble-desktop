# src/ui/pages/dashboard.py
from datetime import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.db.session import get_db
from src.db.dashboard_repo import get_dashboard_totals, get_low_stock_top_items
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
    c.setProperty("level", "ok")  # ok/low/critical/zero

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
    Emits:
      navigate_requested(index:int)
    MainWindow should connect this to go_to_index(index)
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

        # ✅ Main row (cards + low stock panel)
        main_row = QHBoxLayout()
        main_row.setSpacing(12)

        # -----------------------------
        # Cards row
        # -----------------------------
        cards_col = QVBoxLayout()

        row = QHBoxLayout()
        row.setSpacing(12)

        self.card_slab, self.val_slab = _card("Slabs (count)")
        self.card_slab_sqft, self.val_slab_sqft = _card("Slabs (total sqft)")
        self.card_tile, self.val_tile = _card("Tiles (boxes)")
        self.card_tile_sqft, self.val_tile_sqft = _card("Tiles (total sqft)")
        self.card_block, self.val_block = _card("Blocks (pieces)")
        self.card_table, self.val_table = _card("Tables (pieces)")
        self.card_purchase, self.val_purchase = _card("Purchases (count)")

        row.addWidget(self.card_slab)
        row.addWidget(self.card_slab_sqft)
        row.addWidget(self.card_tile)
        row.addWidget(self.card_tile_sqft)
        row.addWidget(self.card_block)
        row.addWidget(self.card_table)
        row.addWidget(self.card_purchase)

        cards_col.addLayout(row)

        self.tip = QLabel("Tip: Click any card to open that page.")
        self.tip.setStyleSheet("color:#9a9a9a; margin-top:8px;")
        cards_col.addWidget(self.tip)

        self.last_updated = QLabel("Last updated: —")
        self.last_updated.setStyleSheet("color:#7f7f7f; font-size:12px;")
        cards_col.addWidget(self.last_updated)

        self.empty_msg = QLabel("")
        self.empty_msg.setStyleSheet("color:#9a9a9a; margin-top:14px;")
        self.empty_msg.setWordWrap(True)
        cards_col.addWidget(self.empty_msg)

        # -----------------------------
        # ✅ Low stock panel (Top 5)
        # -----------------------------
        self.low_panel = QFrame()
        self.low_panel.setObjectName("lowPanel")
        low_lay = QVBoxLayout(self.low_panel)
        low_lay.setContentsMargins(14, 14, 14, 14)
        low_lay.setSpacing(8)

        low_title = QLabel("Low Stock (Top 5)")
        low_title.setStyleSheet("font-size:14px; font-weight:800;")
        low_lay.addWidget(low_title)

        self.low_list = QLabel("—")
        self.low_list.setStyleSheet("color:#cfcfcf; font-size:12px;")
        self.low_list.setWordWrap(True)
        low_lay.addWidget(self.low_list)

        main_row.addLayout(cards_col, 4)
        main_row.addWidget(self.low_panel, 1)

        layout.addLayout(main_row)
        layout.addStretch()

        # Style
        self.setStyleSheet("""
            QFrame#dashCard {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                background: rgba(255,255,255,0.03);
            }
            QFrame#dashCard:hover {
                border: 1px solid rgba(255,255,255,0.18);
                background: rgba(255,255,255,0.05);
            }

            /* LOW */
            QFrame#dashCard[level="low"] {
                border: 1px solid rgba(255, 204, 102, 0.55);
                background: rgba(255, 204, 102, 0.07);
            }
            QFrame#dashCard[level="low"] QLabel#dashValue { color: #ffcc66; }

            /* CRITICAL */
            QFrame#dashCard[level="critical"] {
                border: 1px solid rgba(255, 107, 107, 0.60);
                background: rgba(255, 107, 107, 0.08);
            }
            QFrame#dashCard[level="critical"] QLabel#dashValue { color: #ff6b6b; }

            /* ZERO */
            QFrame#dashCard[level="zero"] {
                border: 1px solid rgba(160,160,160,0.25);
                background: rgba(255,255,255,0.02);
            }
            QFrame#dashCard[level="zero"] QLabel#dashValue { color: #9a9a9a; }

            /* ✅ low stock panel */
            QFrame#lowPanel {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                background: rgba(255,255,255,0.03);
                min-width: 240px;
            }
        """)

        # Auto refresh when inventory changes
        signals.inventory_changed.connect(self.on_inventory_changed)

        # Card clicks → navigation request
        self.card_slab.clicked.connect(lambda: self.navigate_requested.emit(2))
        self.card_slab_sqft.clicked.connect(lambda: self.navigate_requested.emit(2))

        self.card_tile.clicked.connect(lambda: self.navigate_requested.emit(3))
        self.card_tile_sqft.clicked.connect(lambda: self.navigate_requested.emit(3))

        self.card_block.clicked.connect(lambda: self.navigate_requested.emit(4))
        self.card_table.clicked.connect(lambda: self.navigate_requested.emit(5))

        # Purchases page index (agar aap menu me purchases add kar chuke ho)
        self.card_purchase.clicked.connect(lambda: self.navigate_requested.emit(6))

        self.load_totals()

    def on_inventory_changed(self, scope: str):
        self.load_totals()

    def _set_val_int(self, label: QLabel, value):
        try:
            label.setText(str(int(value or 0)))
        except Exception:
            label.setText("0")

    def _set_val_float(self, label: QLabel, value):
        try:
            label.setText(f"{float(value or 0):.3f}")
        except Exception:
            label.setText("0.000")

    def _stock_level(self, value, low, critical):
        try:
            v = float(value or 0)
        except Exception:
            v = 0.0

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
            t = get_dashboard_totals(db) or {}
            low_items = get_low_stock_top_items(db, limit=5)  # ✅ Top 5 global

        # SAFE READ
        slab_count = t.get("slab_count", t.get("slabs_count", 0))
        slab_sqft  = t.get("slab_sqft",  t.get("slabs_sqft", 0))

        tile_boxes = t.get("tile_boxes", t.get("tiles_boxes", 0))
        tile_sqft  = t.get("tile_sqft",  t.get("tiles_sqft", 0))

        block_pcs  = t.get("block_pieces", t.get("blocks_pieces", 0))
        table_pcs  = t.get("table_pieces", t.get("tables_pieces", 0))

        purchase_count = t.get("purchase_count", t.get("purchases_count", 0))

        # values
        self._set_val_int(self.val_slab, slab_count)
        self._set_val_float(self.val_slab_sqft, slab_sqft)

        self._set_val_int(self.val_tile, tile_boxes)
        self._set_val_float(self.val_tile_sqft, tile_sqft)

        self._set_val_int(self.val_block, block_pcs)
        self._set_val_int(self.val_table, table_pcs)

        self._set_val_int(self.val_purchase, purchase_count)

        # thresholds
        SLAB_LOW, SLAB_CRIT = 5, 2
        TILE_LOW, TILE_CRIT = 6, 2        # tile boxes <=2 => CRITICAL
        BLOCK_LOW, BLOCK_CRIT = 20, 10
        TABLE_LOW, TABLE_CRIT = 20, 10
        PURCHASE_LOW, PURCHASE_CRIT = 1, 0

        self._apply_level(self.card_slab, self._stock_level(slab_count, SLAB_LOW, SLAB_CRIT))
        self._apply_level(self.card_tile, self._stock_level(tile_boxes, TILE_LOW, TILE_CRIT))
        self._apply_level(self.card_block, self._stock_level(block_pcs, BLOCK_LOW, BLOCK_CRIT))
        self._apply_level(self.card_table, self._stock_level(table_pcs, TABLE_LOW, TABLE_CRIT))
        self._apply_level(self.card_purchase, self._stock_level(purchase_count, PURCHASE_LOW, PURCHASE_CRIT))

        # sqft cards neutral
        self._apply_level(self.card_slab_sqft, "ok")
        self._apply_level(self.card_tile_sqft, "ok")

        self.last_updated.setText("Last updated: " + datetime.now().strftime("%Y-%m-%d %I:%M:%S %p"))

        # empty state
        all_zero = (
            float(slab_count or 0) == 0 and float(slab_sqft or 0) == 0 and
            float(tile_boxes or 0) == 0 and float(tile_sqft or 0) == 0 and
            float(block_pcs or 0) == 0 and float(table_pcs or 0) == 0
        )
        if all_zero:
            self.empty_msg.setText(
                "No stock yet. Start by adding Items, then add stock in Purchases / Sales."
            )
        else:
            self.empty_msg.setText("")

        # ✅ low-stock panel render
        if not low_items:
            self.low_list.setText("No items found.")
        else:
            lines = []
            for x in low_items:
                lines.append(f"• {x['sku']} — {x['name']}  ({x['qty']} {x['unit']})")
            self.low_list.setText("\n".join(lines))
