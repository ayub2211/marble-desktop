from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class TablesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Tables (Piece)")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Next: Tables products + sales/purchase flow"))
        layout.addStretch()
