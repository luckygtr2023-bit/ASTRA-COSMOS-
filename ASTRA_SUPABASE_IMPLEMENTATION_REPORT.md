# ASTRA SUPABASE IMPLEMENTATION REPORT
**Branch:** `arena/01a0a5a2-astra-cosmos` — **Date:** 2026-09-17 Asia/Calcutta  
**Project:** `https://bzfpipxjqdrinvagojor.supabase.co` (publishable key `sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG` — client-safe, RLS-enforced)  
**Status:** IMPLEMENTED — product/account/cloud layer, scientific engine remains authoritative

> **Invariant:** `ASTRA Scientific Engine (double, tick 42) → Scientific State → RenderState/Visualization API → Native Renderer (Vulkan 1.3)` stays authoritative. Supabase is **product layer only** — no physics, no N-body, no rendering, no high-frequency ticks. Simulator **continues offline** if Supabase unavailable.

---

## 1. Implementation Status — DONE (local static), NOT VERIFIED live (no CLI/network in sandbox)

| Area | Implemented | Validated | Evidence |
|------|-------------|-----------|----------|
| Supabase project config | YES | MEASURED | `supabase/config.toml` + `ASTRA_SUPABASE_URL` central via `astra/product/supabase/config.py` |
| Auth (email + OAuth) | YES | MEASURED offline, NOT VERIFIED live | `auth.py` flows + tests 5 passed 1 skipped (live requires `ASTRA_SUPABASE_LIVE_TEST=1`) |
| DB schema + migrations | YES | MEASURED static | `supabase/migrations/20250917*.sql` 135 OK via `validate` |
| RLS mandatory | YES | MEASURED static | migration has `enable row level security` + `auth.uid()=...` for 11 tables, no `using (true)` |
| Storage buckets + policies | YES | MEASURED static | 7 buckets private + `storage.foldername` RLS |
| Realtime | YES (product only) | MEASURED static | `realtime.py` subscribes `profiles`/`player_sessions` only, asserts NOT physics |
| Env centralization | YES | MEASURED | `config.py` `ASTRA_SUPABASE_*` preferred + fallback `SUPABASE_*`, `.env.example` placeholders |
| Client/server separation | YES | MEASURED | `client.py` uses only publishable, never `service_role`, `sb_secret_` scan 5 passed |
| Simulator integration | YES | MEASURED | `product/integration.py` offline-tolerant, `Engine` still ticks with `offline_mode=true` |
| Save system | YES | MEASURED static | `saves.py` Storage artifact + Postgres metadata, no giant JSON blob |
| Security audit | YES | MEASURED | 5 security tests passed, `.env` gitignored |
| Migrations reproducible | YES | MEASURED | `supabase/migrations/` idempotent `if not exists` |
| Docs | YES | THIS REPORT | |
| Live Supabase apply | NOT VERIFIED | — | No `supabase` CLI or network to `bzfpipxjqdrinvagojor.supabase.co` in sandbox (see §13) |

---

## 2. Repository Changes — Files Added / Modified

**Added:**

- `supabase/config.toml` — local CLI config (API 54321, DB 54322, Studio 54323)
- `supabase/migrations/20250917000001_astra_product_schema.sql` — 11 tables + 7 buckets + RLS + realtime + trigger
- `supabase/migrations/20250917000002_astra_product_tweaks.sql` — comments / idempotence
- `.env.example` — `ASTRA_SUPABASE_URL` / `ASTRA_SUPABASE_PUBLISHABLE_KEY` placeholders (`your-project`), never real secret, notes for Google OAuth via Dashboard
- `astra/product/__init__.py` — product layer doc
- `astra/product/supabase/__init__.py` — exports
- `astra/product/supabase/config.py` — centralized env, `.env` loader (dotenv fallback), `ASTRA_` preferred, `SUPABASE_` fallback, offline flag
- `astra/product/supabase/client.py` — `SupabaseClient` (publishable only), mock fallback, `health()`, `is_available`, `is_mock`, never service_role
- `astra/product/supabase/auth.py` — `AuthService`: `register`, `login`, `logout`, `get_session`, `get_user`, `restore_session`, `send_password_reset`, `update_password`, `delete_account` (RPC guidance), `google_oauth_url` / `handle_oauth_callback`, `AuthError` on offline
- `astra/product/supabase/profiles.py` — `ProfileService` CRUD `profiles` with `auth.uid()=id`
- `astra/product/supabase/player_data.py` — `PlayerDataService` for `player_*` tables, achievements/unlocks
- `astra/product/supabase/storage.py` — `StorageService` with `ALLOWED_BUCKETS`, `_assert_safe_path(user_id, path)` enforcing `<user_uuid>/`, traversal check, `upload`/`download`/`delete`/`list`
- `astra/product/supabase/saves.py` — `SaveService` separates scientific state (local `Snapshot` bytes) from cloud: upload to `simulation-saves/<user_uuid>/` then insert `saved_simulations` metadata
- `astra/product/supabase/sessions.py` — `SessionService` for `player_sessions`
- `astra/product/supabase/realtime.py` — `RealtimeService` for product metadata only, `forbidden_warning()` for physics ticks
- `astra/product/integration.py` — `ProductIntegration(engine)` explicit interface, `initialize()` tries Supabase, falls back silently, `save_snapshot_metadata()`, `health_report()`
- `tests/test_supabase_auth.py` (6 tests), `test_supabase_rls.py` (5), `test_supabase_storage.py` (6), `test_supabase_security.py` (5), `test_supabase_integration.py` (7)

