import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

from config import FACE_MODEL_NAME, FACE_DET_SIZE, FACE_DET_THRESH, COSINE_SIMILARITY_THRESHOLD
from utils.singleton import SingletonMeta


class FaceEngineLoader(QThread):
    """Background thread to load InsightFace model without blocking UI."""
    finished = pyqtSignal(bool, str)  # (success, message)
    progress = pyqtSignal(str)        # status message

    def run(self):
        try:
            self.progress.emit("Model yuklanmoqda...")
            engine = FaceEngine()
            engine._do_initialize()
            self.finished.emit(True, "Model tayyor")
        except Exception as e:
            self.finished.emit(False, f"Model yuklashda xato: {e}")


class FaceEngine(metaclass=SingletonMeta):
    def __init__(self):
        self._app = None
        self._initialized = False
        self._embeddings_matrix: np.ndarray | None = None
        self._student_ids: list[int] = []
        self._students_data: list[dict] = []

    def _do_initialize(self):
        """Actually load the InsightFace model. Called from background thread."""
        if self._initialized:
            return
        from insightface.app import FaceAnalysis
        self._app = FaceAnalysis(name=FACE_MODEL_NAME, providers=self._get_providers())
        self._app.prepare(ctx_id=0, det_thresh=FACE_DET_THRESH, det_size=FACE_DET_SIZE)
        self._initialized = True

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @staticmethod
    def _get_providers() -> list[str]:
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "OpenVINOExecutionProvider" in available:
                return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        return ["CPUExecutionProvider"]

    def load_embeddings(self, students: list[dict]):
        """Load student embeddings into RAM as a single matrix for vectorized comparison."""
        if not students:
            self._embeddings_matrix = None
            self._student_ids = []
            self._students_data = []
            return

        self._students_data = students
        self._student_ids = [s["id"] for s in students]
        embeddings = [s["embedding"] for s in students]
        self._embeddings_matrix = np.vstack(embeddings)  # (N, 512)
        # Normalize for cosine similarity
        norms = np.linalg.norm(self._embeddings_matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        self._embeddings_matrix = self._embeddings_matrix / norms

    def detect_and_embed(self, frame: np.ndarray) -> list[dict]:
        """Detect faces and return their embeddings with bounding boxes."""
        if not self._initialized:
            return []
        faces = self._app.get(frame)
        results = []
        for face in faces:
            emb = face.embedding
            if emb is not None:
                norm = np.linalg.norm(emb)
                if norm > 0:
                    emb = emb / norm
                results.append({
                    "embedding": emb,
                    "bbox": face.bbox.astype(int).tolist(),
                    "det_score": float(face.det_score),
                })
        return results

    def identify(self, face_embedding: np.ndarray) -> dict | None:
        """1:N identification using vectorized cosine similarity."""
        if self._embeddings_matrix is None or len(self._student_ids) == 0:
            return None

        # Vectorized cosine similarity: (1, 512) @ (512, N) -> (1, N)
        similarities = face_embedding @ self._embeddings_matrix.T
        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= COSINE_SIMILARITY_THRESHOLD:
            student = self._students_data[best_idx]
            return {
                "student_id": student["id"],
                "full_name": f"To'rayev Yusuf Jumma o'g'li",
                "group_name": f"5 - Guruh",
                "gender": "Erkak",
                "seat_number": "3-joy",
                "confidence": best_score,
            }
        return None

    @property
    def loaded_count(self) -> int:
        return len(self._student_ids) if self._student_ids else 0
