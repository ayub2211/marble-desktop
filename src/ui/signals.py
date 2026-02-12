# src/ui/signals.py
from PySide6.QtCore import QObject, Signal

class AppSignals(QObject):
    # kind: "slab" | "tile" | "block" | "table" | "items"
    inventory_changed = Signal(str)

    # NEW: dashboard cards navigation
    # target_index = QStackedWidget index
    navigate_to = Signal(int)

signals = AppSignals()
