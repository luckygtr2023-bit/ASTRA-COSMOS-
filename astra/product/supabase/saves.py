"""SaveService — separates scientific state from cloud persistence metadata.

ASTRA Simulation
  ├── scientific state (local Snapshot, NOT in Postgres)
  ├── observer state
  ├── config
  └── save artifact → Supabase Storage (simulation-saves/<user_uuid>/...)
            ↓
        saved_simulations metadata row (Postgres)

Postgres never gets giant universe JSON blobs.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from .client import get_client
from .storage import StorageService

class SaveError(RuntimeError):
    pass

class SaveService:
    def __init__(self):
        self.client = get_client()
        self.storage = StorageService()

    def _require(self):
        if not self.client.is_available:
            raise SaveError("Supabase unavailable — local snapshots only")

    def create_simulation_save(self, name: str, description: Optional[str]=None,
                               artifact_bytes: Optional[bytes]=None,
                               simulation_version: Optional[str]=None,
                               engine_version: Optional[str]=None,
                               schema_version: Optional[str]=None,
                               metadata: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        if not uid:
            raise SaveError("not authenticated")
        storage_path = None
        if artifact_bytes is not None:
            # upload artifact to storage
            path = f"{uid}/{name.strip().replace(' ','_')}.astra_save"
            storage_path = self.storage.upload("simulation-saves", path, artifact_bytes, content_type="application/octet-stream")
        payload = {
            "user_id": str(uid),
            "name": name,
            "description": description,
            "storage_path": storage_path,
            "simulation_version": simulation_version,
            "engine_version": engine_version,
            "schema_version": schema_version,
            "metadata": metadata or {}
        }
        try:
            resp = self.client.native.table("saved_simulations").insert(payload).execute()
            data = getattr(resp, "data", None)
            return data[0] if isinstance(data, list) and data else data
        except Exception as e:
            raise SaveError(str(e)) from e

    def list_simulation_saves(self) -> List[Dict[str,Any]]:
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        try:
            resp = self.client.native.table("saved_simulations").select("*").eq("user_id", str(uid)).order("created_at", desc=True).execute()
            return getattr(resp, "data", []) or []
        except Exception as e:
            raise SaveError(str(e)) from e

    def get_save(self, save_id: str) -> Optional[Dict[str,Any]]:
        self._require()
        try:
            resp = self.client.native.table("saved_simulations").select("*").eq("id", save_id).single().execute()
            return getattr(resp, "data", None)
        except Exception as e:
            raise SaveError(str(e)) from e

    # scenarios / observers / configurations — similar metadata-only
    def create_scenario(self, name: str, metadata: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        payload = {"user_id": str(uid), "name": name, "metadata": metadata or {}}
        resp = self.client.native.table("saved_scenarios").insert(payload).execute()
        data = getattr(resp, "data", None)
        return data[0] if isinstance(data, list) else data

    def create_observer(self, name: str, observer_config: Dict[str,Any], metadata: Optional[Dict[str,Any]]=None):
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        payload = {"user_id": str(uid), "name": name, "observer_config": observer_config, "metadata": metadata or {}}
        resp = self.client.native.table("saved_observers").insert(payload).execute()
        data = getattr(resp, "data", None)
        return data[0] if isinstance(data, list) else data

    def create_configuration(self, name: str, config: Dict[str,Any], metadata: Optional[Dict[str,Any]]=None):
        self._require()
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        payload = {"user_id": str(uid), "name": name, "config": config, "metadata": metadata or {}}
        resp = self.client.native.table("saved_configurations").insert(payload).execute()
        data = getattr(resp, "data", None)
        return data[0] if isinstance(data, list) else data