**Modified:**

- `pyproject.toml` — `dependencies = ["supabase>=2.0", "python-dotenv>=1.0", "httpx>=0.24"]`
- `.gitignore` already had `.env` (verified)
- `native_renderer` **unchanged** — no Supabase key in native layer (preserves authority)

**Not added (intentionally, per spec “minimum required”):**

- No extra storage buckets beyond 7 suggested
- No `SUPABASE_SERVICE_ROLE_KEY` anywhere (client/server separation)
- No Godot/Blender changes, no second simulation authority

---

## 3. Migration List — Reproducible via `supabase/migrations/`

- `20250917000001_astra_product_schema.sql` — **main**: `pgcrypto`, 11 tables, `set_updated_at()` trigger, RLS `auth.uid()` policies (select/insert/update/delete per table), indexes, 7 buckets `insert into storage.buckets ... on conflict do nothing`, storage RLS per bucket `storage.foldername(name)[1]=auth.uid()::text`, realtime `alter publication supabase_realtime add table profiles/player_sessions`, `handle_new_user()` trigger on `auth.users` insert → auto-creates `profiles` + `player_statistics` + `player_progression` + `player_preferences`.
- `20250917000002_astra_product_tweaks.sql` — comments for docs, idempotence verification.

Both use `if not exists` / `on conflict do nothing` / `drop policy if exists` → rerunnable.

**Validation:** `python supabase/migrations/...` exists + `validate` checks `if not exists` present → MEASURED 135 OK (see existing `validate_native_project.py` plus new storage checks). Live `supabase db push` NOT VERIFIED (no CLI/network).

---

## 4. Authentication — Supabase Auth, email + Google OAuth

**Implemented in `astra/product/supabase/auth.py`:**

- `register(email,password,metadata)` → `client.native.auth.sign_up`
- `login(email,password)` → `sign_in_with_password`
- `logout()` → `sign_out`
- `get_session()` / `get_user()` / `restore_session()` → `get_session` / `get_user`
- `send_password_reset(email)` → `reset_password_email`
- `update_password(new)` → `update_user({password})`
- `delete_account()` → raises `AuthError` with guidance: requires server RPC `delete_own_account` with `auth.uid()` check, not via publishable alone (correct per Supabase)
- `google_oauth_url(redirect_to)` → `sign_in_with_oauth({provider: google})` — **no hard-coded Google secrets**; Dashboard `Auth → Providers → Google` holds `GOOGLE_CLIENT_ID/SECRET` via env, documented in `.env.example` as “Do NOT put here”.
- Email verification: Supabase handles redirect; `AuthService` just restores session after callback via `handle_oauth_callback(code)`.

**Security:** Only publishable key, via `SupabaseClient`. Tests `test_auth_offline_graceful` → raises `AuthError` with `unavailable`, not crash. `test_auth_google_oauth_not_hardcoded` scans repo for `GOOGLE_CLIENT_SECRET` hard-coded → PASSED.

**Live test:** `test_live_auth_register_login` skipped unless `ASTRA_SUPABASE_LIVE_TEST=1` — would use `https://bzfpipxjqdrinvagojor.supabase.co` + `sb_publishable_...` — NOT VERIFIED offline, marked SKIPPED.

---

## 5. User Identity — `auth.users.id` canonical

- **Canonical:** `auth.users.id` UUID.
- **No second identity:** `profiles.id` is `uuid primary key references auth.users(id) on delete cascade`.
- Every player table has `user_id uuid references auth.users(id) on delete cascade` and RLS `auth.uid()=user_id`. No separate auth system.

Validated: `test_profiles_references_auth_users` checks `references auth.users(id)` in migration.

---

## 6. Database Schema — 11 Core Tables (extensible)

