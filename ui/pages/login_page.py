import math
import os
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGraphicsDropShadowEffect, QFrame,
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QPropertyAnimation,
    QTimer, QPointF, QRectF, QSize,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QBrush, QPixmap,
)

# Login card uchun brand logo — loyiha ildizidagi images/ papkasidan.
_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "images", "logo_bba.png"
)

from ui.styles import COLORS, FONT_FAMILY


# ──────────────────────────────────────────────
# Background particle
# ──────────────────────────────────────────────
class _Particle:
    def __init__(self, bounds_w: float, bounds_h: float):
        self.x = random.uniform(0, bounds_w)
        self.y = random.uniform(0, bounds_h)
        self.radius = random.uniform(2, 6)
        self.opacity = random.uniform(0.08, 0.25)
        self.speed_x = random.uniform(-0.3, 0.3)
        self.speed_y = random.uniform(-0.5, -0.1)
        self.bounds_w = bounds_w
        self.bounds_h = bounds_h

    def update(self, bounds_w: float, bounds_h: float):
        self.bounds_w = bounds_w
        self.bounds_h = bounds_h
        self.x += self.speed_x
        self.y += self.speed_y
        if self.y < -10:
            self.y = bounds_h + 10
            self.x = random.uniform(0, bounds_w)
        if self.x < -10:
            self.x = bounds_w + 10
        elif self.x > bounds_w + 10:
            self.x = -10


# ──────────────────────────────────────────────
# Material status pill — indicator for model loading state
# ──────────────────────────────────────────────
class _StatusPill(QWidget):
    """MD3-style status indicator pill.

    States:
      - 'loading': spinning amber arc + "Tizim tayyorlanmoqda"
      - 'ready'  : solid green dot + "Tizim tayyor"
      - 'error'  : solid red dot + qisqa xato matni
    """

    AMBER = "#FFB300"
    GREEN = "#43A047"
    RED   = "#E53935"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "loading"
        self._label = "Tizim tayyorlanmoqda..."
        self._spin_angle = 0
        self.setFixedHeight(34)
        self.setMinimumWidth(220)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(28)

    def _tick(self):
        if self._state == "loading":
            self._spin_angle = (self._spin_angle + 8) % 360
            self.update()

    def set_state(self, state: str, label: str = ""):
        self._state = state
        if label:
            self._label = label
        else:
            self._label = {
                "loading": "Tizim tayyorlanmoqda...",
                "ready":   "Tizim tayyor",
                "error":   "Tizim xatosi",
            }.get(state, "")
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(260, 34)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        color = {
            "loading": self.AMBER,
            "ready":   self.GREEN,
            "error":   self.RED,
        }.get(self._state, self.AMBER)
        qcol = QColor(color)

        # Pill background — tonal surface with state tint
        bg = QColor(qcol)
        bg.setAlpha(28)
        bd = QColor(qcol)
        bd.setAlpha(80)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(bd, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), h / 2, h / 2)

        # Indicator (left side)
        ind_x, ind_y, ind_r = 16, h / 2, 8
        if self._state == "loading":
            # Background ring
            p.setPen(QPen(QColor(qcol.red(), qcol.green(), qcol.blue(), 60), 2.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(ind_x, ind_y), ind_r, ind_r)
            # Spinning arc
            pen = QPen(qcol, 2.4)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            rect = QRectF(ind_x - ind_r, ind_y - ind_r, ind_r * 2, ind_r * 2)
            # QPainter.drawArc uses 1/16 degree units
            p.drawArc(rect, int(-self._spin_angle * 16), int(120 * 16))
        else:
            # Solid filled dot with subtle outer halo
            halo = QColor(qcol)
            halo.setAlpha(70)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(ind_x, ind_y), ind_r + 3, ind_r + 3)
            p.setBrush(QBrush(qcol))
            p.drawEllipse(QPointF(ind_x, ind_y), ind_r, ind_r)
            # Inner shine
            shine = QColor(255, 255, 255, 110)
            p.setBrush(QBrush(shine))
            p.drawEllipse(QPointF(ind_x - 2, ind_y - 2), 2.6, 2.6)

        # Label
        p.setPen(QColor(qcol.darker(140)))
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        p.setFont(font)
        text_rect = QRectF(ind_x + ind_r + 10, 0, w - (ind_x + ind_r + 18), h)
        p.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self._label)
        p.end()


