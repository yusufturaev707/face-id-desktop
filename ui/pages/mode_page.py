import math
import os
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath, QPixmap,
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

_HERE = os.path.dirname(os.path.abspath(__file__))


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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(0)

        # ═══ MAIN GLASS CARD ═══
        card = QFrame()
        card.setObjectName("mainCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        card.setStyleSheet(f"""
            QFrame#mainCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,24), stop:1 rgba(255,255,255,12));
                border: 1px solid {CARD_BORDER};
                border-radius: 28px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(50)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 80))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # ── CARD HEADER ──
        header = QFrame()
        header.setObjectName("cardHeader")
        header.setFixedHeight(90)
        header.setStyleSheet("""
            QFrame#cardHeader {
                background: rgba(52,161,255,0.08);
                border: none;
                border-top-left-radius: 28px;
                border-top-right-radius: 28px;
                border-bottom: 1px solid rgba(255,255,255,0.07);
            }
        """)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(34, 0, 34, 0)
        header_layout.setSpacing(18)

        # Brand logo
        logo_path = os.path.join(_HERE, "..", "..", "images", "logo_bba.png")
        logo_label = QLabel()
        logo_label.setFixedSize(62, 52)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("background: transparent; border: none;")
        logo_pixmap = QPixmap(os.path.normpath(logo_path))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(
                62, 52, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        header_layout.addWidget(logo_label)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(4)
        brand_title = QLabel("Bilim va malakalarni baholash agentligi")
        brand_title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        brand_title.setStyleSheet("color: #E4EFF2; background: transparent; border: none; letter-spacing: 0.3px;")
        brand_text.addWidget(brand_title)
        header_layout.addLayout(brand_text, stretch=1)

        # Live badge
        live_badge = QFrame()
        live_badge.setFixedHeight(36)
        live_badge.setStyleSheet("""
            QFrame {
                background: rgba(52,161,255,0.14);
                border: 1px solid rgba(99,197,255,0.18);
                border-radius: 18px;
                padding: 0 14px;
            }
        """)
        lb_layout = QHBoxLayout(live_badge)
        lb_layout.setContentsMargins(14, 0, 14, 0)
        lb_layout.setSpacing(8)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet("background: #38d9a9; border: none; border-radius: 4px;")
        lb_layout.addWidget(dot)

        lb_text = QLabel("FaceID tizimi ishlayapti")
        lb_text.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        lb_text.setStyleSheet("color: #63C5FF; background: transparent; border: none; letter-spacing: 0.3px;")
        lb_layout.addWidget(lb_text)

        header_layout.addWidget(live_badge)
        card_layout.addWidget(header)

        # ── CARD BODY ──
        body = QFrame()
        body.setStyleSheet("background: transparent; border: none;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(34, 24, 34, 10)
        body_layout.setSpacing(20)

        # Body heading
        heading_layout = QHBoxLayout()
        heading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_layout.setSpacing(14)

        h_icon = QLabel("\u2699\ufe0f")
        h_icon.setFixedSize(46, 46)
        h_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_icon.setStyleSheet("""
            background: rgba(52,161,255,0.18);
            border: 1px solid rgba(99,197,255,0.18);
            border-radius: 13px;
            font-size: 20px;
        """)
        heading_layout.addWidget(h_icon)

        h_text_layout = QVBoxLayout()
        h_text_layout.setSpacing(2)
        h_title = QLabel("Ish rejimini tanlang")
        h_title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        h_title.setStyleSheet("color: white; background: transparent; border: none;")
        h_text_layout.addWidget(h_title)

        h_sub = QLabel("Internet aloqasiga qarab rejimni tanlang")
        h_sub.setFont(QFont("Segoe UI", 12))
        h_sub.setStyleSheet("color: rgba(255,255,255,0.72); background: transparent; border: none;")
        h_text_layout.addWidget(h_sub)

        heading_layout.addLayout(h_text_layout)
        body_layout.addLayout(heading_layout)

        body_layout.addStretch(2)

        # ── Mode cards ──
        cards_row = QHBoxLayout()
        cards_row.setSpacing(36)
        cards_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        online_card = _ModeCard(
            icon="\U0001f310",
            title="Online",
            description="Natijalar real vaqtda serverga yuboriladi.\n"
                        "Internet uzilsa avtomatik offline rejimga o\u2018tadi.",
            accent_color=ONLINE_COLOR,
            accent_light=ONLINE_LIGHT,
            glow_color=ONLINE_GLOW,
            btn_text="Online rejim",
        )
        online_card.clicked.connect(lambda: self.mode_selected.emit("online"))
        cards_row.addWidget(online_card)

        offline_card = _ModeCard(
            icon="\U0001f4e1",
            title="Offline",
            description="Barcha natijalar mahalliy bazada saqlanadi.\n"
                        "Keyinchalik internet orqali sinxronlanadi.",
            accent_color="#E65100",
            accent_light=OFFLINE_LIGHT,
            glow_color=OFFLINE_GLOW,
            btn_text="Offline rejim",
        )
        offline_card.clicked.connect(lambda: self.mode_selected.emit("offline"))
        cards_row.addWidget(offline_card)

        body_layout.addLayout(cards_row)
        body_layout.addStretch(3)

        card_layout.addWidget(body, stretch=1)

        # ── CARD FOOTER ──
        footer = QFrame()
        footer.setObjectName("cardFooter")
        footer.setFixedHeight(72)
        footer.setStyleSheet("""
            QFrame#cardFooter {
                background: transparent;
                border: none;
                border-top: 1px solid rgba(255,255,255,0.07);
            }
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(34, 0, 34, 0)
        footer_layout.setSpacing(14)

        # Back button
        back_btn = QPushButton("\u2190   Orqaga")
        back_btn.setFixedHeight(48)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.055);
                color: white;
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 14px;
                padding: 0 22px;
                font-family: {FONT_FAMILY};
                letter-spacing: 0.4px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.09);
                border-color: rgba(255,255,255,0.18);
            }}
        """)
        back_btn.clicked.connect(self.go_back.emit)
        footer_layout.addWidget(back_btn)

        footer_layout.addStretch()

        # Tech note
        tech_note = QLabel("\u2022  BBA")
        tech_note.setFont(QFont("Segoe UI", 11))
        tech_note.setStyleSheet("color: rgba(255,255,255,0.40); background: transparent; border: none;")
        footer_layout.addWidget(tech_note)

        footer_layout.addStretch()

        # Logout button
        logout_btn = QPushButton("Chiqish")
        logout_btn.setFixedHeight(48)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.055);
                color: rgba(255,255,255,0.70);
                border: 1px solid rgba(255,255,255,0.09);
                border-radius: 14px;
                padding: 0 22px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(214,69,69,0.18);
                color: #ff7c7c;
                border-color: rgba(214,69,69,0.35);
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        footer_layout.addWidget(logout_btn)

        card_layout.addWidget(footer)
        outer.addWidget(card)
