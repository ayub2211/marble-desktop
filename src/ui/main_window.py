from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QListWidget,
    QStackedWidget
)

from src.ui.pages.dashboard import DashboardPage
from src.ui.pages.items import ItemsPage


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
        self.stack.addWidget(DashboardPage())
        self.stack.addWidget(ItemsPage("ALL"))
        self.stack.addWidget(ItemsPage("SLAB"))
        self.stack.addWidget(ItemsPage("TILE"))
        self.stack.addWidget(ItemsPage("BLOCK"))
        self.stack.addWidget(ItemsPage("TABLE"))

        self.menu.currentRowChanged.connect(self.stack.setCurrentIndex)

        layout.addWidget(self.menu)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
