import jwt
from datetime import datetime, timezone
from typing import Optional

from services.api_client import ApiClient
from database.db_manager import DatabaseManager


class AuthService:
    def __init__(self):
        self._api = ApiClient()
        self._db = DatabaseManager()
        self._current_staff: Optional[dict] = None

    @property
    def current_staff(self) -> Optional[dict]:
        return self._current_staff

    def login(self, username: str, password: str) -> dict:
        data = self._api.login(username, password)
        token = data.get("access_token") or data.get("token")
        payload = jwt.decode(token, options={"verify_signature": False})
        user = data.get("user") or {}
        staff_id = (
            user.get("id")
            or payload.get("staff_id")
            or payload.get("user_id")
            or payload.get("sub")
        )
        if staff_id is None:
            raise ValueError("Login javobidan staff ID aniqlab bo'lmadi")
        self._current_staff = {
            "id": int(staff_id),
            "username": user.get("username", username),
            "full_name": user.get("full_name", username),
            "zone_id": user.get("zone_id", 0),
            "zone_name": user.get("zone_name", ""),
        }
        self._db.upsert_staff(
            self._current_staff["id"],
            self._current_staff["username"],
            self._current_staff["full_name"],
            self._current_staff["zone_id"],
            self._current_staff["zone_name"],
        )
        return self._current_staff

    def is_token_valid(self) -> bool:
        token = self._api.token
        if not token:
            return False
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(tz=timezone.utc):
                return False
            return True
        except jwt.DecodeError:
            return False

    def logout(self):
        self._current_staff = None
