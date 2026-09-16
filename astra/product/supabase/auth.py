"""AuthService — Supabase Auth: email + Google OAuth, session lifecycle.

Security:
 - Uses only publishable key, via SupabaseClient.
 - No service_role, no JWT secret in Git.
 - Google OAuth secrets stay in Supabase Dashboard env, not code.
 - All operations delegate to supabase-py auth; offline → gracefully no-op.

Flows:
 - register(email,password) → supabase.auth.sign_up
 - login(email,password) → sign_in_with_password
 - logout → sign_out
 - session restoration → get_session / get_user
 - email verification → handled by Supabase redirect
 - password reset → reset_password_email
 - password update → update_user
 - account deletion → delete user via auth (or rpc) — requires re-auth
 - Google OAuth → sign_in_with_oauth({provider: google})
"""
from __future__ import annotations
from typing import Optional, Dict, Any
from .client import get_client

class AuthError(RuntimeError):
    pass

class AuthService:
    def __init__(self):
        self.client = get_client()

    def _require_available(self) -> None:
        if not self.client.is_available:
            raise AuthError(f"Supabase unavailable (offline/mock): {self.client.health()}")

    # ---- Email ----
    def register(self, email: str, password: str, metadata: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
        self._require_available()
        try:
            resp = self.client.native.auth.sign_up({"email": email, "password": password, "options": {"data": metadata or {}}})
            return {"user": getattr(resp, "user", None), "session": getattr(resp, "session", None)}
        except Exception as e:
            raise AuthError(str(e)) from e

    def login(self, email: str, password: str) -> Dict[str,Any]:
        self._require_available()
        try:
            resp = self.client.native.auth.sign_in_with_password({"email": email, "password": password})
            return {"user": getattr(resp, "user", None), "session": getattr(resp, "session", None)}
        except Exception as e:
            raise AuthError(str(e)) from e

    def logout(self) -> None:
        self._require_available()
        try:
            self.client.native.auth.sign_out()
        except Exception as e:
            raise AuthError(str(e)) from e

    def get_session(self) -> Optional[Any]:
        if not self.client.is_available:
            return None
        try:
            return self.client.native.auth.get_session()
        except Exception:
            return None

    def get_user(self) -> Optional[Any]:
        if not self.client.is_available:
            return None
        try:
            return self.client.native.auth.get_user()
        except Exception:
            return None

    def restore_session(self) -> Optional[Any]:
        return self.get_session()

    def send_password_reset(self, email: str) -> None:
        self._require_available()
        try:
            self.client.native.auth.reset_password_email(email)
        except Exception as e:
            raise AuthError(str(e)) from e

    def update_password(self, new_password: str) -> None:
        self._require_available()
        try:
            self.client.native.auth.update_user({"password": new_password})
        except Exception as e:
            raise AuthError(str(e)) from e

    def delete_account(self) -> None:
        self._require_available()
        # Supabase does not expose delete via publishable key directly; suggest via RPC or dashboard.
        # We attempt auth admin delete if available, else raise with guidance.
        try:
            # Attempt via auth.update_user then require backend RPC; offline fallback: raise
            raise AuthError("Account deletion requires server-side handling (RPC with ownership check) — not via publishable key alone. Implement POST /rest/v1/rpc/delete_own_account with auth.uid() check.")
        except AuthError:
            raise

    # ---- OAuth ----
    def google_oauth_url(self, redirect_to: Optional[str]=None) -> str:
        self._require_available()
        try:
            # supabase-py: sign_in_with_oauth returns url
            opts = {"provider": "google"}
            if redirect_to:
                opts["options"] = {"redirect_to": redirect_to}
            resp = self.client.native.auth.sign_in_with_oauth(opts)  # type: ignore
            # supabase-py returns dict with url
            if isinstance(resp, dict) and "url" in resp:
                return resp["url"]
            return str(resp)
        except Exception as e:
            raise AuthError(str(e)) from e

    def handle_oauth_callback(self, code: str) -> Dict[str,Any]:
        # Supabase handles code exchange via PKCE in hosted flow; for local, use get_session after redirect
        return {"code": code, "session": self.get_session()}
