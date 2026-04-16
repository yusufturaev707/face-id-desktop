import os
from pathlib import Path

APP_NAME = "Face-ID Desktop"
APP_VERSION = "2.0.0"

# API Configuration
API_BASE_URL = os.getenv("FACEID_API_URL") or "http://localhost:8000/api/v1"

# Database
APP_DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "FaceIDDesktop"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DATA_DIR / "faceid.db"

# InsightFace
FACE_MODEL_NAME = "buffalo_l"
FACE_DET_SIZE = (640, 640)
FACE_DET_THRESH = 0.75

# Recognition thresholds
COSINE_SIMILARITY_THRESHOLD = 0.5

# Liveness (anti-spoofing) — Silent-Face-Anti-Spoofing (MiniFASNet ONNX)
# True bo'lsa, har bir aniqlangan yuz oldin liveness tekshiruvidan o'tadi.
# False bo'lsa — tekshiruv umuman bajarilmaydi (overhead yo'q).
LIVENESS_DETECTION = True
# Model fayllari joylashgan katalog (ONNX). Ichida minifasnet_v2.onnx fayli
# bo'lishi kutiladi. Bitta yoki bir nechta model qo'shilsa — ensemble ishlaydi.
LIVENESS_MODEL_DIR = Path(__file__).parent / "models" / "anti_spoof"
# Bu qiymatdan past bo'lsa "jonli emas" deb rad etiladi (0..1).
LIVENESS_THRESHOLD = 0.85
# Yuz bbox kengligi (pikselda) shu qiymatdan kichik bo'lsa — identify/liveness
# bajarilmaydi, UI'da "Yaqinroq keling" holati ko'rsatiladi. 0 — chekloviz.
MIN_FACE_WIDTH_PX = 120

# Camera
DEFAULT_CAMERA_INDEX = 0
CAMERA_FPS = 30
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Sync
SYNC_RETRY_INTERVAL_SEC = 30
MAX_RETRY_ATTEMPTS = 5
