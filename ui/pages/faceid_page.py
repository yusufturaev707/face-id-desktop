import base64
import math
import os
import random
import threading
from datetime import datetime

import cv2
import numpy as np

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSizePolicy, QFrame, QGraphicsDropShadowEffect,
    QScrollArea, QSlider, QLineEdit, QDialog, QButtonGroup,
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal, QTimer, QPointF, QRectF, QSize, QEvent, QThread
from PyQt6.QtGui import (
    QImage, QPixmap, QFont, QColor, QPainter,
    QLinearGradient, QRadialGradient, QPainterPath, QPen,
)

from database.db_manager import DatabaseManager
from services.camera_worker import CameraWorker
from services.api_client import ApiClient
from services.sync_service import SyncService, OnlineSubmitWorker
from ui.styles import FONT_FAMILY

_HERE = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════
# Dark Theme — Color Tokens (session_page uyg'un)
# ═══════════════════════════════════════════════════

# Surface hierarchy
SRF          = "#0f1923"      # deepest bg (gradient covers this)
SRF_CARD     = "rgba(255,255,255,0.07)"
SRF_INNER    = "rgba(255,255,255,0.05)"
SRF_FIELD    = "rgba(255,255,255,0.09)"
SRF_HOVER    = "rgba(255,255,255,0.13)"

# Borders (glass-like)
BRD          = "rgba(255,255,255,0.10)"
BRD_ACCENT   = "rgba(255,255,255,0.18)"
BRD_FOCUS    = "rgba(99,197,255,0.35)"

# Text
TXT          = "rgba(255,255,255,0.93)"
TXT_MED      = "rgba(255,255,255,0.72)"
TXT_DIM      = "rgba(255,255,255,0.42)"

# Accent — muted, eye-friendly
ACC_GREEN    = "#66BB6A"
ACC_TEAL     = "#4DB6AC"
ACC_BLUE     = "#63C5FF"
ACC_RED      = "#EF9A9A"
ACC_PINK     = "#F48FB1"
ACC_AMBER    = "#FFD54F"
ACC_MALE     = "#90CAF9"

# Semantic
PRIMARY      = "#66BB6A"
ERROR        = "#EF9A9A"
ERROR_BG     = "rgba(239,154,154,0.12)"
SUCCESS      = "#66BB6A"
SUCCESS_BG   = "rgba(102,187,106,0.12)"

# OpenCV (BGR)
CV_GREEN = (106, 187, 102)
CV_RED   = (154, 154, 239)
CV_AMBER = (79, 213, 255)  # BGR — ACC_AMBER (#FFD54F) ga yaqin

FNT = "Segoe UI"


# ═══════════════════════════════════════════════════
# Animated particles (session_page dan)
# ═══════════════════════════════════════════════════

class _Particle:
    def __init__(self, w: float, h: float):
        self.x = random.uniform(0, w)
        self.y = random.uniform(0, h)
        self.radius = random.uniform(1.5, 4.5)
        self.opacity = random.uniform(0.06, 0.18)
        self.vx = random.uniform(-0.2, 0.2)
        self.vy = random.uniform(-0.35, -0.05)

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


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _decode_b64_pixmap(data, w: int, h: int,
                       mode=Qt.AspectRatioMode.KeepAspectRatio) -> QPixmap | None:
    """Base64 string yoki raw bytes → QPixmap. Data URI prefiksini xavfsiz olib tashlaydi."""
    if not data:
        return None
    try:
        # Bytes/memoryview kelsa to'g'ridan-to'g'ri ishlatiladi (SQLite BLOB)
        if isinstance(data, (bytes, bytearray, memoryview)):
            raw = bytes(data)
        elif isinstance(data, str):
            # Strip data URI prefix if present (e.g. "data:image/jpeg;base64,...")
            if "," in data and data.index(",") < 80:
                data = data.split(",", 1)[1]
            raw = base64.b64decode(data)
        else:
            return None
        img = QImage()
        if not img.loadFromData(raw) or img.isNull():
            return None
        return QPixmap.fromImage(img).scaled(
            w, h, mode, Qt.TransformationMode.SmoothTransformation,
        )
    except Exception:
        return None


def _shadow(blur: int = 20, y: int = 4, alpha: int = 40) -> QGraphicsDropShadowEffect:
    s = QGraphicsDropShadowEffect()
    s.setBlurRadius(blur)
    s.setOffset(0, y)
    s.setColor(QColor(0, 0, 0, alpha))
    return s


def _glass_card(name: str, radius: int = 16) -> QFrame:
    """Create a frosted-glass card."""
    card = QFrame()
    card.setObjectName(name)
    card.setStyleSheet(f"""
        QFrame#{name} {{
            background: {SRF_CARD};
            border: 1px solid {BRD};
            border-radius: {radius}px;
        }}
    """)
    return card


# ═══════════════════════════════════════════════════
# Reusable widgets
# ═══════════════════════════════════════════════════


class _StatCard(QFrame):
    """Stat badge — glass style."""

    def __init__(self, icon: str, label: str, value: str, accent: str,
                 parent=None, value_font_size: int = 14,
                 card_height: int = 55, min_width: int = 80):
        super().__init__(parent)
        self.setFixedHeight(card_height)
        self.setMinimumWidth(min_width)
        self.setStyleSheet(f"""
            QFrame {{
                background: {SRF_CARD};
                border: 1px solid {BRD};
                border-radius: 14px;
            }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 14, 8)
        row.setSpacing(10)

        if icon:
            ic_frame = QFrame()
            ic_frame.setFixedSize(38, 38)
            ic_frame.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                    border-radius: 11px;
                }}
            """)
            ic_lay = QVBoxLayout(ic_frame)
            ic_lay.setContentsMargins(0, 0, 0, 0)
            ic = QLabel(icon)
            ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ic.setFont(QFont(FNT, 15))
            ic.setStyleSheet(f"color: {accent}; background: transparent; border: none;")
            ic_lay.addWidget(ic)
            row.addWidget(ic_frame)

        col = QVBoxLayout()
        self._val = QLabel(value)
        if label == 'gr':
            value_font_size = 42
        self._val.setFont(QFont(FNT, value_font_size, QFont.Weight.Bold))
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setStyleSheet(
            f"color: {accent}; background: transparent; border: none;"
            f" font-size: {value_font_size}pt; font-weight: 800;"
        )
        col.addWidget(self._val)

        row.addLayout(col)

    def set_value(self, v: str):
        self._val.setText(v)


class _InfoRow(QFrame):
    """Single centered row in student details — value only, word-wrap optional.

    `wrap=True` — matn uzun bo'lsa bir necha qatorga bo'linib chiqadi, satr
    balandligi dinamik. Aks holda — qat'iy 38px balandlik."""

    def __init__(self, font_size: int = 12, wrap: bool = False, parent=None):
        super().__init__(parent)
        self._wrap = wrap
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-bottom: 1px solid {BRD};
            }}
        """)
        if not wrap:
            self.setFixedHeight(38)
        else:
            self.setMinimumHeight(38)

        row = QVBoxLayout(self)
        row.setContentsMargins(8, 6, 8, 6)
        row.setSpacing(0)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._val = QLabel("\u2014")
        self._val.setFont(QFont(FNT, font_size, QFont.Weight.DemiBold))
        self._val.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        self._val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._val.setWordWrap(wrap)
        if wrap:
            self._val.setSizePolicy(QSizePolicy.Policy.Expanding,
                                    QSizePolicy.Policy.Preferred)
        row.addWidget(self._val)

    def set_value(self, text: str, color: str = ""):
        c = color or TXT
        self._val.setText(text)
        self._val.setStyleSheet(f"color: {c}; background: transparent; border: none;")


class _RecentCard(QFrame):
    """Recent student card — header: FIO, body: rasm, footer: guruh. Clickable."""
    clicked = pyqtSignal(dict)

    def __init__(self, stu_data: dict, parent=None):
        super().__init__(parent)
        self._stu = stu_data
        self._ps_img_b64 = stu_data.get("ps_img") or ""
        self._is_blacklist = bool(stu_data.get("_is_blacklist", False))
        self._is_cheating = bool(stu_data.get("_is_cheating", False))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        if self._is_blacklist:
            bg = "rgba(239,154,154,0.22)"
            bd = "rgba(239,154,154,0.50)"
            bw = "2"
        elif self._is_cheating:
            bg = "rgba(255,213,79,0.22)"
            bd = "rgba(255,213,79,0.50)"
            bw = "2"
        else:
            bg = "rgba(102,187,106,0.35)"
            bd = "rgba(102,187,106,0.60)"
            bw = "1"
        self.setObjectName("recentCard")
        self.setStyleSheet(f"""
            QFrame#recentCard {{
                background: {bg};
                border: {bw}px solid {bd};
                border-radius: 12px;
            }}
        """)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 3, 5, 3)
        lay.setSpacing(2)

        # Header — familiya ism (qisqartirilgan)
        full = stu_data.get("full_name", "?")
        parts = full.split(maxsplit=1)
        short = parts[0] if parts else "?"
        if len(parts) > 1:
            short += f" {parts[1][0]}."
        nm = QLabel(short)
        nm.setFont(QFont(FNT, 1))
        nm.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        nm.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nm.setMaximumHeight(16)
        lay.addWidget(nm)

        # Body — rasm
        self._avatar = QLabel()
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._avatar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._load_photo(48, 58)
        lay.addWidget(self._avatar, alignment=Qt.AlignmentFlag.AlignCenter)

        # Footer — guruh
        gr = stu_data.get("gr_n") or ""
        gr_lbl = QLabel(f"{gr}-gr" if gr else "\u2014")
        gr_lbl.setFont(QFont(FNT, 7))
        gr_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        gr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(gr_lbl)

    def _load_photo(self, w: int, h: int):
        self._avatar.setFixedSize(w, h)
        pix = _decode_b64_pixmap(self._ps_img_b64, w, h) if self._ps_img_b64 else None
        if pix:
            self._avatar.setPixmap(pix)
            self._avatar.setStyleSheet("border-radius: 8px; border: none; background: transparent;")
        else:
            self._avatar.setText("\U0001f464")
            self._avatar.setStyleSheet(f"""
                background: {SRF_HOVER};
                border: 1px solid {BRD_ACCENT};
                border-radius: 8px;
                font-size: 18px;
            """)

    def update_photo(self, b64: str):
        """Rasmni yangilash (qayta verify qilganda)."""
        if not b64:
            return
        self._ps_img_b64 = b64
        # Modal `_stu["ps_img"]` ni carousel'dagi rasm deb o'qiydi —
        # shu yerda ham yangilab qo'yamiz, aks holda card ko'rsatayotgan
        # kadr bilan modaldagi KAMERA rasmi boshqa bo'lib qoladi.
        self._stu["ps_img"] = b64
        sz = self._avatar.size()
        self._load_photo(sz.width(), sz.height())

    @property
    def student_id(self) -> int:
        return int(self._stu.get("id") or 0)

    def set_cheating(self, cheating: bool = True):
        """Chetlatilgan holatga o'tkazish — kartaning rangini yangilash."""
        self._is_cheating = cheating
        self._stu["_is_cheating"] = cheating
        self._stu["is_cheating"] = 1 if cheating else 0
        if self._is_blacklist:
            bg = "rgba(239,154,154,0.22)"
            bd = "rgba(239,154,154,0.50)"
            bw = "2"
        elif cheating:
            bg = "rgba(255,213,79,0.22)"
            bd = "rgba(255,213,79,0.50)"
            bw = "2"
        else:
            bg = "rgba(102,187,106,0.35)"
            bd = "rgba(102,187,106,0.60)"
            bw = "1"
        self.setStyleSheet(f"""
            QFrame#recentCard {{
                background: {bg};
                border: {bw}px solid {bd};
                border-radius: 12px;
            }}
        """)

    def resize_photo(self, w: int, h: int):
        self._load_photo(w, h)

    def mousePressEvent(self, event):
        self.clicked.emit(self._stu)
        super().mousePressEvent(event)



# ═══════════════════════════════════════════════════
# FaceIDPage
# ═══════════════════════════════════════════════════

class _PinflStudentCard(QFrame):
    """Student card inside PINFL modal with photo, info, action buttons."""
    skip_clicked = pyqtSignal(dict)
    attend_clicked = pyqtSignal(dict)

    def __init__(self, stu: dict, smena_text: str, parent=None):
        super().__init__(parent)
        self._stu = stu
        self._hover = False
        self.setMinimumHeight(160)
        self.setStyleSheet("background: transparent; border: none;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Top: photo + info row ──
        top = QHBoxLayout()
        top.setContentsMargins(12, 10, 12, 8)
        top.setSpacing(14)

        # Passport photo — larger
        photo = QLabel()
        photo.setFixedSize(80, 100)
        photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        photo.setStyleSheet(f"""
            background: {SRF_FIELD};
            border: 1px solid {BRD};
            border-radius: 10px;
            color: {TXT_DIM};
            font-size: 28px;
        """)
        pix = _decode_b64_pixmap(stu.get("ps_img") or "", 80, 100)
        if pix:
            photo.setPixmap(pix)
            photo.setStyleSheet(f"""
                border: 2px solid rgba(102,187,106,0.35);
                border-radius: 10px;
                background: {SRF_FIELD};
            """)
        else:
            photo.setText("\U0001F464")
        top.addWidget(photo)

        # Info column
        info = QVBoxLayout()
        info.setSpacing(3)
        info.setContentsMargins(0, 2, 0, 2)

        fio = f"{stu.get('last_name', '')} {stu.get('first_name', '')}"
        mid = stu.get("middle_name") or ""
        if mid:
            fio += f" {mid}"
        fio_lbl = QLabel(fio)
        fio_lbl.setFont(QFont(FNT, 13, QFont.Weight.Bold))
        fio_lbl.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        fio_lbl.setWordWrap(True)
        info.addWidget(fio_lbl)

        gr = stu.get("gr_n") or 0
        sp = stu.get("sp_n") or "\u2014"
        meta = f"Guruh: {gr}  \u00b7  O\u2018rni: {sp}"
        meta_lbl = QLabel(meta)
        meta_lbl.setFont(QFont(FNT, 10))
        meta_lbl.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        info.addWidget(meta_lbl)

        subj = stu.get("subject_name") or ""
        if subj:
            subj_lbl = QLabel(subj)
            subj_lbl.setFont(QFont(FNT, 10))
            subj_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
            subj_lbl.setWordWrap(True)
            info.addWidget(subj_lbl)

        gender = stu.get("gender", 0)
        gt = {1: "\u2642 Erkak", 2: "\u2640 Ayol"}.get(gender, "")
        gc = {1: ACC_MALE, 2: ACC_PINK}.get(gender, TXT_DIM)
        if gt:
            g_lbl = QLabel(gt)
            g_lbl.setFont(QFont(FNT, 10))
            g_lbl.setStyleSheet(f"color: {gc}; background: transparent; border: none;")
            info.addWidget(g_lbl)

        if smena_text:
            sm_lbl = QLabel(smena_text)
            sm_lbl.setFont(QFont(FNT, 9))
            sm_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
            info.addWidget(sm_lbl)

        info.addStretch()
        top.addLayout(info, stretch=1)
        outer.addLayout(top)

        # ── Bottom: action buttons ──
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(12, 0, 12, 8)
        btn_row.setSpacing(6)
        btn_row.addStretch()

        MB_H = 28
        MB_R = 8
        MB_FNT = QFont(FNT, 9, QFont.Weight.DemiBold)

        skip_btn = QPushButton("\u2717  Chetlatish")
        skip_btn.setFixedHeight(MB_H)
        skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        skip_btn.setFont(MB_FNT)
        skip_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,154,154,0.18);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.30);
                border-radius: {MB_R}px;
                padding: 0 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.30);
                color: #fff;
                border-color: rgba(239,154,154,0.55);
            }}
        """)
        skip_btn.clicked.connect(lambda: self.skip_clicked.emit(self._stu))
        btn_row.addWidget(skip_btn)

        attend_btn = QPushButton("\u2713  Qo\u2018shish")
        attend_btn.setFixedHeight(MB_H)
        attend_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        attend_btn.setFont(MB_FNT)
        attend_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(102,187,106,0.15);
                color: {ACC_GREEN};
                border: 1px solid rgba(102,187,106,0.30);
                border-radius: {MB_R}px;
                padding: 0 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(102,187,106,0.28);
                border-color: rgba(102,187,106,0.50);
            }}
        """)
        attend_btn.clicked.connect(lambda: self.attend_clicked.emit(self._stu))
        btn_row.addWidget(attend_btn)

        outer.addLayout(btn_row)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 14, 14)
        if self._hover:
            p.fillPath(path, QColor(99, 197, 255, 18))
            p.setPen(QPen(QColor(99, 197, 255, 50), 1))
        else:
            p.fillPath(path, QColor(255, 255, 255, 10))
            p.setPen(QPen(QColor(255, 255, 255, 25), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w - 2, h - 2, 14, 14)
        p.end()

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)