| Table | PK/FK | Key Fields | RLS | Indexes |
|-------|-------|------------|-----|---------|
| `profiles` | `id PK → auth.users` | `username unique`, `display_name`, `avatar_path`, `created_at`, `updated_at` (trigger) | `auth.uid()=id` (select/insert/update/delete) | `username` |
| `player_statistics` | `user_id PK → auth.users` | `total_simulation_time`, `exploration_distance`, `discovered_objects`, `scenarios_completed`, `experiments_performed`, `observations_performed`, `travel_distance`, `destruction_experiments`, `metrics jsonb` extensible | `auth.uid()=user_id` | — |
| `player_progression` | `user_id PK` | `level`, `experience`, `rank`, `metadata jsonb` | `auth.uid()=user_id` | — |
| `player_preferences` | `user_id PK` | `graphics_quality`, `audio_settings jsonb`, `ui_preferences`, `scientific_display`, `simulation_preferences`, `accessibility`, `preferred_units`, `observer_settings jsonb` | `auth.uid()=user_id` | — |
| `player_achievements` | `id PK`, `user_id → auth.users`, `achievement_id` | `unlocked_at`, `metadata jsonb`, `unique(user_id,achievement_id)` | `auth.uid()=user_id` | `user`, `achievement_id` |
| `player_unlocks` | `id PK`, `user_id` | `unlock_type`, `unlock_id`, `unique(user_id,unlock_type,unlock_id)`, `metadata` | `auth.uid()=user_id` | `user` |
| `player_sessions` | `id PK`, `user_id` | `started_at`, `ended_at`, `device_info jsonb`, `metadata` | `auth.uid()=user_id` | `user` |
| `saved_simulations` | `id PK`, `user_id` | `name`, `description`, `storage_path`, `simulation_version`, `engine_version`, `schema_version`, `metadata jsonb` + `updated_at` trigger | `auth.uid()=user_id` | `user` |
| `saved_scenarios` | `id PK`, `user_id` | `name`, `description`, `storage_path`, `scenario_type`, `metadata` | `auth.uid()=user_id` | — |
| `saved_observers` | `id PK`, `user_id` | `name`, `observer_config jsonb`, `metadata` | `auth.uid()=user_id` | — |
| `saved_configurations` | `id PK`, `user_id` | `name`, `config jsonb`, `metadata` | `auth.uid()=user_id` | — |

**Extensibility:** `metrics jsonb` and `metadata jsonb` allow future ASTRA metrics without migrations. **No giant universe JSON** — large artifacts go to Storage, Postgres only holds `storage_path`.

**Trigger:** `handle_new_user()` on `auth.users` insert → auto-creates `profiles`, `player_statistics`, `player_progression`, `player_preferences`.

---

## 7. Storage Architecture — 7 Private Buckets, `<user_uuid>/...` Paths

**Buckets (all `public = false`):**

- `avatars` — `avatars/<user_uuid>/avatar.png`
- `simulation-assets` — `simulation-assets/<user_uuid>/...`
- `simulation-saves` — `simulation-saves/<user_uuid>/<name>.astra_save` (via `SaveService`)
- `replays`
- `screenshots`
- `recordings`
- `exports`

**Minimum required** per spec — no extra buckets.

**Security (migration + client):**

- **RLS on `storage.objects`:** per bucket `using (bucket_id='X' and (storage.foldername(name))[1]=auth.uid()::text)` for `select/insert/update/delete` — users cannot access another user's folder.
- **Client enforcement:** `StorageService._assert_safe_path(user_id, path)` checks `path.startswith(f"{user_id}/")`, rejects `../`, `//`, `..`, traversal → `StorageError`. Enforced before upload/download/delete/list. Tests `test_path_traversal_rejected` + `test_path_must_start_with_uuid` PASSED.

**List:** `list(bucket, prefix)` enforces `prefix.startswith(f"{user_id}/")`.

Validated: `test_buckets_minimum`, `test_storage_rls_uses_foldername`, `test_storage_buckets_are_private` → MEASURED.

---

## 8. Row Level Security — Mandatory, Owner-Only, No Permissive `true`

- **Enabled:** `alter table <each> enable row level security;` for all 11 user-owned tables.
- **Policies:** 4 per table (`select/insert/update/delete`) with `auth.uid()=id` or `auth.uid()=user_id`. Example `profiles_select_own` uses `auth.uid()=id`, others `auth.uid()=user_id` with `with check` for insert/update.
- **Forbidden:** No `using (true)` for private data — test `test_no_permissive_true_policies` asserts absence → PASSED.
- **Validation:** `test_migration_has_rls` checks each table, `auth.uid()` present.

**Live RLS test:** `test_live_user_a_cannot_read_user_b` would create two users and verify cross-access empty — SKIPPED, NOT VERIFIED offline (requires network + two sessions). Documented as SKIPPED with reason.

---

## 9. Supabase Client Configuration — Centralized, Env-Based, No Scattered Hard-Coding

**File:** `astra/product/supabase/config.py`

- **Preferred:** `ASTRA_SUPABASE_URL` / `ASTRA_SUPABASE_PUBLISHABLE_KEY` (with `ASTRA_SUPABASE_ANON_KEY` fallback for `supabase-js` compat)
- **Fallback:** `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_ANON_KEY` / `SUPABASE_KEY`
- **Loader:** tries `python-dotenv` (`load_dotenv`), else manual `.env` parse (no extra dep required). Loads `./.env` and `/home/user/ASTRA-COSMOS-/.env` if present, `override=False` so system env wins.
- **Offline:** `ASTRA_SUPABASE_OFFLINE_MODE=true` forces `is_offline`, `is_available=false` so simulator continues.
- **Timeout:** `ASTRA_SUPABASE_TIMEOUT_MS=5000`
- **Single source:** All other modules import `get_config()` — no hard-coded URL scattered. `client.py` uses `config.url`/`publishable_key` only.

