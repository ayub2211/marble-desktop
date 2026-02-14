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

from src.ui.pages.purchases import PurchasesPage
from src.ui.pages.ledger import LedgerPage
from src.ui.pages.sales import SalesPage
from src.ui.pages.adjustments import AdjustmentsPage
from src.ui.pages.returns import ReturnsPage
from src.ui.pages.location_stock_report import LocationStockReportPage

from src.ui.app_state import AppState
from src.ui.pages.users import UsersPage


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.resize(1100, 650)

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar
        self.menu = QListWidget()
        self.menu.setFixedWidth(220)

        self.menu_labels = [
            "Dashboard",                 # 0
            "Items / Products",          # 1
            "Slabs (Stock)",             # 2
            "Tiles (Stock)",             # 3
            "Blocks (Stock)",            # 4
            "Tables (Stock)",            # 5
            "Purchases",                 # 6
            "Ledger",                    # 7
            "Sales",                     # 8
            "Adjustments",               # 9
            "Returns",                   # 10
            "Stock Report (By Location)" # 11
            "Users"  # 12
        ]
        self.menu.addItems(self.menu_labels)
        self.menu.setCurrentRow(0)

        # Content
        self.stack = QStackedWidget()

        self.dashboard_page = DashboardPage()
        self.stack.addWidget(self.dashboard_page)          # 0
        self.stack.addWidget(ItemsPage("ALL"))             # 1
        self.stack.addWidget(SlabsPage())                  # 2
        self.stack.addWidget(TilesPage())                  # 3
        self.stack.addWidget(BlocksPage())                 # 4
        self.stack.addWidget(TablesPage())                 # 5
        self.stack.addWidget(PurchasesPage())              # 6
        self.stack.addWidget(LedgerPage())                 # 7
        self.stack.addWidget(SalesPage())                  # 8
        self.stack.addWidget(AdjustmentsPage())            # 9
        self.stack.addWidget(ReturnsPage())                # 10
        self.stack.addWidget(LocationStockReportPage())    # 11
        self.stack.addWidget(UsersPage())                  # 12


        # Navigation
        self.menu.currentRowChanged.connect(self.on_menu_change)
        self.dashboard_page.navigate_requested.connect(self.go_to_index)

        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

        # ✅ IMPORTANT: apply permissions right after UI build
        self.apply_permissions()

    def on_menu_change(self, index: int):
        self.stack.setCurrentIndex(index)

        if index == 0 and hasattr(self, "dashboard_page"):
            try:
                self.dashboard_page.load_totals()
            except Exception:
                pass

    def go_to_index(self, index: int):
        if 0 <= index < self.stack.count():
            self.menu.setCurrentRow(index)

    def apply_permissions(self):
        """
        Admin: everything
        Staff: can add tx (purchase/sale/returns/adjustments) but cannot edit master (items)
        Viewer: view + export only (no add buttons)
        """
        user = getattr(AppState, "current_user", None)
        username = getattr(user, "username", "") if user else ""
        role = (getattr(user, "role", "") if user else "") or "Viewer"

        # ✅ Title shows who is logged in
        self.setWindowTitle(f"Marble Inventory — {username} ({role})" if username else "Marble Inventory")

        can_add_tx = AppState.can_add_transactions()
        can_edit_master = AppState.can_edit_master_data()

        # --- ItemsPage (master data) ---
        items_page = self.stack.widget(1)
        for attr in ("add_btn", "import_btn", "delete_btn", "edit_btn"):
            if hasattr(items_page, attr):
                getattr(items_page, attr).setEnabled(can_edit_master)

        # --- Purchases ---
        purchases = self.stack.widget(6)
        if hasattr(purchases, "apply_permissions"):
            purchases.apply_permissions()
        elif hasattr(purchases, "add_btn"):
            purchases.add_btn.setEnabled(can_add_tx)

        # --- Sales ---
        sales = self.stack.widget(8)
        if hasattr(sales, "apply_permissions"):
            sales.apply_permissions()
        elif hasattr(sales, "add_btn"):
            sales.add_btn.setEnabled(can_add_tx)

        # --- Adjustments ---
        adj = self.stack.widget(9)
        if hasattr(adj, "apply_permissions"):
            adj.apply_permissions()
        else:
            for attr in ("add_btn", "add_adjust_btn", "create_btn"):
                if hasattr(adj, attr):
                    getattr(adj, attr).setEnabled(can_add_tx)

        # --- Returns ---
        ret = self.stack.widget(10)
        if hasattr(ret, "apply_permissions"):
            ret.apply_permissions()
        else:
            for attr in ("add_sale_btn", "add_purchase_btn", "btn_add_sale", "btn_add_purchase"):
                if hasattr(ret, attr):
                    getattr(ret, attr).setEnabled(can_add_tx)

        # ✅ Optional: Viewer ke liye transactions pages visible रहें, but menu label add indicator
        # (aap chaho to yahan hide bhi kar sakte ho)
