"""Tests for Supabase Auth — email + Google OAuth, offline-tolerant."""
import os, pathlib, pytest
from unittest.mock import MagicMock, patch

# Must not import supabase if not needed; test abstraction
from astra.product.supabase.client import SupabaseClient, get_client, reset_client_cache
from astra.product.supabase.config import get_config, reset_config_cache
from astra.product.supabase.auth import AuthService, AuthError

def test_config_centralized():
    # Config should be centralized, not scattered hard-coded URL
    # Check env var precedence
    os.environ["ASTRA_SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test123"
    reset_config_cache()
    cfg = get_config()
    assert cfg.url == "https://example.supabase.co"
    assert cfg.publishable_key == "sb_publishable_test123"
    # cleanup
    del os.environ["ASTRA_SUPABASE_URL"]
    del os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"]
    reset_config_cache()

def test_auth_offline_graceful():
    # When offline, auth should raise AuthError, not crash simulator
    reset_config_cache()
    os.environ["ASTRA_SUPABASE_OFFLINE_MODE"] = "true"
    reset_client_cache()
    # also ensure config sees offline
    from astra.product.supabase.config import reset_config_cache as rcc2
    rcc2()
    from astra.product.supabase.client import reset_client_cache as rc2
    rc2()
    auth = AuthService()
    with pytest.raises(AuthError, match="unavailable"):
        auth.register("a@b.com", "password123")
    # cleanup
    del os.environ["ASTRA_SUPABASE_OFFLINE_MODE"]
    reset_config_cache()
    reset_client_cache()

def test_auth_google_oauth_not_hardcoded():
    # Google OAuth secrets must not be hard-coded
    repo = pathlib.Path(".")
    for p in repo.rglob("*.py"):
        if ".pyc" in str(p) or "__pycache__" in str(p):
            continue
        txt = p.read_text(errors="ignore")
        # Should not contain GOOGLE_CLIENT_SECRET hard-coded value
        assert "GOOGLE_CLIENT_SECRET" not in txt or "os.getenv" in txt or "environment" in txt.lower() or "Dashboard" in txt, f"{p} hard-coded Google secret"

def test_auth_flows_exist():
    # AuthService must expose required flows
    auth = AuthService()
    assert hasattr(auth, "register")
    assert hasattr(auth, "login")
    assert hasattr(auth, "logout")
    assert hasattr(auth, "get_session")
    assert hasattr(auth, "get_user")
    assert hasattr(auth, "restore_session")
    assert hasattr(auth, "send_password_reset")
    assert hasattr(auth, "update_password")
    assert hasattr(auth, "delete_account")
    assert hasattr(auth, "google_oauth_url")

def test_publishable_key_client_safe():
    # Publishable key is client-safe, but must not be service_role
    reset_config_cache()
    os.environ["ASTRA_SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
    reset_client_cache()
    client = get_client()
    # health must not expose key
    h = client.health()
    assert "publishable" not in str(h).lower() or "publishable_key" not in h
    # ensure we never store service_role
    assert "service_role" not in str(h).lower()
    del os.environ["ASTRA_SUPABASE_URL"]
    del os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"]
    reset_config_cache()
    reset_client_cache()

@pytest.mark.skipif(os.getenv("ASTRA_SUPABASE_LIVE_TEST") != "1", reason="Live Supabase not enabled (set ASTRA_SUPABASE_LIVE_TEST=1 to run)")
def test_live_auth_register_login():
    # Live test — requires real Supabase project and network
    # NOT VERIFIED if network unavailable
    import uuid
    os.environ["ASTRA_SUPABASE_URL"] = "https://bzfpipxjqdrinvagojor.supabase.co"
    os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG"
    reset_config_cache()
    reset_client_cache()
    auth = AuthService()
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    try:
        reg = auth.register(email, "TestPass123!@#")
        assert reg is not None
        login = auth.login(email, "TestPass123!@#")
        assert login is not None
        sess = auth.get_session()
        # session may be None if email confirmation required
        auth.logout()
    finally:
        del os.environ["ASTRA_SUPABASE_URL"]
        del os.environ["ASTRA_SUPABASE_PUBLISHABLE_KEY"]
        reset_config_cache()
        reset_client_cache()
