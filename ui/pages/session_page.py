import math
import os
import random

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGraphicsDropShadowEffect, QSizePolicy, QScrollArea,
    QGridLayout,
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QLinearGradient, QRadialGradient,
    QPen, QPainterPath, QPixmap,
)

from database.db_manager import DatabaseManager
from ui.styles import FONT_FAMILY

# ── Dark theme tokens ──
PRIMARY_LIGHT = "#3ba57c"
ACCENT_BLUE_LIGHT = "#63C5FF"
TEXT_MUTED = "rgba(255,255,255,0.72)"
CARD_BORDER = "rgba(255,255,255,0.14)"

_HERE = os.path.dirname(os.path.abspath(__file__))


class _Particle:
    def __init__(self, w: float, h: float):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.radius = random.uniform(2, 6)
        self.opacity = random.uniform(0.08, 0.25)
        self.vx = random.uniform(-0.3, 0.3)
        self.vy = random.uniform(-0.5, -0.1)

    def update(self, w: float, h: float):
        self.x += self.vx
        self.y += self.vy
        if self.y < -10:
            self.y = h + 10
            self.x = random.uniform(0, w)
        if self.x < -10:
            self.x = w + 10
        elif self.x > w + 10:
            self.x = -10


class _SmenaCard(QFrame):
    """Clickable smena card — aniq tanlash CTA pillini ko'rsatadi.
    `is_active` — haqiqiy DB holati (shu smena hozir faolmi)."""
    clicked = pyqtSignal(int)

    def __init__(self, sm_id: int, title: str, meta: str, badge_text: str,
                 is_active: bool = False, parent=None):
        super().__init__(parent)
        self._sm_id = sm_id
        self._hover = False
        self._active = is_active
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(92)
        self.setStyleSheet("background: transparent; border: none;")

        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(14)

        # Icon — active bo'lsa yashil, aks holda ko'k
        icon = QLabel("\u23f0")
        icon.setFixedSize(46, 46)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if is_active:
            icon.setStyleSheet("""
                background: rgba(37,137,97,0.22);
                border: 1px solid rgba(56,217,169,0.32);
                border-radius: 13px;
                color: #38d9a9;
                font-size: 18px;
            """)
        else:
            icon.setStyleSheet("""
                background: rgba(52,161,255,0.18);
                border: 1px solid rgba(99,197,255,0.22);
                border-radius: 13px;
                color: #63C5FF;
                font-size: 18px;
            """)
        row.addWidget(icon)

        # Text
        text_layout = QVBoxLayout()
        text_layout.setSpacing(3)
        text_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel(title)
        title_label.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        title_label.setStyleSheet("color: white; background: transparent; border: none; letter-spacing: 0.2px;")
        text_layout.addWidget(title_label)

        meta_label = QLabel(meta)
        meta_label.setFont(QFont("Segoe UI", 11))
        meta_label.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent; border: none;")
        text_layout.addWidget(meta_label)

        row.addLayout(text_layout, stretch=1)

        # Badge — "Faol" yashil, "Mavjud" ko'k
        badge = QLabel(badge_text)
        badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(26)
        if is_active:
            badge.setStyleSheet("""
                background: rgba(37,137,97,0.22);
                border: 1px solid rgba(56,217,169,0.36);
                color: #38d9a9;
                border-radius: 13px;
                padding: 2px 12px;
                letter-spacing: 0.3px;
            """)
        else:
            badge.setStyleSheet("""
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.12);
                color: rgba(255,255,255,0.70);
                border-radius: 13px;
                padding: 2px 12px;
                letter-spacing: 0.3px;
            """)
        row.addWidget(badge)

        # ── Aniq CTA pilli: "Tanlash →" ──
        self._cta = QFrame()
        self._cta.setObjectName("smenaCta")
        self._cta.setFixedHeight(36)
        self._cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_cta_style(hover=False)
        cta_layout = QHBoxLayout(self._cta)
        cta_layout.setContentsMargins(14, 0, 14, 0)
        cta_layout.setSpacing(8)

        self._cta_label = QLabel("Tanlash")
        self._cta_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._cta_label.setStyleSheet("color: #ffffff; background: transparent; border: none; letter-spacing: 0.4px;")
        cta_layout.addWidget(self._cta_label)

        self._cta_arrow = QLabel("\u2192")
        self._cta_arrow.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._cta_arrow.setStyleSheet("color: #ffffff; background: transparent; border: none;")
        cta_layout.addWidget(self._cta_arrow)

        row.addWidget(self._cta)

    def _update_cta_style(self, hover: bool):
        """Active vs hover vs default — uchta holatdagi CTA styling."""
        if self._active:
            if hover:
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #38c48c, stop:1 #1fa06f)"
                brd = "rgba(120,248,201,0.70)"
            else:
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2eb07c, stop:1 #1a8f62)"
                brd = "rgba(56,217,169,0.55)"
        else:
            if hover:
                bg = "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3ca7f5, stop:1 #1e6fd6)"
                brd = "rgba(125,211,255,0.70)"
            else:
                bg = "rgba(52,161,255,0.20)"
                brd = "rgba(99,197,255,0.40)"
        self._cta.setStyleSheet(f"""
            QFrame#smenaCta {{
                background: {bg};
                border: 1px solid {brd};
                border-radius: 12px;
            }}
        """)

    def enterEvent(self, event):
        self._hover = True
        self._update_cta_style(hover=True)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._update_cta_style(hover=False)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit(self._sm_id)
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 18, 18)

        # Active (haqiqiy faol smena) → yashil tinted; hover → ko'k glow; default → neytral
        if self._active:
            painter.fillPath(path, QColor(37, 137, 97, 28 if self._hover else 18))
            border_color = QColor(56, 217, 169, 170) if self._hover else QColor(56, 217, 169, 95)
            border_width = 1.5 if self._hover else 1
        elif self._hover:
            painter.fillPath(path, QColor(52, 161, 255, 26))
            border_color = QColor(125, 211, 255, 180)
            border_width = 1.5
        else:
            painter.fillPath(path, QColor(255, 255, 255, 12))
            border_color = QColor(255, 255, 255, 32)
            border_width = 1

        pen = QPen(border_color, border_width)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 18, 18)
        painter.end()


