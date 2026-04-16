import os
import math
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QFrame,
    QGraphicsDropShadowEffect, QSizePolicy, QDialog,
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QTimer, QPointF, QPoint, QRectF,
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
FACE_IMAGE_PATH = os.path.join(_HERE, "..", "..", "images", "face.png")


class _LoadingOverlay(QWidget):
    """Fullscreen modal overlay with spinner (loading) and result (success/warning/error) states."""

    MODE_LOADING = "loading"
    MODE_SUCCESS = "success"
    MODE_WARNING = "warning"
    MODE_ERROR = "error"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._mode = self.MODE_LOADING
        self._angle = 0.0
        self._span = 80.0
        self._span_dir = 1
        self._color_phase = 0.0
        self._pulse_phase = 0.0
        self._status_text = "Yuklab olinmoqda..."
        self._sub_text = "Iltimos, kutib turing..."
        self._result_icon = ""
        self._fade_progress = 0.0  # 0→1 for result icon scale-in

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.stop)

    def _tick(self):
        self._pulse_phase += 0.06
        if self._mode == self.MODE_LOADING:
            self._angle = (self._angle + 4.5) % 360.0
            self._span += self._span_dir * 2.5
            if self._span > 260:
                self._span_dir = -1
            elif self._span < 45:
                self._span_dir = 1
            self._color_phase = (self._color_phase + 0.015) % 1.0
        else:
            # Animate result icon scale-in
            if self._fade_progress < 1.0:
                self._fade_progress = min(1.0, self._fade_progress + 0.06)
        self.update()

    def start(self, text: str = "Yuklab olinmoqda..."):
        self._mode = self.MODE_LOADING
        self._status_text = text
        self._sub_text = "Iltimos, kutib turing..."
        self._fade_progress = 0.0
        self._auto_close_timer.stop()
        if self.parent():
            self.setGeometry(self.parent().rect())
            self.raise_()
        self.setVisible(True)
        if not self._timer.isActive():
            self._timer.start(16)

    def show_result(self, mode: str, title: str, subtitle: str = "",
                    auto_close_ms: int = 2500):
        """Switch overlay to result state (success/warning/error)."""
        self._mode = mode
        self._status_text = title
        self._sub_text = subtitle
        self._fade_progress = 0.0
        if mode == self.MODE_SUCCESS:
            self._result_icon = "\u2713"
        elif mode == self.MODE_WARNING:
            self._result_icon = "!"
        else:
            self._result_icon = "\u2717"
        self.update()
        if auto_close_ms > 0:
            self._auto_close_timer.start(auto_close_ms)

    def stop(self):
        self._timer.stop()
        self._auto_close_timer.stop()
        self.setVisible(False)

    def resizeEvent(self, event):
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Dark overlay ──
        painter.fillRect(self.rect(), QColor(5, 15, 25, 180))

        # ── Card ──
        card_w, card_h = 340, 280
        cx = (w - card_w) // 2
        cy = (h - card_h) // 2

        card_path = QPainterPath()
        card_path.addRoundedRect(float(cx), float(cy),
                                  float(card_w), float(card_h), 28, 28)

        card_bg = QLinearGradient(cx, cy, cx + card_w, cy + card_h)
        card_bg.setColorAt(0.0, QColor(255, 255, 255, 26))
        card_bg.setColorAt(1.0, QColor(255, 255, 255, 13))
        painter.fillPath(card_path, card_bg)

        # Card border
        painter.setPen(QPen(QColor(255, 255, 255, 36), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(card_path)

        # Top shimmer
        shimmer = QPainterPath()
        shimmer.moveTo(cx + 28, cy)
        shimmer.lineTo(cx + card_w - 28, cy)
        sg = QLinearGradient(cx, 0, cx + card_w, 0)

        if self._mode == self.MODE_LOADING:
            sg.setColorAt(0.0, QColor(255, 255, 255, 0))
            sg.setColorAt(0.3, QColor(255, 255, 255, 56))
            sg.setColorAt(0.5, QColor(46, 144, 255, 80))
            sg.setColorAt(0.7, QColor(255, 255, 255, 56))
            sg.setColorAt(1.0, QColor(255, 255, 255, 0))
        elif self._mode == self.MODE_SUCCESS:
            sg.setColorAt(0.0, QColor(0, 0, 0, 0))
            sg.setColorAt(0.3, QColor(56, 217, 169, 60))
            sg.setColorAt(0.5, QColor(37, 137, 97, 100))
            sg.setColorAt(0.7, QColor(56, 217, 169, 60))
            sg.setColorAt(1.0, QColor(0, 0, 0, 0))
        elif self._mode == self.MODE_WARNING:
            sg.setColorAt(0.0, QColor(0, 0, 0, 0))
            sg.setColorAt(0.3, QColor(255, 200, 100, 60))
            sg.setColorAt(0.5, QColor(249, 168, 37, 100))
            sg.setColorAt(0.7, QColor(255, 200, 100, 60))
            sg.setColorAt(1.0, QColor(0, 0, 0, 0))
        else:
            sg.setColorAt(0.0, QColor(0, 0, 0, 0))
            sg.setColorAt(0.3, QColor(255, 100, 100, 60))
            sg.setColorAt(0.5, QColor(214, 69, 69, 100))
            sg.setColorAt(0.7, QColor(255, 100, 100, 60))
            sg.setColorAt(1.0, QColor(0, 0, 0, 0))

        painter.setPen(QPen(QBrush(sg), 1))
        painter.drawPath(shimmer)

        center_x = w // 2
        icon_cy = cy + 85

        if self._mode == self.MODE_LOADING:
            self._paint_spinner(painter, center_x, icon_cy)
        else:
            self._paint_result_icon(painter, center_x, icon_cy)

        # ── Status text ──
        text_y = icon_cy + 50
        painter.setPen(QColor(255, 255, 255, 220))
        painter.setFont(QFont("Segoe UI", 15, QFont.Weight.DemiBold))
        painter.drawText(cx, text_y, card_w, 30,
                          Qt.AlignmentFlag.AlignCenter, self._status_text)

        # Sub-text
        if self._sub_text:
            sub_color = QColor(255, 255, 255, 90)
            if self._mode == self.MODE_SUCCESS:
                sub_color = QColor(56, 217, 169, 160)
            elif self._mode == self.MODE_WARNING:
                sub_color = QColor(255, 200, 100, 160)
            elif self._mode == self.MODE_ERROR:
                sub_color = QColor(255, 124, 124, 160)
            painter.setPen(sub_color)
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(cx, text_y + 34, card_w, 24,
                              Qt.AlignmentFlag.AlignCenter, self._sub_text)

        # Animated dots (loading only)
        if self._mode == self.MODE_LOADING:
            dots_y = text_y + 66
            dot_spacing = 14
            base_x = center_x - dot_spacing
            for i in range(3):
                phase = self._pulse_phase + i * 0.8
                dot_alpha = int(60 + 120 * max(0, math.sin(phase)))
                dot_r = 3.0 + 1.5 * max(0, math.sin(phase))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(46, 144, 255, dot_alpha))
                painter.drawEllipse(QPointF(base_x + i * dot_spacing, dots_y),
                                     dot_r, dot_r)

        painter.end()

    def _paint_spinner(self, painter: QPainter, cx: int, cy: int):
        size, thickness = 64, 4.5
        m = thickness / 2 + 5
        rect = QRectF(cx - size / 2 + m, cy - size / 2 + m,
                       size - 2 * m, size - 2 * m)

        pulse = 0.6 + 0.4 * math.sin(self._pulse_phase)
        painter.setPen(QPen(QColor(46, 144, 255, int(35 * pulse)),
                             thickness + 8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, int(-self._angle * 16), int(-self._span * 16))

        painter.setPen(QPen(QColor(255, 255, 255, 15), thickness,
                             Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawEllipse(rect)

        r = int(46 + 10 * self._color_phase)
        g = int(144 + 73 * self._color_phase)
        b = int(255 - 86 * self._color_phase)
        painter.setPen(QPen(QColor(r, g, b), thickness,
                             Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, int(-self._angle * 16), int(-self._span * 16))

    def _paint_result_icon(self, painter: QPainter, cx: int, cy: int):
        # Determine colors by mode
        if self._mode == self.MODE_SUCCESS:
            ring_color = QColor(37, 137, 97)
            glow_color = QColor(56, 217, 169, 50)
            icon_color = QColor(56, 217, 169)
        elif self._mode == self.MODE_WARNING:
            ring_color = QColor(249, 168, 37)
            glow_color = QColor(255, 200, 100, 45)
            icon_color = QColor(255, 200, 100)
        else:
            ring_color = QColor(214, 69, 69)
            glow_color = QColor(255, 100, 100, 45)
            icon_color = QColor(255, 124, 124)

        radius = 30
        # Ease-out scale
        t = self._fade_progress
        scale = 1.0 + 0.3 * (1.0 - t) ** 2  # starts big, settles to 1.0
        scaled_r = int(radius * scale)

        # Glow
        pulse = 0.7 + 0.3 * math.sin(self._pulse_phase)
        glow = QRadialGradient(cx, cy, scaled_r + 20)
        gc = QColor(glow_color)
        gc.setAlpha(int(gc.alpha() * pulse))
        glow.setColorAt(0.0, gc)
        gc.setAlpha(0)
        glow.setColorAt(1.0, gc)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(QPointF(cx, cy), scaled_r + 20, scaled_r + 20)

        # Ring
        ring_c = QColor(ring_color)
        ring_c.setAlpha(int(200 * min(1.0, t * 2)))
        painter.setPen(QPen(ring_c, 3.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(cx, cy), scaled_r, scaled_r)

        # Icon text
        icon_c = QColor(icon_color)
        icon_c.setAlpha(int(255 * min(1.0, t * 1.5)))
        painter.setPen(icon_c)
        font = QFont("Segoe UI", 24, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(cx - scaled_r, cy - scaled_r,
                          scaled_r * 2, scaled_r * 2,
                          Qt.AlignmentFlag.AlignCenter, self._result_icon)


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

    def __init__(self, sessions: list, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self._sessions = sessions
        self._db = db
        self._checkboxes = []
        self._setup_ui()
        if parent:
            self.resize(parent.size())

    def paintEvent(self, event):
        # Glassmorphism scrim: to'q fon + radial vignette chuqurlik beradi;
        # card ustida yumshoq shisha effekti hosil qiladi.
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 220))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    def mousePressEvent(self, event):
        # Card tashqarisiga bosilganda modal yopiladi (glass modal pattern).
        if not self.childAt(event.pos()):
            self.reject()
        super().mousePressEvent(event)

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("examModalCard")
        card.setFixedWidth(480)
        # Dark glass gradient — scrim bilan kontrast, ichki kontent yaxshi o'qiladi.
        card.setStyleSheet(f"""
            QFrame#examModalCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20,35,60,0.94), stop:1 rgba(12,22,42,0.94));
                border: 1px solid rgba(99,197,255,0.22);
                border-radius: 24px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 24)
        shadow.setColor(QColor(0, 0, 0, 140))
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

        layout.addLayout(header)
        layout.addSpacing(22)

        # Session items
        for s in self._sessions:
            session_row = self._db.get_session(s.get("id", 0))
            is_loaded = bool(session_row and session_row["is_loaded"]) if session_row else False

            item_frame = QFrame()
            item_frame.setObjectName("examItem")
            item_frame.setCursor(Qt.CursorShape.PointingHandCursor)
            if is_loaded:
                item_frame.setStyleSheet(f"""
                    QFrame#examItem {{
                        background: rgba(37,137,97,0.10);
                        border: 1px solid rgba(56,217,169,0.25);
                        border-radius: 14px;
                        padding: 14px 16px;
                    }}
                    QFrame#examItem:hover {{
                        background: rgba(37,137,97,0.18);
                        border-color: rgba(56,217,169,0.40);
                    }}
                """)
            else:
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
            icon_text = "\u2705" if is_loaded else "\U0001f4cb"
            icon_wrap = QLabel(icon_text)
            icon_wrap.setFixedSize(38, 38)
            icon_wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if is_loaded:
                icon_wrap.setStyleSheet("""
                    background: rgba(37,137,97,0.22);
                    border: 1px solid rgba(56,217,169,0.25);
                    border-radius: 10px;
                    font-size: 17px;
                """)
            else:
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

            meta_text = f"{s.get('total_students', 0)} ta student  |  {s.get('start_date', '')}"
            meta_label = QLabel(meta_text)
            meta_label.setFont(QFont("Segoe UI", 12))
            meta_label.setStyleSheet("color: rgba(255,255,255,0.5); background: transparent; border: none;")
            info_layout.addWidget(meta_label)
            row.addLayout(info_layout, stretch=1)

            # Status badge or checkbox
            if is_loaded:
                badge = QLabel("Yuklangan")
                badge.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
                badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
                badge.setFixedHeight(26)
                badge.setStyleSheet("""
                    background: rgba(37,137,97,0.25);
                    color: #38d9a9;
                    border: 1px solid rgba(56,217,169,0.3);
                    border-radius: 8px;
                    padding: 2px 10px;
                """)
                row.addWidget(badge)
            else:
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
                "check": badge if is_loaded else check_label,
                "selected": False,
                "session": s,
                "is_loaded": is_loaded,
            })
            if not is_loaded:
                item_frame.mousePressEvent = lambda e, idx=len(self._checkboxes)-1: self._toggle_item(idx)

            layout.addWidget(item_frame)
            layout.addSpacing(10)

        layout.addSpacing(10)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self._download_btn = QPushButton("\u2B73  Yuklab olish")
        self._download_btn.setFixedHeight(50)
        self._download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._download_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        self._download_btn.setEnabled(False)
        self._download_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3bbf88, stop:1 #1a8f62);
                color: #ffffff;
                border: 1px solid rgba(56,217,169,0.45);
                border-radius: 14px;
                font-family: {FONT_FAMILY};
                padding: 0 18px;
                letter-spacing: 0.3px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #45d19a, stop:1 #1fa06f);
                border-color: rgba(86,235,186,0.65);
            }}
            QPushButton:pressed {{
                background: #1a8f62;
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.28);
                border-color: rgba(255,255,255,0.06);
            }}
        """)
        self._download_btn.clicked.connect(self._on_download)
        footer.addWidget(self._download_btn, stretch=2)

        cancel_btn = QPushButton("\u2715  Bekor qilish")
        cancel_btn.setFixedHeight(50)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Medium))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: rgba(255,255,255,0.65);
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 14px;
                font-family: {FONT_FAMILY};
                padding: 0 18px;
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.06);
                color: rgba(255,255,255,0.92);
                border-color: rgba(255,255,255,0.22);
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.10);
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn, stretch=1)

        layout.addLayout(footer)
        outer.addWidget(card)

    def _toggle_item(self, idx):
        item = self._checkboxes[idx]
        if item.get("is_loaded"):
            return

        # If clicking already selected item — deselect it
        if item["selected"]:
            item["selected"] = False
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
            self._download_btn.setEnabled(False)
            return

        # Deselect previously selected item
        for i, c in enumerate(self._checkboxes):
            if c["selected"] and not c.get("is_loaded"):
                c["selected"] = False
                c["check"].setStyleSheet("""
                    background: rgba(99,197,255,0.05);
                    border: 1.5px solid rgba(99,197,255,0.4);
                    border-radius: 6px;
                """)
                c["check"].setText("")
                c["frame"].setStyleSheet(f"""
                    QFrame#examItem {{
                        background: rgba(255,255,255,0.06);
                        border: 1px solid rgba(255,255,255,0.10);
                        border-radius: 14px;
                        padding: 14px 16px;
                    }}
                """)

        # Select the clicked item
        item["selected"] = True
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
        self._download_btn.setEnabled(True)

    def _on_download(self):
        selected = [c["session"] for c in self._checkboxes if c["selected"]]
        self.download_requested.emit(selected)
        self.accept()


