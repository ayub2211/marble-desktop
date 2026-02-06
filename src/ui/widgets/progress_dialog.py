# src/ui/widgets/progress_dialog.py
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QHBoxLayout
from PySide6.QtCore import Qt, Signal


class ImportProgressDialog(QDialog):
    cancelled = Signal()

    def __init__(self, parent=None, title="Importing CSV..."):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.status = QLabel("Preparing import...")
        self.status.setWordWrap(True)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton("Cancel")
        btn_row.addWidget(self.cancel_btn)

        layout.addWidget(self.status)
        layout.addWidget(self.bar)
        layout.addLayout(btn_row)

        self.cancel_btn.clicked.connect(self._on_cancel)

    def _on_cancel(self):
        self.cancel_btn.setEnabled(False)
        self.status.setText("Cancelling... please wait")
        self.cancelled.emit()

    def set_progress(self, percent: int, text: str = ""):
        self.bar.setValue(max(0, min(100, int(percent))))
        if text:
            self.status.setText(text)
