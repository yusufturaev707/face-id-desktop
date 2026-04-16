import asyncio
import base64
import queue


def _b64_to_bytes(val) -> bytes | None:
    """base64 (data URL yoki sof) → bytes. Bytes bo'lsa o'zini qaytaradi."""
    if not val:
        return None
    if isinstance(val, (bytes, bytearray, memoryview)):
        return bytes(val)
    if not isinstance(val, str):
        return None
    try:
        if "," in val and val.index(",") < 80:
            val = val.split(",", 1)[1]
        return base64.b64decode(val)
    except Exception:
        return None

from PyQt6.QtCore import QThread, pyqtSignal

from config import SYNC_RETRY_INTERVAL_SEC
from database.db_manager import DatabaseManager
from services.api_client import ApiClient


class SyncService(QThread):
    sync_status = pyqtSignal(str)     # status message
    sync_progress = pyqtSignal(int, int)  # (sent_count, total_count)

    def __init__(self, parent=None, one_shot: bool = False):
        super().__init__(parent)
        self._running = False
        self._one_shot = one_shot
        self._db = DatabaseManager()
        self._api = ApiClient()

    def run(self):
        self._running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if self._one_shot:
            try:
                loop.run_until_complete(self._sync_pending())
            except Exception as e:
                self.sync_status.emit(f"Sync xatosi: {e}")
            loop.close()
            self._running = False
            return

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

    BATCH_SIZE = 20

    @staticmethod
    def _blob_to_b64(val) -> str | None:
        if not val:
            return None
        if isinstance(val, (bytes, bytearray, memoryview)):
            return base64.b64encode(bytes(val)).decode("ascii")
        return None

    @staticmethod
    def _build_item(entry) -> dict:
        return {
            "client_entry_id": entry["id"],
            "student_id": entry["student_id"],
            "first_captured": SyncService._blob_to_b64(entry["first_captured"]),
            "last_captured": SyncService._blob_to_b64(entry["last_captured"]),
            "first_enter_time": entry["first_enter_time"],
            "last_enter_time": entry["last_enter_time"],
            "score": entry["score"],
            "max_score": entry["max_score"],
            "is_check_hand": bool(entry["is_check_hand"]),
            "ip_address": entry["ip_address"],
            "mac_address": entry["mac_address"],
            "is_rejected": bool(entry["is_rejected"]) if "is_rejected" in entry.keys() else False,
            "reject_reason_id": entry["reject_reason_id"] if "reject_reason_id" in entry.keys() else None,
            "imei": entry["imei"] if "imei" in entry.keys() else None,
        }

    async def _sync_pending(self):
        unsent = self._db.get_unsent_entries(limit=self.BATCH_SIZE * 5)
        if not unsent:
            return

        total = len(unsent)
        succeeded = 0
        failed = 0
        self.sync_status.emit(f"{total} ta yuborilmagan yozuv topildi...")
        self.sync_progress.emit(0, total)

        for start in range(0, total, self.BATCH_SIZE):
            if not self._running:
                break
            batch = unsent[start:start + self.BATCH_SIZE]
            batch_ids = [e["id"] for e in batch]

            try:
                items = [SyncService._build_item(e) for e in batch]
                resp = await self._api.submit_entries_bulk_async(items)
            except Exception as e:
                self._db.increment_retry_bulk(batch_ids)
                failed += len(batch)
                self.sync_status.emit(f"Tarmoq xatosi: {e}")
                self.sync_progress.emit(succeeded, total)
                continue

            succeeded_ids: list[int] = []
            failed_ids: list[int] = []
            for result in resp.get("items", []):
                cid = result.get("client_entry_id")
                if cid is None:
                    continue
                if result.get("status") == "ok":
                    succeeded_ids.append(cid)
                else:
                    failed_ids.append(cid)

            if succeeded_ids:
                self._db.mark_entries_sent(succeeded_ids)

            if failed_ids:
                self._db.increment_retry_bulk(failed_ids)

            succeeded += len(succeeded_ids)
            failed += len(failed_ids)
            self.sync_progress.emit(succeeded, total)

        if succeeded == total:
            self.sync_status.emit(f"{succeeded} ta yozuv muvaffaqiyatli yuborildi")
        elif succeeded > 0:
            self.sync_status.emit(f"{succeeded}/{total} yuborildi, {failed} xato")
        else:
            self.sync_status.emit(f"Hech qanday yozuv yuborilmadi ({failed} xato)")

    def stop(self):
        self._running = False
        self.wait(5000)