# ──────────────────────────────────────────────
# LoginPage — Material Design 3 redesign
# ──────────────────────────────────────────────
class LoginPage(QWidget):
    login_success = pyqtSignal(dict)
    exit_requested = pyqtSignal()

    def __init__(self, auth_service, parent=None):
        super().__init__(parent)
        self._auth = auth_service
        self._particles: list[_Particle] = []
        self._anim_angle = 0.0
        self._setup_ui()
        self._init_particles(60)
        self._start_animations()

    # ── Background animation ──
    def _init_particles(self, count: int):
        w = max(self.width(), 1920)
        h = max(self.height(), 1080)
        self._particles = [_Particle(w, h) for _ in range(count)]

    def _start_animations(self):
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._tick_background)
        self._bg_timer.start(33)
        self._apply_card_shadow()

    def _tick_background(self):
        self._anim_angle += 0.004
        w, h = self.width(), self.height()
        for p in self._particles:
            p.update(w, h)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Status pill'ni ekranning pastki chap burchagiga joylashtiramiz
        if hasattr(self, "_status_pill"):
            margin = 20
            pill = self._status_pill
            pill.adjustSize()
            pw = max(pill.sizeHint().width(), pill.minimumWidth())
            ph = pill.height()
            pill.setGeometry(margin, self.height() - ph - margin, pw, ph)

    def _apply_card_shadow(self):
        if not hasattr(self, '_card'):
            return
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(72)
        shadow.setOffset(0, 18)
        shadow.setColor(QColor(0, 0, 0, 130))
        self._card.setGraphicsEffect(shadow)

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        offset = math.sin(self._anim_angle) * 0.15
        gradient = QLinearGradient(0, 0, w * (0.6 + offset), h)
        gradient.setColorAt(0.0, QColor("#0a1628"))
        gradient.setColorAt(0.3, QColor("#0D47A1"))
        gradient.setColorAt(0.6, QColor("#1565C0"))
        gradient.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), gradient)

        pulse = 0.7 + 0.3 * math.sin(self._anim_angle * 2)
        glow = QRadialGradient(w * 0.5, h * 0.4, max(w, h) * 0.5)
        glow.setColorAt(0.0, QColor(30, 136, 229, int(40 * pulse)))
        glow.setColorAt(0.5, QColor(13, 71, 161, int(20 * pulse)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        for p in self._particles:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(255 * p.opacity)))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

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

    # ── UI layout ──
    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Top-right exit button
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 22, 30, 0)
        top_bar.addStretch()
        self.exit_btn = QPushButton("Chiqish")
        self.exit_btn.setFixedSize(120, 40)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self.exit_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.12);
                color: rgba(255, 255, 255, 0.88);
                border: 1px solid rgba(255, 255, 255, 0.22);
                border-radius: 20px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background-color: {COLORS['error']};
                color: white;
                border-color: {COLORS['error']};
            }}
        """)
        self.exit_btn.clicked.connect(self.exit_requested.emit)
        top_bar.addWidget(self.exit_btn)
        outer.addLayout(top_bar)

        outer.addStretch()

        # ── Card (Material 3 Surface, elevated) ──
        self._card = QFrame()
        self._card.setObjectName("loginCard")
        self._card.setFixedWidth(440)
        self._card.setStyleSheet(f"""
            QFrame#loginCard {{
                background-color: #FFFFFF;
                border-radius: 28px;
                border: 1px solid rgba(0, 0, 0, 0.06);
            }}
        """)

        layout = QVBoxLayout(self._card)
        layout.setSpacing(0)
        layout.setContentsMargins(40, 36, 40, 28)

        # ── Brand logo ──
        # logo_bba.png — aspect ratio 150:88 ni saqlab, cardga mos ravishda
        # max 180px kenglikda chiqariladi. Rasm bo'lmasa yashirin QLabel.
        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("background: transparent; border: none;")
        pm = QPixmap(_LOGO_PATH)
        if not pm.isNull():
            dpr = self.devicePixelRatioF() or 1.0
            target = QSize(int(110 * dpr), int(64 * dpr))
            scaled = pm.scaled(
                target,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            scaled.setDevicePixelRatio(dpr)
            logo.setPixmap(scaled)
        else:
            logo.setText("BBA")
            logo.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
            logo.setStyleSheet(
                f"color: {COLORS['primary_dark']}; background: transparent;"
            )
        logo.setFixedHeight(64)
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(8)

        # ── Headline / supporting ──
        title = QLabel("Face ID Desktop")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            color: {COLORS['primary_dark']};
            background: transparent;
            letter-spacing: -0.3px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addSpacing(4)

        subtitle = QLabel("Xavfsiz identifikatsiya tizimi")
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet(
            f"color: {COLORS['text_secondary']}; background: transparent;"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)
        layout.addSpacing(24)

        # ── Form ──
        self.username_input = self._make_field("Foydalanuvchi nomi", password=False)
        layout.addWidget(self.username_input)
        layout.addSpacing(14)

        self.password_input = self._make_field("Parol", password=True)
        layout.addWidget(self.password_input)
        layout.addSpacing(22)

        # ── Filled button (MD3 filled) ──
        self.login_btn = QPushButton("Kirish")
        self.login_btn.setFixedHeight(52)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_light']});
                color: white;
                border: none;
                border-radius: 26px;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 1.6px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_light']}, stop:1 #42A5F5);
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary_dark']}, stop:1 {COLORS['primary']});
            }}
            QPushButton:disabled {{
                background: {COLORS['divider']};
                color: {COLORS['text_secondary']};
            }}
        """)
        self.login_btn.clicked.connect(self._on_login)
        layout.addWidget(self.login_btn)

        layout.addSpacing(14)

        # ── Error label (initially hidden) ──
        self.error_label = QLabel("")
        self.error_label.setFont(QFont("Segoe UI", 11))
        self.error_label.setStyleSheet("color: transparent; background: transparent;")
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        self.error_label.setMinimumHeight(20)
        layout.addWidget(self.error_label)

        # ── Version footer outside card ──
        version = QLabel("v2.0.0")
        version.setFont(QFont("Segoe UI", 9))
        version.setStyleSheet("color: rgba(255,255,255,0.45); background: transparent;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)

        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(10)
        outer.addWidget(version, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        # ── Status pill — ekranning pastki chap burchagida (login formadan tashqarida) ──
        # Absolute positioning: outer layout'ga kirmaydi, resizeEvent'da joylashtiriladi.
        self._status_pill = _StatusPill(self)
        self._status_pill.raise_()

        # Enter key triggers login
        self.password_input.returnPressed.connect(self._on_login)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())

    def _make_field(self, placeholder: str, password: bool) -> QLineEdit:
        """MD3 outlined-style text field."""
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setFixedHeight(54)
        field.setFont(QFont("Segoe UI", 13))
        if password:
            field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setStyleSheet(f"""
            QLineEdit {{
                border: 1.5px solid #DADCE0;
                border-radius: 14px;
                padding: 0 18px;
                background-color: #F6F8FB;
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                selection-background-color: {COLORS['primary_light']};
            }}
            QLineEdit:hover {{
                border-color: #B6BCC4;
                background-color: #F1F3F6;
            }}
            QLineEdit:focus {{
                border: 2px solid {COLORS['primary']};
                background-color: #FFFFFF;
                padding: 0 17px;
            }}
        """)
        return field

    # ── External API ──
    def set_model_status(self, text: str, is_ready: bool = False):
        """Backward-compatible API: matn ko'rsatilmaydi, faqat indikator
        holati o'zgaradi (sariq → yashil → qizil)."""
        if is_ready:
            self._status_pill.set_state("ready", "Tizim tayyor")
        elif text and "xato" in text.lower():
            self._status_pill.set_state("error", "Tizim xatosi")
        else:
            self._status_pill.set_state("loading", "Tizim tayyorlanmoqda...")

    # ── Auth ──
    def _on_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self._show_error("Login va parolni kiriting!")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Tekshirilmoqda...")
        self.error_label.setText("")
        self.error_label.setStyleSheet("color: transparent; background: transparent;")

        try:
            staff = self._auth.login(username, password)
            self.login_success.emit(staff)
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                self._show_error("Login yoki parol noto'g'ri!")
            elif "Connection" in error_msg or "connect" in error_msg.lower():
                self._show_error("Serverga ulanib bo'lmadi!")
            else:
                self._show_error(f"Xatolik: {error_msg[:100]}")
        finally:
            self.login_btn.setEnabled(True)
            self.login_btn.setText("Kirish")

    def _show_error(self, msg: str):
        self.error_label.setText(msg)
        self.error_label.setStyleSheet(f"""
            color: {COLORS['error']};
            background-color: #FDECEA;
            padding: 9px 14px;
            border-radius: 10px;
            font-weight: 600;
            border: 1px solid #F5C2C0;
        """)

        if hasattr(self, '_card'):
            anim = QPropertyAnimation(self._card, b"pos", self)
            anim.setDuration(400)
            start = self._card.pos()
            anim.setKeyValueAt(0, start)
            anim.setKeyValueAt(0.15, start + QPointF(-8, 0).toPoint())
            anim.setKeyValueAt(0.3, start + QPointF(8, 0).toPoint())
            anim.setKeyValueAt(0.45, start + QPointF(-6, 0).toPoint())
            anim.setKeyValueAt(0.6, start + QPointF(6, 0).toPoint())
            anim.setKeyValueAt(0.75, start + QPointF(-3, 0).toPoint())
            anim.setKeyValueAt(1, start)
            anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
