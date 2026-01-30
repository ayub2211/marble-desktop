from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

class SlabsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Slabs (Sqft + Slab Count)")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Next: Slabs inventory table + Add/Edit form"))
        layout.addStretch()
