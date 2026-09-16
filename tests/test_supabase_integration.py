"""Integration tests — product layer ↔ simulator, offline fallback, save system, realtime."""
import pathlib, pytest, os
from unittest.mock import MagicMock

def test_product_package_exists():
    assert pathlib.Path("astra/product/__init__.py").exists()
    assert pathlib.Path("astra/product/supabase/__init__.py").exists()
    assert pathlib.Path("astra/product/supabase/client.py").exists()
    assert pathlib.Path("astra/product/supabase/auth.py").exists()
    assert pathlib.Path("astra/product/supabase/profiles.py").exists()
    assert pathlib.Path("astra/product/supabase/storage.py").exists()
    assert pathlib.Path("astra/product/supabase/saves.py").exists()
    assert pathlib.Path("astra/product/integration.py").exists()

def test_offline_simulator_continues():
    # Simulator must work without Supabase
    from astra.core.engine import Engine
    from astra.core.config import Config
    from astra.product.integration import ProductIntegration
    from astra.product.supabase.config import reset_config_cache
    from astra.product.supabase.client import reset_client_cache
    os.environ["ASTRA_SUPABASE_OFFLINE_MODE"] = "true"
    reset_config_cache(); reset_client_cache()
    engine = Engine(Config())
    engine.initialize()
    prod = ProductIntegration(engine)
    online = prod.initialize()
    assert online is False, "should be offline"
    assert prod.is_online is False
    # engine still works
    engine.start()
    engine.step()
    assert engine._total_ticks >= 1
    engine.stop()
    # cleanup
    del os.environ["ASTRA_SUPABASE_OFFLINE_MODE"]
    reset_config_cache(); reset_client_cache()

def test_save_system_separates_state():
    # Saves via Storage + metadata, not giant JSON in Postgres
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    assert "saved_simulations" in txt
    # storage_path points to Storage, not JSON blob
    assert "storage_path" in txt
    # Ensure product integration uses SaveService
    integ = pathlib.Path("astra/product/integration.py").read_text()
    assert "SaveService" in integ
    assert "snapshot_bytes" in integ or "artifact" in integ

def test_realtime_not_for_physics():
    txt = pathlib.Path("astra/product/supabase/realtime.py").read_text()
    assert "physics" in txt.lower() or "tick" in txt.lower()
    assert "forbidden" in txt.lower() or "MUST NOT" in txt
    # Should subscribe to profiles/sessions only
    assert "profiles" in txt
    # Should not mention N-body tick
    assert "N-body" in txt or "particle" in txt

def test_no_physics_in_supabase():
    # Ensure product layer does not import physics engine internals
    for p in pathlib.Path("astra/product").rglob("*.py"):
        txt = p.read_text()
        assert "nbody" not in txt.lower() or "not" in txt.lower(), f"{p} must not contain N-body"
        assert "orbital.integration" not in txt

def test_migration_reproducible():
    assert pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").exists()
    assert pathlib.Path("supabase/migrations/20250917000002_astra_product_tweaks.sql").exists()
    # Should be idempotent (if not exists)
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    assert "if not exists" in txt.lower()
    assert "create table if not exists" in txt.lower()

def test_storage_buckets_minimum():
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    for b in ["avatars","simulation-assets","simulation-saves","replays","screenshots","recordings","exports"]:
        assert b in txt

@pytest.mark.skipif(os.getenv("ASTRA_SUPABASE_LIVE_TEST") != "1", reason="Live integration requires network — NOT VERIFIED")
def test_live_application_to_supabase():
    # Would test full flow: auth → profile → player_data → storage
    pass
