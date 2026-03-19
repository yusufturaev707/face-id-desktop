import cv2
import numpy as np
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal


class CameraWorker(QThread):
    frame_ready = pyqtSignal(np.ndarray)
    face_identified = pyqtSignal(dict)   # {student_id, full_name, group_name, gender, seat_number, confidence, bbox}
    face_detected = pyqtSignal(list)     # list of bboxes for unidentified faces
    error_occurred = pyqtSignal(str)

    def __init__(self, camera_index: int = 0, parent=None):
        super().__init__(parent)
        self._camera_index = camera_index
        self._running = False
        self._face_engine = None
        self._frame_skip = 3  # Process every Nth frame for face detection
        self._identified_cooldown: dict[int, datetime] = {}
        self._cooldown_seconds = 5

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

            self.frame_ready.emit(frame)
            frame_count += 1

            if frame_count % self._frame_skip == 0:
                self._process_frame(frame)

        cap.release()

    def _process_frame(self, frame: np.ndarray):
        try:
            if self._face_engine is None:
                from services.face_engine import FaceEngine
                self._face_engine = FaceEngine()
            if not self._face_engine.is_ready:
                return
            faces = self._face_engine.detect_and_embed(frame)
            unidentified_bboxes = []

            for face_data in faces:
                result = self._face_engine.identify(face_data["embedding"])
                if result:
                    student_id = result["student_id"]
                    now = datetime.now()
                    last_seen = self._identified_cooldown.get(student_id)
                    if last_seen and (now - last_seen).total_seconds() < self._cooldown_seconds:
                        continue
                    self._identified_cooldown[student_id] = now
                    result["bbox"] = face_data["bbox"]
                    self.face_identified.emit(result)
                else:
                    unidentified_bboxes.append(face_data["bbox"])

            if unidentified_bboxes:
                self.face_detected.emit(unidentified_bboxes)

        except Exception as e:
            self.error_occurred.emit(f"Yuz aniqlashda xato: {e}")

    def stop(self):
        self._running = False
        self.wait(3000)