class _StudentDetailModal(QDialog):
    """MD3 modal — student to'liq ma'lumoti + pasport vs kamera rasm solishtirish."""

    def __init__(self, stu: dict, entry: dict | None = None,
                 captured_override=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._build(stu, entry or {}, captured_override)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    def mousePressEvent(self, event):
        if not self.childAt(event.pos()):
            self.reject()
        super().mousePressEvent(event)

    def _build(self, stu: dict, entry: dict, captured_override=None):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("detailCard")
        card.setFixedWidth(720)
        card.setStyleSheet(f"""
            QFrame#detailCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20,35,60,0.97), stop:1 rgba(12,22,42,0.97));
                border: 1px solid {BRD_ACCENT};
                border-radius: 20px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 140))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Top section: photos side-by-side + close button ──
        top_frame = QFrame()
        top_frame.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(99,197,255,0.07), stop:1 rgba(102,187,106,0.05));
                border: none;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }}
        """)
        top_lay = QVBoxLayout(top_frame)
        top_lay.setContentsMargins(20, 10, 20, 18)
        top_lay.setSpacing(6)

        # Close button — top right
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("\u00D7")
        close_btn.setFont(QFont(FNT, 18, QFont.Weight.Bold))
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.16);
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.22);
                border-radius: 16px;
                padding: 0 0 3px 0;
                text-align: center;
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.28);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.45);
            }}
            QPushButton:pressed {{ background: rgba(239,154,154,0.4); }}
        """)
        close_btn.clicked.connect(self.reject)
        close_row.addWidget(close_btn)
        top_lay.addLayout(close_row)

        # Photos row — passport vs captured
        PH_W, PH_H = 260, 300
        photos_row = QHBoxLayout()
        photos_row.setSpacing(20)
        photos_row.addStretch()

        def _photo_block(caption: str, src, border_rgb: str, placeholder: str):
            box = QVBoxLayout()
            box.setSpacing(8)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)

            cap = QLabel(caption)
            cap.setFont(QFont(FNT, 9, QFont.Weight.Bold))
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap.setStyleSheet(
                f"color: {TXT_DIM}; background: transparent; border: none; "
                f"letter-spacing: 1.5px;"
            )
            box.addWidget(cap)

            ph = QLabel()
            ph.setFixedSize(PH_W, PH_H)
            ph.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = _decode_b64_pixmap(src, PH_W, PH_H) if src else None
            if pix:
                ph.setPixmap(pix)
                ph.setStyleSheet(
                    f"border: 2px solid rgba({border_rgb},0.45); "
                    f"border-radius: 16px; background: {SRF_FIELD};"
                )
            else:
                ph.setText(placeholder)
                ph.setStyleSheet(
                    f"background: {SRF_FIELD}; border: 1px dashed {BRD_ACCENT}; "
                    f"border-radius: 16px; color: {TXT_DIM}; font-size: 56px;"
                )
            box.addWidget(ph, alignment=Qt.AlignmentFlag.AlignCenter)
            return box

        photos_row.addLayout(_photo_block(
            "Pasport", stu.get("ps_img") or "", "99,197,255", "\U0001F464"
        ))
        # KAMERA slot prioriteti: carousel cardda ko'rsatilayotgan aynan shu kadr →
        # agar u bo'lmasa, entry_log.last_captured → first_captured. Shu tartib
        # foydalanuvchiga carousel dagi rasm aynan modalda ham chiqishini kafolatlaydi.
        cap_src = captured_override or entry.get("last_captured") or entry.get("first_captured")
        photos_row.addLayout(_photo_block(
            "Kamera", cap_src, "102,187,106", "\U0001F4F7"
        ))
        photos_row.addStretch()
        top_lay.addLayout(photos_row)

        # O'xshashlik chiplari — score + max_score (sqrt-boost qilingan foiz)
        score_v = int(entry.get("score") or 0)
        max_v = int(entry.get("max_score") or 0)
        if score_v or max_v:
            sim_row = QHBoxLayout()
            sim_row.setSpacing(10)
            sim_row.addStretch()

            def _sim_chip(label: str, value: int, color: str, rgb: str) -> QLabel:
                chip = QLabel(f"{label}: {value}%")
                chip.setFont(QFont(FNT, 9, QFont.Weight.Bold))
                chip.setFixedHeight(26)
                chip.setStyleSheet(
                    f"color: {color}; background: rgba({rgb},0.12); "
                    f"border: 1px solid rgba({rgb},0.28); border-radius: 8px; "
                    f"padding: 0 12px;"
                )
                return chip

            sim_row.addWidget(_sim_chip("O\u2018xshashlik", score_v, ACC_BLUE, "99,197,255"))
            sim_row.addWidget(_sim_chip("Maksimal", max_v, ACC_GREEN, "102,187,106"))
            sim_row.addStretch()
            top_lay.addSpacing(4)
            top_lay.addLayout(sim_row)

        top_lay.addSpacing(10)

        # FIO
        fio = f"{stu.get('last_name', '')} {stu.get('first_name', '')}"
        mid = stu.get("middle_name") or ""
        if mid:
            fio += f" {mid}"
        fio_lbl = QLabel(fio)
        fio_lbl.setFont(QFont(FNT, 15, QFont.Weight.Bold))
        fio_lbl.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        fio_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fio_lbl.setWordWrap(True)
        top_lay.addWidget(fio_lbl)

        # Gender + status chips row
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addStretch()

        gender = stu.get("gender", 0)
        gt = {1: "\u2642 Erkak", 2: "\u2640 Ayol"}.get(gender, "")
        # rgba tuples for chip bg/border
        gc_map = {1: (ACC_MALE, "144,202,249"), 2: (ACC_PINK, "244,143,177")}
        gc, gc_rgb = gc_map.get(gender, (TXT_DIM, "255,255,255"))
        if gt:
            g_chip = QLabel(gt)
            g_chip.setFont(QFont(FNT, 5, QFont.Weight.Bold))
            g_chip.setFixedHeight(22)
            g_chip.setStyleSheet(f"""
                color: {gc}; background: rgba({gc_rgb},0.10);
                border: 1px solid rgba({gc_rgb},0.20); border-radius: 7px;
                padding: 0 8px;
            """)
            chips_row.addWidget(g_chip)

        entered = stu.get("is_entered", 0)
        cheating = stu.get("is_cheating", 0)
        if entered:
            s_chip = QLabel("\u2713 Davomatda")
            s_chip.setFont(QFont(FNT, 5, QFont.Weight.Bold))
            s_chip.setFixedHeight(22)
            s_chip.setStyleSheet(f"""
                color: {ACC_GREEN}; background: rgba(102,187,106,0.10);
                border: 1px solid rgba(102,187,106,0.20); border-radius: 7px;
                padding: 0 8px;
            """)
            chips_row.addWidget(s_chip)
        if cheating:
            c_chip = QLabel("\u2717 Chetlatilgan")
            c_chip.setFont(QFont(FNT, 5, QFont.Weight.Bold))
            c_chip.setFixedHeight(22)
            c_chip.setStyleSheet(f"""
                color: {ACC_RED}; background: rgba(239,154,154,0.10);
                border: 1px solid rgba(239,154,154,0.20); border-radius: 7px;
                padding: 0 8px;
            """)
            chips_row.addWidget(c_chip)

        chips_row.addStretch()
        top_lay.addLayout(chips_row)

        lay.addWidget(top_frame)

        # ── Bottom section: details ──
        bot = QVBoxLayout()
        bot.setContentsMargins(22, 14, 22, 18)
        bot.setSpacing(1)

        UZ_MONTHS = (
            "yanvar", "fevral", "mart", "aprel", "may", "iyun",
            "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
        )

        def _fmt_dt(raw) -> str:
            """Vaqtni foydalanuvchiga do'stona formatda qaytaradi.
            Bugun/Kecha — nisbiy, boshqa sanalar — o'zbekcha oy nomi bilan.
            `add_entry_log`/`update_entry_log` da ISO ("YYYY-MM-DDTHH:MM:SS.xxx")
            format ishlatiladi; SQLite DEFAULT esa ("YYYY-MM-DD HH:MM:SS") — har
            ikkalasini ham qabul qilamiz (T → ' ' va mikrosekundlarni kesamiz)."""
            if not raw:
                return "\u2014"
            s = str(raw).strip()
            candidate = s[:19].replace("T", " ")
            try:
                dt = datetime.strptime(candidate, "%Y-%m-%d %H:%M:%S")
            except Exception:
                return s
            today = datetime.now().date()
            delta = (today - dt.date()).days
            hms = dt.strftime("%H:%M:%S")
            if delta == 0:
                return f"Bugun  \u2022  {hms}"
            if delta == 1:
                return f"Kecha  \u2022  {hms}"
            month = UZ_MONTHS[dt.month - 1]
            if dt.year == today.year:
                return f"{dt.day}-{month}  \u2022  {hms}"
            return f"{dt.day}-{month} {dt.year}  \u2022  {hms}"

        ROW_H = 63
        details = [
            ("GURUH: ", str(stu.get("gr_n") or "\u2014")),
            ("JOY: ", str(stu.get("sp_n") or "\u2014")),
            ("FAN: ", stu.get("subject_name") or "\u2014"),
            ("JShShIR: ", stu.get("imei") or "\u2014"),
            ("KIRGAN: ", _fmt_dt(entry.get("first_enter_time"))),
            ("OXIRGI: ", _fmt_dt(entry.get("last_enter_time"))),
        ]
        for i, (label, value) in enumerate(details):
            r = QHBoxLayout()
            r.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label)
            lbl.setFont(QFont(FNT, 10))
            lbl.setFixedHeight(ROW_H)
            lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
            lbl.setFixedWidth(72)
            r.addWidget(lbl)
            val = QLabel(value)
            val.setFont(QFont(FNT, 11, QFont.Weight.DemiBold))
            val.setFixedHeight(ROW_H)
            val.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
            val.setWordWrap(True)
            r.addWidget(val, stretch=1)
            bot.addLayout(r)
            if i < len(details) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background: {BRD};")
                bot.addWidget(sep)

        lay.addLayout(bot)
        outer.addWidget(card)


class _RejectReasonModal(QDialog):
    """Chetlatish sababini tanlash modali — 2 ta select (reason type + reason)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self._db = db
        self._selected_reason_id: int | None = None
        self._selected_reason_name: str = ""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._setup_ui()
        self._load_reason_types()

    @property
    def reason_id(self) -> int | None:
        return self._selected_reason_id

    @property
    def reason_name(self) -> str:
        return self._selected_reason_name

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    # ── Pill/chip va reason card stillari ──

    @staticmethod
    def _type_pill_style(selected: bool) -> str:
        if selected:
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(239,154,154,0.42),
                        stop:1 rgba(239,154,154,0.28));
                    color: #fff;
                    border: 1.5px solid rgba(239,154,154,0.85);
                    border-radius: 14px;
                    padding: 0 18px;
                    font-family: {FONT_FAMILY};
                    font-weight: 600;
                    letter-spacing: 0.3px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(239,154,154,0.55),
                        stop:1 rgba(239,154,154,0.38));
                    border-color: #fff;
                }}
            """
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.06);
                color: {TXT_MED};
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 14px;
                padding: 0 18px;
                font-family: {FONT_FAMILY};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.14);
                color: #fff;
                border-color: rgba(239,154,154,0.42);
            }}
        """

    @staticmethod
    def _reason_card_style(selected: bool) -> str:
        if selected:
            return f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 rgba(239,154,154,0.22),
                        stop:1 rgba(239,154,154,0.10));
                    color: #fff;
                    border: 1.5px solid rgba(239,154,154,0.75);
                    border-radius: 14px;
                    padding: 14px 18px;
                    text-align: left;
                    font-family: {FONT_FAMILY};
                    font-weight: 600;
                    letter-spacing: 0.2px;
                }}
            """
        return f"""
            QPushButton {{
                background: rgba(255,255,255,0.05);
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 14px;
                padding: 14px 18px;
                text-align: left;
                font-family: {FONT_FAMILY};
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.10);
                border-color: rgba(239,154,154,0.42);
                color: #fff;
            }}
        """

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("rejectCard")
        card.setFixedWidth(520)
        card.setStyleSheet(f"""
            QFrame#rejectCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {BRD};
                border-radius: 22px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # ── Header: ogohlantirish belgisi + sarlavha ──
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        warn_icon = QLabel("\u26A0")
        warn_icon.setFixedSize(42, 42)
        warn_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warn_icon.setStyleSheet(f"""
            background: rgba(239,154,154,0.18);
            border: 1px solid rgba(239,154,154,0.35);
            border-radius: 13px;
            color: {ACC_RED};
            font-size: 20px;
        """)
        hdr.addWidget(warn_icon)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Chetlatish sababi")
        title.setFont(QFont(FNT, 15, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none; letter-spacing: 0.3px;")
        title_col.addWidget(title)

        subtitle = QLabel("Sababni aniq tanlang \u2014 logga yoziladi")
        subtitle.setFont(QFont(FNT, 10))
        subtitle.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        title_col.addWidget(subtitle)

        hdr.addLayout(title_col, stretch=1)
        lay.addLayout(hdr)

        lay.addSpacing(4)

        # ── Sabab turi: chip pill'lar ──
        lbl1 = QLabel("Qachon")
        lbl1.setFont(QFont(FNT, 10, QFont.Weight.Bold))
        lbl1.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none; letter-spacing: 0.4px;")
        lay.addWidget(lbl1)

        self._type_row = QHBoxLayout()
        self._type_row.setSpacing(10)
        self._type_row.setContentsMargins(0, 0, 0, 0)
        self._type_buttons: list[QPushButton] = []
        self._type_group = QButtonGroup(self)
        self._type_group.setExclusive(True)
        lay.addLayout(self._type_row)

        # ── Sabab ro'yxati: radio card'lar ──
        lbl2 = QLabel("Sabab")
        lbl2.setFont(QFont(FNT, 10, QFont.Weight.Bold))
        lbl2.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none; letter-spacing: 0.4px;")
        lay.addWidget(lbl2)

        # Reason list uchun container (dinamik to'ldiriladi)
        self._reason_container = QFrame()
        self._reason_container.setStyleSheet("background: transparent; border: none;")
        self._reason_layout = QVBoxLayout(self._reason_container)
        self._reason_layout.setContentsMargins(0, 0, 0, 0)
        self._reason_layout.setSpacing(8)
        lay.addWidget(self._reason_container)

        self._reason_buttons: list[QPushButton] = []
        self._reason_group = QButtonGroup(self)
        self._reason_group.setExclusive(True)

        lay.addSpacing(6)

        # ── Tugmalar: Bekor / Chetlatish ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        cancel_btn = QPushButton("Bekor qilish")
        cancel_btn.setFixedHeight(44)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setFont(QFont(FNT, 12, QFont.Weight.DemiBold))
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {TXT_MED};
                border: 1px solid rgba(255,255,255,0.18);
                border-radius: 13px;
                padding: 0 22px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.07);
                color: {TXT};
                border-color: rgba(255,255,255,0.28);
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.12);
            }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn, stretch=1)

        self._ok_btn = QPushButton("\u2717  Chetlatish")
        self._ok_btn.setFixedHeight(44)
        self._ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ok_btn.setFont(QFont(FNT, 12, QFont.Weight.Bold))
        self._ok_btn.setEnabled(False)
        self._ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #e57373, stop:1 #c55454);
                color: #ffffff;
                border: 1px solid rgba(255,180,180,0.55);
                border-radius: 13px;
                padding: 0 24px;
                font-family: {FONT_FAMILY};
                letter-spacing: 0.4px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f08989, stop:1 #d66161);
                border-color: #ffd1d1;
            }}
            QPushButton:pressed {{
                background: #b54646;
            }}
            QPushButton:disabled {{
                background: rgba(255,255,255,0.05);
                color: rgba(255,255,255,0.28);
                border-color: rgba(255,255,255,0.08);
            }}
        """)
        self._ok_btn.clicked.connect(self._on_confirm)
        btn_row.addWidget(self._ok_btn, stretch=2)
        lay.addLayout(btn_row)

        outer.addWidget(card)

    def _load_reason_types(self):
        """Sabab turlarini pill chip sifatida yaratadi."""
        types = self._db.get_reason_types()
        # Oldingi pill'larni tozalash (qayta ochilgan holat uchun)
        for b in self._type_buttons:
            self._type_group.removeButton(b)
            b.deleteLater()
        self._type_buttons = []

        for t in types:
            btn = QPushButton(t["name"])
            btn.setCheckable(True)
            btn.setFixedHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFont(QFont(FNT, 11, QFont.Weight.DemiBold))
            btn.setStyleSheet(self._type_pill_style(False))
            btn.setProperty("type_id", int(t["id"]))
            btn.clicked.connect(lambda _=False, b=btn: self._on_type_selected(b))
            self._type_group.addButton(btn)
            self._type_row.addWidget(btn)
            self._type_buttons.append(btn)

        self._type_row.addStretch()

        if self._type_buttons:
            self._type_buttons[0].setChecked(True)
            self._on_type_selected(self._type_buttons[0])

    def _on_type_selected(self, btn: QPushButton):
        """Tur tanlanganda pill'lar styli yangilanadi va sabablar ro'yxati qayta yuklanadi."""
        for b in self._type_buttons:
            b.setStyleSheet(self._type_pill_style(b is btn))
        type_id = btn.property("type_id")
        self._load_reasons(int(type_id) if type_id is not None else None)

    def _load_reasons(self, type_id: int | None):
        """Tanlangan tur uchun sabab card'larini yaratadi."""
        # Eski card'larni tozalash
        for b in self._reason_buttons:
            self._reason_group.removeButton(b)
            b.deleteLater()
        self._reason_buttons = []
        self._selected_reason_id = None
        self._selected_reason_name = ""
        self._ok_btn.setEnabled(False)

        if type_id is None:
            return

        reasons = self._db.get_reasons_by_type(type_id)
        for r in reasons:
            card = QPushButton(f"\u25CB   {r['name']}")
            card.setCheckable(True)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setFont(QFont(FNT, 12, QFont.Weight.Medium))
            card.setMinimumHeight(50)
            card.setStyleSheet(self._reason_card_style(False))
            card.setProperty("reason_id", int(r["id"]))
            card.setProperty("reason_name", r["name"])
            card.clicked.connect(lambda _=False, c=card: self._on_reason_selected(c))
            self._reason_group.addButton(card)
            self._reason_layout.addWidget(card)
            self._reason_buttons.append(card)

    def _on_reason_selected(self, card: QPushButton):
        """Sabab card tanlandi — styl yangilanadi, confirm tugmasi yoqiladi."""
        for c in self._reason_buttons:
            if c is card:
                c.setStyleSheet(self._reason_card_style(True))
                c.setText(f"\u25CF   {c.property('reason_name')}")
            else:
                c.setStyleSheet(self._reason_card_style(False))
                c.setText(f"\u25CB   {c.property('reason_name')}")

        rid = card.property("reason_id")
        if rid is not None:
            self._selected_reason_id = int(rid)
            self._selected_reason_name = str(card.property("reason_name") or "")
            self._ok_btn.setEnabled(True)

    def _on_confirm(self):
        if self._selected_reason_id is None:
            return
        self.accept()


