from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QStackedWidget, QLabel
)
from PySide6.QtCore import Qt

from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.items import ItemsPage
from src.ui.pages.slabs import SlabsPage
from src.ui.pages.tiles import TilesPage
from src.ui.pages.blocks import BlocksPage
from src.ui.pages.tables import TablesPage


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
            "Dashboard",
            "Items",
            "Slabs",
            "Tiles",
            "Blocks",
            "Tables",
        ])
        self.menu.setCurrentRow(0)

        # Content area
        self.stack = QStackedWidget()
        self.stack.addWidget(DashboardPage())  # index 0
        self.stack.addWidget(ItemsPage())      # index 1
        self.stack.addWidget(SlabsPage())      # index 2
        self.stack.addWidget(TilesPage())      # index 3
        self.stack.addWidget(BlocksPage())     # index 4
        self.stack.addWidget(TablesPage())     # index 5

        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)

        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
