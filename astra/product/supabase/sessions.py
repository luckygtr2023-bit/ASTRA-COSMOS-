"""SessionService — player_sessions metadata, NOT passwords."""
from __future__ import annotations
from typing import Optional, Dict, Any
from .client import get_client

class SessionService:
    def __init__(self):
        self.client = get_client()

    def _require(self):
        if not self.client.is_available:
            raise RuntimeError("Supabase unavailable — sessions local only")

    def start_session(self, device_info: Optional[Dict[str,Any]]=None, metadata: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        if not uid:
            raise RuntimeError("not authenticated")
        payload = {"user_id": str(uid), "device_info": device_info or {}, "metadata": metadata or {}}
        resp = self.client.native.table("player_sessions").insert(payload).execute()
        data = getattr(resp, "data", None)
        return data[0] if isinstance(data, list) else data

    def end_session(self, session_id: str) -> None:
        self._require()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.client.native.table("player_sessions").update({"ended_at": now}).eq("id", session_id).execute()
