"""PlayerDataService — generic CRUD for player_* tables, RLS auth.uid()=user_id."""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from .client import get_client

PLAYER_TABLES = [
    "player_statistics",
    "player_progression",
    "player_preferences",
    "player_achievements",
    "player_unlocks",
    "player_sessions",
]

class PlayerDataError(RuntimeError):
    pass

class PlayerDataService:
    def __init__(self):
        self.client = get_client()

    def _require(self):
        if not self.client.is_available:
            raise PlayerDataError("Supabase unavailable — local fallback")

    def get(self, table: str) -> Optional[Dict[str,Any]]:
        if table not in PLAYER_TABLES:
            raise PlayerDataError(f"unknown player table {table}")
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            if not uid:
                raise PlayerDataError("not authenticated")
            # player_statistics etc have PK user_id
            resp = self.client.native.table(table).select("*").eq("user_id", uid).single().execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise PlayerDataError(str(e)) from e

    def upsert(self, table: str, payload: Dict[str,Any]) -> Any:
        if table not in PLAYER_TABLES:
            raise PlayerDataError(f"unknown table {table}")
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            if not uid:
                raise PlayerDataError("not authenticated")
            payload = {**payload, "user_id": uid}
            resp = self.client.native.table(table).upsert(payload).execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise PlayerDataError(str(e)) from e

    def list_achievements(self) -> List[Dict[str,Any]]:
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            resp = self.client.native.table("player_achievements").select("*").eq("user_id", uid).execute()
            return getattr(resp, "data", []) or []
        except Exception as e:
            raise PlayerDataError(str(e)) from e

    def unlock_achievement(self, achievement_id: str, metadata: Optional[Dict[str,Any]]=None) -> Any:
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            if not uid:
                raise PlayerDataError("not authenticated")
            payload = {"user_id": uid, "achievement_id": achievement_id, "metadata": metadata or {}}
            resp = self.client.native.table("player_achievements").upsert(payload, on_conflict="user_id,achievement_id").execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise PlayerDataError(str(e)) from e
