"""StorageService — secure Supabase Storage with <user_uuid>/... path enforcement.

All user-owned objects must live under <user_uuid>/... and RLS checks (storage.foldername(name))[1] = auth.uid()::text.
Never rely on client alone — RLS is mandatory server-side too (see migrations).
Client helper here enforces path locally before upload and refuses traversal.
"""
from __future__ import annotations
import re
from pathlib import PurePosixPath
from typing import Optional, List
from .client import get_client

ALLOWED_BUCKETS = ["avatars","simulation-assets","simulation-saves","replays","screenshots","recordings","exports"]
_PATH_TRAVERSAL_RE = re.compile(r"(\.\./|//)")

class StorageError(RuntimeError):
    pass

def _assert_safe_path(user_id: str, path: str) -> str:
    if _PATH_TRAVERSAL_RE.search(path):
        raise StorageError("path traversal detected")
    # must start with user_id/
    norm = str(PurePosixPath(path)).replace("\\","/")
    if not norm.startswith(f"{user_id}/"):
        raise StorageError(f"path must start with <user_uuid>/, got {norm}")
    if ".." in norm.split("/"):
        raise StorageError("relative path not allowed")
    return norm

class StorageService:
    def __init__(self):
        self.client = get_client()

    def _require(self):
        if not self.client.is_available:
            raise StorageError("Supabase unavailable — cannot use cloud storage offline")

    def _user_id(self) -> str:
        user = self.client.native.auth.get_user()
        uid = getattr(getattr(user, "user", user), "id", None) if user else None
        if not uid:
            raise StorageError("not authenticated")
        return str(uid)

    def upload(self, bucket: str, path: str, file_bytes: bytes, content_type: Optional[str]=None) -> str:
        if bucket not in ALLOWED_BUCKETS:
            raise StorageError(f"unknown bucket {bucket}")
        self._require()
        uid = self._user_id()
        safe = _assert_safe_path(uid, path)
        try:
            res = self.client.native.storage.from_(bucket).upload(safe, file_bytes, {"content-type": content_type} if content_type else {})
            return safe
        except Exception as e:
            raise StorageError(str(e)) from e

    def download(self, bucket: str, path: str) -> bytes:
        if bucket not in ALLOWED_BUCKETS:
            raise StorageError(f"unknown bucket {bucket}")
        self._require()
        uid = self._user_id()
        safe = _assert_safe_path(uid, path)
        try:
            data = self.client.native.storage.from_(bucket).download(safe)
            return data
        except Exception as e:
            raise StorageError(str(e)) from e

    def delete(self, bucket: str, paths: List[str]) -> None:
        if bucket not in ALLOWED_BUCKETS:
            raise StorageError(f"unknown bucket {bucket}")
        self._require()
        uid = self._user_id()
        safe_paths = [_assert_safe_path(uid, p) for p in paths]
        try:
            self.client.native.storage.from_(bucket).remove(safe_paths)
        except Exception as e:
            raise StorageError(str(e)) from e

    def list(self, bucket: str, prefix: str="") -> List[dict]:
        if bucket not in ALLOWED_BUCKETS:
            raise StorageError(f"unknown bucket {bucket}")
        self._require()
        uid = self._user_id()
        # enforce prefix is under user
        if prefix and not prefix.startswith(f"{uid}/"):
            raise StorageError("prefix must be under <user_uuid>/")
        try:
            # list under prefix
            res = self.client.native.storage.from_(bucket).list(prefix or f"{uid}/")
            return res
        except Exception as e:
            raise StorageError(str(e)) from e
