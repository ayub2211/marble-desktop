from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class TilesPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Tiles (Sqft + Box)")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Next: Tiles inventory table + box conversion"))
        layout.addStretch()
