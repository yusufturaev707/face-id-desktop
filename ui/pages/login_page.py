import math
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QGraphicsDropShadowEffect, QFrame,
)
from PyQt6.QtCore import (
    pyqtSignal, Qt, QPropertyAnimation,
    QTimer, QPointF,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QBrush, QPainterPath,
)

from ui.styles import COLORS, FONT_FAMILY


class _Particle:
    """Floating particle for background animation."""

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


class LoginPage(QWidget):
    login_success = pyqtSignal(dict)  # staff data
    exit_requested = pyqtSignal()

    def __init__(self, auth_service, parent=None):
        super().__init__(parent)
        self._auth = auth_service
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
        # Background animation timer
        self._bg_timer = QTimer(self)
        self._bg_timer.timeout.connect(self._tick_background)
        self._bg_timer.start(33)  # ~30 FPS

        # Apply card shadow immediately
        self._apply_card_shadow()

    def _tick_background(self):
        self._anim_angle += 0.004
        w, h = self.width(), self.height()
        for p in self._particles:
            p.update(w, h)
        self.update()

    def _apply_card_shadow(self):
        if not hasattr(self, '_card'):
            return
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 100))
        self._card.setGraphicsEffect(shadow)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Animated gradient background
        offset = math.sin(self._anim_angle) * 0.15
        gradient = QLinearGradient(0, 0, w * (0.6 + offset), h)
        gradient.setColorAt(0.0, QColor("#0a1628"))
        gradient.setColorAt(0.3, QColor("#0D47A1"))
        gradient.setColorAt(0.6, QColor("#1565C0"))
        gradient.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), gradient)

        # Radial glow accent (subtle pulsing)
        pulse = 0.7 + 0.3 * math.sin(self._anim_angle * 2)
        glow = QRadialGradient(w * 0.5, h * 0.4, max(w, h) * 0.5)
        glow.setColorAt(0.0, QColor(30, 136, 229, int(40 * pulse)))
        glow.setColorAt(0.5, QColor(13, 71, 161, int(20 * pulse)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        # Floating particles
        for p in self._particles:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(255 * p.opacity)))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # Connecting lines between close particles
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
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Top-right exit button ──
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 20, 30, 0)
        top_bar.addStretch()

        self.exit_btn = QPushButton("Chiqish")
        self.exit_btn.setFixedSize(130, 42)
        self.exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        self.exit_btn.setStyleSheet(f"""
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
        self.exit_btn.clicked.connect(self.exit_requested.emit)
        top_bar.addWidget(self.exit_btn)
        outer.addLayout(top_bar)

        outer.addStretch()

        # ── Card container ──
        self._card = QFrame()
        self._card.setObjectName("loginCard")
        self._card.setFixedWidth(480)
        self._card.setStyleSheet("""
            QFrame#loginCard {
                background-color: rgba(255, 255, 255, 245);
                border-radius: 20px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
        """)

        layout = QVBoxLayout(self._card)
        layout.setSpacing(0)
        layout.setContentsMargins(44, 36, 44, 32)

        # ── Logo area ──
        logo_container = QWidget()
        logo_container.setStyleSheet("background: transparent;")
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)
        logo_layout.setSpacing(10)
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Animated shield icon with gradient circle
        icon_circle = QLabel()
        icon_circle.setFixedSize(80, 80)
        icon_circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_circle.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_dark']});
            border-radius: 40px;
            color: white;
            font-size: 36px;
        """)
        icon_circle.setText("\U0001f6e1")
        logo_layout.addWidget(icon_circle, alignment=Qt.AlignmentFlag.AlignCenter)

        # Title
        title = QLabel("Face-ID Desktop")
        title.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        title.setStyleSheet(f"""
            color: {COLORS['primary_dark']};
            background: transparent;
            letter-spacing: -0.5px;
        """)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(title)

        # Subtitle
        subtitle = QLabel("Xavfsiz identifikatsiya tizimi")
        subtitle.setFont(QFont("Segoe UI", 14))
        subtitle.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_layout.addWidget(subtitle)

        layout.addWidget(logo_container)
        layout.addSpacing(20)

        # ── Divider line ──
        divider = QFrame()
        divider.setObjectName("loginDivider")
        divider.setFixedHeight(1)
        divider.setStyleSheet("""
            QFrame#loginDivider {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 transparent, stop:0.3 #BDBDBD,
                    stop:0.7 #BDBDBD, stop:1 transparent);
                border: none;
            }
        """)
        layout.addWidget(divider)
        layout.addSpacing(20)

        # ── Form fields ──
        form_container = QWidget()
        form_container.setStyleSheet("background: transparent;")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(6)

        # Username field
        username_label = QLabel("Foydalanuvchi nomi")
        username_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        username_label.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        form_layout.addWidget(username_label)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Login kiriting...")
        self.username_input.setFixedHeight(50)
        self.username_input.setFont(QFont("Segoe UI", 14))
        self.username_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 12px;
                padding: 10px 18px;
                font-size: 15px;
                background-color: #F8F9FA;
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
                background-color: #FFFFFF;
                border-width: 2px;
            }}
            QLineEdit::placeholder {{
                color: #BDBDBD;
            }}
        """)
        form_layout.addWidget(self.username_input)

        # Password field
        password_label = QLabel("Parol")
        password_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        password_label.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        form_layout.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Parol kiriting...")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFixedHeight(50)
        self.password_input.setFont(QFont("Segoe UI", 14))
        self.password_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E0E0E0;
                border-radius: 12px;
                padding: 10px 18px;
                font-size: 16px;
                background-color: #F8F9FA;
                color: {COLORS['text_primary']};
                font-family: {FONT_FAMILY};
                lineedit-password-character: 9679;
                letter-spacing: 4px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['primary']};
                background-color: #FFFFFF;
                border-width: 2px;
            }}
            QLineEdit::placeholder {{
                color: #BDBDBD;
                letter-spacing: 0px;
            }}
        """)
        form_layout.addWidget(self.password_input)

        layout.addWidget(form_container)
        layout.addSpacing(20)

        # ── Login button with gradient ──
        self.login_btn = QPushButton("Kirish")
        self.login_btn.setFixedHeight(52)
        self.login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_btn.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.login_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['primary']}, stop:1 {COLORS['primary_light']});
                color: white;
                border: none;
                border-radius: 14px;
                font-size: 17px;
                font-weight: 700;
                letter-spacing: 1.5px;
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

        layout.addSpacing(10)

        # ── Error label ──
        self.error_label = QLabel("")
        self.error_label.setFont(QFont("Segoe UI", 12))
        self.error_label.setStyleSheet(f"""
            color: {COLORS['error']};
            background: transparent;
            padding: 6px;
            border-radius: 8px;
        """)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # ── Model loading status ──
        self._model_status = QLabel("AI model yuklanmoqda...")
        self._model_status.setFont(QFont("Segoe UI", 11))
        self._model_status.setStyleSheet(f"""
            color: {COLORS['text_secondary']};
            background: transparent;
            padding: 4px;
        """)
        self._model_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._model_status)

        # ── Version footer ──
        version_container = QWidget()
        version_container.setStyleSheet("background: transparent;")
        version_layout = QHBoxLayout(version_container)
        version_layout.setContentsMargins(0, 0, 0, 12)

        version = QLabel("v1.0.0")
        version.setFont(QFont("Segoe UI", 10))
        version.setStyleSheet("color: rgba(255,255,255,0.4); background: transparent;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_layout.addWidget(version)

        outer.addWidget(self._card, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(6)
        outer.addWidget(version_container, alignment=Qt.AlignmentFlag.AlignCenter)
        outer.addStretch()

        # Enter key triggers login
        self.password_input.returnPressed.connect(self._on_login)
        self.username_input.returnPressed.connect(lambda: self.password_input.setFocus())

    def set_model_status(self, text: str, is_ready: bool = False):
        self._model_status.setText(text)
        if is_ready:
            self._model_status.setStyleSheet(f"""
                color: {COLORS['success']};
                background: transparent;
                padding: 4px;
                font-weight: 600;
            """)
        elif "xato" in text.lower():
            self._model_status.setStyleSheet(f"""
                color: {COLORS['error']};
                background: transparent;
                padding: 4px;
            """)

    def _on_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self._show_error("Login va parolni kiriting!")
            return

        self.login_btn.setEnabled(False)
        self.login_btn.setText("Tekshirilmoqda...")
        self.error_label.setText("")

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
            background-color: #FFEBEE;
            padding: 10px;
            border-radius: 8px;
            font-weight: 500;
        """)

        # Shake animation on the card
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
