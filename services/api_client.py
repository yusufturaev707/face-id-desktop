import httpx
from typing import Optional

from config import API_BASE_URL
from utils.singleton import SingletonMeta


class ApiClient(metaclass=SingletonMeta):
    def __init__(self):
        self._token: Optional[str] = None
        self._client = httpx.Client(base_url=API_BASE_URL, timeout=30.0)
        self._async_client = httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)

    @property
    def token(self) -> Optional[str]:
        return self._token

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    # ── Auth ──
    def login(self, username: str, password: str) -> dict:
        resp = self._client.post(
            "/auth/login",
            data={"username": username, "password": password},
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data.get("access_token") or data.get("token")
        return data

    # ── Sessions ──
    def get_active_sessions(self) -> list[dict]:
        resp = self._client.get("/test-sessions/active", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ── Students ──
    def get_students_by_session(self, session_id: int) -> list[dict]:
        resp = self._client.get(f"/test-sessions/{session_id}/students", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_smena_attendance_stats(self, smena_id: int) -> dict:
        """Serverdan smena + bino kesimida davomat statistikasini olish.

        Qaytaradi: {total, entered, not_entered, cheating}.
        """
        resp = self._client.get(
            f"/test-sessions/smenas/{smena_id}/attendance-stats",
            headers=self._headers(),
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Lookup: reasons ──
    def get_reason_types(self) -> list[dict]:
        resp = self._client.get("/lookup/reason-types", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    def get_reasons(self) -> list[dict]:
        resp = self._client.get("/lookup/reasons", headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    # ── Entry submission ──
    def submit_entry(self, entry_data: dict) -> dict:
        """Legacy: bitta entry yuborish — bulk endpointga wrap qilingan."""
        resp = self._client.post(
            "/students/logs/bulk",
            json={"items": [entry_data]},
            headers=self._headers(),
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()

    async def submit_entries_bulk_async(self, items: list[dict]) -> dict:
        """Batch verify-log yuborish. Server har bir item uchun alohida natija qaytaradi."""
        resp = await self._async_client.post(
            "/students/logs/bulk",
            json={"items": items},
            headers=self._headers(),
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Connection check ──
    def is_online(self) -> bool:
        try:
            resp = self._client.get("/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def close(self):
        self._client.close()
