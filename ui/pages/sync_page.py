import os
import math
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QProgressBar, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog,
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QTimer, QPointF, QPoint,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QConicalGradient, QPen, QBrush, QPixmap, QPainterPath,
)

from database.db_manager import DatabaseManager
from services.api_client import ApiClient
from services.sync_service import DataDownloader
from ui.styles import FONT_FAMILY

# ── Dark theme colors (matching load_page.html) ──
BG_DARK_1 = "#07141d"
BG_DARK_2 = "#0d2b3d"
BG_DARK_3 = "#123b4f"
PRIMARY_GREEN = "#258961"
PRIMARY_GREEN_LIGHT = "#3ba57c"
ACCENT_BLUE = "#2e90ff"
ACCENT_BLUE_LIGHT = "#63C5FF"
DANGER_RED = "#d64545"
TEXT_LIGHT = "#f8fbfc"
TEXT_MUTED = "rgba(255, 255, 255, 0.72)"
CARD_BG = "rgba(255, 255, 255, 0.08)"
CARD_BORDER = "rgba(255, 255, 255, 0.14)"

# Path to face image
_HERE = os.path.dirname(os.path.abspath(__file__))
FACE_IMAGE_PATH = os.path.join(_HERE, "..", "..", "1.png")


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


class _ClickableCard(QFrame):
    """QFrame that emits clicked signal on mouse press."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


class _GlowCircle:
    """Data for an animated glowing circle on the right panel."""
    def __init__(self, x, y, radius, color, phase):
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.phase = phase


class _ExamModal(QDialog):
    """Modal dialog for selecting exams to download."""
    download_requested = pyqtSignal(list)  # list of session dicts

    def __init__(self, sessions: list, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._sessions = sessions
        self._checkboxes = []
        self._setup_ui()
        if parent:
            self.resize(parent.size())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(5, 15, 25, 166))
        painter.end()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("examModalCard")
        card.setFixedWidth(480)
        card.setStyleSheet(f"""
            QFrame#examModalCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {CARD_BORDER};
                border-radius: 24px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 115))
        card.setGraphicsEffect(shadow)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(28, 32, 28, 28)
        layout.setSpacing(0)

        # Header
        header = QHBoxLayout()
        title = QLabel("Imtihonni tanlang")
        title.setFont(QFont("Segoe UI", 19, QFont.Weight.DemiBold))
        title.setStyleSheet("color: white; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addStretch()
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(34, 34)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.08);
                color: rgba(255,255,255,0.65);
                border: none;
                border-radius: 10px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.15);
                color: white;
            }
        """)
        close_btn.clicked.connect(self.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)
        layout.addSpacing(22)

        # Session items
        for s in self._sessions:
            item_frame = QFrame()
            item_frame.setObjectName("examItem")
            item_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            item_frame.setStyleSheet(f"""
                QFrame#examItem {{
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 14px;
                    padding: 14px 16px;
                }}
                QFrame#examItem:hover {{
                    background: rgba(46,144,255,0.14);
                    border-color: rgba(99,197,255,0.35);
                }}
            """)

            row = QHBoxLayout(item_frame)
            row.setContentsMargins(14, 10, 14, 10)
            row.setSpacing(14)

            # Icon
            icon_wrap = QLabel("\U0001f4cb")
            icon_wrap.setFixedSize(38, 38)
            icon_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_wrap.setStyleSheet("""
                background: rgba(46,144,255,0.18);
                border: 1px solid rgba(99,197,255,0.2);
                border-radius: 10px;
                font-size: 17px;
            """)
            row.addWidget(icon_wrap)

            # Info
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            name_label = QLabel(s.get("test", "Test"))
            name_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Medium))
            name_label.setStyleSheet("color: white; background: transparent; border: none;")
            info_layout.addWidget(name_label)

            meta_label = QLabel(
                f"{s.get('total_students', 0)} ta student  |  {s.get('start_date', '')}"
            )
            meta_label.setFont(QFont("Segoe UI", 12))
            meta_label.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent; border: none;")
            info_layout.addWidget(meta_label)
            row.addLayout(info_layout, stretch=1)

            # Checkbox indicator
            check_label = QLabel()
            check_label.setFixedSize(20, 20)
            check_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            check_label.setStyleSheet("""
                background: rgba(99,197,255,0.05);
                border: 1.5px solid rgba(99,197,255,0.4);
                border-radius: 6px;
            """)
            row.addWidget(check_label)

            self._checkboxes.append({
                "frame": item_frame,
                "check": check_label,
                "selected": False,
                "session": s,
            })
            item_frame.mousePressEvent = lambda e, idx=len(self._checkboxes)-1: self._toggle_item(idx)

            layout.addWidget(item_frame)
            layout.addSpacing(10)

        layout.addSpacing(10)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self._download_btn = QPushButton("Yuklab olish")
        self._download_btn.setFixedHeight(46)
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        self._download_btn.setEnabled(False)
        self._download_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2aa774, stop:1 #1a8f62);
                color: white;
                border: none;
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: #258961;
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.07);
                color: rgba(255,255,255,0.3);
            }}
        """)
        self._download_btn.clicked.connect(self._on_download)
        footer.addWidget(self._download_btn, stretch=1)

        cancel_btn = QPushButton("Bekor qilish")
        cancel_btn.setFixedHeight(46)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFont(QFont("Segoe UI", 14))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.07);
                color: rgba(255,255,255,0.7);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.13);
                color: white;
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn, stretch=1)

        layout.addLayout(footer)
        outer.addWidget(card)

    def _toggle_item(self, idx):
        item = self._checkboxes[idx]
        item["selected"] = not item["selected"]
        if item["selected"]:
            item["check"].setStyleSheet("""
                background: rgba(46,144,255,0.85);
                border: 1.5px solid #63C5FF;
                border-radius: 6px;
                color: white;
                font-size: 12px;
            """)
            item["check"].setText("\u2713")
            item["frame"].setStyleSheet(f"""
                QFrame#examItem {{
                    background: rgba(46,144,255,0.12);
                    border: 1px solid rgba(99,197,255,0.3);
                    border-radius: 14px;
                    padding: 14px 16px;
                }}
            """)
        else:
            item["check"].setStyleSheet("""
                background: rgba(99,197,255,0.05);
                border: 1.5px solid rgba(99,197,255,0.4);
                border-radius: 6px;
            """)
            item["check"].setText("")
            item["frame"].setStyleSheet(f"""
                QFrame#examItem {{
                    background: rgba(255,255,255,0.06);
                    border: 1px solid rgba(255,255,255,0.10);
                    border-radius: 14px;
                    padding: 14px 16px;
                }}
            """)

        any_selected = any(c["selected"] for c in self._checkboxes)
        self._download_btn.setEnabled(any_selected)

    def _on_download(self):
        selected = [c["session"] for c in self._checkboxes if c["selected"]]
        self.download_requested.emit(selected)
        self.accept()


