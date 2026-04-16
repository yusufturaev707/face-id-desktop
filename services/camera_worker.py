import cv2
import math
import numpy as np
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal

from config import MIN_FACE_WIDTH_PX


def _cos_to_pct(conf: float) -> int:
    """Cosine similarity [-1,1] → foiz [0,100]. Manfiy/nol → 0.
    Musbat qiymatlar uchun sqrt (gamma 0.5) normallashtirish — `faceid_page`
    dagi UI/DB konvertatsiyasi bilan bir xil bo'lishi uchun."""
    c = float(conf or 0.0)
    return int(round(math.sqrt(max(0.0, min(1.0, c))) * 100))


class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    # captured_img — crop qilingan yuzning raw JPEG bytes (SQLite BLOB ga saqlash uchun)
    face_identified = pyqtSignal(dict)   # {student_id, full_name, gender, seat_number, confidence, bbox, captured_img}
    face_not_found = pyqtSignal(list)    # list of bboxes — tanilmagan yuzlar
    faces_update = pyqtSignal(list)      # barcha yuzlar bboxlari — real-time overlay uchun
    no_face = pyqtSignal()               # kadrda yuz topilmadi
    error_occurred = pyqtSignal(str)

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index
        self._running = False
        self._face_engine = None
        self._frame_skip = 2  # Process every Nth frame for face detection
        self._identified_cooldown: dict[int, datetime] = {}
        self._cooldown_seconds = 3

    @property
    def camera_index(self) -> int:
        return self._camera_index

    @camera_index.setter
    def camera_index(self, value: int):
        self._camera_index = value

    def run(self):
        cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            self.error_occurred.emit(f"Kamera {self._camera_index} ochilmadi!")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        self._running = True
        frame_count = 0

        while self._running:
            ret, frame = cap.read()
            if not ret:
                self.error_occurred.emit("Kadrni o'qib bo'lmadi!")
                break

            self.frame_ready.emit(frame.copy())
            frame_count += 1

            if frame_count % self._frame_skip == 0:
                self._process_frame(frame)

        cap.release()

    @staticmethod
    def _crop_face_bytes(frame: np.ndarray, bbox: list, pad: float = 0.25) -> bytes:
        """Crop face from frame with padding and encode as raw JPEG bytes (SQLite BLOB)."""
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = bbox
        bw, bh = x2 - x1, y2 - y1
        px, py = int(bw * pad), int(bh * pad)
        cx1 = max(0, x1 - px)
        cy1 = max(0, y1 - py)
        cx2 = min(w, x2 + px)
        cy2 = min(h, y2 + py)
        crop = frame[cy1:cy2, cx1:cx2]
        _, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buf.tobytes()

    def _process_frame(self, frame: np.ndarray):
        try:
            if self._face_engine is None:
                from services.face_engine import FaceEngine
                self._face_engine = FaceEngine()
            if not self._face_engine.is_ready:
                return
            faces = self._face_engine.detect_and_embed(frame)
            if not faces:
                self.no_face.emit()
                return

            # Real-time bbox overlay — barcha yuzlarni darhol yuborish
            bbox_infos = []
            for face_data in faces:
                # Minimal bbox gate — yuz juda uzoqda bo'lsa (kichik bbox),
                # identify bajarilmaydi. Bu masofa majburlash qatlami.
                bx1, _by1, bx2, _by2 = face_data["bbox"]
                bbox_w = max(0, bx2 - bx1)
                if MIN_FACE_WIDTH_PX > 0 and bbox_w < MIN_FACE_WIDTH_PX:
                    bbox_infos.append({
                        "bbox": face_data["bbox"],
                        "identified": False,
                        "too_far": True,
                    })
                    continue

                result = self._face_engine.identify(face_data["embedding"])
                if result:
                    bbox_infos.append({
                        "bbox": face_data["bbox"],
                        "identified": True,
                        "name": result["full_name"],
                        "pct": _cos_to_pct(result["confidence"]),
                    })
                    # Cooldown tekshiruvi — faqat yangi aniqlash uchun
                    student_id = result["student_id"]
                    now = datetime.now()
                    last_seen = self._identified_cooldown.get(student_id)
                    if last_seen and (now - last_seen).total_seconds() < self._cooldown_seconds:
                        continue
                    self._identified_cooldown[student_id] = now
                    result["bbox"] = face_data["bbox"]
                    result["captured_img"] = self._crop_face_bytes(frame, face_data["bbox"])
                    self.face_identified.emit(result)
                else:
                    bbox_infos.append({
                        "bbox": face_data["bbox"],
                        "identified": False,
                    })

            self.faces_update.emit(bbox_infos)

        except Exception as e:
            self.error_occurred.emit(f"Yuz aniqlashda xato: {e}")

    def stop(self):
        self._running = False
        self.wait(3000)