class _AccordionItem(QFrame):
    """Expandable accordion item for a test session."""
    smena_clicked = pyqtSignal(int)

    def __init__(self, session: dict, smenas: list, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self._expanded = False
        self._hover = False
        self._session = session
        self.setStyleSheet("background: transparent; border: none;")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header (clickable) ──
        self._header = QFrame()
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setStyleSheet("background: transparent; border: none;")
        self._header.setFixedHeight(90)
        self._header.mousePressEvent = lambda e: self.toggle()

        h_layout = QHBoxLayout(self._header)
        h_layout.setContentsMargins(22, 16, 22, 16)
        h_layout.setSpacing(16)

        # Icon
        icon = QLabel("\U0001f310")
        icon.setFixedSize(52, 52)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("""
            background: rgba(52,161,255,0.18);
            border: 1px solid rgba(99,197,255,0.18);
            border-radius: 14px;
            font-size: 22px;
        """)
        h_layout.addWidget(icon)

        # Meta text
        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(3)
        meta_layout.setContentsMargins(0, 0, 0, 0)

        tag = QLabel("Imtihon yo'nalishi")
        tag.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        tag.setStyleSheet(f"color: {ACCENT_BLUE_LIGHT}; background: transparent; border: none;")
        meta_layout.addWidget(tag)

        name = QLabel(session.get("test", "Test"))
        name.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        name.setStyleSheet("color: white; background: transparent; border: none;")
        name.setWordWrap(True)
        meta_layout.addWidget(name)

        date_label = QLabel(f"\U0001f4c5  {session.get('start_date', '')}")
        date_label.setFont(QFont("Segoe UI", 11))
        date_label.setStyleSheet("color: rgba(255,255,255,0.50); background: transparent; border: none;")
        meta_layout.addWidget(date_label)

        h_layout.addLayout(meta_layout, stretch=1)

        # Right side: smena count badge + aniq "Ochish/Yopish" CTA
        right = QHBoxLayout()
        right.setSpacing(10)

        badge = QLabel(f"\U0001F4CB  {len(smenas)} smena")
        badge.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedHeight(30)
        badge.setStyleSheet("""
            background: rgba(52,161,255,0.16);
            border: 1px solid rgba(99,197,255,0.26);
            color: #7DD3FF;
            border-radius: 15px;
            padding: 2px 14px;
            letter-spacing: 0.3px;
        """)
        right.addWidget(badge)

        self._toggle_label = QLabel("Ochish  \u25BC")
        self._toggle_label.setFixedHeight(30)
        self._toggle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._toggle_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self._toggle_label.setStyleSheet("""
            background: rgba(52,161,255,0.20);
            border: 1px solid rgba(99,197,255,0.35);
            color: #ffffff;
            border-radius: 15px;
            padding: 2px 14px;
            letter-spacing: 0.3px;
        """)
        right.addWidget(self._toggle_label)

        h_layout.addLayout(right)
        main_layout.addWidget(self._header)

        # ── Body (smena cards grid, hidden by default) ──
        self._body = QFrame()
        self._body.setStyleSheet("background: transparent; border: none;")
        self._body.setVisible(False)

        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(22, 8, 22, 18)
        body_layout.setSpacing(12)

        # Sub-header — aniq CTA: "Smenani tanlang" + yo'riqnoma matni
        sub_header_layout = QHBoxLayout()
        sub_header_layout.setSpacing(12)
        sh_icon = QLabel("\U0001F446")
        sh_icon.setFixedSize(32, 32)
        sh_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sh_icon.setStyleSheet("""
            background: rgba(56,217,169,0.16);
            border: 1px solid rgba(56,217,169,0.28);
            border-radius: 10px;
            color: #38d9a9;
            font-size: 14px;
        """)
        sub_header_layout.addWidget(sh_icon)

        sh_text_layout = QVBoxLayout()
        sh_text_layout.setSpacing(2)
        sh_title = QLabel("Smenani tanlang")
        sh_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        sh_title.setStyleSheet("color: white; background: transparent; border: none; letter-spacing: 0.2px;")
        sh_text_layout.addWidget(sh_title)

        sh_hint = QLabel("Kerakli smenani bosing \u2014 FaceID tizimi shu smena uchun ishga tushiriladi")
        sh_hint.setFont(QFont("Segoe UI", 10))
        sh_hint.setStyleSheet("color: rgba(255,255,255,0.55); background: transparent; border: none;")
        sh_text_layout.addWidget(sh_hint)

        sub_header_layout.addLayout(sh_text_layout, stretch=1)
        body_layout.addLayout(sub_header_layout)

        # Grid of smena cards (2 columns)
        grid = QGridLayout()
        grid.setSpacing(10)

        for i, sm in enumerate(smenas):
            students = db.get_students_by_smena(sm["id"])
            with_emb = sum(1 for st in students if st["embedding"])
            title = f"{sm['test_day']}  \u00b7  {sm['sm']}-smena"
            meta = f"\U0001F465 {len(students)} student  \u00b7  \U0001F9E0 {with_emb} embedding"
            is_active = bool(sm["is_active"])
            badge_text = "Faol" if is_active else "Mavjud"

            card = _SmenaCard(
                sm_id=sm["id"],
                title=title,
                meta=meta,
                badge_text=badge_text,
                is_active=is_active,
            )
            card.clicked.connect(self.smena_clicked.emit)
            grid.addWidget(card, i // 2, i % 2)

        body_layout.addLayout(grid)
        main_layout.addWidget(self._body)

    def toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        if self._expanded:
            self._toggle_label.setText("Yopish  \u25B2")
            self._toggle_label.setStyleSheet("""
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #2eb07c, stop:1 #1a8f62);
                border: 1px solid rgba(56,217,169,0.55);
                color: #ffffff;
                border-radius: 15px;
                padding: 2px 14px;
                letter-spacing: 0.3px;
            """)
        else:
            self._toggle_label.setText("Ochish  \u25BC")
            self._toggle_label.setStyleSheet("""
                background: rgba(52,161,255,0.20);
                border: 1px solid rgba(99,197,255,0.35);
                color: #ffffff;
                border-radius: 15px;
                padding: 2px 14px;
                letter-spacing: 0.3px;
            """)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 18, 18)

        painter.fillPath(path, QColor(255, 255, 255, 14))

        if self._expanded:
            border = QColor(37, 137, 97, 72)
        else:
            border = QColor(255, 255, 255, 23)
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 18, 18)

        # Header bottom border when expanded
        if self._expanded:
            header_h = self._header.height()
            painter.setPen(QPen(QColor(37, 137, 97, 41), 1))
            painter.drawLine(22, header_h, w - 22, header_h)

        painter.end()