class OnlineSubmitWorker(QThread):
    """Online rejimda entry_log yozuvlarini ketma-ket backend'ga yuboradi.

    Logika:
      - Asosiy navbat (queue) — yangi aniqlangan studentlar kelib turadi.
      - Har bir yozuv birma-bir yuboriladi: status=ok bo'lgandan keyingina
        keyingi yozuvga o'tiladi.
      - Xatolik bo'lgan yozuvlar retry_queue'ga yig'iladi.
      - Asosiy navbat bo'shaganda, retry_queue'dagi xatoliklar qayta yuboriladi.
      - Har bir yozuv uchun MAX_ATTEMPTS marta urinib ko'riladi; undan keyin
        is_sent=0 holida qoldiriladi (Yuborish tugmasi yoki keyingi sessiyada
        yuboriladi).
    """

    MAX_ATTEMPTS = 3
    RETRY_BACKOFF_MS = 2000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: "queue.Queue[int]" = queue.Queue()
        self._retry_queue: list[int] = []
        self._attempts: dict[int, int] = {}
        self._running = False
        self._db = DatabaseManager()
        self._api = ApiClient()

    def enqueue(self, entry_id: int):
        self._queue.put(entry_id)

    def run(self):
        self._running = True
        while self._running:
            entry_id = self._next_entry_id()
            if entry_id is None:
                self.msleep(200)
                continue

            ok = self._submit_one(entry_id)
            if ok:
                self._attempts.pop(entry_id, None)
            else:
                attempts = self._attempts.get(entry_id, 0) + 1
                self._attempts[entry_id] = attempts
                if attempts < self.MAX_ATTEMPTS:
                    # Xato — retry navbatiga. Asosiy navbat bo'shagandan keyin
                    # qayta urinamiz.
                    self._retry_queue.append(entry_id)
                    self.msleep(self.RETRY_BACKOFF_MS)
                else:
                    # Urinishlar tugadi — is_sent=0 holida qoldiriladi.
                    self._attempts.pop(entry_id, None)

    def _next_entry_id(self) -> int | None:
        """Avval asosiy navbatdan olamiz; u bo'sh bo'lsa — retry navbatidan."""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            pass
        if self._retry_queue:
            return self._retry_queue.pop(0)
        return None

    def _submit_one(self, entry_id: int) -> bool:
        try:
            row = self._db.get_entry_by_id(entry_id)
            if not row:
                return True
            item = SyncService._build_item(row)
            resp = self._api.submit_entry(item)
            for result in (resp or {}).get("items", []):
                if result.get("client_entry_id") == entry_id:
                    if result.get("status") == "ok":
                        self._db.mark_entry_sent(entry_id)
                        return True
                    return False
            return False
        except Exception:
            try:
                self._db.increment_retry(entry_id)
            except Exception:
                pass
            return False

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
            self.progress.emit(0, 4)

            # Step 0: Sinxronlash — reason_type va reason lookup jadvallari
            try:
                rtypes = self._api.get_reason_types() or []
                self._db.upsert_reason_types(rtypes)
                reasons = self._api.get_reasons() or []
                self._db.upsert_reasons(reasons)
            except Exception:
                # lookup sinxronlash sessiya yuklashni to'sib qo'ymasin
                pass

            # Step 1: Fetch students from API
            self.progress.emit(1, 4)
            students_raw = self._api.get_students_by_session(self._session_id)

            # Step 2: Transform and store
            self.progress.emit(2, 4)
            smenas = self._db.get_smenas_by_session(self._session_id)
            default_sm_id = smenas[0]["id"] if smenas else 0

            students = []
            skipped_names = []
            for s in students_raw:
                ps_data = s.get("ps_data") or {}

                # Embedding: backend endi base64-encoded float32 bytes yuboradi
                embedding_bytes = _b64_to_bytes(ps_data.get("embedding"))
                # 512-dim float32 = 2048 bayt
                if not embedding_bytes or len(embedding_bytes) != 2048:
                    embedding_bytes = None

                # ps_img: backend endi base64-encoded raw image bytes yuboradi
                ps_img_bytes = _b64_to_bytes(ps_data.get("ps_img"))

                missing = []
                if not embedding_bytes:
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
                    # API dan kelgan id → student.student_id ustuniga yoziladi
                    "student_id": s["id"],
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
                    "ps_img": ps_img_bytes,
                    "embedding": embedding_bytes,
                })

            if students:
                self._db.bulk_upsert_students(students)

            self.progress.emit(4, 4)

            if skipped_names:
                err_msg = f"{len(skipped_names)} ta student yuklanmadi:\n"
                err_msg += "\n".join(skipped_names[:20])
                if len(skipped_names) > 20:
                    err_msg += f"\n... va yana {len(skipped_names) - 20} ta"
                self.error.emit(err_msg)

            if students:
                self._db.mark_session_loaded(self._session_id)

            self.finished_ok.emit(len(students), len(skipped_names))
        except Exception as e:
            self.error.emit(str(e))
