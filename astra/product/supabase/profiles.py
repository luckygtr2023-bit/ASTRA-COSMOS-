"""ProfileService — CRUD for public.profiles, RLS auth.uid()=id."""
from __future__ import annotations
from typing import Optional, Dict, Any
from .client import get_client

class ProfileError(RuntimeError):
    pass

class ProfileService:
    def __init__(self):
        self.client = get_client()

    def _require(self):
        if not self.client.is_available:
            raise ProfileError("Supabase unavailable — offline profile cache only")

    def get_own_profile(self) -> Optional[Dict[str,Any]]:
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            if not uid:
                return None
            resp = self.client.native.table("profiles").select("*").eq("id", uid).single().execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise ProfileError(str(e)) from e

    def upsert_own_profile(self, username: Optional[str]=None, display_name: Optional[str]=None, avatar_path: Optional[str]=None) -> Dict[str,Any]:
        self._require()
        try:
            user = self.client.native.auth.get_user()
            uid = getattr(getattr(user, "user", user), "id", None) if user else None
            if not uid:
                raise ProfileError("not authenticated")
            payload: Dict[str,Any] = {"id": uid}
            if username is not None: payload["username"] = username
            if display_name is not None: payload["display_name"] = display_name
            if avatar_path is not None: payload["avatar_path"] = avatar_path
            resp = self.client.native.table("profiles").upsert(payload).execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise ProfileError(str(e)) from e