class _SyncModal(QDialog):
    """Yuborish jarayoni modali — spinner, stats (jami/yuborilgan/yuborilmagan), progress."""

    def __init__(self, stats: dict, parent=None):
        super().__init__(parent)
        self._stats = {
            "total": stats.get("total", 0),
            "sent": stats.get("sent", 0),
            "unsent": stats.get("unsent", 0),
        }
        self._unsent_count = self._stats["unsent"]
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._finished = False
        self._spin_angle = 0
        self._build()
        self._spin_timer = QTimer(self)
        self._spin_timer.timeout.connect(self._tick_spinner)
        self._spin_timer.start(60)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    def mousePressEvent(self, event):
        if self._finished and not self.childAt(event.pos()):
            self.accept()
        super().mousePressEvent(event)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("syncCard")
        card.setFixedWidth(400)
        card.setStyleSheet(f"""
            QFrame#syncCard {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(20,35,60,0.97), stop:1 rgba(12,22,42,0.97));
                border: 1px solid {BRD_ACCENT};
                border-radius: 20px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 140))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(32, 28, 32, 24)
        lay.setSpacing(16)

        title = QLabel("Ma'lumotlarni yuborish")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont(FNT, 15, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        lay.addWidget(title)

        self._spinner_label = QLabel()
        self._spinner_label.setFixedSize(48, 48)
        self._spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner_label.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(self._spinner_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Stats row: Jami / Yuborilgan / Yuborilmagan ──
        stats_row = QFrame()
        stats_row.setStyleSheet(f"""
            QFrame {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 12px;
            }}
        """)
        stats_lay = QHBoxLayout(stats_row)
        stats_lay.setContentsMargins(12, 12, 12, 12)
        stats_lay.setSpacing(8)

        self._stat_total_val, total_col = self._build_stat_col(
            "Jami", self._stats["total"], ACC_BLUE
        )
        self._stat_sent_val, sent_col = self._build_stat_col(
            "Yuborilgan", self._stats["sent"], ACC_GREEN
        )
        self._stat_unsent_val, unsent_col = self._build_stat_col(
            "Yuborilmagan", self._stats["unsent"], ACC_AMBER
        )
        stats_lay.addWidget(total_col, stretch=1)
        stats_lay.addWidget(self._vline(), stretch=0)
        stats_lay.addWidget(sent_col, stretch=1)
        stats_lay.addWidget(self._vline(), stretch=0)
        stats_lay.addWidget(unsent_col, stretch=1)

        lay.addWidget(stats_row)

        self._status_label = QLabel(
            f"{self._unsent_count} ta yozuv yuborilmoqda..."
            if self._unsent_count > 0 else "Yuborilmagan yozuv yo'q"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setWordWrap(True)
        self._status_label.setFont(QFont(FNT, 12))
        self._status_label.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        lay.addWidget(self._status_label)

        self._progress_label = QLabel("0 / {0}".format(self._unsent_count))
        self._progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._progress_label.setFont(QFont(FNT, 20, QFont.Weight.Bold))
        self._progress_label.setStyleSheet(f"color: {ACC_BLUE}; background: transparent; border: none;")
        lay.addWidget(self._progress_label)

        self._close_btn = QPushButton("Yopish")
        self._close_btn.setFixedHeight(40)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setFont(QFont(FNT, 12, QFont.Weight.DemiBold))
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: {SRF_FIELD};
                color: {TXT};
                border: 1px solid {BRD_ACCENT};
                border-radius: 10px;
            }}
            QPushButton:hover {{ background: {SRF_HOVER}; }}
        """)
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setVisible(False)
        lay.addWidget(self._close_btn)

        outer.addWidget(card)

    def _build_stat_col(self, title: str, value: int, color: str):
        col = QFrame()
        col.setStyleSheet("background: transparent; border: none;")
        v = QVBoxLayout(col)
        v.setContentsMargins(4, 2, 4, 2)
        v.setSpacing(2)

        val_lbl = QLabel(str(value))
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setFont(QFont(FNT, 18, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")

        title_lbl = QLabel(title)
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setFont(QFont(FNT, 10))
        title_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")

        v.addWidget(val_lbl)
        v.addWidget(title_lbl)
        return val_lbl, col

    def _vline(self) -> QFrame:
        line = QFrame()
        line.setFixedWidth(1)
        line.setStyleSheet(f"background: {BRD}; border: none;")
        return line

    def update_stats(self, stats: dict):
        """DB'dan yangilangan statistikani modalda ko'rsatish."""
        self._stats = {
            "total": stats.get("total", 0),
            "sent": stats.get("sent", 0),
            "unsent": stats.get("unsent", 0),
        }
        self._stat_total_val.setText(str(self._stats["total"]))
        self._stat_sent_val.setText(str(self._stats["sent"]))
        self._stat_unsent_val.setText(str(self._stats["unsent"]))

    def _tick_spinner(self):
        if self._finished:
            return
        self._spin_angle = (self._spin_angle + 30) % 360
        size = 48
        pix = QPixmap(QSize(size, size))
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = size / 2, size / 2, 18
        dot_count = 8
        for i in range(dot_count):
            angle = math.radians(self._spin_angle + i * (360 / dot_count))
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            alpha = int(255 * (1.0 - i / dot_count))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(99, 197, 255, alpha))
            dot_r = 4.0 if i == 0 else 3.0
            p.drawEllipse(QPointF(x, y), dot_r, dot_r)
        p.end()
        self._spinner_label.setPixmap(pix)

    @pyqtSlot(int, int)
    def on_progress(self, sent: int, total: int):
        self._progress_label.setText(f"{sent} / {total}")
        if total > 0:
            self._status_label.setText(f"Yuborilmoqda... ({sent * 100 // total}%)")

    @pyqtSlot(str)
    def on_status(self, msg: str):
        self._status_label.setText(msg)

    def on_finished(self, error: str = ""):
        self._finished = True
        self._spin_timer.stop()
        self._close_btn.setVisible(True)
        if error:
            self._spinner_label.setText("\u26a0")
            self._spinner_label.setFont(QFont(FNT, 24))
            self._spinner_label.setStyleSheet(f"color: {ACC_RED}; background: transparent; border: none;")
            self._status_label.setText(error)
            self._status_label.setStyleSheet(f"color: {ACC_RED}; background: transparent; border: none;")
        else:
            self._spinner_label.setText("\u2714")
            self._spinner_label.setFont(QFont(FNT, 24))
            self._spinner_label.setStyleSheet(f"color: {ACC_GREEN}; background: transparent; border: none;")
            self._status_label.setText("Muvaffaqiyatli yuborildi!")
            self._status_label.setStyleSheet(f"color: {ACC_GREEN}; background: transparent; border: none;")
            self._progress_label.setStyleSheet(f"color: {ACC_GREEN}; background: transparent; border: none;")


class _PinflModal(QDialog):
    """MD3 modal — JShShIR qidiruv, studentlar listi."""
    student_selected = pyqtSignal(dict)
    student_skipped = pyqtSignal(dict)

    def __init__(self, db, session_sm_id: int, staff_id: int, parent=None):
        super().__init__(parent)
        self._db = db
        self._session_sm_id = session_sm_id
        self._staff_id = staff_id
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._setup_ui()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. Solid dark scrim — fully opaque
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))

        # 2. Subtle radial vignette — darker edges, lighter center
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)

        p.end()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("pinflCard")
        card.setFixedWidth(540)
        card.setMaximumHeight(640)
        card.setStyleSheet(f"""
            QFrame#pinflCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {BRD};
                border-radius: 24px;
            }}
        """)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 24, 24, 20)
        lay.setSpacing(0)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("JShShIR bo\u2018yicha qidiruv")
        title.setFont(QFont(FNT, 16, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedHeight(24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.16);
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.22);
                border-radius: 16px;
                font-size: 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.28);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.45);
            }}
            QPushButton:pressed {{
                background: rgba(239,154,154,0.4);
            }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)
        lay.addSpacing(30)

        # PINFL input
        self._pinfl_input = QLineEdit()
        self._pinfl_input.setPlaceholderText("14 xonali JShShIR kiriting")
        self._pinfl_input.setMaxLength(14)
        self._pinfl_input.setFixedHeight(46)
        self._pinfl_input.setFont(QFont(FNT, 15, QFont.Weight.Medium))
        self._pinfl_input.setStyleSheet(f"""
            QLineEdit {{
                background: {SRF_FIELD};
                color: {TXT};
                border: 2px solid {BRD};
                border-radius: 14px;
                padding: 4px 18px;
                font-family: {FONT_FAMILY};
                letter-spacing: 2px;
            }}
            QLineEdit:focus {{
                border: 2px solid {ACC_BLUE};
            }}
            QLineEdit::placeholder {{
                color: {TXT_DIM};
                letter-spacing: 0px;
            }}
        """)
        self._pinfl_input.textChanged.connect(self._on_text_changed)
        lay.addWidget(self._pinfl_input)
        lay.addSpacing(12)

        # Result count label
        self._count_lbl = QLabel("")
        self._count_lbl.setFont(QFont(FNT, 11))
        self._count_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        lay.addWidget(self._count_lbl)
        lay.addSpacing(6)

        # Scrollable student list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QWidget {{ background: transparent; }}
            QScrollBar:vertical {{
                background: transparent; width: 5px; margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(255,255,255,0.15);
                border-radius: 2px; min-height: 30px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
        """)
        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(6)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        lay.addWidget(scroll, stretch=1)

        # Not found label
        self._not_found = QLabel("")
        self._not_found.setFont(QFont(FNT, 12))
        self._not_found.setStyleSheet(f"color: {ACC_RED}; background: transparent; border: none;")
        self._not_found.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._not_found)

        outer.addWidget(card)
        self._pinfl_input.setFocus()

    def _clear_list(self):
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_text_changed(self, text: str):
        digits = "".join(c for c in text if c.isdigit())
        if digits != text:
            self._pinfl_input.setText(digits)
            return

        self._not_found.setText("")
        self._count_lbl.setText("")
        if len(digits) == 14:
            self._lookup(digits)
        else:
            self._clear_list()

    def _lookup(self, pinfl: str):
        rows = self._db.get_student_by_pinfl(pinfl, self._session_sm_id)
        self._clear_list()

        if not rows:
            self._not_found.setText("Student topilmadi")
            self._count_lbl.setText("")
            return

        self._not_found.setText("")
        self._count_lbl.setText(f"{len(rows)} ta natija topildi")

        sm_row = self._db.get_smena_with_session(self._session_sm_id)
        smena_text = ""
        if sm_row:
            smena_text = f"{sm_row['test_day']} \u00b7 {sm_row['sm']}-sm"

        for r in rows:
            stu = dict(r)
            # Downstream kod (entry_log, get_student, mark_*) API id bilan ishlaydi —
            # stu["id"] ni student_id (API id) ga tenglashtirish.
            stu["id"] = stu["student_id"]
            card = _PinflStudentCard(stu, smena_text)
            card.attend_clicked.connect(self._on_attend)
            card.skip_clicked.connect(self._on_skip)
            self._list_layout.insertWidget(self._list_layout.count() - 1, card)

    def _on_attend(self, stu: dict):
        self.student_selected.emit(stu)
        self.accept()

    def _on_skip(self, stu: dict):
        self.student_skipped.emit(stu)
        self.accept()


class _AlertModal(QDialog):
    """MD3 ogohlantirish modali — icon + sarlavha + matn + bitta OK tugmasi.

    Boshqa modallar (PinflModal, RejectReasonModal) bilan bir xil uslub:
    scrim + vignette paint, glass card, drop shadow.

    Accent — tugma/ikon rangi uchun: 'warn' (amber), 'error' (red), 'info' (blue).
    """

    def __init__(self, title: str, message: str,
                 accent: str = "warn", icon: str = "\u26a0",
                 ok_text: str = "Tushunarli", parent=None):
        super().__init__(parent)
        self._title = title
        self._message = message
        self._icon = icon
        self._accent = accent
        self._ok_text = ok_text
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._setup_ui()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    def _accent_color(self) -> str:
        return {
            "warn":  ACC_AMBER,
            "error": ACC_RED,
            "info":  ACC_BLUE,
        }.get(self._accent, ACC_AMBER)

    def _accent_rgba(self, alpha: float) -> str:
        rgb = {
            "warn":  (255, 213, 79),
            "error": (239, 154, 154),
            "info":  (99, 197, 255),
        }.get(self._accent, (255, 213, 79))
        return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha})"

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("alertCard")
        card.setFixedWidth(440)
        card.setStyleSheet(f"""
            QFrame#alertCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {BRD};
                border-radius: 20px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(24, 22, 24, 20)
        lay.setSpacing(14)

        # Header: icon chip + title + close
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        icon_lbl = QLabel(self._icon)
        icon_lbl.setFixedSize(44, 44)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont(FNT, 20, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"""
            background: {self._accent_rgba(0.18)};
            color: {self._accent_color()};
            border: 1px solid {self._accent_rgba(0.40)};
            border-radius: 22px;
        """)
        hdr.addWidget(icon_lbl)

        title = QLabel(self._title)
        title.setFont(QFont(FNT, 15, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        hdr.addWidget(title)
        hdr.addStretch()

        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(32, 32)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(255,255,255,0.16);
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.22);
                border-radius: 16px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.28);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.45);
            }}
        """)
        close_btn.clicked.connect(self.reject)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        # Message
        msg = QLabel(self._message)
        msg.setWordWrap(True)
        msg.setFont(QFont(FNT, 12))
        msg.setStyleSheet(f"""
            color: {TXT_MED};
            background: transparent;
            border: none;
            padding: 0 2px;
            line-height: 1.4;
        """)
        lay.addWidget(msg)

        lay.addSpacing(4)

        # OK button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton(self._ok_text)
        ok_btn.setFixedHeight(36)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFont(QFont(FNT, 10, QFont.Weight.DemiBold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self._accent_rgba(0.22)};
                color: {self._accent_color()};
                border: 1px solid {self._accent_rgba(0.45)};
                border-radius: 10px;
                padding: 0 22px;
            }}
            QPushButton:hover {{
                background: {self._accent_rgba(0.35)};
                color: #fff;
                border-color: {self._accent_rgba(0.65)};
            }}
            QPushButton:pressed {{
                background: {self._accent_rgba(0.45)};
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        outer.addWidget(card)


class _StatsModal(QDialog):
    """MD3 statistika modali — online rejimda davomat holatini ko'rsatadi.

    Jami / Verify qilingan / Yuborilgan / Yuborilmagan — to'rt ustunda, ranglari
    bilan ajratilgan. Stats — `DatabaseManager.count_entries_stats()` natijasi."""

    def __init__(self, stats: dict, show_server: bool = False, parent=None):
        super().__init__(parent)
        self._stats = {
            "total": stats.get("total", 0),
            "verified": stats.get("verified", 0),
            "sent": stats.get("sent", 0),
            "unsent": stats.get("unsent", 0),
        }
        self._show_server = show_server
        # Server bo'limi holati — set_server_stats/error chaqirilgach yangilanadi.
        self._server_body_layout: QVBoxLayout | None = None
        self._spinner_label: QLabel | None = None
        self._spin_timer: QTimer | None = None
        self._spin_angle = 0
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        if parent:
            self.resize(parent.size())
        self._setup_ui()
        if self._show_server:
            self._render_server_loading()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(8, 14, 22, 240))
        center = QPointF(w / 2, h / 2)
        vignette = QRadialGradient(center, max(w, h) * 0.6)
        vignette.setColorAt(0.0, QColor(15, 25, 40, 0))
        vignette.setColorAt(0.7, QColor(5, 10, 18, 60))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 120))
        p.fillRect(self.rect(), vignette)
        p.end()

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("statsCard")
        card.setFixedWidth(520)
        card.setStyleSheet(f"""
            QFrame#statsCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(255,255,255,26), stop:1 rgba(255,255,255,13));
                border: 1px solid {BRD};
                border-radius: 22px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 20)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(16)

        # ── Header ──
        hdr = QHBoxLayout()
        hdr.setSpacing(12)

        icon_lbl = QLabel("\U0001F4CA")
        icon_lbl.setFixedSize(44, 44)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont(FNT, 18, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"""
            background: rgba(99,197,255,0.18);
            color: {ACC_BLUE};
            border: 1px solid rgba(99,197,255,0.40);
            border-radius: 22px;
        """)
        hdr.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("Davomat statistikasi")
        title.setFont(QFont(FNT, 15, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        subtitle = QLabel("Shu kompyuterda to\u2018plangan ma\u2018lumotlar")
        subtitle.setFont(QFont(FNT, 10))
        subtitle.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        hdr.addLayout(title_box)
        hdr.addStretch()

        # close_btn = QPushButton("\u2715")
        # close_btn.setFixedSize(32, 32)
        # close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # close_btn.setStyleSheet(f"""
        #     QPushButton {{
        #         background: rgba(255,255,255,0.16);
        #         color: {TXT};
        #         border: 1px solid rgba(255,255,255,0.22);
        #         border-radius: 16px;
        #         font-size: 14px;
        #         font-weight: bold;
        #     }}
        #     QPushButton:hover {{
        #         background: rgba(239,154,154,0.28);
        #         color: {ACC_RED};
        #         border: 1px solid rgba(239,154,154,0.45);
        #     }}
        # """)
        # close_btn.clicked.connect(self.accept)
        # hdr.addWidget(close_btn)

        lay.addLayout(hdr)

        # ── Stat cards (2x2 grid) ──
        grid = QVBoxLayout()
        grid.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self._stat_card(
            "Umumiy", self._stats["total"], ACC_BLUE,
            "\U0001F465", "Jami yozuvlar soni",
        ))
        row1.addWidget(self._stat_card(
            "Verifydan o\u2018tgan", self._stats["verified"], ACC_TEAL,
            "\u2713", "Yuz orqali tasdiqlangan",
        ))
        grid.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self._stat_card(
            "Yuborilgan", self._stats["sent"], ACC_GREEN,
            "\u2191", "Backendga muvaffaqiyatli",
        ))
        row2.addWidget(self._stat_card(
            "Yuborilmagan", self._stats["unsent"], ACC_AMBER,
            "\u29D6", "Yuborish navbatida",
        ))
        grid.addLayout(row2)

        lay.addLayout(grid)

        # ── Sent progress bar (sent / total) ──
        total = max(self._stats["total"], 1)
        pct = int(self._stats["sent"] * 100 / total)
        pct_label = QLabel(
            f"Yuborish darajasi: <b style='color:{ACC_GREEN}'>{pct}%</b>"
        )
        pct_label.setTextFormat(Qt.TextFormat.RichText)
        pct_label.setFont(QFont(FNT, 11))
        pct_label.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        lay.addWidget(pct_label)

        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet(f"""
            QFrame {{
                background: rgba(255,255,255,0.08);
                border: none;
                border-radius: 4px;
            }}
        """)
        bar_lay = QHBoxLayout(bar_bg)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)

        fill = QFrame()
        fill.setFixedHeight(8)
        fill.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {ACC_TEAL}, stop:1 {ACC_GREEN});
                border: none;
                border-radius: 4px;
            }}
        """)
        # Max percentage scaled to available width on show
        self._bar_fill = fill
        self._bar_pct = pct
        bar_lay.addWidget(fill, stretch=pct if pct > 0 else 0)
        spacer = QFrame()
        spacer.setStyleSheet("background: transparent; border: none;")
        bar_lay.addWidget(spacer, stretch=max(0, 100 - pct))
        lay.addWidget(bar_bg)

        # ── Server bilan sinxron bo'limi ──
        # show_server=True bo'lsa, header va bo'sh body yaratiladi. Keyin
        # _render_server_loading/set_server_stats/set_server_error body ni
        # yangilaydi (spinner → ma'lumot yoki xato).
        if self._show_server:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background: {BRD}; border: none;")
            lay.addWidget(sep)

            srv_hdr = QHBoxLayout()
            srv_hdr.setSpacing(8)
            srv_icon = QLabel("\u2601")
            srv_icon.setFixedSize(28, 28)
            srv_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            srv_icon.setFont(QFont(FNT, 13, QFont.Weight.Bold))
            srv_icon.setStyleSheet(f"""
                background: rgba(99,197,255,0.16);
                color: {ACC_BLUE};
                border: 1px solid rgba(99,197,255,0.32);
                border-radius: 14px;
            """)
            srv_hdr.addWidget(srv_icon)

            srv_title_box = QVBoxLayout()
            srv_title_box.setSpacing(0)
            srv_title = QLabel("Server bilan sinxron")
            srv_title.setFont(QFont(FNT, 12, QFont.Weight.DemiBold))
            srv_title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
            srv_sub = QLabel("Shu kun \u00b7 smena \u00b7 bino kesimidagi davomat")
            srv_sub.setFont(QFont(FNT, 9))
            srv_sub.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
            srv_title_box.addWidget(srv_title)
            srv_title_box.addWidget(srv_sub)
            srv_hdr.addLayout(srv_title_box)
            srv_hdr.addStretch()
            lay.addLayout(srv_hdr)

            # Server bo'limi body — kerakli holatga qarab qayta to'ldiriladi.
            body = QFrame()
            body.setObjectName("serverBody")
            body.setStyleSheet(f"""
                QFrame#serverBody {{
                    background: transparent;
                    border: none;
                }}
            """)
            body_lay = QVBoxLayout(body)
            body_lay.setContentsMargins(0, 0, 0, 0)
            body_lay.setSpacing(10)
            self._server_body_layout = body_lay
            lay.addWidget(body)

        # ── Close button ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok_btn = QPushButton("Yopish")
        ok_btn.setFixedHeight(36)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_btn.setFont(QFont(FNT, 10, QFont.Weight.DemiBold))
        ok_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(99,197,255,0.22);
                color: {ACC_BLUE};
                border: 1px solid rgba(99,197,255,0.45);
                border-radius: 10px;
                padding: 0 22px;
            }}
            QPushButton:hover {{
                background: rgba(99,197,255,0.35);
                color: #fff;
                border-color: rgba(99,197,255,0.65);
            }}
        """)
        ok_btn.clicked.connect(self.accept)
        ok_btn.setDefault(True)
        btn_row.addWidget(ok_btn)
        lay.addLayout(btn_row)

        outer.addWidget(card)

    def _stat_card(self, title: str, value: int, color: str,
                   icon: str, subtitle: str) -> QFrame:
        """Bitta statistika kartasi — icon chip + value + title + subtitle."""
        card = QFrame()
        card.setObjectName("statInner")
        card.setStyleSheet(f"""
            QFrame#statInner {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 14px;
            }}
        """)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setFixedSize(32, 32)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFont(QFont(FNT, 14, QFont.Weight.Bold))
        r, g, b = self._hex_to_rgb(color)
        icon_lbl.setStyleSheet(f"""
            background: rgba({r},{g},{b},0.16);
            color: {color};
            border: 1px solid rgba({r},{g},{b},0.32);
            border-radius: 16px;
        """)
        top.addWidget(icon_lbl)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont(FNT, 11, QFont.Weight.Medium))
        title_lbl.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        top.addWidget(title_lbl)
        top.addStretch()
        lay.addLayout(top)

        val_lbl = QLabel(str(value))
        val_lbl.setFont(QFont(FNT, 28, QFont.Weight.Bold))
        val_lbl.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        lay.addWidget(val_lbl)

        sub_lbl = QLabel(subtitle)
        sub_lbl.setFont(QFont(FNT, 9))
        sub_lbl.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        lay.addWidget(sub_lbl)

        return card

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        if len(h) != 6:
            return (99, 197, 255)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    # ── Server bo'limi — holatlar: loading / stats / error ──

    def _clear_server_body(self):
        """Server bo'limi body ichidagi widgetlarni tozalaydi va spinner
        taymerini to'xtatadi."""
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        self._spinner_label = None
        if self._server_body_layout is None:
            return
        while self._server_body_layout.count():
            item = self._server_body_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            else:
                sub = item.layout()
                if sub:
                    # rekursiv tozalash
                    while sub.count():
                        sub_item = sub.takeAt(0)
                        sw = sub_item.widget()
                        if sw:
                            sw.setParent(None)
                            sw.deleteLater()

    def _render_server_loading(self):
        """Server bo'limiga animatsiyalangan spinner va 'Yuklanmoqda...' chiqaradi."""
        if self._server_body_layout is None:
            return
        self._clear_server_body()

        wrap = QFrame()
        wrap.setMinimumHeight(170)
        wrap.setStyleSheet(f"""
            QFrame {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 14px;
            }}
        """)
        wlay = QVBoxLayout(wrap)
        wlay.setContentsMargins(12, 20, 12, 20)
        wlay.setSpacing(10)
        wlay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        spin = QLabel()
        spin.setFixedSize(48, 48)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setStyleSheet("background: transparent; border: none;")
        wlay.addWidget(spin, alignment=Qt.AlignmentFlag.AlignCenter)

        txt = QLabel("Server bilan bog\u2018lanmoqda...")
        txt.setFont(QFont(FNT, 10, QFont.Weight.DemiBold))
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")
        wlay.addWidget(txt, alignment=Qt.AlignmentFlag.AlignCenter)

        self._server_body_layout.addWidget(wrap)

        self._spinner_label = spin
        self._spin_angle = 0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(60)
        self._spin_timer.timeout.connect(self._tick_spinner)
        self._spin_timer.start()
        self._tick_spinner()

    def _tick_spinner(self):
        """SyncModal spinner pattern'ining qisqartirilgan ko'rinishi."""
        if self._spinner_label is None:
            return
        self._spin_angle = (self._spin_angle + 30) % 360
        size = 48
        pix = QPixmap(QSize(size, size))
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, r = size / 2, size / 2, 18
        dot_count = 8
        for i in range(dot_count):
            angle = math.radians(self._spin_angle + i * (360 / dot_count))
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            alpha = int(255 * (1.0 - i / dot_count))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(99, 197, 255, alpha))
            dot_r = 4.0 if i == 0 else 3.0
            p.drawEllipse(QPointF(x, y), dot_r, dot_r)
        p.end()
        self._spinner_label.setPixmap(pix)

    @pyqtSlot(dict)
    def set_server_stats(self, stats: dict):
        """Server javobi kelganda 2x2 grid'da ma'lumotlarni chiqaradi."""
        if self._server_body_layout is None:
            return
        self._clear_server_body()
        data = {
            "total": int(stats.get("total", 0) or 0),
            "entered": int(stats.get("entered", 0) or 0),
            "not_entered": int(stats.get("not_entered", 0) or 0),
            "cheating": int(stats.get("cheating", 0) or 0),
        }

        row1 = QHBoxLayout()
        row1.setSpacing(10)
        row1.addWidget(self._stat_card(
            "Umumiy", data["total"], ACC_BLUE,
            "\U0001F465", "Bino bo\u2018yicha studentlar",
        ))
        row1.addWidget(self._stat_card(
            "Kirganlar", data["entered"], ACC_GREEN,
            "\u2713", "Davomatga kirgan",
        ))
        self._server_body_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addWidget(self._stat_card(
            "Kirmaganlar", data["not_entered"], ACC_AMBER,
            "\u2212", "Hozircha kirmagan",
        ))
        row2.addWidget(self._stat_card(
            "Chetlatilgan", data["cheating"], ACC_RED,
            "\u2718", "Cheating bilan chetlatilgan",
        ))
        self._server_body_layout.addLayout(row2)

    @pyqtSlot(str)
    def set_server_error(self, msg: str):
        """Server bilan bog'lanib bo'lmasa, amber rangli xato kartasi."""
        if self._server_body_layout is None:
            return
        self._clear_server_body()
        err_lbl = QLabel(msg or "Server bilan bog\u2018lanib bo\u2018lmadi")
        err_lbl.setWordWrap(True)
        err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        err_lbl.setFont(QFont(FNT, 10))
        err_lbl.setStyleSheet(f"""
            color: {ACC_AMBER};
            background: rgba(255,213,79,0.10);
            border: 1px solid rgba(255,213,79,0.28);
            border-radius: 10px;
            padding: 14px;
        """)
        self._server_body_layout.addWidget(err_lbl)

    def closeEvent(self, event):
        if self._spin_timer is not None:
            self._spin_timer.stop()
            self._spin_timer = None
        super().closeEvent(event)