class SessionPage(QWidget):
    session_selected = pyqtSignal(int)  # session_sm_id
    logout_requested = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = DatabaseManager()
        self._particles: list[_Particle] = []
        self._anim_angle = 0.0
        self._glow_phase = 0.0
        self._setup_ui()
        self._init_particles(60)
        self._start_animations()

    def _init_particles(self, count: int):
        w = max(self.width(), 1920)
        h = max(self.height(), 1080)
        self._particles = [_Particle(w, h) for _ in range(count)]

    def _start_animations(self):
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def _tick(self):
        self._anim_angle += 0.004
        self._glow_phase += 0.03
        w, h = self.width(), self.height()
        for p in self._particles:
            p.update(w, h)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Animated gradient background (matching login/sync/mode pages) ──
        offset = math.sin(self._anim_angle) * 0.15
        bg = QLinearGradient(0, 0, w * (0.6 + offset), h)
        bg.setColorAt(0.0, QColor("#0a1628"))
        bg.setColorAt(0.3, QColor("#0D47A1"))
        bg.setColorAt(0.6, QColor("#1565C0"))
        bg.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), bg)

        # ── Radial glow accent (pulsing) ──
        pulse = 0.7 + 0.3 * math.sin(self._anim_angle * 2)
        glow = QRadialGradient(w * 0.5, h * 0.4, max(w, h) * 0.5)
        glow.setColorAt(0.0, QColor(30, 136, 229, int(40 * pulse)))
        glow.setColorAt(0.5, QColor(13, 71, 161, int(20 * pulse)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        # ── Particles ──
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
                dist_sq = dx * dx + dy * dy
                if dist_sq < 14400:  # 120^2
                    dist = math.sqrt(dist_sq)
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

        self._live_dot = QLabel()
        self._live_dot.setFixedSize(8, 8)
        self._live_dot.setStyleSheet("""
            background: #38d9a9;
            border: none;
            border-radius: 4px;
        """)
        lb_layout.addWidget(self._live_dot)

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

        h_icon = QLabel("\U0001f4c5")
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
        h_title = QLabel("Imtihon sessiyasini tanlang")
        h_title.setFont(QFont("Segoe UI", 17, QFont.Weight.Bold))
        h_title.setStyleSheet("color: white; background: transparent; border: none;")
        h_text_layout.addWidget(h_title)

        h_sub = QLabel("Imtihon yo'nalishini oching \u2192 kerakli smenani tanlang")
        h_sub.setFont(QFont("Segoe UI", 12))
        h_sub.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none;")
        h_text_layout.addWidget(h_sub)

        heading_layout.addLayout(h_text_layout)
        body_layout.addLayout(heading_layout)

        # Scrollable accordion area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QWidget { background: transparent; }
            QScrollBar:vertical {
                background: transparent;
                width: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.15);
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.25);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        self._accordion_container = QWidget()
        self._accordion_layout = QVBoxLayout(self._accordion_container)
        self._accordion_layout.setContentsMargins(0, 0, 6, 0)
        self._accordion_layout.setSpacing(12)
        self._accordion_layout.addStretch()

        scroll.setWidget(self._accordion_container)
        body_layout.addWidget(scroll, stretch=1)

        # Info label (when no sessions)
        self._info_label = QLabel("")
        self._info_label.setFont(QFont("Segoe UI", 13))
        self._info_label.setStyleSheet(f"color: {TEXT_MUTED}; background: transparent; border: none;")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setWordWrap(True)
        body_layout.addWidget(self._info_label)

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

        outer.addWidget(self._card)

    def showEvent(self, event):
        super().showEvent(event)
        self._load_sessions()

    def _load_sessions(self):
        # Clear existing accordion items
        while self._accordion_layout.count() > 1:
            item = self._accordion_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        all_sessions = self._db.get_active_sessions()
        sessions = [s for s in all_sessions if s["is_loaded"]]
        sessions.sort(key=lambda s: s["start_date"] or "")

        if not sessions:
            self._info_label.setText("Yuklab olingan test topilmadi.\nAvval sinxronlash sahifasidan yuklang.")
            return

        self._info_label.setText("")
        first = True
        for s in sessions:
            smenas = self._db.get_smenas_by_session(s["id"])
            if not smenas:
                continue

            acc = _AccordionItem(dict(s), smenas, self._db)
            acc.smena_clicked.connect(self._on_smena_selected)
            # Auto expand first item
            if first:
                acc.toggle()
                first = False

            self._accordion_layout.insertWidget(
                self._accordion_layout.count() - 1, acc
            )

    def _on_smena_selected(self, sm_id: int):
        self.session_selected.emit(sm_id)