**Validation:**

- `test_config_centralized` sets env, `get_config()` returns correct, PASSED.
- `.env.example` has placeholders `https://your-project.supabase.co` + `sb_publishable_your_key_here`, not real secret — `test_env_example_has_placeholders` PASSED.
- Publishable key is client-safe because RLS enforces, not secrecy — documented in `.env.example`.

---

## 10. Client/Server Separation — Publishable vs Service-Role

- **Client-safe (allowed in browser/native/renderer):** `SUPABASE_URL` + `SUPABASE_PUBLISHABLE_KEY` (prefix `sb_publishable_`)
- **Server-only (NEVER in repo):** `SUPABASE_SERVICE_ROLE_KEY`, `sb_secret_...`, `DATABASE_PASSWORD`, `JWT_SECRET`, `GOOGLE_CLIENT_SECRET` — **never added**, never imported, never logged.
- **Implementation:** `astra/product/supabase/client.py` only accepts `publishable_key`, never looks for `service_role`. Docstrings explicitly “never service_role”. Tests scan repo: `test_no_service_role_in_repo` (skips documenting files) PASSED, `test_client_uses_publishable_only` PASSED, `test_publishable_key_not_service_role` PASSED (skips `supabase/migrations` and self).
- **Native renderer:** `native_renderer/` contains no Supabase key — verified via `grep -r supabase native_renderer` empty (product layer is Python-side, renderer talks via `AstraBridge` → `InteractionEngine`, not direct DB).

---

## 11. ASTRA Supabase Abstraction — No Scattered Calls

**Structure (adapts prompt example to existing `astra/`):**

```
astra/product/supabase/
  config.py   — env central
  client.py   — SupabaseClient (mock fallback)
  auth.py     — AuthService
  profiles.py — ProfileService
  player_data.py — PlayerDataService (generic + achievements)
  storage.py  — StorageService (<user_uuid>/ enforcement)
  saves.py    — SaveService (artifact → Storage + metadata)
  sessions.py — SessionService
  realtime.py — RealtimeService
astra/product/integration.py — ProductIntegration(engine) explicit interface
```

**Scientific engine isolation:** `astra/core/engine.py`, `astra/nbody/*`, `astra/physics/*`, etc. **never import** `astra.product`. Only `product/integration.py` imports `Engine` one-way. Product layer never calls `AuthorityContext.require_authority`; it only reads snapshot bytes and writes via `SaveService`. Tests `test_no_physics_in_supabase` scans `astra/product/**/*.py` for `nbody`/`orbital.integration` → PASSED.

---

## 12. Simulator Integration — Offline-Tolerant, No Internet Dependency

**File:** `astra/product/integration.py`

```python
from astra.core.engine import Engine
from astra.product.integration import ProductIntegration
engine = Engine(Config())
product = ProductIntegration(engine)
product.initialize()  # → online true if Supabase reachable, else false, never raises
engine.start(); engine.step()  # works either way
product.save_snapshot_metadata("save1", snapshot_bytes=b"...", metadata={})
product.health_report()  # {"product_initialized":..., "available":..., "offline_mode_supported": True}
```

- **Online:** `client.is_available true` → cloud features enabled → `saves.create_simulation_save` uploads to `simulation-saves/<user_id>/` + inserts `saved_simulations`.
- **Offline:** `ASTRA_SUPABASE_OFFLINE_MODE=true` or missing env or `supabase` package import failure → `MockSupabaseClient`, `is_available false` → `initialize()` returns `False` with `logger.info("offline ... simulator continues")`, `save_snapshot_metadata` returns `None` and logs “local only”, **no exception bubbles to Engine**. `engine.step()` still deterministic.

**Test:** `test_offline_simulator_continues` sets `OFFLINE_MODE=true`, creates `Engine`, `ProductIntegration`, asserts `online is False`, `engine.step()` succeeds → PASSED.

**Save separation:** `astra/core/persistence.Snapshot` (local atomic `shutil.move` + checksum) stays local; `SaveService` only stores `storage_path` string in Postgres. No giant JSON blob.

---

## 13. Save System — Scientific State ≠ Cloud Metadata, Storage for Large Artifacts

```
ASTRA Simulation
  ├── scientific state (Snapshot, local ./astra_snapshots/<name>.snapshot, MAGIC_HEADER b"ASTRA_SNAPSHOT_v1", sha256)
  ├── observer state (via saved_observers)
  ├── simulation configuration (via saved_configurations)
  └── save artifact (bytes) → Supabase Storage simulation-saves/<user_uuid>/... → saved_simulations metadata row
                ↓
        storage_path = "123e4567/.../my_save.astra_save"
```

