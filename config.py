import os
from pathlib import Path

APP_NAME = "Face-ID Desktop"
APP_VERSION = "1.0.0"

# API Configuration
API_BASE_URL = os.getenv("FACEID_API_URL") or "http://localhost:8000/api/v1"

# Database
APP_DATA_DIR = Path(os.getenv("APPDATA", Path.home())) / "FaceIDDesktop"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = APP_DATA_DIR / "faceid.db"

# InsightFace
FACE_MODEL_NAME = "buffalo_l"
FACE_DET_SIZE = (320, 320)
FACE_DET_THRESH=0.3

# Recognition thresholds
COSINE_SIMILARITY_THRESHOLD = 0.5

# Camera
DEFAULT_CAMERA_INDEX = 0
CAMERA_FPS = 30
FRAME_WIDTH = 640
FRAME_HEIGHT = 480

# Sync
SYNC_RETRY_INTERVAL_SEC = 30
MAX_RETRY_ATTEMPTS = 5