class _StatsFetchWorker(QThread):
    """Background worker — smena attendance stats'ni backend'dan oladi.
    UI thread'ni bloklamaslik uchun alohida QThread'da ishlaydi."""
    finished_ok = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, smena_id: int, parent=None):
        super().__init__(parent)
        self._smena_id = smena_id

    def run(self):
        try:
            api = ApiClient()
            data = api.get_smena_attendance_stats(self._smena_id)
            self.finished_ok.emit(data or {})
        except Exception as e:
            self.error.emit(str(e))


class FaceIDPage(QWidget):
    logout_requested = pyqtSignal()
    go_back = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = DatabaseManager()
        self._face_engine = None
        self._api = ApiClient()
        self._camera_worker: CameraWorker | None = None
        self._sync_service: SyncService | None = None
        self._online_worker: OnlineSubmitWorker | None = None
        self._session_sm_id: int | None = None
        self._staff_id: int | None = None
        self._mode: str = "offline"
        self._last_frame: np.ndarray | None = None
        self._overlay_bboxes: list = []
        self._no_person_active: bool = False
        self._is_running = False
        self._similarity_threshold = 69
        self._match_pulse = 0.0
        self._current_student_id: int | None = None
        self._displayed_student_id: int | None = None  # info cardda ko'rsatilayotgan
        self._verify_cooldown = 3  # camera_worker bilan bir xil
        # Tashrif (visit) kuzatuvi — first_captured/last_captured semantikasi uchun.
        # Har bir student uchun oxirgi aniqlangan vaqt; oradagi bo'shliq
        # _NEW_VISIT_GAP_SEC'dan katta bo'lsa, bu yangi tashrif deb hisoblanadi.
        self._last_identified_at: dict[int, datetime] = {}
        self._NEW_VISIT_GAP_SEC = 10
        # Carouseldagi har bir student uchun optimal (eng yuqori) score — card
        # rasmi faqat shu qiymat oshganda yangilanadi. `entry_log.last_captured`
        # DB semantikasiga mos: carousel doim eng aniq (score-max) kadrni ko'rsatadi.
        self._carousel_max_score: dict[int, int] = {}
        self._countdown_remaining = 0
        self._countdown_timer: QTimer | None = None

        # Animation state (session_page bilan uyg'un)
        self._anim_angle = 0.0
        self._particles: list[_Particle] = []

        self._setup_ui()

        # Animation timer — 25 FPS, ko'z uchun yumshoq
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start(40)

    # ════════════════════════════════════════════
    # Animated background (session_page uslubida)
    # ════════════════════════════════════════════

    def _tick_animation(self):
        self._anim_angle += 0.008
        w, h = self.width(), self.height()

        if not self._particles and w > 0 and h > 0:
            self._particles = [_Particle(w, h) for _ in range(35)]

        for p in self._particles:
            p.update(w, h)

        # Match pulse decay
        if self._match_pulse > 0:
            self._match_pulse = max(0, self._match_pulse - 0.025)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Animated gradient background ──
        offset = math.sin(self._anim_angle) * 0.12
        bg = QLinearGradient(0, 0, w * (0.6 + offset), h)
        bg.setColorAt(0.0, QColor("#0a1628"))
        bg.setColorAt(0.3, QColor("#0D47A1"))
        bg.setColorAt(0.6, QColor("#1565C0"))
        bg.setColorAt(1.0, QColor("#0a1628"))
        painter.fillRect(self.rect(), bg)

        # ── Subtle radial glow (pulsing) ──
        pulse = 0.7 + 0.3 * math.sin(self._anim_angle * 1.8)
        glow = QRadialGradient(w * 0.45, h * 0.35, max(w, h) * 0.45)
        glow.setColorAt(0.0, QColor(30, 136, 229, int(30 * pulse)))
        glow.setColorAt(0.5, QColor(13, 71, 161, int(15 * pulse)))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)

        # ── Match pulse (green glow on identify) ──
        if self._match_pulse > 0:
            mg = QRadialGradient(w * 0.33, h * 0.4, w * 0.4)
            mg.setColorAt(0, QColor(102, 187, 106, int(18 * self._match_pulse)))
            mg.setColorAt(1, QColor(0, 0, 0, 0))
            painter.fillRect(self.rect(), mg)

        # ── Particles ──
        for p in self._particles:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 255, 255, int(255 * p.opacity)))
            painter.drawEllipse(QPointF(p.x, p.y), p.radius, p.radius)

        # ── Connecting lines ──
        pen = QPen(QColor(255, 255, 255, 12))
        pen.setWidthF(0.5)
        painter.setPen(pen)
        for i, p1 in enumerate(self._particles):
            for p2 in self._particles[i + 1:]:
                dx = p1.x - p2.x
                dy = p1.y - p2.y
                dist_sq = dx * dx + dy * dy
                if dist_sq < 14400:
                    dist = math.sqrt(dist_sq)
                    alpha = int(12 * (1 - dist / 120))
                    pen.setColor(QColor(255, 255, 255, alpha))
                    painter.setPen(pen)
                    painter.drawLine(QPointF(p1.x, p1.y), QPointF(p2.x, p2.y))

        painter.end()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_carousel_wrap'):
            self._resize_carousel_cards()

    def showEvent(self, event):
        super().showEvent(event)
        # Layout birinchi marta renderlanganidan keyin cardlarni resize qilish
        QTimer.singleShot(0, self._resize_carousel_cards)

    # ════════════════════════════════════════════
    # UI Setup
    # ════════════════════════════════════════════

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(0)

        # Main glass card
        self._card = QFrame()
        self._card.setObjectName("mainCard")
        self._card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._card.setStyleSheet(f"""
            QFrame#mainCard {{
                background: {SRF_CARD};
                border: 1px solid {BRD};
                border-radius: 20px;
            }}
        """)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        # 1. Header
        card_layout.addWidget(self._build_header())

        # 2. Body
        body = QFrame()
        body.setStyleSheet("background: transparent; border: none;")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(22, 14, 22, 10)
        body_layout.setSpacing(12)

        # Stats row
        body_layout.addLayout(self._build_stats_row())

        # Session info
        body_layout.addWidget(self._build_session_info())

        # Main content: Camera | Passport | Student
        content = QHBoxLayout()
        content.setSpacing(12)
        content.addWidget(self._build_camera_card(), stretch=5)
        content.addWidget(self._build_passport_card(), stretch=3)
        content.addWidget(self._build_student_card(), stretch=4)
        body_layout.addLayout(content, stretch=5)

        # Controls
        body_layout.addWidget(self._build_controls_bar())

        # Carousel
        body_layout.addWidget(self._build_carousel(), stretch=2)

        card_layout.addWidget(body, stretch=1)

        outer.addWidget(self._card)

    # ── 1. Header / Top App Bar ──
    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("hdr")
        header.setFixedHeight(76)
        header.setStyleSheet(f"""
            QFrame#hdr {{
                background: {SRF_FIELD};
                border: none;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
                border-bottom: 1px solid {BRD};
            }}
        """)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(24, 0, 24, 0)
        layout.setSpacing(16)

        # Logo
        logo_path = os.path.join(_HERE, "..", "..", "images", "logo_bba.png")
        logo_lbl = QLabel()
        logo_lbl.setFixedSize(50, 44)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_lbl.setStyleSheet("background: transparent; border: none;")
        logo_pix = QPixmap(os.path.normpath(logo_path))
        if not logo_pix.isNull():
            logo_lbl.setPixmap(logo_pix.scaled(
                50, 44, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
        layout.addWidget(logo_lbl)

        # Title
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        title = QLabel("Bilim va malakalarni baholash agentligi")
        title.setFont(QFont(FNT, 14, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        title_col.addWidget(title)

        # subtitle = QLabel("Face ID tizimi")
        # subtitle.setFont(QFont(FNT, 10))
        # subtitle.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
        # title_col.addWidget(subtitle)

        layout.addLayout(title_col, stretch=1)

        # Status chip
        self._status_chip = QFrame()
        self._status_chip.setFixedHeight(34)
        self._status_chip.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: 1px solid rgba(102,187,106,0.20);
                border-radius: 17px;
            }}
        """)
        sc = QHBoxLayout(self._status_chip)
        sc.setContentsMargins(14, 0, 16, 0)
        sc.setSpacing(8)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(9, 9)
        self._status_dot.setStyleSheet(f"background: {ACC_GREEN}; border: none; border-radius: 4px;")
        sc.addWidget(self._status_dot)

        self._status_text = QLabel("Tayyor")
        self._status_text.setFont(QFont(FNT, 11, QFont.Weight.Medium))
        self._status_text.setStyleSheet(f"color: {ACC_GREEN}; background: transparent; border: none;")
        sc.addWidget(self._status_text)

        layout.addWidget(self._status_chip)

        # Mode chip (online/offline)
        self._mode_chip = QFrame()
        self._mode_chip.setFixedHeight(34)
        self._mode_chip.setStyleSheet(f"""
            QFrame {{
                background: rgba(99,197,255,0.10);
                border: 1px solid rgba(99,197,255,0.20);
                border-radius: 17px;
            }}
        """)
        mc = QHBoxLayout(self._mode_chip)
        mc.setContentsMargins(14, 0, 16, 0)
        mc.setSpacing(8)

        self._mode_dot = QLabel()
        self._mode_dot.setFixedSize(9, 9)
        self._mode_dot.setStyleSheet(f"background: {ACC_BLUE}; border: none; border-radius: 4px;")
        mc.addWidget(self._mode_dot)

        self._mode_text = QLabel("—")
        self._mode_text.setFont(QFont(FNT, 11, QFont.Weight.Medium))
        self._mode_text.setStyleSheet(f"color: {ACC_BLUE}; background: transparent; border: none;")
        mc.addWidget(self._mode_text)

        layout.addWidget(self._mode_chip)

        return header

    # ── 2. Stats Row ──
    def _build_stats_row(self) -> QHBoxLayout:
        h = QHBoxLayout()
        h.setSpacing(10)

        self._st_entered = _StatCard("\u2714", "Aniqlangan", "0", ACC_GREEN)
        self._st_male    = _StatCard("\u2642", "Erkak",      "0", ACC_MALE)
        self._st_female  = _StatCard("\u2640", "Ayol",       "0", ACC_PINK)
        h.addWidget(self._st_entered)
        h.addWidget(self._st_male)
        h.addWidget(self._st_female)

        h.addStretch()

        self._st_group = _StatCard(
            "", "gr", "\u2014", ACC_BLUE,
            value_font_size=36, card_height=75, min_width=150,
        )
        h.addWidget(self._st_group)

        h.addStretch()

        self._st_total    = _StatCard("\u03A3", "Jami",   "0", ACC_BLUE)
        self._st_t_male   = _StatCard("\u2642", "Erkak", "0", ACC_MALE)
        self._st_t_female = _StatCard("\u2640", "Ayol", "0", ACC_PINK)
        h.addWidget(self._st_total)
        h.addWidget(self._st_t_male)
        h.addWidget(self._st_t_female)

        return h

    # ── 3. Session Info ──
    def _build_session_info(self) -> QFrame:
        bar = QFrame()
        bar.setFixedHeight(42)
        bar.setStyleSheet(f"""
            QFrame {{
                background: {SRF_FIELD};
                border: 1px solid {BRD};
                border-radius: 12px;
            }}
        """)
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 0, 18, 0)
        row.setSpacing(0)

        self._ses_name = QLabel("\u2014")
        self._ses_name.setFont(QFont(FNT, 13))
        self._ses_name.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
        row.addWidget(self._ses_name)

        row.addStretch()

        self._ses_zone = QLabel("\u2014")
        self._ses_zone.setFont(QFont(FNT, 11))
        self._ses_zone.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")

        self._ses_date = QLabel("\u2014")
        self._ses_date.setFont(QFont(FNT, 11))
        self._ses_date.setStyleSheet(f"color: {TXT_MED}; background: transparent; border: none;")

        self._ses_smena = QLabel("\u2014")
        self._ses_smena.setFont(QFont(FNT, 11, QFont.Weight.DemiBold))
        self._ses_smena.setStyleSheet(f"color: {ACC_BLUE}; background: transparent; border: none;")

        for lbl in [self._ses_zone, self._ses_date, self._ses_smena]:
            sep = QLabel("  \u2502  ")
            sep.setStyleSheet(f"color: {BRD_ACCENT}; background: transparent; border: none;")
            sep.setFont(QFont(FNT, 11))
            row.addWidget(sep)
            row.addWidget(lbl)

        return bar

    # ── Card header helper ──
    def _card_header(self, icon: str, title: str) -> QHBoxLayout:
        hdr = QHBoxLayout()
        hdr.setSpacing(8)

        if icon:
            ic = QLabel(icon)
            ic.setFont(QFont(FNT, 16))
            ic.setStyleSheet(f"color: {ACC_GREEN}; background: transparent; border: none;")
            hdr.addWidget(ic)

        if title:
            t = QLabel(title)
            t.setFont(QFont(FNT, 12))
            t.setStyleSheet(f"color: {TXT}; background: transparent; border: none;")
            hdr.addWidget(t)

        hdr.addStretch()
        return hdr

    # ── Inner card helper ──
    def _inner_card(self, name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(name)
        card.setStyleSheet(f"""
            QFrame#{name} {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 16px;
            }}
        """)
        return card

    # ── 4a. Camera Card ──
    def _build_camera_card(self) -> QFrame:
        card = self._inner_card("camCard")
        self._cam_card = card

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)

        hdr = self._card_header("\U0001F3A5", "Kamera")

        # Match chip
        self._match_chip = QLabel("\u2014")
        self._match_chip.setFont(QFont(FNT, 11, QFont.Weight.Bold))
        self._match_chip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._match_chip.setFixedHeight(28)
        self._match_chip.setMinimumWidth(108)
        self._match_chip.setStyleSheet(f"""
            color: {TXT_DIM};
            background: {SRF_FIELD};
            border: 1px solid {BRD};
            border-radius: 8px;
            padding: 0 12px;
        """)
        hdr.addWidget(self._match_chip)
        lay.addLayout(hdr)

        # Video
        self.video_label = QLabel()
        self.video_label.setMinimumSize(260, 250)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.video_label.setScaledContents(False)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("\U0001f4f7  Kamera stream kutilmoqda...")
        self.video_label.setStyleSheet(f"""
            background: rgba(0,0,0,0.25);
            border: 1px dashed {BRD_ACCENT};
            border-radius: 12px;
            color: {TXT_DIM};
            font-size: 13px;
        """)
        # Resize eventini kuzatamiz — kamera to'xtatilgan holatda placeholder'ni
        # yangi o'lchamda qayta chizish uchun kerak (pixmap auto-scale qilmaydi).
        self.video_label.installEventFilter(self)
        lay.addWidget(self.video_label)

        # Countdown overlay — video_label ustida ko'rinadi
        self._countdown_overlay = QLabel(self.video_label)
        self._countdown_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._countdown_overlay.setFixedSize(42, 42)
        self._countdown_overlay.setStyleSheet(f"""
            background: rgba(0,0,0,0.55);
            color: {ACC_GREEN};
            border-radius: 21px;
            font-size: 16px;
            font-weight: bold;
            font-family: {FONT_FAMILY};
        """)
        self._countdown_overlay.hide()

        return card

    # ── 4b. Passport Card ──
    def _build_passport_card(self) -> QFrame:
        card = self._inner_card("psCard")
        self._ps_card = card

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(10)

        hdr = self._card_header("\U0001FAAA", "Pasport")
        lay.addLayout(hdr)

        self._ps_img = QLabel()
        self._ps_img.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._ps_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ps_img.setMinimumSize(150, 190)
        self._ps_img.setText("\U0001f464")
        self._ps_img.setStyleSheet(f"""
            background: rgba(0,0,0,0.20);
            border: 1px dashed {BRD_ACCENT};
            border-radius: 12px;
            color: {TXT_DIM};
            font-size: 36px;
        """)
        lay.addWidget(self._ps_img)

        # "Aniqlandi" tick overlay — pasport rasm markazida katta yashil belgi.
        self._success_tick = QLabel("\u2713", card)
        self._success_tick.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_tick.setStyleSheet(
            "color: #fff;"
            "background: rgba(46,196,117,0.92);"
            "border: 3px solid rgba(255,255,255,0.85);"
            "border-radius: 60px;"
            "font-size: 72pt;"
            "font-weight: 900;"
        )
        self._success_tick.setFixedSize(120, 120)
        self._success_tick.hide()

        self._success_label = QLabel("Aniqlandi", card)
        self._success_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._success_label.setStyleSheet(
            f"color: #fff; background: {ACC_GREEN};"
            "border-radius: 10px; font-size: 14pt; font-weight: 800;"
            "padding: 4px 14px;"
        )
        self._success_label.setFixedHeight(34)
        self._success_label.hide()

        card.installEventFilter(self)

        return card

    # ── 4c. Student Details Card ──
    def _build_student_card(self) -> QFrame:
        card = self._inner_card("stuCard")
        self._stu_card = card

        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        # Row 1 — Avatar icon chip (markazda)
        icon_wrap = QFrame()
        icon_wrap.setStyleSheet("background: transparent; border: none;")
        ilay = QHBoxLayout(icon_wrap)
        ilay.setContentsMargins(0, 0, 0, 4)
        ilay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        avatar = QLabel("\U0001f464")
        avatar.setFixedSize(56, 56)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setFont(QFont(FNT, 24, QFont.Weight.Bold))
        avatar.setStyleSheet(f"""
            background: rgba(102,187,106,0.14);
            color: {ACC_GREEN};
            border: 1px solid rgba(102,187,106,0.35);
            border-radius: 28px;
        """)
        ilay.addWidget(avatar)
        lay.addWidget(icon_wrap)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BRD}; border: none;")
        lay.addWidget(sep)
        lay.addSpacing(2)

        # Info rows — hammasi markazlashgan
        self._row_last   = _InfoRow(font_size=14)
        self._row_first  = _InfoRow(font_size=14)
        self._row_middle = _InfoRow(font_size=14)
        self._row_imei   = _InfoRow(font_size=12)
        self._row_group  = _InfoRow()
        self._row_seat   = _InfoRow()
        self._row_subj   = _InfoRow(wrap=True)
        self._row_gender = _InfoRow()
        self._row_conf   = _InfoRow()

        for r in [self._row_last, self._row_first, self._row_middle,
                  self._row_imei,
                  self._row_group, self._row_seat,
                  self._row_subj, self._row_gender, self._row_conf]:
            lay.addWidget(r)

        lay.addStretch()

        # Rad etish button — hidden until face identified
        self._reject_btn = QPushButton("\u26a0  Chetlatish")
        self._reject_btn.setFixedHeight(28)
        self._reject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reject_btn.setFont(QFont(FNT, 9, QFont.Weight.DemiBold))
        self._reject_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,154,154,0.18);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.30);
                border-radius: 8px;
                padding: 0 14px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.30);
                color: #fff;
                border-color: rgba(239,154,154,0.55);
            }}
            QPushButton:pressed {{
                background: rgba(239,154,154,0.42);
            }}
        """)
        self._reject_btn.setVisible(False)
        self._reject_btn.clicked.connect(self._on_reject_student)
        lay.addWidget(self._reject_btn)

        return card

    # ── 5. Controls Bar ──
    def _build_controls_bar(self) -> QFrame:
        H = 32           # uniform height — MD3 dense
        R = 8            # border-radius

        BTN_FONT = QFont(FNT, 9, QFont.Weight.DemiBold)
        BTN_PAD = "0 14px"

        # ── Outer wrapper — elevated surface ──
        wrapper = QFrame()
        wrapper.setObjectName("ctlBar")
        wrapper.setStyleSheet(f"""
            QFrame#ctlBar {{
                background: rgba(255,255,255,0.05);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                padding: 5px;
            }}
        """)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 35))
        wrapper.setGraphicsEffect(shadow)

        # Root — 3 ta teng enlikdagi bo'lim (grp1 left, grp2 center, grp3 right).
        # Teng stretch faktorlar grp2 ni gorometrik markazga joylashtiradi,
        # chap va o'ng bo'limlar eni farqlansa ham.
        root = QHBoxLayout(wrapper)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(16)

        # ═══════════════════════════════════════════
        # GROUP 1 — Navigation + Camera controls
        # ═══════════════════════════════════════════
        grp1 = QHBoxLayout()
        grp1.setSpacing(6)

        # Shared: MD3 tonal icon button
        ICON_STYLE = f"""
            QPushButton {{
                background: rgba(99,197,255,0.16);
                color: {ACC_BLUE};
                border: 1px solid rgba(99,197,255,0.24);
                border-radius: {R}px;
                padding: {BTN_PAD};
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(255,255,255,0.15);
                color: {TXT};
                border-color: rgba(255,255,255,0.20);
            }}
            QPushButton:pressed {{
                background: rgba(255,255,255,0.22);
            }}
        """

        # Orqaga
        back_btn = QPushButton("\u2190 Orqaga")
        back_btn.setFixedHeight(H)
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setFont(BTN_FONT)
        back_btn.setToolTip("Orqaga qaytish")
        back_btn.setStyleSheet(ICON_STYLE)
        back_btn.clicked.connect(self.go_back.emit)
        self._back_btn = back_btn
        grp1.addWidget(back_btn)

        # Separator dot
        dot1 = QLabel("\u00b7")
        dot1.setFixedWidth(8)
        dot1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dot1.setStyleSheet(f"color: rgba(255,255,255,0.18); border: none; background: transparent;")
        dot1.setFont(QFont(FNT, 14))
        grp1.addWidget(dot1)

        # Reload
        reload_btn = QPushButton("\u21bb Reload")
        reload_btn.setFixedHeight(H)
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.setFont(BTN_FONT)
        reload_btn.setToolTip("Kameralarni yangilash")
        reload_btn.setStyleSheet(ICON_STYLE)
        reload_btn.clicked.connect(self._populate_cameras)
        self._reload_btn = reload_btn
        grp1.addWidget(reload_btn)

        # Camera combo
        self.camera_combo = QComboBox()
        self.camera_combo.setFixedHeight(H)
        self.camera_combo.setMinimumWidth(80)
        self.camera_combo.setMaximumWidth(200)
        self.camera_combo.setStyleSheet(f"""
            QComboBox {{
                background: rgba(255,255,255,0.07);
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: {R}px;
                padding: 0 10px 0 8px;
                font-family: {FONT_FAMILY};
                font-size: 13px;
            }}
            QComboBox:hover {{
                border-color: rgba(99,197,255,0.35);
                background: rgba(255,255,255,0.10);
            }}
            QComboBox::drop-down {{
                border: none; width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background: #1a2a3e;
                color: {TXT};
                border: 1px solid rgba(255,255,255,0.12);
                selection-background-color: rgba(99,197,255,0.18);
                padding: 4px;
            }}
        """)
        self._populate_cameras()
        grp1.addWidget(self.camera_combo)

        # Similarity: slider + value
        self._sim_slider = QSlider(Qt.Orientation.Horizontal)
        self._sim_slider.setRange(69, 95)
        self._sim_slider.setValue(self._similarity_threshold)
        self._sim_slider.setFixedWidth(100)
        self._sim_slider.setFixedHeight(H)
        self._sim_slider.setToolTip("Aniqlik chegarasi")
        self._sim_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: rgba(255,255,255,0.10);
                height: 4px; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {ACC_BLUE};
                width: 14px; height: 14px;
                margin: -5px 0; border-radius: 7px;
                border: 1px solid rgba(10,22,40,0.6);
            }}
            QSlider::sub-page:horizontal {{
                background: rgba(99,197,255,0.50);
                border-radius: 2px;
            }}
        """)
        self._sim_slider.valueChanged.connect(self._on_sim_changed)
        grp1.addWidget(self._sim_slider)

        self._sim_val = QLabel(f"{self._similarity_threshold}%")
        self._sim_val.setFont(QFont(FNT, 9, QFont.Weight.Bold))
        self._sim_val.setFixedWidth(30)
        self._sim_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sim_val.setStyleSheet(f"color: {ACC_BLUE}; background: transparent; border: none;")
        grp1.addWidget(self._sim_val)

        # Start / Stop
        self.start_btn = QPushButton("\u25b6")
        self.start_btn.setFixedHeight(H)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFont(BTN_FONT)
        self._apply_start_style()
        self.start_btn.clicked.connect(self._toggle_camera)
        grp1.addWidget(self.start_btn)

        # LEFT section wrapper — grp1 ni chap chekkaga tortadi
        left_wrap = QHBoxLayout()
        left_wrap.setSpacing(0)
        left_wrap.addLayout(grp1)
        left_wrap.addStretch(1)
        root.addLayout(left_wrap, 1)

        # ═══════════════════════════════════════════
        # GROUP 2 — Action buttons (center)
        # ═══════════════════════════════════════════
        grp2 = QHBoxLayout()
        grp2.setSpacing(6)


        # JShShIR — MD3 filled tonal (primary)
        jshshir_btn = QPushButton("\U0001f50d  JShShIR")
        jshshir_btn.setFixedHeight(H)
        jshshir_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        jshshir_btn.setFont(BTN_FONT)
        jshshir_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(99,197,255,0.16);
                color: {ACC_BLUE};
                border: 1px solid rgba(99,197,255,0.24);
                border-radius: {R}px;
                padding: {BTN_PAD};
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(99,197,255,0.28);
                border-color: rgba(99,197,255,0.45);
                color: #fff;
            }}
            QPushButton:pressed {{
                background: rgba(99,197,255,0.36);
            }}
        """)
        jshshir_btn.clicked.connect(self._open_pinfl_modal)
        grp2.addWidget(jshshir_btn)

        # Statistika — online rejimda ko'rinadi (JShShIR yonida)
        self._stats_btn = QPushButton("\U0001F4CA  Statistika")
        self._stats_btn.setFixedHeight(H)
        self._stats_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._stats_btn.setFont(BTN_FONT)
        self._stats_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(77,182,172,0.16);
                color: {ACC_TEAL};
                border: 1px solid rgba(77,182,172,0.24);
                border-radius: {R}px;
                padding: {BTN_PAD};
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(77,182,172,0.28);
                border-color: rgba(77,182,172,0.45);
                color: #fff;
            }}
            QPushButton:pressed {{
                background: rgba(77,182,172,0.36);
            }}
        """)
        self._stats_btn.setVisible(False)
        self._stats_btn.clicked.connect(self._on_stats_clicked)
        grp2.addWidget(self._stats_btn)

        # Yuborish — MD3 tonal (secondary, hidden)
        self._send_btn = QPushButton("\u2191  Yuborish")
        self._send_btn.setFixedHeight(H)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFont(BTN_FONT)
        self._send_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(77,182,172,0.16);
                color: {ACC_TEAL};
                border: 1px solid rgba(77,182,172,0.24);
                border-radius: {R}px;
                padding: {BTN_PAD};
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(77,182,172,0.28);
                border-color: rgba(77,182,172,0.45);
            }}
            QPushButton:pressed {{
                background: rgba(77,182,172,0.36);
            }}
        """)
        self._send_btn.setVisible(False)
        self._send_btn.clicked.connect(self._on_send_clicked)
        grp2.addWidget(self._send_btn)

        # CENTER section wrapper — grp2 ni geometrik markazda ushlaydi
        center_wrap = QHBoxLayout()
        center_wrap.setSpacing(0)
        center_wrap.addStretch(1)
        center_wrap.addLayout(grp2)
        center_wrap.addStretch(1)
        root.addLayout(center_wrap, 1)

        # ═══════════════════════════════════════════
        # GROUP 3 — Chiqish (right edge)
        # ═══════════════════════════════════════════
        logout_btn = QPushButton("\u2715  Chiqish")
        logout_btn.setFixedHeight(H)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.setFont(BTN_FONT)
        logout_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,154,154,0.08);
                color: rgba(239,154,154,0.65);
                border: 1px solid rgba(239,154,154,0.10);
                border-radius: {R}px;
                padding: {BTN_PAD};
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.18);
                color: {ACC_RED};
                border-color: rgba(239,154,154,0.30);
            }}
            QPushButton:pressed {{
                background: rgba(239,154,154,0.26);
            }}
        """)
        logout_btn.clicked.connect(self.logout_requested.emit)

        # RIGHT section wrapper — logout_btn ni o'ng chekkaga tortadi
        right_wrap = QHBoxLayout()
        right_wrap.setSpacing(0)
        right_wrap.addStretch(1)
        right_wrap.addWidget(logout_btn)
        root.addLayout(right_wrap, 1)

        return wrapper

    # ── 6. Carousel ──
    def _build_carousel(self) -> QFrame:
        self._carousel_wrap = QFrame()
        self._carousel_wrap.setMinimumHeight(110)
        self._carousel_wrap.setStyleSheet(f"""
            QFrame {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 14px;
            }}
        """)

        lay = QVBoxLayout(self._carousel_wrap)
        lay.setContentsMargins(14, 6, 14, 6)
        lay.setSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;} QWidget{background:transparent;}")

        self._carousel_w = QWidget()
        self._carousel_lay = QHBoxLayout(self._carousel_w)
        self._carousel_lay.setContentsMargins(0, 0, 0, 0)
        self._carousel_lay.setSpacing(8)
        self._carousel_lay.setAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)

        scroll.setWidget(self._carousel_w)
        lay.addWidget(scroll, stretch=1)

        return self._carousel_wrap

    def _resize_carousel_cards(self):
        """Carousel card sizes adapt to available height."""
        avail = self._carousel_wrap.height() - 16  # margins
        card_h = max(90, avail)
        card_w = int(card_h * 0.82)
        photo_h = max(30, card_h - 48)
        photo_w = int(photo_h * 0.78)

        for i in range(self._carousel_lay.count()):
            item = self._carousel_lay.itemAt(i)
            w = item.widget() if item else None
            if isinstance(w, _RecentCard):
                w.setFixedSize(card_w, card_h)
                w.resize_photo(photo_w, photo_h)

    # ── Button styles ──
    def _apply_start_style(self):
        self.start_btn.setText("\u25b6 Start")
        self.start_btn.setToolTip("Start")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(102,187,106,0.15);
                color: {ACC_GREEN};
                border: 1px solid rgba(102,187,106,0.30);
                border-radius: 8px;
                padding: 0 14px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(102,187,106,0.25);
                border-color: rgba(102,187,106,0.50);
            }}
        """)

    def _apply_stop_style(self):
        self.start_btn.setText("\u25a0 Stop")
        self.start_btn.setToolTip("Stop")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(239,154,154,0.15);
                color: {ACC_RED};
                border: 1px solid rgba(239,154,154,0.30);
                border-radius: 8px;
                padding: 0 14px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: rgba(239,154,154,0.25);
                border-color: rgba(239,154,154,0.50);
            }}
        """)

    # ════════════════════════════════════════════
    # Session setup
    # ════════════════════════════════════════════

    def setup_session(self, session_sm_id: int, staff_id: int, mode: str):
        self._session_sm_id = session_sm_id
        self._staff_id = staff_id
        self._mode = mode

        # Update mode chip
        self._update_mode_chip(mode)

        from services.face_engine import FaceEngine
        self._face_engine = FaceEngine()
        students = self._db.load_embeddings_for_smena(session_sm_id)
        self._face_engine.load_embeddings(students)
        device = self._face_engine.device_name
        self._set_status(f"{self._face_engine.loaded_count} ta face yuklandi")

        row = self._db.get_smena_with_session(session_sm_id)
        if row:
            self._ses_name.setText(row["test"])
            self._ses_zone.setText(row["zone_name"])
            self._ses_date.setText(row["test_day"])
            self._ses_smena.setText(f"{row['sm']}-Smena")

        totals = self._db.get_total_student_count(session_sm_id)
        self._st_total.set_value(str(totals["total"]))
        self._st_t_male.set_value(str(totals["male"]))
        self._st_t_female.set_value(str(totals["female"]))

        self._refresh_counts()
        self._refresh_carousel()

        # Yuborish tugmasi faqat offline rejimda ko'rinadi.
        # Online rejimda yozuvlar avtomatik birma-bir yuboriladi.
        self._send_btn.setVisible(mode == "offline")
        # Statistika tugmasi faqat online rejimda ko'rinadi.
        self._stats_btn.setVisible(mode == "online")

        if mode == "online":
            self._start_online_worker()
        else:
            self._stop_online_worker()

    def _refresh_counts(self):
        if not self._session_sm_id:
            return
        c = self._db.get_entered_count(self._session_sm_id)
        self._st_entered.set_value(str(c["total"]))
        self._st_male.set_value(str(c["male"] or 0))
        self._st_female.set_value(str(c["female"] or 0))

    def _apply_verify_effect(self, color: str, icon: str, label: str) -> None:
        """Verify natijasi bo'yicha effekt: pasport va student info kartalari
        atrofi `color` hoshiya, pasport markazida `icon` + `label` belgilari.
        color — ACC_GREEN (aniqlandi) / ACC_AMBER (chetlatilgan) / ACC_RED (blacklist)."""
        card_style = f"""
            QFrame#{{name}} {{
                background: {SRF_INNER};
                border: 2px solid {color};
                border-radius: 16px;
            }}
        """
        if getattr(self, "_ps_card", None):
            self._ps_card.setStyleSheet(card_style.replace("{name}", "psCard"))
        if getattr(self, "_stu_card", None):
            self._stu_card.setStyleSheet(card_style.replace("{name}", "stuCard"))
        if getattr(self, "_cam_card", None):
            self._cam_card.setStyleSheet(card_style.replace("{name}", "camCard"))

        if getattr(self, "_success_tick", None):
            rgba = self._hex_to_rgba(color, 0.92)
            self._success_tick.setText(icon)
            self._success_tick.setStyleSheet(
                f"color: #fff;"
                f"background: {rgba};"
                f"border: 3px solid rgba(255,255,255,0.85);"
                f"border-radius: 60px;"
                f"font-size: 72pt;"
                f"font-weight: 900;"
            )
            self._success_label.setText(label)
            self._success_label.setStyleSheet(
                f"color: #fff; background: {color};"
                f"border-radius: 10px; font-size: 14pt; font-weight: 800;"
                f"padding: 4px 14px;"
            )
            self._position_success_overlay()
            self._success_tick.show()
            self._success_tick.raise_()
            self._success_label.show()
            self._success_label.raise_()

        if hasattr(self, "_success_hide_timer"):
            self._success_hide_timer.stop()
        else:
            self._success_hide_timer = QTimer(self)
            self._success_hide_timer.setSingleShot(True)
            self._success_hide_timer.timeout.connect(self._hide_success_overlay)
        self._success_hide_timer.start(1500)

    @staticmethod
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        """'#RRGGBB' → 'rgba(r,g,b,alpha)'. Noto'g'ri format — fallback qora."""
        s = hex_color.lstrip("#")
        if len(s) != 6:
            return f"rgba(0,0,0,{alpha})"
        try:
            r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            return f"rgba(0,0,0,{alpha})"
        return f"rgba({r},{g},{b},{alpha})"

    def _apply_verify_success(self) -> None:
        self._apply_verify_effect(ACC_GREEN, "\u2713", "Aniqlandi")

    def _apply_verify_cheating(self) -> None:
        self._apply_verify_effect(ACC_AMBER, "\u26a0", "Chetlatilgan")

    def _apply_verify_blacklist(self) -> None:
        self._apply_verify_effect(ACC_RED, "\u26a0", "Qora ro'yxat")

    def _hide_success_overlay(self) -> None:
        if getattr(self, "_success_tick", None):
            self._success_tick.hide()
        if getattr(self, "_success_label", None):
            self._success_label.hide()

    def _clear_verify_success(self) -> None:
        """Yashil effektni olib tashlash — cleanup, blacklist/cheating, yoki
        yangi non-match holatida."""
        default_style = f"""
            QFrame#{{name}} {{
                background: {SRF_INNER};
                border: 1px solid {BRD};
                border-radius: 16px;
            }}
        """
        if getattr(self, "_ps_card", None):
            self._ps_card.setStyleSheet(default_style.replace("{name}", "psCard"))
        if getattr(self, "_stu_card", None):
            self._stu_card.setStyleSheet(default_style.replace("{name}", "stuCard"))
        if getattr(self, "_cam_card", None):
            self._cam_card.setStyleSheet(default_style.replace("{name}", "camCard"))
        self._hide_success_overlay()

    def _position_success_overlay(self) -> None:
        """Tick va label'ni pasport kartochkasi markaziga joylashtirish."""
        card = getattr(self, "_ps_card", None)
        if not card or not getattr(self, "_success_tick", None):
            return
        w, h = card.width(), card.height()
        tw, th = self._success_tick.width(), self._success_tick.height()
        self._success_tick.move((w - tw) // 2, (h - th) // 2 - 20)
        lw = max(140, self._success_label.sizeHint().width())
        self._success_label.setFixedWidth(lw)
        self._success_label.move(
            (w - lw) // 2,
            (h - th) // 2 + th - 10,
        )

    def eventFilter(self, obj, event):
        if obj is getattr(self, "_ps_card", None) and event.type() == QEvent.Type.Resize:
            self._position_success_overlay()
        # Kamera to'xtatilgan placeholder — video_label o'lchami o'zgarsa qayta chizamiz
        if (obj is getattr(self, "video_label", None)
                and event.type() == QEvent.Type.Resize
                and not getattr(self, "_is_running", False)
                and self.video_label.pixmap() is not None
                and not self.video_label.pixmap().isNull()):
            self._paint_stopped_placeholder()
        return super().eventFilter(obj, event)

    def _set_group_card(self, gr_n) -> None:
        """_st_group qiymati uchun yagona nuqta: None/0/''/'-' → '\u2014',
        aks holda sonni string ko'rinishda yozadi."""
        try:
            n = int(gr_n) if gr_n not in (None, "", "\u2014") else 0
        except (TypeError, ValueError):
            n = 0
        self._st_group.set_value(str(n) if n else "\u2014")

    def reset_stats(self):
        """Barcha stat kartochkalarni 0 ga tushirish va sessiyani tozalash."""
        self._session_sm_id = None
        for card in (
            self._st_entered, self._st_male, self._st_female,
            self._st_total, self._st_t_male, self._st_t_female,
        ):
            card.set_value("0")
        self._set_group_card(None)
        while self._carousel_lay.count():
            it = self._carousel_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

    def _refresh_carousel(self):
        if not self._session_sm_id:
            return
        while self._carousel_lay.count():
            it = self._carousel_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        recent = self._db.get_recently_entered(self._session_sm_id, 10)
        if not recent:
            ph = QLabel("Hali aniqlanmagan...")
            ph.setFont(QFont(FNT, 10))
            ph.setStyleSheet(f"color: {TXT_DIM}; background: transparent; border: none;")
            self._carousel_lay.addWidget(ph)
            return

        # DB DESC qaytaradi (eng yangisi birinchi) — caruselda eng yangisi
        # o'ng tomonda turishi uchun teskari tartibda joylashtiramiz.
        for i, s in enumerate(reversed(recent)):
            stu_data = dict(s)
            stu_data["id"] = stu_data.get("student_id") or stu_data.get("id")
            stu_data["full_name"] = f"{s['last_name']} {s['first_name']}"
            # Carouselda MAJBURIY ravishda faqat entry_log.last_captured (kamera surati)
            # ko'rsatiladi. Pasport ps_img uni almashtiradi. Yo'q bo'lsa — placeholder.
            face_bytes = stu_data.get("face_img")
            if isinstance(face_bytes, (bytes, bytearray, memoryview)) and len(bytes(face_bytes)) > 0:
                stu_data["ps_img"] = bytes(face_bytes)
            else:
                stu_data["ps_img"] = None
            stu_data["_is_blacklist"] = bool(stu_data.get("is_blacklist", 0))
            stu_data["_is_cheating"] = bool(stu_data.get("is_cheating", 0))
            card = _RecentCard(stu_data)
            card.clicked.connect(self._on_carousel_card_clicked)
            self._carousel_lay.addWidget(card)

        self._resize_carousel_cards()

    def _add_to_carousel(self, data: dict):
        # Placeholder labelni o'chirish
        for i in range(self._carousel_lay.count()):
            it = self._carousel_lay.itemAt(i)
            if it and it.widget() and isinstance(it.widget(), QLabel):
                it.widget().deleteLater()
                break

        # Agar shu student allaqachon caruselda bo'lsa — o'chirib tashlash
        sid = data.get("id")
        if sid:
            for i in range(self._carousel_lay.count()):
                it = self._carousel_lay.itemAt(i)
                if it and it.widget() and isinstance(it.widget(), _RecentCard):
                    if it.widget()._stu.get("id") == sid:
                        removed = self._carousel_lay.takeAt(i)
                        removed.widget().deleteLater()
                        break

        # Yangi card oxiriga (o'ng tomonga) qo'shish
        card = _RecentCard(data)
        card.clicked.connect(self._on_carousel_card_clicked)
        self._carousel_lay.addWidget(card)

        # Eng eskisini (chapdagi) o'chirish — max 10 ta
        while self._carousel_lay.count() > 10:
            it = self._carousel_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        self._resize_carousel_cards()

    def _on_carousel_card_clicked(self, stu: dict):
        """Carousel card bosildi — to'liq ma'lumot modali.

        Modalni keyingi event-loop tickda ochamiz: aks holda `_RecentCard`ning
        mousePressEvent ichida `modal.exec()` nested loop ochilib, shu vaqt
        davomida kamera verify qilsa `_add_to_carousel` xuddi shu cardni
        `deleteLater()` qiladi; modal yopilgach `super().mousePressEvent`
        o'chirilgan widgetga ishora qilib crash beradi.
        """
        QTimer.singleShot(0, lambda s=stu: self._open_student_modal(s))

    def _open_student_modal(self, stu: dict) -> None:
        sid = stu.get("id")
        # Carousel card `ps_img` maydonida kameradan olingan (eng so'nggi) kadr'ni saqlaydi.
        # DB lookup stu'ni qayta yozadi (u yerda ps_img — pasport), shuning uchun
        # carousel kadrini oldin olib qo'yamiz va modalga aniq uzatamiz — modalda
        # KAMERA slotida aynan carousel'dagi rasm chiqadi.
        carousel_captured = stu.get("ps_img")
        entry: dict | None = None
        if sid:
            row = self._db.get_student(sid)
            if row:
                stu = dict(row)
            try:
                e_row = self._db.get_entry_by_student(sid)
                if e_row:
                    entry = dict(e_row)
            except Exception:
                entry = None
        modal = _StudentDetailModal(
            stu, entry, captured_override=carousel_captured, parent=self,
        )
        modal.exec()

    # ════════════════════════════════════════════
    # Camera
    # ════════════════════════════════════════════

    def _populate_cameras(self):
        self.camera_combo.clear()
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            for i, name in enumerate(graph.get_input_devices()):
                self.camera_combo.addItem(name, i)
        except Exception:
            pass
        # Kamera topilmasa — ro'yxat bo'sh qoladi. Start bosilganda foydalanuvchiga
        # material design styledagi ogohlantirish modali ko'rsatiladi.

    def _toggle_camera(self):
        if self._camera_worker and self._camera_worker.isRunning():
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        if self.camera_combo.count() == 0:
            _AlertModal(
                title="Kamera topilmadi",
                message=(
                    "Kompyuterda ishlovchi kamera aniqlanmadi. Iltimos, "
                    "kamerani ulab, yonidagi \u21BB tugmasini bosib "
                    "ro\u2018yxatni yangilang."
                ),
                accent="warn",
                icon="\U0001F4F7",
                parent=self,
            ).exec()
            self._set_status("Kamera topilmadi", "error")
            return

        idx = self.camera_combo.currentData()
        if idx is None or idx < 0:
            self._set_status("Kamera tanlanmadi!", "error")
            return

        # Kamera ishga tushishidan oldin slider qiymatini FaceEngine'ga uzatamiz.
        # Slider boost qilingan pct shkalasida (sqrt), FaceEngine esa xom cosine kutadi —
        # shuning uchun sqrt ning teskarisini (kvadratini) qo'llaymiz: raw = (pct/100)^2.
        # Masalan: slider 69% → raw 0.476 (~0.48), slider 95% → raw 0.9025.
        try:
            from services.face_engine import FaceEngine
            FaceEngine().set_threshold((self._sim_slider.value() / 100.0) ** 2)
        except Exception:
            pass

        self._camera_worker = CameraWorker(idx, parent=self)
        self._camera_worker.frame_ready.connect(self._on_frame)
        self._camera_worker.face_identified.connect(self._on_face_identified)
        self._camera_worker.faces_update.connect(self._on_faces_update)
        self._camera_worker.no_face.connect(self._on_no_face)
        self._camera_worker.error_occurred.connect(self._on_cam_error)
        self._camera_worker.start()

        self._apply_stop_style()
        self.camera_combo.setEnabled(False)
        self._set_controls_enabled(False)
        self._is_running = True
        self._set_status("Kamera ishlayapti...")

    def _stop_camera(self):
        # Avval flag'ni tushiramiz — _on_frame navbatdagi stale signallarni ignor qiladi
        self._is_running = False
        if self._camera_worker:
            # Signallarni uzib qo'yamiz: worker.stop() `wait()` davomida
            # queued `frame_ready` signallari placeholder'ni bosib ketmasligi uchun
            try:
                self._camera_worker.frame_ready.disconnect(self._on_frame)
                self._camera_worker.face_identified.disconnect(self._on_face_identified)
                self._camera_worker.faces_update.disconnect(self._on_faces_update)
                self._camera_worker.no_face.disconnect(self._on_no_face)
                self._camera_worker.error_occurred.disconnect(self._on_cam_error)
            except (TypeError, RuntimeError):
                pass
            self._camera_worker.stop()
            self._camera_worker.deleteLater()
            self._camera_worker = None
        self._stop_countdown()
        self._apply_start_style()
        self.camera_combo.setEnabled(True)
        self._set_controls_enabled(True)
        # Overlay bbox va no-person flag'ni tozalaymiz — placeholder toza chiqishi uchun
        self._overlay_bboxes = []
        self._no_person_active = False
        self._set_status("Kamera to'xtatildi")
        self._show_camera_stopped_placeholder()

    def _on_sim_changed(self, v: int):
        self._similarity_threshold = v
        self._sim_val.setText(f"{v}%")

    def _show_camera_stopped_placeholder(self) -> None:
        """Kamera to'xtaganda custom-painted placeholder. Fon stylesheet'dan,
        ustidagi ikonka + matn esa QPainter orqali QPixmap'ga chiziladi."""
        self.video_label.clear()
        self.video_label.setText("")
        self.video_label.setStyleSheet(f"""
            QLabel {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(30,40,55,0.95),
                    stop:1 rgba(15,22,34,0.95)
                );
                border: 1px solid {BRD_ACCENT};
                border-radius: 12px;
            }}
        """)
        self._paint_stopped_placeholder()

    def _paint_stopped_placeholder(self) -> None:
        """Custom camera-off ikonka: glass chip ichida kamera siluet + qizil slash.
        Matn: "Kamera to'xtatilgan" va ko'rsatma. Resize'da qayta chiziladi."""
        sz = self.video_label.size()
        W = max(sz.width(), 260)
        H = max(sz.height(), 250)

        pix = QPixmap(W, H)
        pix.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        cx, cy = W // 2, H // 2 - 24
        chip_r = 56

        # 1) Yumshoq soya — chip ostida
        shadow_grad = QRadialGradient(QPointF(cx, cy + 6), chip_r + 22)
        shadow_grad.setColorAt(0.0, QColor(0, 0, 0, 75))
        shadow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(shadow_grad)
        painter.drawEllipse(QPointF(cx, cy + 6), chip_r + 22, chip_r + 22)

        # 2) Glass chip — gradient fill + ingichka highlight
        chip_grad = QLinearGradient(cx - chip_r, cy - chip_r, cx + chip_r, cy + chip_r)
        chip_grad.setColorAt(0.0, QColor(255, 255, 255, 50))
        chip_grad.setColorAt(0.55, QColor(235, 245, 255, 28))
        chip_grad.setColorAt(1.0, QColor(190, 210, 230, 18))
        painter.setPen(QPen(QColor(255, 255, 255, 95), 1.5))
        painter.setBrush(chip_grad)
        painter.drawEllipse(QPointF(cx, cy), chip_r, chip_r)

        # 3) Kamera siluet — chip ichida, nozik chiziqli
        body_w, body_h = 54, 32
        body_x = cx - body_w // 2
        body_y = cy - body_h // 2 + 4
        body_pen = QPen(QColor(225, 236, 248, 235), 2.3,
                        Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin)
        painter.setPen(body_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(body_x, body_y, body_w, body_h, 6, 6)

        # Viewfinder "bump" (trapezoid) — tepadagi kichik chiqish
        vf_w = 18
        vf_l = cx - vf_w // 2 + 2
        painter.drawPolyline([
            QPointF(vf_l + 2, body_y),
            QPointF(vf_l + 5, body_y - 6),
            QPointF(vf_l + vf_w - 5, body_y - 6),
            QPointF(vf_l + vf_w - 2, body_y),
        ])

        # Lens — tashqi aylana + ichki nuqta
        painter.drawEllipse(QPointF(cx, cy + 4), 8, 8)
        painter.setBrush(QColor(225, 236, 248, 130))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPointF(cx, cy + 4), 3.2, 3.2)

        # Flash dot — o'ng tepada
        painter.setBrush(QColor(225, 236, 248, 220))
        painter.drawEllipse(QPointF(body_x + body_w - 6, body_y + 5), 1.8, 1.8)

        # 4) Qizil diagonal slash — universal "off/stopped" belgisi
        #    Ikki qatlam: qorong'i tag + yorqin asosiy chiziq (puxta ko'rinish uchun)
        inset = 14
        sx1, sy1 = cx - chip_r + inset, cy + chip_r - inset
        sx2, sy2 = cx + chip_r - inset, cy - chip_r + inset
        shade_pen = QPen(QColor(60, 14, 18, 190), 6.5,
                         Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(shade_pen)
        painter.drawLine(sx1, sy1, sx2, sy2)
        slash_pen = QPen(QColor(239, 115, 115, 245), 4.2,
                         Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(slash_pen)
        painter.drawLine(sx1, sy1, sx2, sy2)

        # 5) Sarlavha matni
        title_y = cy + chip_r + 20
        painter.setPen(QColor(220, 232, 245, 245))
        title_font = QFont(FNT, 14, QFont.Weight.Bold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(0, title_y, W, 24),
            Qt.AlignmentFlag.AlignCenter,
            "Kamera to'xtatilgan",
        )

        # 6) Yordamchi matn
        hint_y = title_y + 26
        painter.setPen(QColor(170, 182, 200, 215))
        hint_font = QFont(FNT, 10)
        painter.setFont(hint_font)
        painter.drawText(
            QRectF(0, hint_y, W, 20),
            Qt.AlignmentFlag.AlignCenter,
            "Qayta ishga tushirish uchun START bosing",
        )

        painter.end()
        self.video_label.setPixmap(pix)

    def _paint_no_face_glass(self, pix: QPixmap) -> None:
        """Video frame ustiga glassmorphism uslubida "No face detection"
        kartasini chizadi: scanner-bracket + dashed face siluet + matn.
        Qt QPainter orqali — cv2'dagidan tiniqroq va zamonaviy ko'rinish."""
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        W = pix.width()
        H = pix.height()
        if W <= 0 or H <= 0:
            painter.end()
            return

        # 1) Butun frame ustiga tuman (dim) qatlami — diqqatni kartaga jamlaydi
        painter.fillRect(pix.rect(), QColor(8, 14, 22, 110))

        # 2) Glass card — markazda, yumshoq gradient + ingichka chegara
        card_w = min(int(W * 0.64), 380)
        card_h = min(int(H * 0.62), 240)
        card_x = (W - card_w) // 2
        card_y = (H - card_h) // 2
        card_rect = QRectF(card_x, card_y, card_w, card_h)

        # Glass fill — sovuq kul oq gradient, past alpha (shisha ta'siri)
        grad = QLinearGradient(card_x, card_y, card_x, card_y + card_h)
        grad.setColorAt(0.0, QColor(255, 255, 255, 44))
        grad.setColorAt(0.55, QColor(235, 245, 255, 22))
        grad.setColorAt(1.0, QColor(180, 200, 225, 18))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(grad)
        painter.drawRoundedRect(card_rect, 22, 22)

        # Ichki highlight (top edge) — shisha yog'dusi taassurotini beradi
        hi_pen = QPen(QColor(255, 255, 255, 90), 1.4)
        painter.setPen(hi_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(card_rect, 22, 22)

        # 3) Scanner-bracket ikonka — 4 burchakli face-scan frame (bo'sh)
        icon_size = int(min(card_w, card_h) * 0.42)
        icon_cx = card_x + card_w // 2
        icon_cy = card_y + int(card_h * 0.34)
        half = icon_size // 2
        bracket_len = max(12, int(icon_size * 0.26))

        bracket_pen = QPen(QColor(125, 211, 255, 235), 2.6,
                           Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(bracket_pen)

        # top-left
        painter.drawLine(icon_cx - half, icon_cy - half,
                         icon_cx - half + bracket_len, icon_cy - half)
        painter.drawLine(icon_cx - half, icon_cy - half,
                         icon_cx - half, icon_cy - half + bracket_len)
        # top-right
        painter.drawLine(icon_cx + half, icon_cy - half,
                         icon_cx + half - bracket_len, icon_cy - half)
        painter.drawLine(icon_cx + half, icon_cy - half,
                         icon_cx + half, icon_cy - half + bracket_len)
        # bottom-left
        painter.drawLine(icon_cx - half, icon_cy + half,
                         icon_cx - half + bracket_len, icon_cy + half)
        painter.drawLine(icon_cx - half, icon_cy + half,
                         icon_cx - half, icon_cy + half - bracket_len)
        # bottom-right
        painter.drawLine(icon_cx + half, icon_cy + half,
                         icon_cx + half - bracket_len, icon_cy + half)
        painter.drawLine(icon_cx + half, icon_cy + half,
                         icon_cx + half, icon_cy + half - bracket_len)

        # Dashed face outline — "yuz izlanmoqda, topilmadi" signali
        face_rx = int(half * 0.48)
        face_ry = int(half * 0.60)
        face_pen = QPen(QColor(255, 255, 255, 175), 1.6, Qt.PenStyle.DashLine)
        face_pen.setDashPattern([3.5, 3.0])
        painter.setPen(face_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QPointF(icon_cx, icon_cy), face_rx, face_ry)

        # Dot ko'zlar — yengil, diqqatni tortmasdan yuzni eslatadi
        eye_pen = QPen(QColor(255, 255, 255, 210), 2.4,
                       Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(eye_pen)
        eye_dx = max(4, int(face_rx * 0.45))
        eye_dy = int(face_ry * 0.20)
        painter.drawPoint(icon_cx - eye_dx, icon_cy - eye_dy)
        painter.drawPoint(icon_cx + eye_dx, icon_cy - eye_dy)

        # 4) Asosiy matn — "No face detection"
        title_y = card_y + int(card_h * 0.70)
        painter.setPen(QColor(255, 255, 255, 240))
        title_font = QFont(FONT_FAMILY, 13, QFont.Weight.DemiBold)
        title_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
        painter.setFont(title_font)
        painter.drawText(
            QRectF(card_x, title_y, card_w, 22),
            Qt.AlignmentFlag.AlignCenter,
            "No face detection",
        )

        # 5) Yordamchi matn — o'zbekcha ko'rsatma
        sub_y = title_y + 24
        painter.setPen(QColor(220, 232, 245, 160))
        sub_font = QFont(FONT_FAMILY, 9, QFont.Weight.Normal)
        painter.setFont(sub_font)
        painter.drawText(
            QRectF(card_x, sub_y, card_w, 18),
            Qt.AlignmentFlag.AlignCenter,
            "Kamera oldiga yuzingizni joylashtiring",
        )

        painter.end()

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Kamera ishlab turganda Orqaga/Reload/Slider boshqaruvlarini
        disable qilish, to'xtaganda qaytarish."""
        for w in (
            getattr(self, "_back_btn", None),
            getattr(self, "_reload_btn", None),
            getattr(self, "_sim_slider", None),
        ):
            if w is not None:
                w.setEnabled(enabled)

    @staticmethod
    def _fmt_subject(name: str | None) -> str:
        """Student info cardda subject_name maxsimum 70 ta belgigacha chiqadi.
        Undan uzun bo'lsa — oxirida ellipsis ko'rsatiladi."""
        if not name:
            return "\u2014"
        s = str(name).strip()
        return s if len(s) <= 70 else s[:69].rstrip() + "\u2026"

    def _try_capture_current_face(self) -> bytes | None:
        """Agar kamera ishlab turgan bo'lsa va joriy kadrda yuz aniqlansa,
        eng katta yuzni crop qilib JPEG bytes qaytaradi. Aks holda None.

        JShShIR orqali qo'shish paytida camera ko'z ostidagi rasmni
        first_captured'ga yozish uchun foydalaniladi."""
        if not self._is_running:
            return None
        frame = self._last_frame
        if frame is None:
            return None
        try:
            from services.face_engine import FaceEngine
            engine = FaceEngine()
            if not engine.is_ready:
                return None
            faces = engine.detect_and_embed(frame)
            if not faces:
                return None
            # Eng katta bbox'li yuzni tanlaymiz — odatda cameraga qaragan odam.
            best = max(
                faces,
                key=lambda f: max(0, f["bbox"][2] - f["bbox"][0])
                              * max(0, f["bbox"][3] - f["bbox"][1]),
            )
            return CameraWorker._crop_face_bytes(frame, best["bbox"])
        except Exception:
            return None

    def _open_pinfl_modal(self):
        if not self._session_sm_id:
            self._set_status("Sessiya tanlanmagan!", "error")
            return
        modal = _PinflModal(self._db, self._session_sm_id, self._staff_id or 0, parent=self)
        modal.student_selected.connect(self._on_pinfl_student_selected)
        modal.student_skipped.connect(self._on_pinfl_student_skipped)
        modal.exec()

    def _on_pinfl_student_selected(self, stu: dict):
        """Fill student card from PINFL lookup result."""
        # Camera ishlab turmagan yoki camera oldida yuz aniqlanmagan bo'lsa —
        # davomatga qo'shishni taqiqlaymiz. Faqat allaqachon kiritilgan
        # studentni ko'rsatishga ruxsat berilmaydi.
        sid = stu.get("id")
        already_entered = False
        if sid:
            row = self._db.get_student(sid)
            already_entered = bool(row and row["is_entered"])
        if not already_entered:
            if not self._is_running or self._camera_worker is None:
                _AlertModal(
                    title="Kamera ishlamayapti",
                    message=(
                        "Davomatga qo\u2018shish uchun avval kamerani ishga "
                        "tushiring va student kameraga qarasin."
                    ),
                    accent="warn",
                    icon="\u26a0",
                    parent=self,
                ).exec()
                self._set_status("Kamera ishlamayapti — qo\u2018shilmadi", "error")
                return
            captured_face = self._try_capture_current_face()
            if not captured_face:
                _AlertModal(
                    title="Yuz aniqlanmadi",
                    message=(
                        "Kamera oldida student yuzi aniqlanmadi. Iltimos, "
                        "student kameraga qarab tursin va qayta urinib "
                        "ko\u2018ring."
                    ),
                    accent="warn",
                    icon="\U0001F464",
                    parent=self,
                ).exec()
                self._set_status("Kamerada yuz aniqlanmadi — qo\u2018shilmadi", "error")
                return
        else:
            captured_face = None

        self._row_last.set_value(stu.get("last_name") or "\u2014")
        self._row_first.set_value(stu.get("first_name") or "\u2014")
        self._row_middle.set_value(stu.get("middle_name") or "\u2014")
        self._row_imei.set_value(stu.get("imei") or "\u2014")
        gr = stu.get("gr_n") or "\u2014"
        self._row_group.set_value(f"{gr}-GURUH" if gr != "\u2014" else "\u2014")
        self._set_group_card(stu.get("gr_n"))
        sp = stu.get("sp_n") or "\u2014"
        self._row_seat.set_value(f"{sp}-JOY" if sp != "\u2014" else "\u2014")
        self._row_subj.set_value(self._fmt_subject(stu.get("subject_name")))
        gender = stu.get("gender", 0)
        gt = {1: "Erkak", 2: "Ayol"}.get(gender, str(gender))
        self._row_gender.set_value(gt)
        self._row_conf.set_value("JShShIR", ACC_BLUE)

        # Passport image
        self._show_passport(stu.get("ps_img") or "")

        self._set_status(f"JShShIR: {stu.get('last_name', '')} {stu.get('first_name', '')}")

        # Mark entered only if not already entered
        if sid:
            self._current_student_id = sid
            self._displayed_student_id = sid
            self._reject_btn.setVisible(True)
            if not already_entered:
                # captured_face yuqorida guardda olingan — cameradan olingan
                # yuz bu yerda first_captured va last_captured'ga saqlanadi.
                self._db.mark_student_entered(sid)
                entry_id = self._db.add_entry_log(
                    student_id=sid, staff_id=self._staff_id or 0,
                    score=0, is_sent=False,
                    face_img=captured_face,
                )
                # Birinchi tashrif boshlandi — gap kuzatuvini yangilaymiz.
                self._last_identified_at[sid] = datetime.now()
                if self._mode == "online":
                    self._submit_entry_online(entry_id)
                self._refresh_counts()
                stu["full_name"] = f"{stu.get('last_name', '')} {stu.get('first_name', '')}"
                # Carouselda faqat kamera surati ko'rsatiladi; kamera aniqlagan
                # bo'lsa shu rasm, bo'lmasa placeholder.
                stu_for_carousel = dict(stu)
                stu_for_carousel["ps_img"] = captured_face or None
                self._add_to_carousel(stu_for_carousel)
                self._row_conf.set_value("Davomatga qo\u2018shildi", ACC_GREEN)
            else:
                self._row_conf.set_value("Allaqachon qo\u2018shilgan", ACC_TEAL)

    def _on_pinfl_student_skipped(self, stu: dict):
        """Chetlatish — sabab modalini ochib, is_cheating=1 qilib belgilash."""
        reason_id, reason_name = self._ask_reject_reason()
        if reason_id is None:
            return  # foydalanuvchi bekor qildi

        self._row_last.set_value(stu.get("last_name") or "\u2014")
        self._row_first.set_value(stu.get("first_name") or "\u2014")
        self._row_middle.set_value(stu.get("middle_name") or "\u2014")
        self._row_imei.set_value(stu.get("imei") or "\u2014")
        gr = stu.get("gr_n") or "\u2014"
        self._row_group.set_value(f"{gr}-GURUH" if gr != "\u2014" else "\u2014")
        sp = stu.get("sp_n") or "\u2014"
        self._row_seat.set_value(f"{sp}-JOY" if sp != "\u2014" else "\u2014")
        self._row_subj.set_value(self._fmt_subject(stu.get("subject_name")))
        gender = stu.get("gender", 0)
        gt = {1: "Erkak", 2: "Ayol"}.get(gender, str(gender))
        self._row_gender.set_value(gt)
        self._row_conf.set_value(f"Chetlatildi: {reason_name}", ACC_RED)
        self._set_group_card(stu.get("gr_n"))
        self._show_passport(stu.get("ps_img") or "")
        self._reject_btn.setVisible(False)

        sid = stu.get("id")
        if sid:
            self._db.mark_student_cheating(sid, reason_id)

            # Entry log — chetlatilgan yozuv (is_rejected=True)
            row = self._db.get_student(sid)
            already_entered = row["is_entered"] if row else 0
            if not already_entered:
                self._db.mark_student_entered(sid)
                entry_id = self._db.add_entry_log(
                    student_id=sid, staff_id=self._staff_id or 0,
                    score=0, is_sent=False,
                    is_rejected=True, reject_reason_id=reason_id,
                )
                if self._mode == "online":
                    self._submit_entry_online(entry_id)
                self._refresh_counts()
            else:
                existing = self._db.get_entry_by_student(sid)
                if existing:
                    self._db.mark_entry_rejected(existing["id"], reason_id)

            # Carouselga chetlatilgan rangda qo'shish (yoki yangilash)
            stu_data = dict(stu)
            stu_data["full_name"] = (
                f"{stu.get('last_name', '')} {stu.get('first_name', '')}".strip() or "?"
            )
            stu_data["_is_cheating"] = True
            stu_data["_is_blacklist"] = bool(stu.get("is_blacklist", 0))
            # Carouselda faqat kamera surati; kamera aniqlagach yangilanadi.
            stu_data["ps_img"] = None
            self._add_to_carousel(stu_data)

        self._set_status(
            f"Chetlatildi ({reason_name}): {stu.get('last_name', '')} {stu.get('first_name', '')}"
        )

    def _ask_reject_reason(self) -> tuple[int | None, str]:
        """Chetlatish sabab modalini ko'rsatadi. (reason_id, reason_name) qaytaradi."""
        modal = _RejectReasonModal(self._db, parent=self)
        if modal.exec() != QDialog.DialogCode.Accepted:
            return None, ""
        return modal.reason_id, modal.reason_name

    def _mark_carousel_cheating(self, student_id: int):
        """Caroseldagi shu talaba kartasini chetlatilgan rangga o'tkazish."""
        if not student_id or not hasattr(self, "_carousel_lay"):
            return
        for i in range(self._carousel_lay.count()):
            it = self._carousel_lay.itemAt(i)
            w = it.widget() if it else None
            if isinstance(w, _RecentCard) and w.student_id == student_id:
                w.set_cheating(True)
                break

    # ════════════════════════════════════════════
    # Frames & faces
    # ════════════════════════════════════════════

    @pyqtSlot(np.ndarray)
    def _on_frame(self, frame: np.ndarray):
        # Kamera to'xtatilgan bo'lsa, pending (queued) signallarni e'tiborsiz qoldiramiz —
        # aks holda placeholder pixmap ustidan eski kadr yoziladi
        if not self._is_running:
            return
        # frame — worker threaddan copy bo'lib keladi, qayta copy kerak emas
        self._last_frame = frame

        # Overlay bo'lsagina copy qilib chizamiz, bo'lmasa to'g'ridan-to'g'ri
        if self._overlay_bboxes:
            disp = frame.copy()
            for bi in self._overlay_bboxes:
                b = bi["bbox"]
                c = bi.get("color", CV_GREEN)
                label = bi.get("label", "")
                th = bi.get("thickness", 2)
                cv2.rectangle(disp, (b[0], b[1]), (b[2], b[3]), c, th)
                if label:
                    (tw, th_), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(disp, (b[0], b[1] - th_ - 12), (b[0] + tw + 10, b[1]), c, -1)
                    cv2.putText(disp, label, (b[0] + 5, b[1] - 6),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        else:
            disp = frame

        # cvtColor yangi array yaratadi — alohida copy kerak emas
        rgb = cv2.cvtColor(disp, cv2.COLOR_BGR2RGB)

        # cv2.resize QPixmap.scaled dan 3-5x tezroq
        lbl_sz = self.video_label.size()
        lw, lh = lbl_sz.width(), lbl_sz.height()
        h, w = rgb.shape[:2]
        if lw > 0 and lh > 0 and (w != lw or h != lh):
            scale = min(lw / w, lh / h)
            tw, th = int(w * scale), int(h * scale)
            rgb = cv2.resize(rgb, (tw, th), interpolation=cv2.INTER_LINEAR)
            h, w = th, tw

        ch = 3
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pix = QPixmap.fromImage(qimg)

        # "No face detection" — glassmorphism overlay pixmap ustida chiziladi
        # (cv2 ustida emas — tiniqroq matn, yumshoq yumaloq burchaklar).
        if self._no_person_active:
            self._paint_no_face_glass(pix)

        self.video_label.setPixmap(pix)

    @pyqtSlot(dict)
    def _on_face_identified(self, data: dict):
        try:
            self._handle_identified(data)
        except Exception as e:
            self._set_status(f"Xato: {e}", "error")

    def _handle_identified(self, data: dict):
        sid = data["student_id"]
        # Cosine similarity [-1,1] → foiz [0,100]. Manfiy/nol → 0.
        # Musbat qiymatlar uchun sqrt (gamma 0.5) normallashtirish: past-o'rta
        # qiymatlarni perceptual jihatdan ko'taradi (0.5 → 71%, 0.48 → 69%),
        # endpoint'lar saqlanadi (0→0, 1→100), monoton va parametr talab qilmaydi.
        conf = float(data.get("confidence", 0) or 0.0)
        pct = int(round(math.sqrt(max(0.0, min(1.0, conf))) * 100))
        captured_img = data.get("captured_img", "")
        self._no_person_active = False

        # ── Qayta tekshiruv: shu student hali ham turgan bo'lsa ──
        if sid == self._current_student_id:
            self._do_silent_update(sid, pct, captured_img, data)
            return

        # ── Yangi student — to'liq UI rebuild ──
        row = self._db.get_student(sid)
        is_blacklist = False
        is_cheating = False
        ps_img = ""
        stu = {}
        if row:
            stu = dict(row)
            ps_img = stu.get("ps_img") or ""
            is_blacklist = bool(stu.get("is_blacklist", 0))
            is_cheating = bool(stu.get("is_cheating", 0))
            self._row_last.set_value(stu.get("last_name") or "\u2014")
            self._row_first.set_value(stu.get("first_name") or "\u2014")
            self._row_middle.set_value(stu.get("middle_name") or "\u2014")
            self._row_imei.set_value(stu.get("imei") or "\u2014")
            self._row_subj.set_value(self._fmt_subject(stu.get("subject_name")))
            self._set_group_card(stu.get("gr_n"))
        else:
            full = data.get("full_name", "\u2014")
            parts = full.split(maxsplit=2)
            self._row_last.set_value(parts[0] if len(parts) > 0 else "\u2014")
            self._row_first.set_value(parts[1] if len(parts) > 1 else "\u2014")
            self._row_middle.set_value(parts[2] if len(parts) > 2 else "\u2014")
            self._row_imei.set_value("\u2014")
            self._row_subj.set_value("\u2014")
            self._set_group_card(None)

        # Match chip — blacklist qizil, cheating sariq
        if is_blacklist:
            self._match_chip.setText("\u26a0 Yaxshilab tekshirish kerak!")
            self._match_chip.setStyleSheet(f"""
                color: #fff;
                background: {ACC_RED};
                border: none;
                border-radius: 8px;
                padding: 0 12px;
                font-weight: bold;
            """)
        elif is_cheating:
            self._match_chip.setText("\u26a0 Chetlatilgan")
            self._match_chip.setStyleSheet(f"""
                color: #3e2c00;
                background: {ACC_AMBER};
                border: none;
                border-radius: 8px;
                padding: 0 12px;
                font-weight: bold;
            """)
        elif pct >= self._similarity_threshold:
            self._match_chip.setText(f"\u2713 {pct}%  Mos keldi")
            self._match_chip.setStyleSheet(f"""
                color: #1a3a28;
                background: {ACC_GREEN};
                border: none;
                border-radius: 8px;
                padding: 0 12px;
                font-weight: bold;
            """)
        else:
            self._match_chip.setText(f"\u2717 {pct}%  Past")
            self._match_chip.setStyleSheet(f"""
                color: {ACC_RED};
                background: rgba(239,154,154,0.12);
                border: 1px solid rgba(239,154,154,0.28);
                border-radius: 8px;
                padding: 0 12px;
                font-weight: bold;
            """)

        self._match_pulse = 1.0

        gr_n = stu.get("gr_n") if stu else None
        seat_number = stu.get("sp_n") if stu else None
        self._row_group.set_value(f"{gr_n}-GURUH" if gr_n else "\u2014")
        self._set_group_card(gr_n)
        self._row_seat.set_value(f"{seat_number}-JOY" if seat_number else "\u2014")

        gender = data.get("gender", 0)
        if isinstance(gender, int):
            gt = {1: "Erkak", 2: "Ayol"}.get(gender, str(gender))
        else:
            gt = str(gender)
        self._row_gender.set_value(gt)

        if is_blacklist:
            conf_color = ACC_RED
        elif is_cheating:
            conf_color = ACC_AMBER
        elif pct >= self._similarity_threshold:
            conf_color = ACC_GREEN
        else:
            conf_color = ACC_RED
        self._row_conf.set_value(f"{pct}%", conf_color)

        # UI o'zgarishlarini tezda qilib, og'ir ishlarni background threadga ko'chiramiz.
        # Avval faqat UI ni yangilash — keyin bg threadda DB/HTTP.
        def _ui_update():
            try:
                ps_accent = ACC_RED if is_blacklist else (ACC_AMBER if is_cheating else ACC_GREEN)
                self._show_passport(ps_img, accent=ps_accent)

                carousel_data = dict(stu) if stu else {"full_name": data.get("full_name", "?")}
                carousel_data["id"] = sid
                if "full_name" not in carousel_data:
                    carousel_data["full_name"] = data.get("full_name", "?")
                # Carouselda faqat kamera surati (entry_log.last_captured) ko'rsatiladi.
                carousel_data["ps_img"] = captured_img or None
                carousel_data["_is_blacklist"] = is_blacklist
                carousel_data["_is_cheating"] = is_cheating
                # Yangi tashrif / yangi student — optimal baseline'ni hozirgi pct ga o'rnatamiz.
                self._carousel_max_score[sid] = pct
                self._add_to_carousel(carousel_data)
            except Exception as e:
                self._set_status(f"UI xato: {e}", "error")

        # Yangi tashrif aniqlash — oldingi identify'dan beri gap o'tganligi.
        now_dt = datetime.now()
        prev_seen = self._last_identified_at.get(sid)
        is_new_visit = bool(
            prev_seen is not None
            and (now_dt - prev_seen).total_seconds() > self._NEW_VISIT_GAP_SEC
        )
        self._last_identified_at[sid] = now_dt

        def _bg():
            try:
                self._db.mark_student_entered(sid)
                existing = self._db.get_entry_by_student(sid)
                if existing:
                    eid = existing["id"]
                    self._db.update_entry_log(
                        eid, score=pct, face_img=captured_img,
                        is_new_visit=is_new_visit,
                    )
                else:
                    eid = self._db.add_entry_log(
                        student_id=sid, staff_id=self._staff_id,
                        score=pct, is_sent=False,
                        face_img=captured_img,
                    )
                if self._mode == "online":
                    self._submit_entry_online(eid)
                QTimer.singleShot(0, self._refresh_counts)
            except Exception:
                import traceback
                traceback.print_exc()

        QTimer.singleShot(0, _ui_update)
        threading.Thread(target=_bg, daemon=True).start()

        if is_blacklist:
            self._set_status("\u26a0 QORA RO'YXATDA! Tekshirish kerak!", "error")
            self._apply_verify_blacklist()
        elif is_cheating:
            self._set_status("\u26a0 CHETLATILGAN! Ogohlantirish!", "error")
            self._apply_verify_cheating()
        else:
            self._set_status("Aniqlandi")
            if pct >= self._similarity_threshold:
                self._apply_verify_success()
            else:
                self._clear_verify_success()

        self._current_student_id = sid
        self._displayed_student_id = sid
        self._reject_btn.setVisible(True)
        self._start_countdown()

    def _do_silent_update(self, sid: int, pct: int, captured_img: bytes | str, data: dict):
        """Shu student hali turgan — DB background, UI yengil update."""
        # Silent update — student cameradan ketmagan, shuning uchun bu doim
        # mavjud tashrifning davomi (is_new_visit=False).
        self._last_identified_at[sid] = datetime.now()

        # Carousel rasmi yaxshilanganmi? Shu yerda bir marta hisoblab olamiz:
        # DB update va backend resubmit aynan shu shart bilan bog'liq bo'ladi.
        improved = False
        if captured_img:
            prev_max = self._carousel_max_score.get(sid, 0)
            if pct > prev_max:
                improved = True
                self._carousel_max_score[sid] = pct

        # DB — background thread. Yaxshilangan kadrda backendga ham qayta
        # yuboramiz — aks holda server'da eski (birinchi verify) rasm qolib
        # ketadi, caruseldagi/modaldagi rasmdan farq qiladi.
        def _bg():
            try:
                existing = self._db.get_entry_by_student(sid)
                if not existing:
                    return
                eid = existing["id"]
                self._db.update_entry_log(
                    eid, score=pct, face_img=captured_img,
                    is_new_visit=False,
                )
                if improved and self._mode == "online":
                    try:
                        self._db.mark_entry_unsent(eid)
                    except Exception:
                        pass
                    self._submit_entry_online(eid)
            except Exception:
                pass
        threading.Thread(target=_bg, daemon=True).start()

        # UI — score yangilash (yengil, qotmaydi)
        if pct >= self._similarity_threshold:
            self._match_chip.setText(f"\u2713 {pct}%  Mos keldi")
        self._row_conf.set_value(f"{pct}%")

        # Carousel card rasmini yangilash — faqat score yaxshilanganda.
        if improved:
            self._update_carousel_photo(sid, captured_img)

        self._start_countdown()

    def _update_carousel_photo(self, sid: int, b64: bytes | str):
        """Caruseldagi cardni student_id bo'yicha topib rasmini yangilash.
        b64 — raw JPEG bytes yoki base64 string (ikkalasi ham qo'llab-quvvatlanadi)."""
        for i in range(self._carousel_lay.count()):
            it = self._carousel_lay.itemAt(i)
            if it and it.widget() and isinstance(it.widget(), _RecentCard):
                if it.widget()._stu.get("id") == sid:
                    it.widget().update_photo(b64)
                    break

    def _start_countdown(self):
        """Qayta tekshiruv countdownini boshlash."""
        self._countdown_remaining = self._verify_cooldown
        if self._countdown_timer is None:
            self._countdown_timer = QTimer(self)
            self._countdown_timer.setInterval(1000)
            self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start()
        self._update_countdown_ui()

    def _on_countdown_tick(self):
        self._countdown_remaining -= 1
        if self._countdown_remaining > 0:
            self._update_countdown_ui()
        else:
            self._countdown_timer.stop()
            # Check icon ko'rsatish — keyingi verify kutilmoqda
            self._countdown_overlay.setText("\u2713")
            self._countdown_overlay.setStyleSheet(f"""
                background: rgba(0,0,0,0.55);
                color: {ACC_GREEN};
                border-radius: 21px;
                font-size: 20px;
                font-weight: bold;
                font-family: {FONT_FAMILY};
            """)
            self._countdown_overlay.move(self.video_label.width() - 52, 10)
            self._countdown_overlay.raise_()
            self._countdown_overlay.show()
            self._set_status("Tekshiruv...")

    def _update_countdown_ui(self):
        n = self._countdown_remaining
        self._set_status(f"Qayta tekshiruv: {n}s")
        self._countdown_overlay.setText(f"{n}s")
        self._countdown_overlay.setStyleSheet(f"""
            background: rgba(0,0,0,0.55);
            color: {ACC_GREEN};
            border-radius: 21px;
            font-size: 16px;
            font-weight: bold;
            font-family: {FONT_FAMILY};
        """)
        self._countdown_overlay.move(self.video_label.width() - 52, 10)
        self._countdown_overlay.raise_()
        self._countdown_overlay.show()

    def _stop_countdown(self):
        if self._countdown_timer:
            self._countdown_timer.stop()
        self._countdown_remaining = 0
        self._countdown_overlay.hide()

    def _on_reject_student(self):
        """Chetlatish — sabab modalini ochib, is_cheating=1 qilib belgilash."""
        sid = self._displayed_student_id or self._current_student_id
        if not sid:
            return
        reason_id, reason_name = self._ask_reject_reason()
        if reason_id is None:
            return  # bekor qilindi

        self._db.mark_student_cheating(sid, reason_id)
        # Server tomoniga is_rejected=True yuborish uchun entry_log ni yangilash/yaratish
        existing = self._db.get_entry_by_student(sid)
        if existing:
            entry_id = existing["id"]
            self._db.mark_entry_rejected(entry_id, reason_id)
        else:
            entry_id = self._db.add_entry_log(
                student_id=sid, staff_id=self._staff_id or 0,
                score=0, is_sent=False,
                is_rejected=True, reject_reason_id=reason_id,
            )
        if self._mode == "online":
            self._submit_entry_online(entry_id)
        self._mark_carousel_cheating(sid)

        # Kartada sababni ko'rsatish (keyingi yuz aniqlanganda tabiiy yangilanadi)
        self._row_conf.set_value(f"Chetlatildi: {reason_name}", ACC_RED)
        self._match_chip.setText("\u2717 Chetlatildi")
        self._match_chip.setStyleSheet(f"""
            color: {ACC_RED};
            background: rgba(239,154,154,0.14);
            border: 1px solid rgba(239,154,154,0.35);
            border-radius: 8px;
            padding: 0 12px;
        """)

        self._current_student_id = None
        self._displayed_student_id = None
        self._stop_countdown()
        self._reject_btn.setVisible(False)
        self._set_status(f"Chetlatildi: {reason_name}")

    def _show_passport(self, b64: str, accent: str = ""):
        if not b64:
            self._ps_img.clear()
            self._ps_img.setText("\U0001f464")
            self._ps_img.setStyleSheet(f"""
                background: rgba(0,0,0,0.20);
                border: 1px dashed {BRD_ACCENT};
                border-radius: 12px;
                color: {TXT_DIM};
                font-size: 36px;
            """)
            return
        # Map accent color to rgba bg
        _accent_bg = {
            ACC_GREEN: "rgba(102,187,106,0.10)",
            ACC_RED:   "rgba(239,154,154,0.10)",
            ACC_AMBER: "rgba(255,213,79,0.10)",
        }
        c_bg = _accent_bg.get(accent, "rgba(102,187,106,0.10)")
        sz = self._ps_img.size()
        pix = _decode_b64_pixmap(b64, sz.width(), sz.height())
        if pix:
            self._ps_img.setPixmap(pix)
            self._ps_img.setStyleSheet(f"""
                background: {c_bg};
                border: none;
                border-radius: 12px;
            """)

    @pyqtSlot(list)
    def _on_faces_update(self, bbox_infos: list):
        """Real-time bbox overlay — har detect qilinganda yangilanadi."""
        self._overlay_bboxes = []
        has_unknown = False
        has_too_far = False
        for info in bbox_infos:
            # Masofa chekloviga tushgan — identify hatto bajarilmagan.
            if info.get("too_far"):
                has_too_far = True
                self._overlay_bboxes.append({
                    "bbox": info["bbox"],
                    "color": CV_AMBER,
                    "label": "Yaqinroq",
                    "thickness": 2,
                })
                continue
            if info["identified"]:
                self._overlay_bboxes.append({
                    "bbox": info["bbox"],
                    "color": CV_GREEN,
                    "label": f"{info['pct']}%",
                    "thickness": 2,
                })
            else:
                has_unknown = True
                self._overlay_bboxes.append({
                    "bbox": info["bbox"],
                    "color": CV_RED,
                    "label": "?",
                    "thickness": 2,
                })
        # "Odam aniqlanmadi" — faqat kadrda yuz umuman topilmaganda ko'rsatiladi.
        # Bu yerda bbox_infos bo'sh emas (aks holda no_face signali kelardi), demak
        # yuz bor — unknown/too_far holatlar o'z labellari bilan ko'rsatiladi.
        self._no_person_active = False
        if has_too_far and not has_unknown:
            self._set_status("Kameraga yaqinroq keling", "error")
        elif has_unknown:
            self._set_status("Shaxs aniqlanmadi!", "error")

    @pyqtSlot()
    def _on_no_face(self):
        self._overlay_bboxes = []
        self._current_student_id = None
        self._no_person_active = True
        self._stop_countdown()
        self._set_status("Tasvirda odam aniqlanmadi")

    @pyqtSlot(str)
    def _on_cam_error(self, err: str):
        self._set_status(f"Xato: {err}", "error")

    # ════════════════════════════════════════════
    # Helpers
    # ════════════════════════════════════════════

    def _update_mode_chip(self, mode: str):
        if mode == "online":
            c = ACC_GREEN
            text = "\u26a1 Online"
        else:
            c = ACC_BLUE
            text = "\u2601 Offline"

        self._mode_chip.setStyleSheet(f"""
            QFrame {{
                background: {c}14;
                border: 1px solid {c}28;
                border-radius: 17px;
            }}
        """)
        self._mode_dot.setStyleSheet(f"background: {c}; border: none; border-radius: 4px;")
        self._mode_text.setText(text)
        self._mode_text.setStyleSheet(f"color: {c}; background: transparent; border: none;")

    def _set_status(self, text: str, kind: str = "ok"):
        self._status_text.setText(text)
        c = ACC_RED if kind == "error" else ACC_GREEN
        self._status_chip.setStyleSheet(f"QFrame {{ background: transparent; border: 1px solid {c}28; border-radius: 17px; }}")
        self._status_dot.setStyleSheet(f"background: {c}; border: none; border-radius: 4px;")
        self._status_text.setStyleSheet(f"color: {c}; background: transparent; border: none;")

    def _start_online_worker(self):
        """Online rejim uchun ketma-ket yuboruvchi worker'ni ishga tushirish."""
        if self._online_worker and self._online_worker.isRunning():
            return
        self._online_worker = OnlineSubmitWorker(parent=self)
        self._online_worker.start()

    def _stop_online_worker(self):
        if self._online_worker and self._online_worker.isRunning():
            self._online_worker.stop()
        self._online_worker = None

    def _submit_entry_online(self, entry_id: int):
        """Online rejimda entry_log ni ketma-ket yuborish navbatiga qo'yish.
        Worker har bir yozuvni birma-bir yuboradi: ok bo'lsa — keyingisiga o'tadi,
        xato bo'lsa — retry navbatiga qo'yadi va asosiy navbat bo'shagach qayta urinadi."""
        if not self._online_worker or not self._online_worker.isRunning():
            self._start_online_worker()
        self._online_worker.enqueue(entry_id)

    def _on_stats_clicked(self):
        """Statistika tugmasi (online rejim) — davomat statistikasini modalda
        ko'rsatadi: umumiy / verifydan o'tgan / yuborilgan / yuborilmagan.

        Modal darhol ochiladi; server bilan sinxron bo'limida spinner turadi.
        Backend javobi kelganda (yoki xato bo'lsa) bo'lim yangilanadi —
        lokal statistika va UI thread bloklanmaydi."""
        try:
            stats = self._db.count_entries_stats()
        except Exception as e:
            self._set_status(f"Statistika olinmadi: {e}", "error")
            return

        show_server = bool(self._session_sm_id)
        modal = _StatsModal(stats, show_server=show_server, parent=self)

        worker: _StatsFetchWorker | None = None
        if show_server:
            worker = _StatsFetchWorker(self._session_sm_id, modal)
            worker.finished_ok.connect(modal.set_server_stats)
            worker.error.connect(
                lambda e: modal.set_server_error(
                    f"Server bilan bog\u2018lanib bo\u2018lmadi: {e}"
                )
            )
            worker.start()

        modal.exec()

        # Modal yopilganda ishlayotgan worker'ni kutib kelamiz.
        if worker is not None and worker.isRunning():
            worker.quit()
            worker.wait(3000)

    def _on_send_clicked(self):
        """Yuborish tugmasi — modal ochib, spinner bilan yuborish jarayonini ko'rsatadi."""
        try:
            if self._sync_service and self._sync_service.isRunning():
                self._set_status("Yuborish jarayoni davom etmoqda...")
                return

            try:
                stats = self._db.count_entries_stats()
            except Exception as e:
                self._set_status(f"DB xato: {e}", "error")
                return

            unsent_count = stats["unsent"]
            modal = _SyncModal(stats, parent=self)

            if unsent_count == 0:
                modal.on_finished(error="Yuborilmagan yozuv yo'q")
                modal.exec()
                return

            state = {"last_error": "", "sent": 0, "total": unsent_count}

            def _refresh_modal_stats():
                try:
                    modal.update_stats(self._db.count_entries_stats())
                except Exception:
                    pass

            def _on_status(msg: str):
                lower = msg.lower()
                if "xato" in lower or "error" in lower:
                    state["last_error"] = msg
                modal.on_status(msg)

            def _on_progress(sent: int, total: int):
                state["sent"] = sent
                state["total"] = total
                modal.on_progress(sent, total)
                _refresh_modal_stats()

            def _on_finished():
                self._send_btn.setEnabled(True)
                _refresh_modal_stats()
                if state["last_error"]:
                    modal.on_finished(error=state["last_error"])
                elif state["sent"] == 0 and state["total"] > 0:
                    modal.on_finished(error="Internet bilan bog'lanib bo'lmadi")
                else:
                    modal.on_finished()

            self._sync_service = SyncService(parent=self, one_shot=True)
            self._sync_service.sync_status.connect(_on_status)
            self._sync_service.sync_progress.connect(_on_progress)
            self._sync_service.finished.connect(_on_finished)
            self._send_btn.setEnabled(False)
            self._sync_service.start()

            modal.exec()
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._set_status(f"Yuborish xatosi: {e}", "error")
            self._send_btn.setEnabled(True)

    def cleanup(self):
        self._stop_camera()
        self._stop_countdown()
        if self._sync_service:
            self._sync_service.stop()
        self._stop_online_worker()

        self._match_chip.setText("\u2014")
        self._match_chip.setStyleSheet(f"""
            color: {TXT_DIM};
            background: {SRF_FIELD};
            border: 1px solid {BRD};
            border-radius: 8px;
            padding: 0 12px;
        """)
        self._ps_img.clear()
        self._ps_img.setText("\U0001f464")
        self._set_group_card(None)
        for r in [self._row_last, self._row_first, self._row_middle,
                   self._row_group, self._row_seat,
                   self._row_subj, self._row_gender, self._row_conf]:
            r.set_value("\u2014")
        self._overlay_bboxes = []
        self._reject_btn.setVisible(False)
        self._clear_verify_success()
        self._set_status("Tayyor")
