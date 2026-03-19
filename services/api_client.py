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

    # ── Entry submission ──
    def submit_entry(self, entry_data: dict) -> dict:
        resp = self._client.post("/entries", json=entry_data, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def submit_entry_async(self, entry_data: dict) -> dict:
        resp = await self._async_client.post("/entries", json=entry_data, headers=self._headers())
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
