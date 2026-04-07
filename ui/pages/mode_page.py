import math
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath,
)

from ui.styles import COLORS, FONT_FAMILY


# ── Dark theme palette (matching login & sync pages) ──
BG_DARK_1 = "#0a1628"
BG_DARK_2 = "#0D47A1"
BG_DARK_3 = "#1565C0"
CARD_BORDER = "rgba(255, 255, 255, 0.14)"

ONLINE_COLOR = "#2E7D32"
ONLINE_LIGHT = "#43A047"
ONLINE_GLOW = QColor(46, 125, 50, 60)

OFFLINE_COLOR = "#F9A825"
OFFLINE_LIGHT = "#FBC02D"
OFFLINE_GLOW = QColor(249, 168, 37, 50)


class _Particle:
    """Floating particle for background animation."""

    def __init__(self, bounds_w: float, bounds_h: float):
        self.x = random.uniform(0, bounds_w)
        self.y = random.uniform(0, bounds_h)
        self.radius = random.uniform(2, 6)
        self.opacity = random.uniform(0.08, 0.25)
        self.speed_x = random.uniform(-0.3, 0.3)
        self.speed_y = random.uniform(-0.5, -0.1)

    def update(self, bounds_w: float, bounds_h: float):
        self.x += self.speed_x
        self.y += self.speed_y
        if self.y < -10:
            self.y = bounds_h + 10
            self.x = random.uniform(0, bounds_w)
        if self.x < -10:
            self.x = bounds_w + 10
        elif self.x > bounds_w + 10:
            self.x = -10