class SyncPage(QWidget):
    sync_complete = pyqtSignal()
    logout_requested = pyqtSignal()
    data_cleared = pyqtSignal()

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

        # ── Right panel area (map to SyncPage coordinates) ──
        if hasattr(self, '_right_panel') and self._right_panel.isVisible():
            pos = self._right_panel.mapTo(self, QPoint(0, 0))
            rw, rh = self._right_panel.width(), self._right_panel.height()
            if rw > 100:
                self._paint_right_panel(painter, pos.x(), pos.y(), rw, rh)

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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 22, 22, 22)
        outer.setSpacing(0)

        # ═══ MAIN GLASS CARD ═══
        self._card = QFrame()
        self._card.setObjectName("mainCard")
        self._card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._card.setStyleSheet(f"""
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
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
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

        # Brand text
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
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(24, 20, 24, 10)
        body_layout.setSpacing(24)

        # ── Left: Action panel (MD3 kompakt, zamonaviy) ──
        left = QFrame()
        left.setStyleSheet("background: transparent; border: none;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 14, 6, 10)
        left_layout.setSpacing(0)

        # ── Heading: ixcham 38px chip + mayda tipografiya ──
        heading_layout = QHBoxLayout()
        heading_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        heading_layout.setSpacing(12)

        h_icon = QLabel("\U0001F504")
        h_icon.setFixedSize(38, 38)
        h_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        h_icon.setStyleSheet("""
            background: rgba(52,161,255,0.16);
            border: 1px solid rgba(99,197,255,0.24);
            border-radius: 12px;
            color: #63C5FF;
            font-size: 16px;
        """)
        heading_layout.addWidget(h_icon)

        h_text_layout = QVBoxLayout()
        h_text_layout.setSpacing(1)
        h_title = QLabel("Ma\u2018lumotlarni boshqarish")
        h_title.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        h_title.setStyleSheet("color: #F0F6FA; background: transparent; border: none; letter-spacing: 0.2px;")
        h_text_layout.addWidget(h_title)

        h_sub = QLabel("Bazani yuklash, sinxronlash va tozalash")
        h_sub.setFont(QFont("Segoe UI", 10))
        h_sub.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent; border: none;")
        h_text_layout.addWidget(h_sub)

        heading_layout.addLayout(h_text_layout)
        heading_layout.addStretch()
        left_layout.addLayout(heading_layout)
        left_layout.addSpacing(20)

        # ── Asosiy amallar bo'limi ──
        section_primary = self._make_section_label("Asosiy amallar")
        left_layout.addWidget(section_primary)
        left_layout.addSpacing(10)

        # Bazani yuklab olish — MA'LUMOT YUKLASH (tonal info action)
        self._download_action_btn = self._create_action_button(
            icon_text="\U0001F4E5",
            label="Bazani yuklab olish",
            hint="Serverdan sessiyalarni olish",
            icon_bg="rgba(52,161,255,0.22)",
            icon_border="rgba(99,197,255,0.32)",
            icon_color="#7DD3FF",
            border_color="rgba(52,161,255,0.28)",
            hover_border="rgba(125,211,255,0.55)",
            hover_bg="rgba(52,161,255,0.12)",
        )
        self._download_action_btn.clicked.connect(self._on_download_clicked)
        left_layout.addWidget(self._download_action_btn)
        left_layout.addSpacing(22)

        # ── Xavfli zona bo'limi — chiziqli ajratkich bilan ──
        danger_sep = self._make_divider("Xavfli zona", accent="rgba(255,124,124,0.55)")
        left_layout.addWidget(danger_sep)
        left_layout.addSpacing(10)

        # Bazani tozalash — DESTRUCTIVE (danger action)
        delete_btn = self._create_action_button(
            icon_text="\U0001F5D1\uFE0F",
            label="Bazani tozalash",
            hint="Mahalliy ma\u2018lumotlarni butunlay o\u2018chirish",
            icon_bg="rgba(214,69,69,0.22)",
            icon_border="rgba(255,124,124,0.32)",
            icon_color="#FF9090",
            border_color="rgba(214,69,69,0.30)",
            hover_border="rgba(255,124,124,0.58)",
            hover_bg="rgba(214,69,69,0.14)",
        )
        delete_btn.clicked.connect(self._on_delete_clicked)
        left_layout.addWidget(delete_btn)
        left_layout.addSpacing(14)

        # ── Status chip — faqat matn bo'lsa ko'rinadi ──
        self.status_label = QLabel("")
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setVisible(False)
        self.status_label.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,0.72);
                background: rgba(255,255,255,0.04);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 8px 14px;
            }
        """)
        left_layout.addWidget(self.status_label)

        # Stretch pushes Face Recognition hero button to the very bottom
        left_layout.addStretch()

        # ── Face Recognition — HERO primary CTA (asosiy oldinga o'tish amali) ──
        hero_sep = QFrame()
        hero_sep.setFixedHeight(1)
        hero_sep.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 rgba(56,217,169,0.00),
                stop:0.5 rgba(56,217,169,0.35),
                stop:1 rgba(56,217,169,0.00));
            border: none;
        """)
        left_layout.addWidget(hero_sep)
        left_layout.addSpacing(14)

        face_rec_btn = self._create_hero_button(
            icon_text="\U0001F50D",
            label="Face Recognition",
            hint="Biometrik yuzni aniqlash tizimini ishga tushirish",
        )
        face_rec_btn.clicked.connect(self.sync_complete.emit)
        left_layout.addWidget(face_rec_btn)
        body_layout.addWidget(left, stretch=1)

        # ── Right: Decorative panel (painted in paintEvent) ──
        self._right_panel = QFrame()
        self._right_panel.setObjectName("rightPanel")
        self._right_panel.setStyleSheet("QFrame#rightPanel { background: transparent; border: none; }")
        self._right_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        body_layout.addWidget(self._right_panel, stretch=1)

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
        outer.addWidget(self._card)

        # Loading overlay (fullscreen modal spinner)
        self._loading_overlay = _LoadingOverlay(parent=self)

    def _make_section_label(self, text: str) -> QLabel:
        """Kompakt bo'lim sarlavhasi — yumshoq kulrang tonda."""
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        lbl.setStyleSheet("""
            color: rgba(255,255,255,0.55);
            background: transparent;
            border: none;
        """)
        return lbl

    def _make_divider(self, text: str, accent: str = "rgba(255,255,255,0.18)") -> QFrame:
        """Chiziqli ajratkich: ikki tomonlama chiziq + markazda label.
        `accent` — matn va chiziq rangi (xavfli bo'limlar uchun qizg'ish)."""
        wrap = QFrame()
        wrap.setStyleSheet("background: transparent; border: none;")
        wrap.setFixedHeight(20)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)

        left_line = QFrame()
        left_line.setFixedHeight(1)
        left_line.setStyleSheet(f"background: {accent}; border: none;")
        left_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(left_line)

        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"""
            color: {accent};
            background: transparent;
            border: none;
        """)
        row.addWidget(lbl)

        right_line = QFrame()
        right_line.setFixedHeight(1)
        right_line.setStyleSheet(f"background: {accent}; border: none;")
        right_line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        row.addWidget(right_line)

        return wrap

    def _set_status(self, text: str, variant: str = "info"):
        """Status chip'ni yangilaydi. `variant`: info / success / warning / error.
        Matn bo'sh bo'lsa chip yashiriladi."""
        if not text:
            self.status_label.setVisible(False)
            self.status_label.setText("")
            return

        palette = {
            "info":    ("rgba(255,255,255,0.80)", "rgba(255,255,255,0.04)", "rgba(255,255,255,0.08)"),
            "success": ("#38d9a9",                 "rgba(56,217,169,0.10)", "rgba(56,217,169,0.28)"),
            "warning": ("#ffc864",                 "rgba(255,200,100,0.10)", "rgba(255,200,100,0.28)"),
            "error":   ("#ff7c7c",                 "rgba(255,124,124,0.10)", "rgba(255,124,124,0.28)"),
        }
        color, bg, brd = palette.get(variant, palette["info"])
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: {bg};
                border: 1px solid {brd};
                border-radius: 10px;
                padding: 8px 14px;
                font-weight: 600;
            }}
        """)
        self.status_label.setVisible(True)

    def _create_action_button(self, icon_text, label, hint,
                               icon_bg, icon_border, icon_color,
                               border_color, hover_border, hover_bg):
        """MD3 filled-tonal action card — ixcham, zamonaviy."""
        btn = _ClickableCard()
        btn.setObjectName("actionBtn")
        btn.setFixedHeight(76)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QFrame#actionBtn {{
                background: rgba(255,255,255,0.045);
                border: 1px solid {border_color};
                border-radius: 16px;
            }}
            QFrame#actionBtn:hover {{
                border-color: {hover_border};
                background: {hover_bg};
            }}
        """)

        layout = QHBoxLayout(btn)
        layout.setContentsMargins(14, 12, 16, 12)
        layout.setSpacing(14)

        # Icon chip — 44x44, MD3 radius 12
        icon_label = QLabel(icon_text)
        icon_label.setFixedSize(44, 44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet(f"""
            background: {icon_bg};
            border: 1px solid {icon_border};
            border-radius: 12px;
            color: {icon_color};
            font-size: 20px;
        """)
        layout.addWidget(icon_label)

        # Text block
        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        label_widget = QLabel(label)
        label_widget.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        label_widget.setStyleSheet("color: #F0F6FA; background: transparent; border: none; letter-spacing: 0.2px;")
        text_layout.addWidget(label_widget)

        hint_widget = QLabel(hint)
        hint_widget.setFont(QFont("Segoe UI", 10))
        hint_widget.setStyleSheet("color: rgba(255,255,255,0.52); background: transparent; border: none;")
        text_layout.addWidget(hint_widget)

        layout.addLayout(text_layout, stretch=1)

        # Chevron — kichik, ixcham
        chevron = QLabel("\u203A")
        chevron.setFixedWidth(16)
        chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chevron.setFont(QFont("Segoe UI", 18, QFont.Weight.Medium))
        chevron.setStyleSheet(f"color: {icon_color}; background: transparent; border: none;")
        layout.addWidget(chevron)

        return btn

    def _create_hero_button(self, icon_text: str, label: str, hint: str) -> QFrame:
        """Asosiy HERO button — Face Recognition uchun, to'ldirilgan gradient ko'rinishi.
        Kartochka shaklida emas, aniq CTA primary buttoni kabi."""
        btn = _ClickableCard()
        btn.setObjectName("heroBtn")
        btn.setFixedHeight(84)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QFrame#heroBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2eb07c,
                    stop:0.55 #1f9a6a,
                    stop:1 #14855a);
                border: 1px solid rgba(86,235,186,0.45);
                border-radius: 18px;
            }}
            QFrame#heroBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #38c48c,
                    stop:0.55 #25ac78,
                    stop:1 #179664);
                border-color: rgba(120,248,201,0.75);
            }}
        """)

        layout = QHBoxLayout(btn)
        layout.setContentsMargins(18, 14, 22, 14)
        layout.setSpacing(16)

        # Icon chip — bigger, white tinted for hero
        icon_label = QLabel(icon_text)
        icon_label.setFixedSize(52, 52)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("""
            background: rgba(255,255,255,0.18);
            border: 1px solid rgba(255,255,255,0.28);
            border-radius: 14px;
            color: #ffffff;
            font-size: 22px;
        """)
        layout.addWidget(icon_label)

        # Text block
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        label_widget = QLabel(label)
        label_widget.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        label_widget.setStyleSheet("color: #ffffff; background: transparent; border: none; letter-spacing: 0.3px;")
        text_layout.addWidget(label_widget)

        hint_widget = QLabel(hint)
        hint_widget.setFont(QFont("Segoe UI", 10))
        hint_widget.setStyleSheet("color: rgba(255,255,255,0.78); background: transparent; border: none;")
        text_layout.addWidget(hint_widget)

        layout.addLayout(text_layout, stretch=1)

        # Arrow — white, prominent
        arrow = QLabel("\u2192")
        arrow.setFixedWidth(28)
        arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        arrow.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        arrow.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        layout.addWidget(arrow)

        return btn

    # ══════════════════════════════════════
    # Signals / Slots
    # ══════════════════════════════════════

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._loading_overlay.isVisible():
            self._loading_overlay.setGeometry(self.rect())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._sessions:
            self._load_sessions()

    def _on_download_clicked(self):
        """Open exam selection modal."""
        if not self._sessions:
            self._load_sessions()
            if not self._sessions:
                self._set_status("Aktiv testlar topilmadi", "warning")
                return

        modal = _ExamModal(self._sessions, self._db, parent=self)
        modal.download_requested.connect(self._start_download_sessions)
        modal.exec()

    def _on_delete_clicked(self):
        """Clear local database."""
        self._db.clear_all_data()
        self._sessions = []
        self.data_cleared.emit()
        self._set_status("Ma'lumotlar muvaffaqiyatli tozalandi!", "success")

    def _load_sessions(self):
        self._set_status("Serverdan ma'lumot olinmoqda...", "info")

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
            self._set_status("Offline rejim: mahalliy ma'lumotlar yuklandi", "warning")
            return

        if self._sessions:
            self._set_status(f"{len(self._sessions)} ta aktiv test topildi", "success")
        else:
            self._set_status("Aktiv testlar topilmadi", "warning")

    def _start_download_sessions(self, sessions: list):
        """Download data for selected sessions."""
        if not sessions:
            return

        session = sessions[0]
        session_id = session.get("id")
        if not session_id:
            return

        self._loading_overlay.start("Ma'lumotlar yuklanmoqda...")
        self._download_action_btn.setEnabled(False)

        self._downloader = DataDownloader(session_id, parent=self)
        self._downloader.finished_ok.connect(self._on_download_ok)
        self._downloader.error.connect(self._on_download_error)
        self._downloader.start()

    def _on_download_ok(self, loaded: int, skipped: int):
        self._download_action_btn.setEnabled(True)
        if skipped > 0:
            self._loading_overlay.show_result(
                _LoadingOverlay.MODE_WARNING,
                title=f"{loaded} ta yuklandi",
                subtitle=f"{skipped} ta yuklanmadi (ma'lumot to'liq emas)",
            )
            self._set_status(
                f"{loaded} ta yuklandi, {skipped} ta yuklanmadi", "warning",
            )
        else:
            self._loading_overlay.show_result(
                _LoadingOverlay.MODE_SUCCESS,
                title=f"{loaded} ta student yuklandi",
                subtitle="Ma'lumotlar muvaffaqiyatli saqlandi",
            )
            self._set_status(
                f"{loaded} ta student muvaffaqiyatli yuklandi!", "success",
            )

    def _on_download_error(self, err):
        self._download_action_btn.setEnabled(True)
        self._loading_overlay.show_result(
            _LoadingOverlay.MODE_ERROR,
            title="Xatolik yuz berdi",
            subtitle=str(err)[:80],
            auto_close_ms=3500,
        )
        self._set_status(f"Xatolik: {err}", "error")