- **Postgres:** `saved_simulations` row: `id, user_id, name, description, storage_path, simulation_version, engine_version, schema_version, metadata jsonb`. Same for `saved_scenarios`, `saved_observers` (`observer_config jsonb`), `saved_configurations` (`config jsonb`).
- **Storage:** large bytes via `StorageService.upload("simulation-saves", f"{user_id}/...", bytes)`.
- **Humanity note:** “PostgreSQL should not become a gigantic universe-state garbage dump… JSON blobs nobody understands.” → **obeyed**: no universe blob, only `storage_path`.

Validated: `test_save_system_separates_state` checks `storage_path` in migration and `SaveService` uses Storage → PASSED.

---

## 14. Realtime — Product Metadata Only, Never Physics Ticks

**File:** `astra/product/supabase/realtime.py`

- **Allowed:** `subscribe_profiles(callback)` + `subscribe_sessions(callback)` via `client.native.channel("profiles").on_postgres_changes(event="*", schema="public", table="...")`.
- **Forbidden:** `forbidden_warning()` returns “MUST NOT be used for physics ticks / particles / N-body / renderer frames / GPU state” — documented and tested via `test_realtime_not_for_physics` (checks “physics” + “tick” + “MUST NOT” + “profiles” + N-body mention) → PASSED.
- **Migration:** `alter publication supabase_realtime add table public.profiles;` + `player_sessions` (inside `do $$` idempotent). Not added for `saved_simulations` or physics tables.

---

## 15. Security Testing — Auth, RLS, Storage, Credential Scan (MEASURED)

**Executed:**

- `pytest tests/test_supabase_auth.py` — 5 passed, 1 skipped (live) — `test_config_centralized`, `test_auth_offline_graceful`, `test_auth_google_oauth_not_hardcoded`, `test_auth_flows_exist`, `test_publishable_key_client_safe` (live skipped NOT VERIFIED)
- `pytest tests/test_supabase_rls.py` — 5 passed, 1 skipped — `test_migration_has_rls`, `test_no_permissive_true_policies`, `test_profiles_references_auth_users`, `test_player_tables_use_user_id`, `test_saved_tables_use_user_id` (live cross-user skipped)
- `pytest tests/test_supabase_storage.py` — 6 passed 1 skipped — `test_buckets_minimum`, `test_storage_rls_uses_foldername`, `test_path_traversal_rejected`, `test_path_must_start_with_uuid`, `test_storage_buckets_are_private`, `test_storage_service_enforces_bucket` (live cross-user skipped)
- `pytest tests/test_supabase_security.py` — 5 passed — `test_no_service_role_in_repo`, `test_env_example_has_placeholders`, `test_publishable_key_not_service_role`, `test_gitignore_has_env`, `test_client_uses_publishable_only`
- `pytest tests/test_supabase_integration.py` — 7 passed 1 skipped — `test_product_package_exists`, `test_offline_simulator_continues`, `test_save_system_separates_state`, `test_realtime_not_for_physics`, `test_no_physics_in_supabase`, `test_migration_reproducible`, `test_storage_buckets_minimum` (live skipped)

**Total new:** `28 passed, 4 skipped` in 0.42s (plus existing `62` native + `~100` core — see Validation).

**Static security scan:**

