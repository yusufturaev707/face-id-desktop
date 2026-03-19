from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QSpacerItem, QSizePolicy, QFrame,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont, QColor, QPainter, QLinearGradient

from database.db_manager import DatabaseManager
from ui.styles import COLORS, FONT_FAMILY


class SessionPage(QWidget):
    session_selected = pyqtSignal(int)  # session_sm_id
    logout_requested = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = DatabaseManager()
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(30, 20, 30, 30)
        outer.setSpacing(0)

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

        outer.addLayout(top_bar)
        outer.addStretch()

        # ── Main card ──
        card = QFrame()
        card.setObjectName("sessionCard")
        card.setFixedSize(700, 560)
        card.setStyleSheet("""
            QFrame#sessionCard {
                background-color: rgba(255, 255, 255, 245);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 100))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 36, 36, 30)
        layout.setSpacing(12)

        # Header
        header = QWidget()
        header.setStyleSheet("background: transparent;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        icon_circle = QLabel()
        icon_circle.setFixedSize(64, 64)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_dark']});
            border-radius: 32px;
            color: white;
            font-size: 28px;
        """)
        icon_circle.setText("\U0001f4cb")
        header_layout.addWidget(icon_circle, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Test tanlang")
        title.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['primary_dark']}; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title)

        subtitle = QLabel("Yuklangan testlardan kun va smenani tanlang")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(subtitle)

        layout.addWidget(header)
        layout.addSpacing(18)

        # Session list
        self.session_list = QListWidget()
        self.session_list.setMinimumHeight(220)
        self.session_list.setStyleSheet(f"""
            QListWidget {{
                border: 2px solid #E0E0E0;
                border-radius: 12px;
                background-color: #FAFAFA;
                padding: 6px;
                font-size: 15px;
                font-family: {FONT_FAMILY};
            }}
            QListWidget::item {{
                padding: 16px 16px;
                border-bottom: 1px solid #EEEEEE;
                border-radius: 8px;
                color: {COLORS['text_primary']};
            }}
            QListWidget::item:selected {{
                background-color: {COLORS['primary']};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: #E3F2FD;
            }}
        """)
        layout.addWidget(self.session_list)

        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 13))
        self.info_label.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)

        layout.addSpacing(8)

        # ── Bottom buttons ──
        self.start_btn = QPushButton("Boshlash  \u2192")
        self.start_btn.setFixedHeight(52)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.start_btn.setEnabled(False)
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['success']}, stop:1 #43A047);
                color: white;
                border: none;
                border-radius: 14px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #388E3C, stop:1 #4CAF50);
            }}
            QPushButton:pressed {{
                background: #1B5E20;
            }}
            QPushButton:disabled {{
                background: {COLORS['divider']};
                color: {COLORS['text_secondary']};
            }}
        """)
        self.start_btn.clicked.connect(self._on_start)
        layout.addWidget(self.start_btn)

        layout.addStretch()

        outer.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        self.session_list.currentRowChanged.connect(self._on_selection_changed)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_sessions()

    def _load_sessions(self):
        self.session_list.clear()
        sessions = self._db.get_active_sessions()

        for s in sessions:
            smenas = self._db.get_smenas_by_session(s["id"])
            for sm in smenas:
                students = self._db.get_students_by_smena(sm["id"])
                with_embedding = sum(1 for st in students if st["embedding"])
                text = (
                    f"{s['test']}  |  {sm['test_day']}  |  Smena: {sm['sm']}\n"
                    f"   Studentlar: {len(students)}  (embedding: {with_embedding})"
                )
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, sm["id"])
                self.session_list.addItem(item)

        if not sessions:
            self.info_label.setText("Hech qanday test topilmadi. Avval sinxronlash sahifasidan yuklang.")

    def _on_selection_changed(self, row):
        self.start_btn.setEnabled(row >= 0)
        if row >= 0:
            item = self.session_list.item(row)
            sm_id = item.data(Qt.ItemDataRole.UserRole)
            self.info_label.setText(f"Tanlangan smena ID: {sm_id}")

    def _on_start(self):
        item = self.session_list.currentItem()
        if item:
            sm_id = item.data(Qt.ItemDataRole.UserRole)
            self.session_selected.emit(sm_id)