class _ModeCard(QFrame):
    """Glassmorphism mode selection card with glow effects."""
    clicked = pyqtSignal()

    def __init__(self, icon: str, title: str, description: str,
                 accent_color: str, accent_light: str, glow_color: QColor,
                 btn_text: str, parent=None):
        super().__init__(parent)
        self._accent = accent_color
        self._accent_light = accent_light
        self._glow_color = glow_color
        self._hover = False

        self.setFixedSize(380, 340)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("background: transparent; border: none;")

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 32)
        layout.setSpacing(16)

        # Icon circle
        icon_label = QLabel(icon)
        icon_label.setFixedSize(68, 68)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background: rgba({self._qcolor_to_rgba(glow_color, 0.25)});
            border: 1px solid rgba({self._qcolor_to_rgba(glow_color, 0.35)});
            border-radius: 34px;
            color: white;
            font-size: 30px;
        """)
        layout.addWidget(icon_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        title_label.setStyleSheet(f"""
            color: {accent_light};
            background: transparent;
            letter-spacing: 2px;
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Segoe UI", 13))
        desc_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); background: transparent;")
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc_label)

        layout.addStretch()

        # Button
        btn = QPushButton(btn_text)
        btn.setFixedHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {accent_color}, stop:1 {accent_light});
                color: white;
                border: none;
                border-radius: 14px;
                font-family: {FONT_FAMILY};
                letter-spacing: 0.5px;
            }}
            QPushButton:hover {{
                background: {accent_light};
            }}
        """)
        btn.clicked.connect(self.clicked.emit)
        layout.addWidget(btn)

    @staticmethod
    def _qcolor_to_rgba(color: QColor, alpha: float) -> str:
        return f"{color.red()}, {color.green()}, {color.blue()}, {alpha}"

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 22, 22)

        # Card background
        bg_alpha = 0.12 if self._hover else 0.08
        bg = QLinearGradient(0, 0, w, h)
        bg.setColorAt(0.0, QColor(255, 255, 255, int(255 * bg_alpha)))
        bg.setColorAt(1.0, QColor(255, 255, 255, int(255 * bg_alpha * 0.5)))
        painter.fillPath(path, bg)

        # Hover glow
        if self._hover:
            glow = QRadialGradient(w * 0.5, h * 0.3, w * 0.6)
            gc = QColor(self._glow_color)
            gc.setAlpha(55)
            glow.setColorAt(0.0, gc)
            gc.setAlpha(0)
            glow.setColorAt(1.0, gc)
            painter.save()
            painter.setClipPath(path)
            painter.fillRect(self.rect(), glow)
            painter.restore()

        # Border
        border_alpha = 0.30 if self._hover else 0.14
        pen_color = QColor(self._glow_color) if self._hover else QColor(255, 255, 255)
        pen_color.setAlphaF(border_alpha)
        painter.setPen(QPen(pen_color, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 22, 22)

        painter.end()


class ModePage(QWidget):
    mode_selected = pyqtSignal(str)  # "online" or "offline"
    logout_requested = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles: list[_Particle] = []
        self._anim_angle = 0.0
        self._setup_ui()
        self._init_particles(60)
        self._start_animations()

    def _init_particles(self, count: int):
        w = max(self.width(), 1920)
        h = max(self.height(), 1080)
        self._particles = [_Particle(w, h) for _ in range(count)]

    def _start_animations(self):
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(33)  # ~30 FPS

    def _tick(self):
        self._anim_angle += 0.004
        w, h = self.width(), self.height()
        for p in self._particles:
            p.update(w, h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Animated gradient background ──
        offset = math.sin(self._anim_angle) * 0.15
        gradient = QLinearGradient(0, 0, w * (0.6 + offset), h)
        gradient.setColorAt(0.0, QColor(BG_DARK_1))
        gradient.setColorAt(0.3, QColor(BG_DARK_2))
        gradient.setColorAt(0.6, QColor(BG_DARK_3))
        gradient.setColorAt(1.0, QColor(BG_DARK_1))
        painter.fillRect(self.rect(), gradient)

        # ── Radial glow accent ──
        pulse = 0.7 + 0.3 * math.sin(self._anim_angle * 2)
        glow = QRadialGradient(w * 0.5, h * 0.4, max(w, h) * 0.5)
        glow.setColorAt(0.0, QColor(30, 136, 229, int(40 * pulse)))
        glow.setColorAt(0.5, QColor(13, 71, 161, int(20 * pulse)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        # ── Floating particles ──
        for p in self._particles:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(255 * p.opacity)))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # ── Connecting lines ──
        pen = QPen(QColor(255, 255, 255, 15))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        for i, p1 in enumerate(self._particles):
            for p2 in self._particles[i + 1:]:
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 120:
                    alpha = int(15 * (1 - dist / 120))
                    pen.setColor(QColor(255, 255, 255, alpha))
                    painter.setPen(pen)
                    painter.drawLine(QPointF(p1.x, p1.y), QPointF(p2.x, p2.y))

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
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.15);
                color: white;
                border-color: rgba(255, 255, 255, 0.30);
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
                background: rgba(255, 255, 255, 0.08);
                color: rgba(255, 255, 255, 0.75);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(211, 47, 47, 0.25);
                color: #ff7c7c;
                border-color: rgba(211, 47, 47, 0.4);
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        top_bar.addWidget(logout_btn)

        layout.addLayout(top_bar)
        layout.addStretch(2)

        # ── Title section ──
        title = QLabel("Ish rejimini tanlang")
        title.setFont(QFont("Segoe UI", 34, QFont.Weight.Bold))
        title.setStyleSheet("color: white; background: transparent; letter-spacing: -0.5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Internet aloqasiga qarab rejimni tanlang")
        subtitle.setFont(QFont("Segoe UI", 15))
        subtitle.setStyleSheet("color: rgba(255, 255, 255, 0.55); background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(44)

        # ── Cards row ──
        cards_row = QHBoxLayout()
        cards_row.setSpacing(36)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        online_card = _ModeCard(
            icon="\U0001f310",
            title="ONLINE",
            description="Natijalar real vaqtda serverga yuboriladi.\n"
                        "Internet uzilsa avtomatik offline rejimga o'tadi.",
            accent_color=ONLINE_COLOR,
            accent_light=ONLINE_LIGHT,
            glow_color=ONLINE_GLOW,
            btn_text="Online rejim",
        )
        online_card.clicked.connect(lambda: self.mode_selected.emit("online"))
        cards_row.addWidget(online_card)

        offline_card = _ModeCard(
            icon="\U0001f4e1",
            title="OFFLINE",
            description="Barcha natijalar mahalliy bazada saqlanadi.\n"
                        "Keyinchalik internet orqali sinxronlanadi.",
            accent_color="#E65100",
            accent_light=OFFLINE_LIGHT,
            glow_color=OFFLINE_GLOW,
            btn_text="Offline rejim",
        )
        offline_card.clicked.connect(lambda: self.mode_selected.emit("offline"))
        cards_row.addWidget(offline_card)

        layout.addLayout(cards_row)

        layout.addStretch(3)