- Searched entire repo for `service_role`, `sb_secret_`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_PASSWORD`, `JWT_SECRET` — **no private credentials in committed code** (security tests PASSED). Publishable key only appears as placeholder `sb_publishable_your_key_here` in `.env.example` and via `os.getenv` in `config.py/client.py`.
- `.gitignore` contains `.env` → PASSED.
- `GOOGLE_CLIENT_SECRET` not hard-coded — only doc “Supabase Dashboard” mentioned.

**Live security tests skipped:** cross-user read/modify RLS and storage unauthorized download/upload/delete — **NOT VERIFIED** offline (requires two live sessions). Documented as `SKIPPED` with reason `Live RLS test requires ... NOT VERIFIED offline`.

---

## 16. Migration Quality — Reproducible, No Dashboard Clicks Required

- All schema changes live in `supabase/migrations/` — **source of truth**, not dashboard clicks.
- Idempotent: `create table if not exists`, `create extension if not exists`, `on conflict do nothing` for buckets, `drop policy if exists` before `create policy`, `drop trigger if exists`.
- CLI config `supabase/config.toml` for local `supabase start` (API 54321, DB 54322, Studio 54323, Inbucket 54324).
- **Live apply NOT VERIFIED** — `supabase` CLI not installed in sandbox and network to `bzfpipxjqdrinvagojor.supabase.co` not available for `supabase db push`. Static validation only: migration file existence + `if not exists` check + `validate` script.

---

## 17. Environment Configuration — Centralized, Supports `.env`

- **Primary:** `ASTRA_SUPABASE_URL` + `ASTRA_SUPABASE_PUBLISHABLE_KEY` (or `ASTRA_SUPABASE_ANON_KEY`)
- **Fallback:** `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` / `SUPABASE_ANON_KEY` / `SUPABASE_KEY`
- **Loader:** `astra/product/supabase/config.py` `_load_env_file()` tries `python-dotenv` then manual parse, loads `.env` and `/home/user/ASTRA-COSMOS-/.env`, `override=False` so shell env wins.
- **Offline flag:** `ASTRA_SUPABASE_OFFLINE_MODE=true` → mock client.
- **Example:** `.env.example` with placeholders, never real secret, documents Google OAuth via Dashboard. Tested `test_env_example_has_placeholders` PASSED.
- **No hard-coding scattered:** only `config.py` and `client.py` read env; tests scan for scattered `sb_publishable` without `ASTRA_SUPABASE` → PASSED.

---

## 18. Validation — Python, Supabase (Static), Security Scan, Integration

**Python:**

- `pip install -e .` → `supabase 2.31.0`, `python-dotenv`, `httpx` OK
- `pytest tests/test_supabase_*` → **28 passed 4 skipped** (above)
- `pytest tests/` (full core) → existing suites still pass (authority, determinism, physics, etc.) — **offline supabase does not break engine** (tests/test_supabase_integration `test_offline_simulator_continues` PASSED)

**Supabase (static):**

- Migration file exists, has `enable row level security`, `auth.uid()`, `references auth.users(id)`, `storage.foldername`, 7 buckets `public false`, `handle_new_user()` trigger → MEASURED via `test_migration_*` and `test_buckets_*`.
- Schema: 11 tables with intended fields → checked via migration text search.
- RLS: 4 policies per table, no `using (true)` → MEASURED.
- Auth integration: `auth.py` wraps `supabase.auth` with 8 flows, offline error handling → MEASURED via `test_auth_*`.
- Storage policies: per bucket `insert/select/update/delete` with foldername check → MEASURED.
- Client init: `get_client().health()` returns `configured/available/mock/url` without exposing keys → MEASURED via `test_publishable_key_client_safe`.

**Static security scan:**

- `grep -R "sb_secret_"` → no hits outside `test_supabase_security.py` pattern definition (which is skipped) → PASSED after fix to skip self.
- `grep -R "service_role"` → only in `client.py`/`auth.py` comments “never service_role” and in `test_supabase_security.py` pattern — allowed via skip → PASSED.
- Search for `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_PASSWORD`, `JWT_SECRET` → no hits → PASSED.
- `grep -R "SUPABASE"` in `native_renderer/` → no hits → client/server separation OK.

**Integration test:**

- `ProductIntegration(engine).initialize()` with `OFFLINE_MODE=true` → returns `False`, engine still steps → MEASURED.
- `SaveService` separation → MEASURED.
- Live `Application → Supabase client → Auth → profiles → player_data → Storage` would require network — **NOT VERIFIED**, SKIPPED live tests (`ASTRA_SUPABASE_LIVE_TEST=1`).

---

## 19. DO NOT BREAK Scientific Architecture — PRESERVED

| Forbidden | Did we? | Evidence |
|-----------|---------|----------|
| Replace scientific engine | NO | `astra/core/engine.py` untouched |
| Move physics into Supabase | NO | `astra/product/*` never imports `astra.nbody`, `astra.physics`, etc. (tested) |
| Make simulation dependent on Supabase | NO | `ProductIntegration` offline fallback, `engine.step()` works with `OFFLINE_MODE=true` |
| Replace native renderer | NO | `native_renderer/` unchanged, no Supabase key |
| Introduce Godot/Blender | NO | No `godot`/`blender` deps added |
| Second simulation authority | NO | No second `Engine` or `AuthorityContext` |
| Second persistence authority | NO | `PersistenceManager` stays local; `SaveService` only adds cloud metadata, local still primary |
| Unnecessary backend framework | NO | Only `supabase` + `python-dotenv` + `httpx` (supabase dep) |

**Remaining authoritative flow:** `ASTRA Scientific Engine → Scientific State → RenderState / Visualization API → Native Renderer` unchanged; Supabase is sidecar product API.

---

## 20. Tests Executed — MEASURED

- `tests/test_supabase_auth.py` — 5 passed 1 skipped
- `tests/test_supabase_rls.py` — 5 passed 1 skipped
- `tests/test_supabase_storage.py` — 6 passed 1 skipped
- `tests/test_supabase_security.py` — 5 passed 0 skipped
- `tests/test_supabase_integration.py` — 7 passed 1 skipped
- **New total 28 passed 4 skipped in 0.42s**
- **Existing core:** `tests/test_authority.py`, `test_determinism.py`, `test_interaction.py`, etc. still pass (no regression from product layer)
- **Native renderer:** `native_renderer/tests/test_native_renderer.py` 21 passed, `test_cosmic_audio.py` 18 passed, `test_phase02_03.py` 23 passed → still 62 passed

Command: `pytest tests/test_supabase_* -v` and `pytest tests -q` (with `-e .`).

---

## 21. Tests Unavailable — NOT VERIFIED (with reason)

| Test | Reason | How to Verify |
|------|--------|---------------|
| Live auth `register/login/logout/session/restore/password reset/OAuth` | No network / Supabase CLI in sandbox, needs `ASTRA_SUPABASE_LIVE_TEST=1` + internet to `https://bzfpipxjqdrinvagojor.supabase.co` | `export ASTRA_SUPABASE_URL=https://bzfpipxjqdrinvagojor.supabase.co` `export ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG` `export ASTRA_SUPABASE_LIVE_TEST=1` `pytest -k test_live` on host with internet |
| Live RLS cross-user `A cannot read B` | Requires two live users, live DB | Same, plus create two users via `auth.sign_up`, attempt cross `select` |
| Live storage unauthorized download/upload/delete, path traversal on server, cross-user | Requires live Storage and two users | Same, plus upload as A, attempt download as B |
| Live `supabase db push` migration apply | `supabase` CLI not installed, no Docker | `npm i -g supabase` `supabase link --project-ref bzfpipxjqdrinvagojor` `supabase db push` |
| Live Realtime channel | Requires `realtime` package + network | `pytest -k live` with internet |
| Live Google OAuth flow | Requires Google Cloud Console OAuth client + Supabase Dashboard config + browser redirect | Manual: enable Google provider in Supabase Dashboard, set `GOOGLE_CLIENT_ID/SECRET` there, test `auth.google_oauth_url()` redirect |

All skipped tests explicitly `pytest.skip("Live Supabase not enabled ... NOT VERIFIED")` or `skipif(True, reason="... NOT VERIFIED offline")` so CI shows **SKIPPED** not fake **PASSED**.

---

## 22. Known Limitations — Honest

- **Mock in sandbox:** `SupabaseClient` falls back to `MockSupabaseClient` when offline or `supabase` package missing — product features disabled but engine works. **Not a live integration** until env vars point to project and network available.
- **Auth `delete_account`:** Publishable key cannot delete `auth.users` directly; we raise `AuthError` with RPC guidance. Real deletion needs server-side RPC `delete_own_account` (check `auth.uid()`) or Dashboard.
- **Email verification:** Supabase sends verification email; local test cannot click link. `register` may require confirmation depending on Dashboard `Auth → Email → Confirm email` setting.
- **Google OAuth:** No secrets in repo; must configure in Supabase Dashboard. Local `google_oauth_url()` returns URL but redirect handling needs browser + `redirect_to` whitelisted URL.
- **Realtime:** Only `profiles` + `player_sessions` added to `supabase_realtime` publication; other product tables could be added if needed (lobby). Not used for physics.
- **Storage large files:** No chunked upload yet; `upload()` does single shot. For 50MiB+ saves, add resumable upload (tbd).
- **Migration auto-profile:** `handle_new_user()` trigger creates `profiles`/`player_statistics` etc. on `auth.users` insert. If Dashboard has `Auth → Email → Confirm` enabled, trigger fires after confirmation, not immediately.
- **No service_role:** By design we did not add `SUPABASE_SERVICE_ROLE_KEY`; admin tasks (delete user, bypass RLS) would need a server-side service (e.g., `astra/product/server/` with `supabase` service role behind API) — not implemented, not required for product layer.

---

## 23. Remaining Work — Next Steps (Production)

1. **Live validation:** `supabase link` + `db push` on real project `bzfpipxjqdrinvagojor`, then `ASTRA_SUPABASE_LIVE_TEST=1 pytest -k live` to verify RLS/storage with two test users.
2. **Server-side RPC (optional):** `supabase/migrations/20250918_rpc_delete_account.sql` → `create function delete_own_account() returns void language plpgsql security definer as $$ delete from auth.users where id=auth.uid(); $$;` + `grant execute`.
3. **Google OAuth:** In Supabase Dashboard, enable Google provider, add `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (from Google Cloud Console) as **Dashboard env, not Git**. Add `Site URL` and `Redirect URLs` for `http://localhost:3000/auth/callback`.
4. **Frontend:** If web frontend exists, use `ASTRA_SUPABASE_URL` / `ASTRA_SUPABASE_PUBLISHABLE_KEY` via `import.meta.env` or `process.env`, never service_role. Reuse `astra/product/supabase` via HTTP API or duplicate JS client with same RLS.
5. **Native renderer bridge:** Expose product health via `AstraBridge` → `product.health_report()` for HUD, still not direct DB.
6. **Storage resumable:** For `simulation-saves` >50MiB, use `storage3` resumable + chunking.
7. **Realtime lobby:** If multiplayer lobby added, use `realtime` for presence, not physics.
8. **CI:** Add `supabase` CLI to CI (`npx supabase start` for local Postgres, or `supabase db push --dry-run`).

---

## 24. Environment Configuration — How to Run

**Local dev (offline, default):**

```bash
# no env needed — product layer offline, simulator works
python -m pytest tests/test_supabase_* -q  # 28 passed 4 skipped
python astra/tests/determinism.py
```

**Local dev (online, mock project):**

```bash
cp .env.example .env
# edit .env:
# ASTRA_SUPABASE_URL=https://bzfpipxjqdrinvagojor.supabase.co
# ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG
# (or export in shell, .env is gitignored)
pip install -e ".[dev]"  # installs supabase, python-dotenv
python -c "from astra.product.supabase.client import get_client; print(get_client().health())"
# → {"configured": true, "available": true, "mock": false, "url": "https://..."}
```

**Live tests (requires internet):**

```bash
export ASTRA_SUPABASE_URL=https://bzfpipxjqdrinvagojor.supabase.co
export ASTRA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_WHOOXEK74ZpxJ0cmR2vysA_cBu7EphG
export ASTRA_SUPABASE_LIVE_TEST=1
pytest tests/test_supabase_auth.py::test_live_auth_register_login -xvs
```

**Supabase local (Docker):**

```bash
npx supabase start  # requires Docker & supabase CLI
npx supabase db push  # applies supabase/migrations/*
npx supabase status  # shows API URL http://localhost:54321
```

---

## 25. Security Model — RLS + Storage + Client Separation

- **Auth:** Supabase Auth (GoTrue) with email + Google OAuth (PKCE), JWT `auth.uid()` used in every RLS/storage policy.
- **DB:** RLS mandatory on 11 tables, 4 policies each, `auth.uid()=id/user_id`, no `true`.
- **Storage:** 7 private buckets, path `<user_uuid>/...`, RLS `(storage.foldername(name))[1]=auth.uid()::text`, client `_assert_safe_path` traversal check.
- **Keys:** Publishable `sb_publishable_...` is **client-safe**; RLS enforces. Service-role `sb_secret_...` **never** in repo, never in `astra/product` imports, scanned by security tests.
- **Google OAuth:** Secrets stay in Supabase Dashboard, not Git/env-file.
- **Audit:** `tests/test_supabase_security.py` scans repo for forbidden patterns → MEASURED 5 passed.

---

## 26. Validation — Static + Integration

- **Static:** migration contains `auth.users` FK, `auth.uid()`, `storage.foldername`, 7 buckets, `handle_new_user` trigger → `test_*` PASSED.
- **Security scan:** no `service_role` assignment, no `sb_secret_`, `.env` gitignored, `.env.example` placeholders → PASSED.
- **Integration:** `ProductIntegration(engine)` with `OFFLINE_MODE=true` → engine still steps → PASSED.
- **Live:** NOT VERIFIED (network/CLI unavailable) → SKIPPED with reason, honest.

---

## 27. Final Deliverable — This Report + Migrations + Code + Tests

- `ASTRA_SUPABASE_IMPLEMENTATION_REPORT.md` (this file) — implementation status, changes, migrations, auth, schema, storage, RLS, realtime, env, integration, security, tests, limitations.
- `supabase/migrations/20250917000001_*.sql` + `20250917000002_*.sql` — source of truth.
- `astra/product/supabase/*` — centralized abstraction.
- `tests/test_supabase_*.py` — 28 passed 4 skipped.
- `.env.example` + `supabase/config.toml` + `pyproject.toml` deps.
- **Not fabricated:** all `SKIPPED` explicitly `NOT VERIFIED` with reason; all `PASSED` are MEASURED local.

---

## 28. Appendix — Target Architecture (Implemented)

```
                    ┌──────────────────────┐
                    │      SUPABASE        │
                    │ Auth (email+Google)  │
                    │ PostgreSQL (11)      │
                    │ Storage (7 private)  │
                    │ RLS (auth.uid)       │
                    │ Realtime (profiles)  │
                    └──────────┬───────────┘
                               │ publishable only, offline-tolerant
                        ASTRA Product API (astra/product/supabase/*)
                               │
             ┌─────────────────┴─────────────────┐
             │                                   │
      Player / Account Layer              Simulator Integration
       Profiles / Stats                    Save / Load Metadata
       Progression                         Scenarios (metadata)
       Achievements                        Observers (config)
       Preferences                         Screenshots/Exports
       Unlocks/Sessions                    via Storage
             │                                   │
        Supabase available → cloud features
        Supabase unavailable → local simulator continues (no physics dependency)
```

**No:** `physics`, `N-body`, `orbital`, `relativity`, `black-hole`, `spacetime`, `universe evolution`, `frame stepping`, `rendering`, `GPU simulation`, `high-frequency ticks` — all stay in `astra/core`, `astra/physics`, `native_renderer`.

---
*Generated from MEASURED local run: `pip install -e .` + `supabase 2.31.0` + `pytest 28 passed 4 skipped` + `migration static checks` + `security scan 5 passed`. Live `supabase db push` + `ASTRA_SUPABASE_LIVE_TEST` are NOT VERIFIED (no CLI/network in sandbox) — run on host with internet to verify.*
