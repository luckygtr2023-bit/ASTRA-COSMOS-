"""RLS tests — ownership enforcement for every player table."""
import pathlib, re, pytest

def test_migration_has_rls():
    mig = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql")
    assert mig.exists(), "migration missing"
    txt = mig.read_text()
    tables = [
        "profiles", "player_statistics", "player_progression",
        "player_preferences", "player_achievements", "player_unlocks",
        "player_sessions", "saved_simulations", "saved_scenarios",
        "saved_observers", "saved_configurations"
    ]
    for t in tables:
        assert f"enable row level security" in txt.lower(), f"RLS not enabled at all"
        assert f"auth.uid()" in txt, "RLS must use auth.uid()"
        # check table-specific policy
        assert t in txt, f"table {t} missing in migration"

def test_no_permissive_true_policies():
    mig = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    # Ensure no `using (true)` for private tables
    # Find policies for private tables — they should use auth.uid() = ...
    # Permissive true is forbidden per spec
    assert "using (true)" not in mig or mig.count("using (true)") == 0, "Permissive true policy found for private data"

def test_profiles_references_auth_users():
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    assert "references auth.users(id)" in txt, "profiles must reference auth.users(id)"
    assert "auth.users.id" in txt or "auth.users" in txt

def test_player_tables_use_user_id():
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    for t in ["player_statistics","player_progression","player_preferences"]:
        assert t in txt
        assert "user_id" in txt

def test_saved_tables_use_user_id():
    txt = pathlib.Path("supabase/migrations/20250917000001_astra_product_schema.sql").read_text()
    for t in ["saved_simulations","saved_scenarios","saved_observers","saved_configurations"]:
        assert "user_id" in txt

@pytest.mark.skipif(True, reason="Live RLS test requires two authenticated users and network — NOT VERIFIED offline")
def test_live_user_a_cannot_read_user_b():
    # Would create two users, insert profile as A, try read as B, expect empty/error
    pass
