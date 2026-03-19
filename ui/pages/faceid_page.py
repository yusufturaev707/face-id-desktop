import cv2
import numpy as np
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QSizePolicy, QFrame, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSlot, pyqtSignal
from PyQt6.QtGui import QImage, QPixmap, QFont, QColor, QPainter, QLinearGradient

from database.db_manager import DatabaseManager
from services.camera_worker import CameraWorker
from services.api_client import ApiClient
from services.sync_service import SyncService
from ui.components.dashboard import Dashboard
from ui.styles import COLORS, FONT_FAMILY

# OpenCV colors (BGR)
COLORS_OPENCV_GREEN = (0, 200, 0)
COLORS_OPENCV_RED = (0, 0, 220)


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
        self._session_sm_id: int | None = None
        self._staff_id: int | None = None
        self._mode: str = "offline"
        self._last_frame: np.ndarray | None = None
        self._overlay_bboxes: list = []
        self._setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0.0, QColor("#0F172A"))
        gradient.setColorAt(0.5, QColor("#1E293B"))
        gradient.setColorAt(1.0, QColor("#0F172A"))
        painter.fillRect(self.rect(), gradient)
        painter.end()

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 16, 24, 24)
        root_layout.setSpacing(12)

        # ── Top bar: Orqaga + Chiqish ──
        top_bar = QHBoxLayout()

        back_btn = QPushButton("\u2190  Orqaga")
        back_btn.setFixedSize(140, 40)
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
        logout_btn.setFixedSize(130, 40)
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

        root_layout.addLayout(top_bar)

        # ── Content area ──
        main_layout = QHBoxLayout()
        main_layout.setSpacing(24)

        # ── Left: Camera panel ──
        left_card = QFrame()
        left_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 240);
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        shadow_left = QGraphicsDropShadowEffect()
        shadow_left.setBlurRadius(40)
        shadow_left.setOffset(0, 8)
        shadow_left.setColor(QColor(0, 0, 0, 80))
        left_card.setGraphicsEffect(shadow_left)

        left = QVBoxLayout(left_card)
        left.setContentsMargins(20, 20, 20, 20)
        left.setSpacing(14)

        # Camera selector row
        cam_row = QHBoxLayout()
        cam_label = QLabel("Kamera:")
        cam_label.setFont(QFont("Segoe UI", 14, QFont.Weight.DemiBold))
        cam_label.setStyleSheet(f"color: {COLORS['text_primary']}; border: none;")
        cam_row.addWidget(cam_label)

        self.camera_combo = QComboBox()
        self.camera_combo.setMinimumWidth(240)
        self.camera_combo.setFixedHeight(44)
        self.camera_combo.setFont(QFont("Segoe UI", 13))
        self.camera_combo.setStyleSheet(f"""
            QComboBox {{
                border: 2px solid #E0E0E0;
                border-radius: 10px;
                padding: 8px 16px;
                background-color: #FAFAFA;
                font-family: {FONT_FAMILY};
            }}
            QComboBox:focus {{
                border-color: {COLORS['primary']};
            }}
        """)
        self._populate_cameras()
        cam_row.addWidget(self.camera_combo)
        cam_row.addStretch()

        self.start_btn = QPushButton("Boshlash")
        self.start_btn.setFixedSize(160, 44)
        self.start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.start_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['success']}, stop:1 #43A047);
                color: white;
                border: none;
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: #388E3C;
            }}
        """)
        self.start_btn.clicked.connect(self._toggle_camera)
        cam_row.addWidget(self.start_btn)

        left.addLayout(cam_row)

        # Video display
        self.video_label = QLabel()
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video_label.setStyleSheet("""
            background-color: #0F172A;
            border-radius: 12px;
            border: 2px solid #334155;
        """)
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("Kamera stream...")
        self.video_label.setStyleSheet("""
            background-color: #0F172A;
            border-radius: 12px;
            border: 2px solid #334155;
            color: #64748B;
            font-size: 18px;
        """)
        left.addWidget(self.video_label)

        # Status bar
        self.status_label = QLabel("Tayyor")
        self.status_label.setFont(QFont("Segoe UI", 13))
        self.status_label.setStyleSheet(f"color: {COLORS['text_secondary']}; border: none;")
        left.addWidget(self.status_label)

        main_layout.addWidget(left_card, stretch=3)

        # ── Right: Dashboard ──
        right_card = QFrame()
        right_card.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 240);
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
        """)
        shadow_right = QGraphicsDropShadowEffect()
        shadow_right.setBlurRadius(40)
        shadow_right.setOffset(0, 8)
        shadow_right.setColor(QColor(0, 0, 0, 80))
        right_card.setGraphicsEffect(shadow_right)

        right_layout = QVBoxLayout(right_card)
        right_layout.setContentsMargins(20, 20, 20, 20)

        self.dashboard = Dashboard()
        right_layout.addWidget(self.dashboard)

        main_layout.addWidget(right_card, stretch=2)

        root_layout.addLayout(main_layout)

    def _populate_cameras(self):
        self.camera_combo.clear()
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            for i, name in enumerate(devices):
                self.camera_combo.addItem(f"{name}", i)
        except Exception:
            pass

        if self.camera_combo.count() == 0:
            self.camera_combo.addItem("Kamera 0", 0)

    def setup_session(self, session_sm_id: int, staff_id: int, mode: str):
        self._session_sm_id = session_sm_id
        self._staff_id = staff_id
        self._mode = mode

        from services.face_engine import FaceEngine
        self._face_engine = FaceEngine()
        students = self._db.load_embeddings_for_smena(session_sm_id)
        self._face_engine.load_embeddings(students)
        self.status_label.setText(
            f"{self._face_engine.loaded_count} ta student embeddingi RAMga yuklandi"
        )

        self._refresh_counts()

        if mode == "online":
            self._start_sync_service()

    def _refresh_counts(self):
        if self._session_sm_id:
            counts = self._db.get_entered_count(self._session_sm_id)
            self.dashboard.update_counts(
                counts["total"], counts["male"] or 0, counts["female"] or 0
            )

    def _toggle_camera(self):
        if self._camera_worker and self._camera_worker.isRunning():
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        cam_index = self.camera_combo.currentData()
        if cam_index is None or cam_index < 0:
            self.status_label.setText("Kamera tanlanmadi!")
            return

        self._camera_worker = CameraWorker(cam_index, parent=self)
        self._camera_worker.frame_ready.connect(self._on_frame)
        self._camera_worker.face_identified.connect(self._on_face_identified)
        self._camera_worker.face_detected.connect(self._on_faces_detected)
        self._camera_worker.error_occurred.connect(self._on_camera_error)
        self._camera_worker.start()

        self.start_btn.setText("To'xtatish")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['error']};
                color: white;
                border: none;
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: #C62828;
            }}
        """)
        self.camera_combo.setEnabled(False)
        self.status_label.setText("Kamera ishlayapti...")

    def _stop_camera(self):
        if self._camera_worker:
            self._camera_worker.stop()
            self._camera_worker = None

        self.start_btn.setText("Boshlash")
        self.start_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {COLORS['success']}, stop:1 #43A047);
                color: white;
                border: none;
                border-radius: 12px;
                font-family: {FONT_FAMILY};
            }}
            QPushButton:hover {{
                background: #388E3C;
            }}
        """)
        self.camera_combo.setEnabled(True)
        self.status_label.setText("Kamera to'xtatildi")
        self.video_label.clear()
        self.video_label.setText("Kamera stream...")

    @pyqtSlot(np.ndarray)
    def _on_frame(self, frame: np.ndarray):
        self._last_frame = frame.copy()
        display = frame.copy()

        for bbox_info in self._overlay_bboxes:
            bbox = bbox_info["bbox"]
            color = bbox_info.get("color", COLORS_OPENCV_GREEN)
            label = bbox_info.get("label", "")
            cv2.rectangle(display, (bbox[0], bbox[1]), (bbox[2], bbox[3]), color, 2)
            if label:
                cv2.putText(display, label, (bbox[0], bbox[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.video_label.setPixmap(pixmap)

    @pyqtSlot(dict)
    def _on_face_identified(self, data: dict):
        student_id = data["student_id"]

        self.dashboard.show_student(data)
        self._db.mark_student_entered(student_id)

        is_sent = False
        score = int(data["confidence"] * 100)
        entry_id = self._db.add_entry_log(
            student_id=student_id,
            staff_id=self._staff_id,
            score=score,
            is_sent=is_sent,
        )

        if self._mode == "online":
            try:
                self._api.submit_entry(self._build_entry_payload(data))
                self._db.mark_entry_sent(entry_id)
            except Exception:
                pass

        self._refresh_counts()

        self._overlay_bboxes = [{
            "bbox": data["bbox"],
            "color": COLORS_OPENCV_GREEN,
            "label": f"{data['full_name']} ({data['confidence']*100:.0f}%)",
        }]

        self.status_label.setText(f"Aniqlandi: {data['full_name']}")

    @pyqtSlot(list)
    def _on_faces_detected(self, bboxes: list):
        self._overlay_bboxes = [
            {"bbox": bb, "color": COLORS_OPENCV_RED, "label": "?"} for bb in bboxes
        ]

    @pyqtSlot(str)
    def _on_camera_error(self, error: str):
        self.status_label.setText(f"Xato: {error}")
        self.status_label.setStyleSheet(f"color: {COLORS['error']}; font-size: 14px; border: none;")

    def _build_entry_payload(self, data: dict) -> dict:
        now = datetime.now().isoformat()
        return {
            "student_id": data["student_id"],
            "staff_id": self._staff_id,
            "first_enter_time": now,
            "last_enter_time": now,
            "score": int(data["confidence"] * 100),
            "max_score": int(data["confidence"] * 100),
        }

    def _start_sync_service(self):
        if self._sync_service and self._sync_service.isRunning():
            return
        self._sync_service = SyncService(parent=self)
        self._sync_service.sync_status.connect(
            lambda msg: self.status_label.setText(f"Sync: {msg}")
        )
        self._sync_service.start()

    def cleanup(self):
        self._stop_camera()
        if self._sync_service:
            self._sync_service.stop()
