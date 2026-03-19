from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpacerItem, QSizePolicy, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient

from ui.styles import COLORS, FONT_FAMILY


class _ModeCard(QFrame):
    """Styled card for mode selection."""
    clicked = pyqtSignal()

    def __init__(self, icon: str, title: str, description: str,
                 color: str, btn_text: str, btn_bg: str, btn_fg: str = "white",
                 parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 320)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: white;
                border-radius: 18px;
                border: 2px solid #E0E0E0;
            }}
            QFrame:hover {{
                border-color: {color};
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 28)
        layout.setSpacing(14)

        # Icon circle
        icon_label = QLabel(icon)
        icon_label.setFixedSize(64, 64)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background-color: {color};
            border-radius: 32px;
            border: none;
            color: white;
            font-size: 28px;
        """)
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; border: none;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 13))
        desc_label.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Button
        btn = QPushButton(btn_text)
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {btn_bg};
                color: {btn_fg};
                border: none;
                border-radius: 14px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        btn.clicked.connect(self.clicked.emit)
        layout.addWidget(btn)


class ModePage(QWidget):
    mode_selected = pyqtSignal(str)  # "online" or "offline"
    logout_requested = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#0a1628"))
        gradient.setColorAt(0.3, QColor("#0D47A1"))
        gradient.setColorAt(0.7, QColor("#1565C0"))
        gradient.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), gradient)
        painter.end()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 30)
        layout.setSpacing(16)

        # ── Top bar: Orqaga + Chiqish ──
        top_bar = QHBoxLayout()

        back_btn = QPushButton("\u2190  Orqaga")
        back_btn.setFixedSize(140, 42)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background-color: rgba(255, 255, 255, 0.25);
                color: white;
            }}
        """)
        back_btn.clicked.connect(self.go_back.emit)
        top_bar.addWidget(back_btn)

        top_bar.addStretch()

        logout_btn = QPushButton("Chiqish")
        logout_btn.setFixedSize(130, 42)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 0.85);
                border: 1px solid rgba(255, 255, 255, 0.25);
                border-radius: 10px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background-color: {COLORS['error']};
                color: white;
                border-color: {COLORS['error']};
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        top_bar.addWidget(logout_btn)

        layout.addLayout(top_bar)
        layout.addStretch(2)

        # Title
        title = QLabel("Ish rejimini tanlang")
        title.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Internet aloqasiga qarab rejimni tanlang")
        subtitle.setFont(QFont("Segoe UI", 16))
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.7); background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(40)

        # Cards row
        cards_row = QHBoxLayout()
        cards_row.setSpacing(32)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        online_card = _ModeCard(
            icon="\U0001f310",
            title="ONLINE",
            description="Natijalar real vaqtda serverga yuboriladi.\n"
                        "Internet uzilsa avtomatik offline rejimga o'tadi.",
            color=COLORS['success'],
            btn_text="Online rejim",
            btn_bg=COLORS['success'],
        )
        online_card.clicked.connect(lambda: self.mode_selected.emit("online"))
        cards_row.addWidget(online_card)

        offline_card = _ModeCard(
            icon="\U0001f4e1",
            title="OFFLINE",
            description="Barcha natijalar mahalliy bazada saqlanadi.\n"
                        "Keyinchalik internet orqali sinxronlanadi.",
            color=COLORS['warning'],
            btn_text="Offline rejim",
            btn_bg=COLORS['warning'],
            btn_fg="#212121",
        )
        offline_card.clicked.connect(lambda: self.mode_selected.emit("offline"))
        cards_row.addWidget(offline_card)

        layout.addLayout(cards_row)

        layout.addStretch(3)
