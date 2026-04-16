import logging

import numpy as np
import torch
from PyQt6.QtCore import QThread, pyqtSignal

from config import FACE_MODEL_NAME, FACE_DET_SIZE, FACE_DET_THRESH, COSINE_SIMILARITY_THRESHOLD
from utils.singleton import SingletonMeta

log = logging.getLogger(__name__)

# GPU/CPU avtomatik aniqlash — bir marta
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
log.info("PyTorch device: %s", DEVICE)


class FaceEngineLoader(QThread):
    """Background thread to load InsightFace model without blocking UI."""
    finished = pyqtSignal(bool, str)  # (success, message)
    progress = pyqtSignal(str)        # status message

    def run(self):
        try:
            engine = FaceEngine()
            providers = engine._get_providers()
            device = "GPU (CUDA)" if "CUDAExecutionProvider" in providers else "CPU"
            torch_dev = "GPU" if DEVICE.type == "cuda" else "CPU"
            self.progress.emit(f"Model yuklanmoqda ({device}, torch: {torch_dev})...")
            engine._do_initialize()
            self.finished.emit(True, f"Model tayyor — {device} · torch: {torch_dev}")
        except Exception as e:
            self.finished.emit(False, f"Model yuklashda xato: {e}")


class FaceEngine(metaclass=SingletonMeta):
    def __init__(self):
        self._app = None
        self._initialized = False
        self._use_gpu = False
        # Torch tensors — GPU da turadi (agar mavjud bo'lsa)
        self._embeddings_tensor: torch.Tensor | None = None
        self._student_ids: list[int] = []
        self._students_data: list[dict] = []
        # Dinamik cosine threshold — UI sliderdan yangilanadi.
        self._threshold: float = float(COSINE_SIMILARITY_THRESHOLD)

    def set_threshold(self, value: float) -> None:
        """Cosine similarity threshold'ni o'zgartirish (0..1 diapazoni).
        Diapazondan tashqari qiymat clamp qilinadi."""
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        self._threshold = max(0.0, min(1.0, v))
        log.info("FaceEngine cosine threshold set to %.3f", self._threshold)

    @property
    def threshold(self) -> float:
        return self._threshold

    def _do_initialize(self):
        """Actually load the InsightFace model. Called from background thread."""
        if self._initialized:
            return
        from insightface.app import FaceAnalysis

        providers = self._get_providers()
        self._use_gpu = "CUDAExecutionProvider" in providers
        ctx_id = 0 if self._use_gpu else -1

        log.info("InsightFace providers: %s  ctx_id: %d", providers, ctx_id)

        self._app = FaceAnalysis(name=FACE_MODEL_NAME, providers=providers)
        self._app.prepare(ctx_id=ctx_id, det_thresh=FACE_DET_THRESH, det_size=FACE_DET_SIZE)
        self._initialized = True

    @property
    def is_ready(self) -> bool:
        return self._initialized

    @property
    def device_name(self) -> str:
        if not self._initialized:
            return "—"
        onnx = "GPU (CUDA)" if self._use_gpu else "CPU"
        torch_dev = "GPU" if DEVICE.type == "cuda" else "CPU"
        return f"{onnx} · torch: {torch_dev}"

    @staticmethod
    def _get_providers() -> list[str]:
        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
            log.info("ONNX Runtime available providers: %s", available)
            if "CUDAExecutionProvider" in available:
                return ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if "OpenVINOExecutionProvider" in available:
                return ["OpenVINOExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        return ["CPUExecutionProvider"]

    def load_embeddings(self, students: list[dict]):
        """Load student embeddings as torch tensor on GPU/CPU."""
        if not students:
            self._embeddings_tensor = None
            self._student_ids = []
            self._students_data = []
            return

        self._students_data = students
        self._student_ids = [s["id"] for s in students]
        embeddings = [s["embedding"] for s in students]
        matrix = np.vstack(embeddings)  # (N, 512)

        # Torch tensor ga o'tkazish va normalize qilish
        t = torch.from_numpy(matrix).float().to(DEVICE)
        norms = t.norm(dim=1, keepdim=True).clamp(min=1e-8)
        self._embeddings_tensor = t / norms

        log.info(
            "Loaded %d embeddings on %s (shape: %s)",
            len(students), DEVICE, self._embeddings_tensor.shape,
        )

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
        """1:N identification — torch GPU/CPU da cosine similarity."""
        if self._embeddings_tensor is None or len(self._student_ids) == 0:
            return None

        # numpy → torch tensor (GPU/CPU)
        query = torch.from_numpy(face_embedding).float().to(DEVICE)

        # Cosine similarity: (512,) @ (512, N) -> (N,)
        similarities = query @ self._embeddings_tensor.T
        best_idx = int(torch.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self._threshold:
            student = self._students_data[best_idx]
            return {
                "student_id": student["id"],
                "full_name": student["full_name"],
                "gender": student.get("gender", 0),
                "seat_number": student.get("seat_number", ""),
                "confidence": best_score,
            }
        return None

    @property
    def loaded_count(self) -> int:
        return len(self._student_ids) if self._student_ids else 0
