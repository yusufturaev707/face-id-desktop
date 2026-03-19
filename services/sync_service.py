import asyncio
import json
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal

from config import SYNC_RETRY_INTERVAL_SEC, MAX_RETRY_ATTEMPTS
from database.db_manager import DatabaseManager
from services.api_client import ApiClient


class SyncService(QThread):
    sync_success = pyqtSignal(int)    # entry_id
    sync_failed = pyqtSignal(int, str)  # entry_id, error
    sync_status = pyqtSignal(str)     # status message

    def __init__(self, parent=None):
        super().__init__(parent)
        self._running = False
        self._db = DatabaseManager()
        self._api = ApiClient()

    def run(self):
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                loop.run_until_complete(self._sync_pending())
            except Exception as e:
                self.sync_status.emit(f"Sync xatosi: {e}")

            # Sleep in small intervals so we can stop quickly
            for _ in range(int(SYNC_RETRY_INTERVAL_SEC)):
                if not self._running:
                    break
                self.msleep(1000)

        loop.close()

    async def _sync_pending(self):
        unsent = self._db.get_unsent_entries()
        if not unsent:
            return

        self.sync_status.emit(f"{len(unsent)} ta yuborilmagan yozuv topildi...")

        for entry in unsent:
            if not self._running:
                break
            if entry["retry_count"] >= MAX_RETRY_ATTEMPTS:
                continue

            try:
                entry_data = {
                    "student_id": entry["student_id"],
                    "staff_id": entry["staff_id"],
                    "first_enter_time": entry["first_enter_time"],
                    "last_enter_time": entry["last_enter_time"],
                    "score": entry["score"],
                    "max_score": entry["max_score"],
                    "ip_address": entry["ip_address"],
                    "mac_address": entry["mac_address"],
                }
                await self._api.submit_entry_async(entry_data)
                self._db.mark_entry_sent(entry["id"])
                self.sync_success.emit(entry["id"])
            except Exception as e:
                self._db.increment_retry(entry["id"])
                self.sync_failed.emit(entry["id"], str(e))

    def stop(self):
        self._running = False
        self.wait(5000)


class DataDownloader(QThread):
    """Downloads students from API to local SQLite."""
    progress = pyqtSignal(int, int)  # current, total
    finished_ok = pyqtSignal(int, int)  # (loaded, skipped)
    error = pyqtSignal(str)

    def __init__(self, session_id: int, parent=None):
        super().__init__(parent)
        self._session_id = session_id
        self._api = ApiClient()
        self._db = DatabaseManager()

    def run(self):
        try:
            self.progress.emit(0, 3)

            # Step 1: Fetch students from API
            self.progress.emit(1, 3)
            students_raw = self._api.get_students_by_session(self._session_id)

            # Step 2: Transform and store
            self.progress.emit(2, 3)
            # Get smenas for this session to find session_sm_id
            smenas = self._db.get_smenas_by_session(self._session_id)
            default_sm_id = smenas[0]["id"] if smenas else 0

            students = []
            skipped_names = []
            for s in students_raw:
                ps_data = s.get("ps_data") or {}
                embedding = ps_data.get("embedding")

                # Embedding string bo'lsa, list ga parse qilish
                if isinstance(embedding, str):
                    try:
                        embedding = json.loads(embedding)
                    except (json.JSONDecodeError, ValueError):
                        embedding = None

                # Majburiy maydonlarni tekshirish
                missing = []
                if not embedding or not isinstance(embedding, list):
                    missing.append("embedding")
                if not s.get("last_name"):
                    missing.append("last_name")
                if not s.get("first_name"):
                    missing.append("first_name")
                if not s.get("imei"):
                    missing.append("imei")

                if missing:
                    name = f"{s.get('last_name', '?')} {s.get('first_name', '?')}"
                    skipped_names.append(f"{name} (kamchilik: {', '.join(missing)})")
                    continue

                students.append({
                    "id": s["id"],
                    "session_sm_id": s.get("session_smena_id") or default_sm_id,
                    "zone_id": s.get("zone_id") or 0,
                    "last_name": s["last_name"],
                    "first_name": s["first_name"],
                    "middle_name": s.get("middle_name") or "",
                    "imei": s["imei"],
                    "gr_n": int(s.get("gr_n")) or 0,
                    "sp_n": int(s.get("sp_n")) or 0,
                    "gender": ps_data.get("gender_id") or 0,
                    "subject_id": s.get("subject_id") or 0,
                    "subject_name": s.get("subject_name") or "",
                    "is_ready": 1 if s.get("is_ready") else 0,
                    "is_face": 1 if s.get("is_face") else 0,
                    "is_image": 1 if s.get("is_image") else 0,
                    "is_cheating": 1 if s.get("is_cheating") else 0,
                    "is_blacklist": 1 if s.get("is_blacklist") else 0,
                    "is_entered": 1 if s.get("is_entered") else 0,
                    "ps_img": ps_data.get("ps_img") or "",
                    "embedding": json.dumps(embedding),
                })

            if students:
                self._db.bulk_upsert_students(students)

            self.progress.emit(3, 3)

            if skipped_names:
                err_msg = f"{len(skipped_names)} ta student yuklanmadi:\n"
                err_msg += "\n".join(skipped_names[:20])
                if len(skipped_names) > 20:
                    err_msg += f"\n... va yana {len(skipped_names) - 20} ta"
                self.error.emit(err_msg)

            self.finished_ok.emit(len(students), len(skipped_names))
        except Exception as e:
            self.error.emit(str(e))