class SyncPage(QWidget):
    sync_complete = pyqtSignal()
    logout_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._api = ApiClient()
        self._db = DatabaseManager()
        self._downloader = None
        self._sessions: list[dict] = []
        self._face_pixmap = None
        self._anim_angle = 0.0
        self._bg_anim_angle = 0.0
        self._glow_phase = 0.0
        self._particles: list[_Particle] = []

        # Glowing circles for right panel
        self._glow_circles = [
            _GlowCircle(0.65, 0.25, 210, QColor(46, 144, 255, 56), 0.0),
            _GlowCircle(0.85, 0.7, 130, QColor(46, 144, 255, 45), 1.0),
            _GlowCircle(0.2, 0.8, 80, QColor(46, 144, 255, 35), 2.0),
        ]

        self._load_face_image()
        self._init_particles(60)
        self._setup_ui()
        self._start_animations()

    def _load_face_image(self):
        path = os.path.normpath(FACE_IMAGE_PATH)
        if os.path.exists(path):
            self._face_pixmap = QPixmap(path)

    def _init_particles(self, count: int):
        w = max(self.width(), 1920)
        h = max(self.height(), 1080)
        self._particles = [_Particle(w, h) for _ in range(count)]

    def _start_animations(self):
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start(33)  # ~30 FPS (same as login page)

    def _tick_animation(self):
        self._anim_angle = (self._anim_angle + 1.125) % 360.0
        self._bg_anim_angle += 0.004
        self._glow_phase += 0.05
        w, h = self.width(), self.height()
        for p in self._particles:
            p.update(w, h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Animated gradient background (same as login page) ──
        offset = math.sin(self._bg_anim_angle) * 0.15
        gradient = QLinearGradient(0, 0, w * (0.6 + offset), h)
        gradient.setColorAt(0.0, QColor("#0a1628"))
        gradient.setColorAt(0.3, QColor("#0D47A1"))
        gradient.setColorAt(0.6, QColor("#1565C0"))
        gradient.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), gradient)

        # ── Radial glow accent (subtle pulsing) ──
        pulse = 0.7 + 0.3 * math.sin(self._bg_anim_angle * 2)
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

        # ── Connecting lines between close particles ──
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

        # ── Right panel area (use actual widget geometry) ──
        if hasattr(self, '_right_panel') and self._right_panel.isVisible():
            rg = self._right_panel.geometry()
            if rg.width() > 100:
                self._paint_right_panel(painter, rg.x(), rg.y(), rg.width(), rg.height())

        painter.end()

    def _paint_right_panel(self, painter: QPainter, rx, ry, rw, rh):
        """Draw the decorative right panel with grid, glows, and hero card."""
        # Panel background
        path = QPainterPath()
        path.addRoundedRect(float(rx), float(ry), float(rw), float(rh), 28, 28)

        panel_bg = QLinearGradient(rx, ry, rx + rw, ry + rh)
        panel_bg.setColorAt(0.0, QColor(255, 255, 255, 15))
        panel_bg.setColorAt(1.0, QColor(255, 255, 255, 5))
        painter.fillPath(path, panel_bg)

        # Panel border
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.drawPath(path)

        painter.save()
        painter.setClipPath(path)

        # ── Grid lines ──
        grid_pen = QPen(QColor(255, 255, 255, 9), 1)
        painter.setPen(grid_pen)
        grid_size = 42
        for x in range(rx, rx + rw, grid_size):
            painter.drawLine(x, ry, x, ry + rh)
        for y in range(ry, ry + rh, grid_size):
            painter.drawLine(rx, y, rx + rw, y)

        # ── Glowing circles ──
        for circle in self._glow_circles:
            scale = 1.0 + 0.08 * math.sin(self._glow_phase + circle.phase)
            cx = rx + int(circle.x * rw)
            cy = ry + int(circle.y * rh)
            r = int(circle.radius * scale)

            glow = QRadialGradient(cx, cy, r)
            c = QColor(circle.color)
            c.setAlpha(int(56 * (0.65 + 0.35 * math.sin(self._glow_phase + circle.phase))))
            glow.setColorAt(0.0, c)
            glow.setColorAt(0.7, QColor(c.red(), c.green(), c.blue(), 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(QPoint(cx, cy), r, r)

        # ── Hero card (centered) ──
        card_w = min(int(rw * 0.82), 620)
        card_h = int(card_w * 1.08)
        card_x = rx + (rw - card_w) // 2
        card_y = ry + (rh - card_h) // 2

        # Rotating conic gradient border
        conic_center_x = card_x + card_w // 2
        conic_center_y = card_y + card_h // 2
        conic = QConicalGradient(conic_center_x, conic_center_y, self._anim_angle)
        conic.setColorAt(0.0, QColor(0, 0, 0, 0))
        conic.setColorAt(0.14, QColor(46, 144, 255, 56))
        conic.setColorAt(0.28, QColor(0, 0, 0, 0))
        conic.setColorAt(0.50, QColor(37, 137, 97, 51))
        conic.setColorAt(0.67, QColor(0, 0, 0, 0))
        conic.setColorAt(0.89, QColor(228, 239, 242, 25))
        conic.setColorAt(1.0, QColor(0, 0, 0, 0))

        # Outer card (border ring)
        outer_path = QPainterPath()
        outer_path.addRoundedRect(float(card_x), float(card_y),
                                   float(card_w), float(card_h), 34, 34)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(conic)
        painter.drawPath(outer_path)

        # Inner card background
        inner_margin = 13
        inner_x = card_x + inner_margin
        inner_y = card_y + inner_margin
        inner_w = card_w - 2 * inner_margin
        inner_h = card_h - 2 * inner_margin

        inner_path = QPainterPath()
        inner_path.addRoundedRect(float(inner_x), float(inner_y),
                                   float(inner_w), float(inner_h), 28, 28)

        inner_bg = QLinearGradient(inner_x, inner_y, inner_x, inner_y + inner_h)
        inner_bg.setColorAt(0.0, QColor(7, 24, 34, 224))
        inner_bg.setColorAt(1.0, QColor(12, 37, 52, 240))
        painter.fillPath(inner_path, inner_bg)

        # Radial highlight inside
        inner_glow = QRadialGradient(inner_x + inner_w * 0.5, inner_y + inner_h * 0.4,
                                      inner_w * 0.45)
        inner_glow.setColorAt(0.0, QColor(46, 144, 255, 36))
        inner_glow.setColorAt(1.0, QColor(46, 144, 255, 0))
        painter.fillPath(inner_path, inner_glow)

        # Inner border
        painter.setPen(QPen(QColor(255, 255, 255, 25), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(inner_path)

        # ── Face image (larger, centered) ──
        if self._face_pixmap and not self._face_pixmap.isNull():
            painter.save()
            painter.setClipPath(inner_path)
            scaled = self._face_pixmap.scaled(
                inner_w, inner_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            px = inner_x + (inner_w - scaled.width()) // 2
            py = inner_y + (inner_h - scaled.height()) // 2
            painter.drawPixmap(px, py, scaled)
            painter.restore()

        # ── Top badge ──
        painter.setPen(Qt.PenStyle.NoPen)
        badge_text = "AI Scan Interface"
        badge_font = QFont("Segoe UI", 11)
        badge_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
        painter.setFont(badge_font)
        fm = painter.fontMetrics()
        tw = fm.horizontalAdvance(badge_text) + 28
        th = fm.height() + 20

        badge_x = inner_x + inner_w - tw - 20
        badge_y = inner_y + 20
        badge_path = QPainterPath()
        badge_path.addRoundedRect(float(badge_x), float(badge_y),
                                   float(tw), float(th), 14, 14)
        painter.fillPath(badge_path, QColor(228, 239, 242, 20))
        painter.setPen(QPen(QColor(228, 239, 242, 46), 1))
        painter.drawPath(badge_path)
        painter.setPen(QColor(228, 239, 242))
        painter.drawText(badge_x, badge_y, tw, th,
                          Qt.AlignmentFlag.AlignCenter, badge_text)

        # ── Bottom badge ──
        badge2_text = "Biometric Identity Verification"
        painter.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        fm2 = painter.fontMetrics()
        tw2 = fm2.horizontalAdvance(badge2_text) + 32
        th2 = fm2.height() + 20

        badge2_x = inner_x + 22
        badge2_y = inner_y + inner_h - th2 - 22
        badge2_path = QPainterPath()
        badge2_path.addRoundedRect(float(badge2_x), float(badge2_y),
                                    float(tw2), float(th2), 20, 20)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillPath(badge2_path, QColor(37, 137, 97, 41))
        painter.setPen(QPen(QColor(37, 137, 97, 82), 1))
        painter.drawPath(badge2_path)
        painter.setPen(QColor(223, 247, 238))
        painter.drawText(badge2_x, badge2_y, tw2, th2,
                          Qt.AlignmentFlag.AlignCenter, badge2_text)

        painter.restore()

    def _setup_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(24)

        # ══════════════════════════════════════
        # LEFT PANEL - glassmorphism action card
        # ══════════════════════════════════════
        left_panel = QFrame()
        left_panel.setObjectName("leftPanel")
        left_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_panel.setStyleSheet(f"""
            QFrame#leftPanel {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {CARD_BORDER};
                border-radius: 28px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 14)
        shadow.setColor(QColor(0, 0, 0, 72))
        left_panel.setGraphicsEffect(shadow)

        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(30, 36, 30, 30)
        left_layout.setSpacing(0)

        # ── Brand section ──
        brand_layout = QHBoxLayout()
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.setSpacing(18)

        # Logo image
        logo_path = os.path.join(_HERE, "..", "..", "images", "logo_bba.png")
        logo_label = QLabel()
        logo_label.setFixedSize(120, 100)
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("background: transparent; border: none;")
        logo_pixmap = QPixmap(os.path.normpath(logo_path))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(
                120, 100,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        brand_layout.addWidget(logo_label)

        # Brand text
        brand_text_layout = QVBoxLayout()
        brand_text_layout.setSpacing(6)

        brand_title = QLabel("BILIM VA MALAKALARNI\nBAHOLASH AGENTLIGI")
        brand_title.setFont(QFont("Segoe UI", 48, QFont.Weight.Bold))
        brand_title.setStyleSheet("color: #E4EFF2; background: transparent; border: none; letter-spacing: 0.6px;")
        brand_text_layout.addWidget(brand_title)

        brand_layout.addLayout(brand_text_layout)
        left_layout.addLayout(brand_layout)
        left_layout.addSpacing(70)
        left_panel.setLayout(left_layout)

        # ── Action buttons ──

        # 1. Download button (blue/secondary)
        self._download_action_btn = self._create_action_button(
            icon_text="\u2B07",
            label="BAZANI YUKLAB OLISH",
            hint="Serverdan ma'lumotlarni yuklab olish",
            icon_bg="rgba(52,161,255,0.18)",
            icon_border="rgba(99,197,255,0.18)",
            icon_color="#63C5FF",
            border_color="rgba(52,161,255,0.22)",
            hover_border="rgba(99,197,255,0.42)",
            hover_bg="rgba(52,161,255,0.08)",
        )
        self._download_action_btn.clicked.connect(self._on_download_clicked)
        left_layout.addWidget(self._download_action_btn)
        left_layout.addSpacing(16)

        # 2. Face Recognition button (green/primary)
        face_rec_btn = self._create_action_button(
            icon_text="\U0001f9d1",
            label="FACE RECOGNITION",
            hint="Biometrik yuzni aniqlash tizimi",
            icon_bg="rgba(37,137,97,0.2)",
            icon_border="rgba(56,217,169,0.2)",
            icon_color="#38d9a9",
            border_color="rgba(37,137,97,0.28)",
            hover_border="rgba(56,217,169,0.42)",
            hover_bg="rgba(37,137,97,0.08)",
        )
        face_rec_btn.clicked.connect(self.sync_complete.emit)
        left_layout.addWidget(face_rec_btn)
        left_layout.addSpacing(32)

        # Note text
        note = QLabel("\u2022  Testlar tugagach bazani tozalash mumkin")
        note.setFont(QFont("Segoe UI", 12))
        note.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent; border: none;")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(note)
        left_layout.addSpacing(16)

        # 3. Delete button (red/danger)
        delete_btn = self._create_action_button(
            icon_text="\U0001f5d1",
            label="BAZANI TOZALASH",
            hint="Vaqtinchalik ma'lumotlarni o'chirish",
            icon_bg="rgba(214,69,69,0.18)",
            icon_border="rgba(255,100,100,0.18)",
            icon_color="#ff7c7c",
            border_color="rgba(214,69,69,0.24)",
            hover_border="rgba(255,100,100,0.38)",
            hover_bg="rgba(214,69,69,0.07)",
        )
        delete_btn.clicked.connect(self._on_delete_clicked)
        left_layout.addWidget(delete_btn)

        left_layout.addSpacing(20)

        # ── Progress bar (hidden by default) ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: rgba(255,255,255,0.1);
            }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACCENT_BLUE}, stop:1 #38d9a9);
                border-radius: 4px;
            }}
        """)
        left_layout.addWidget(self.progress_bar)

        # ── Status label ──
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 13))
        self.status_label.setStyleSheet("color: rgba(255,255,255,0.6); background: transparent; border: none;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        left_layout.addWidget(self.status_label)

        left_layout.addStretch()

        # ── Logout button at bottom ──
        logout_btn = QPushButton("Chiqish")
        logout_btn.setFixedHeight(42)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.6);
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(214,69,69,0.15);
                color: #ff7c7c;
                border-color: rgba(214,69,69,0.3);
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)
        left_layout.addWidget(logout_btn)

        root.addWidget(left_panel, stretch=1)

        # Right panel placeholder (painted in paintEvent)
        self._right_panel = QFrame()
        self._right_panel.setObjectName("rightPanel")
        self._right_panel.setStyleSheet("QFrame#rightPanel { background: transparent; border: none; }")
        self._right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._right_panel, stretch=1)

    def _create_action_button(self, icon_text, label, hint,
                               icon_bg, icon_border, icon_color,
                               border_color, hover_border, hover_bg):
        """Create a styled action button matching the HTML design."""
        btn = _ClickableCard()
        btn.setObjectName("actionBtn")
        btn.setFixedHeight(110)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QFrame#actionBtn {{
                background: rgba(255,255,255,0.055);
                border: 1px solid {border_color};
                border-radius: 20px;
            }}
            QFrame#actionBtn:hover {{
                border-color: {hover_border};
                background: {hover_bg};
            }}
        """)

        # Internal layout
        layout = QHBoxLayout(btn)
        layout.setContentsMargins(20, 20, 22, 20)
        layout.setSpacing(18)

        # Icon wrap
        icon_label = QLabel(icon_text)
        icon_label.setFixedSize(58, 58)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background: {icon_bg};
            border: 1px solid {icon_border};
            border-radius: 16px;
            color: {icon_color};
            font-size: 26px;
        """)
        layout.addWidget(icon_label)

        # Text wrap
        text_layout = QVBoxLayout()
        text_layout.setSpacing(6)
        text_layout.setContentsMargins(0, 0, 0, 0)

        label_widget = QLabel(label)
        label_widget.setFont(QFont("Segoe UI", 16, QFont.Weight.DemiBold))
        label_widget.setStyleSheet("color: white; background: transparent; border: none; letter-spacing: 0.5px;")
        text_layout.addWidget(label_widget)

        hint_widget = QLabel(hint)
        hint_widget.setFont(QFont("Segoe UI", 13))
        hint_widget.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent; border: none;")
        text_layout.addWidget(hint_widget)

        layout.addLayout(text_layout, stretch=1)

        # Chevron
        chevron = QLabel("\u203A")
        chevron.setFont(QFont("Segoe UI", 26))
        chevron.setStyleSheet("color: rgba(255,255,255,0.35); background: transparent; border: none;")
        layout.addWidget(chevron)

        return btn

    # ══════════════════════════════════════
    # Signals / Slots
    # ══════════════════════════════════════

    def showEvent(self, event):
        super().showEvent(event)
        self._load_sessions()

    def _on_download_clicked(self):
        """Open exam selection modal."""
        if not self._sessions:
            self._load_sessions()
            if not self._sessions:
                self.status_label.setText("Aktiv testlar topilmadi")
                self.status_label.setStyleSheet(
                    "color: rgba(255,200,100,0.9); background: transparent; border: none;"
                )
                return

        modal = _ExamModal(self._sessions, parent=self)
        modal.download_requested.connect(self._start_download_sessions)
        modal.exec()

    def _on_delete_clicked(self):
        """Clear local database."""
        self._db.clear_all_data()
        self.status_label.setText("Ma'lumotlar muvaffaqiyatli tozalandi!")
        self.status_label.setStyleSheet(
            "color: #38d9a9; background: transparent; border: none; font-weight: 600;"
        )

    def _load_sessions(self):
        self.status_label.setText("Serverdan ma'lumot olinmoqda...")
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,0.6); background: transparent; border: none;"
        )

        try:
            raw_sessions = self._api.get_active_sessions()
            self._sessions = []
            for raw in raw_sessions:
                test_name = raw.get("name", "")
                test_info = raw.get("test", {})
                if test_info and test_info.get("name"):
                    test_name = f"{test_name} - {test_info['name']}"

                smenas = raw.get("smenas", [])
                mapped = {
                    "id": raw["id"],
                    "hash_key": raw.get("hash_key", ""),
                    "test": test_name,
                    "start_date": raw.get("start_date", ""),
                    "finish_date": raw.get("finish_date", ""),
                    "zone_name": raw.get("zone_name", ""),
                    "total_students": raw.get("zone_student_count", 0),
                    "is_active": 1 if raw.get("is_active") else 0,
                }
                self._sessions.append(mapped)
                self._db.upsert_test_session(mapped)

                for sm in smenas:
                    sm_mapped = {
                        "id": sm["id"],
                        "session_id": raw["id"],
                        "test_day": sm.get("day", ""),
                        "sm": sm.get("number", 0),
                        "count_st": sm.get("sm_student_count", 0),
                        "is_active": 1 if sm.get("is_active") else 0,
                    }
                    self._db.upsert_session_smena(sm_mapped)

        except Exception:
            rows = self._db.get_active_sessions()
            self._sessions = [dict(r) for r in rows]
            self.status_label.setText("Offline rejim: mahalliy ma'lumotlar yuklandi")
            self.status_label.setStyleSheet(
                "color: rgba(255,200,100,0.9); background: transparent; border: none;"
            )
            return

        if self._sessions:
            self.status_label.setText(f"{len(self._sessions)} ta aktiv test topildi")
            self.status_label.setStyleSheet(
                "color: #38d9a9; background: transparent; border: none;"
            )
        else:
            self.status_label.setText("Aktiv testlar topilmadi")

    def _start_download_sessions(self, sessions: list):
        """Download data for selected sessions."""
        if not sessions:
            return

        session = sessions[0]
        session_id = session.get("id")
        if not session_id:
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._download_action_btn.setEnabled(False)
        self.status_label.setText("Yuklab olinmoqda...")
        self.status_label.setStyleSheet(
            "color: rgba(255,255,255,0.7); background: transparent; border: none;"
        )

        self._downloader = DataDownloader(session_id, parent=self)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished_ok.connect(self._on_download_ok)
        self._downloader.error.connect(self._on_download_error)
        self._downloader.start()

    def _start_download(self):
        """Legacy: direct download for a session (used if modal bypassed)."""
        if self._sessions:
            self._start_download_sessions([self._sessions[0]])

    def _on_progress(self, current, total):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)

    def _on_download_ok(self, loaded: int, skipped: int):
        if skipped > 0:
            self.status_label.setText(
                f"{loaded} ta yuklandi, {skipped} ta yuklanmadi"
            )
            self.status_label.setStyleSheet(
                "color: rgba(255,200,100,0.9); background: transparent; border: none; font-weight: 600;"
            )
        else:
            self.status_label.setText(f"{loaded} ta student muvaffaqiyatli yuklandi!")
            self.status_label.setStyleSheet(
                "color: #38d9a9; background: transparent; border: none; font-weight: 600;"
            )
        self.progress_bar.setVisible(False)
        self._download_action_btn.setEnabled(True)

    def _on_download_error(self, err):
        self.status_label.setText(f"Xatolik: {err}")
        self.status_label.setStyleSheet(
            "color: #ff7c7c; background: transparent; border: none; font-weight: 600;"
        )
        self.progress_bar.setVisible(False)
        self._download_action_btn.setEnabled(True)
