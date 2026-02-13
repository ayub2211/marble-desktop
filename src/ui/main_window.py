# src/ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget,
    QStackedWidget
)

from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.items import ItemsPage

# Inventory pages
from src.ui.pages.slabs import SlabsPage
from src.ui.pages.tiles import TilesPage
from src.ui.pages.blocks import BlocksPage
from src.ui.pages.tables import TablesPage

# ✅ NEW: Purchases page
from src.ui.pages.purchases import PurchasesPage
from src.ui.pages.ledger import LedgerPage
from src.ui.pages.sales import SalesPage
from src.ui.pages.location_stock_report import LocationStockReportPage


# ✅ NEW: Adjustment page
from src.ui.pages.adjustments import AdjustmentsPage
from src.ui.pages.returns import ReturnsPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Marble Inventory")
        self.resize(1100, 650)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.menu = QListWidget()
        self.menu.setFixedWidth(220)
        self.menu.addItems([
            "Dashboard",          # 0
            "Items / Products",   # 1
            "Slabs (Stock)",      # 2
            "Tiles (Stock)",      # 3
            "Blocks (Stock)",     # 4
            "Tables (Stock)",     # 5
            "Purchases",  #6
            "Ledger", # 7 ✅ NEW (kept last so indexes don't break)
            "Sales", # 8 ✅ 
            "Adjustments", # 9 ✅ 
            "Returns", # 10
            "Stock Report (By Location)", # 11 ✅ 
        ])
        self.menu.setCurrentRow(0)

        # Content
        self.stack = QStackedWidget()

        # ✅ Keep instance (important for signals + refresh)
        self.dashboard_page = DashboardPage()

        self.stack.addWidget(self.dashboard_page)  # 0
        self.stack.addWidget(ItemsPage("ALL"))     # 1
        self.stack.addWidget(SlabsPage())          # 2
        self.stack.addWidget(TilesPage())          # 3
        self.stack.addWidget(BlocksPage())         # 4
        self.stack.addWidget(TablesPage())         # 5
        self.stack.addWidget(PurchasesPage())      # 6 ✅ NEW
        self.stack.addWidget(LedgerPage())         # 7
        self.stack.addWidget(SalesPage())         # 8
        self.stack.addWidget(AdjustmentsPage())   # 9
        self.stack.addWidget(ReturnsPage())         # 10
        self.stack.addWidget(LocationStockReportPage()) #11

        # ✅ Sidebar navigation
        self.menu.currentRowChanged.connect(self.on_menu_change)

        # ✅ Dashboard cards navigation (click card -> open page)
        self.dashboard_page.navigate_requested.connect(self.go_to_index)

        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def on_menu_change(self, index: int):
        self.stack.setCurrentIndex(index)

        # Optional: whenever user returns to dashboard, refresh totals
        if index == 0 and hasattr(self, "dashboard_page"):
            try:
                self.dashboard_page.load_totals()
            except Exception:
                pass

    def go_to_index(self, index: int):
        """
        ✅ Real fix:
        - stack change
        - sidebar highlight also moves (back feeling solved)
        """
        if 0 <= index < self.stack.count():
            self.menu.setCurrentRow(index)
