-- ASTRA COSMOS — Supabase product layer migration
-- 20250917000001 — core product tables, RLS, storage buckets
-- Requires: auth.users(id) from Supabase Auth
-- Security: RLS mandatory, no permissive true policies, paths <user_uuid>/...

-- Enable pgcrypto for gen_random_uuid if not already
create extension if not exists "pgcrypto";

-- ===========================================================================
-- PROFILES — canonical player identity, references auth.users(id)
-- ===========================================================================
create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    username text unique,
    display_name text,
    avatar_path text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
-- Policies: user can read/update own profile, others can read limited? For now private.
drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own" on public.profiles
    for select to authenticated using (auth.uid() = id);
drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own" on public.profiles
    for insert to authenticated with check (auth.uid() = id);
drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own" on public.profiles
    for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);
drop policy if exists "profiles_delete_own" on public.profiles;
create policy "profiles_delete_own" on public.profiles
    for delete to authenticated using (auth.uid() = id);

create index if not exists idx_profiles_username on public.profiles(username);

-- updated_at trigger
create or replace function public.set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end; $$ language plpgsql;
drop trigger if exists trg_profiles_updated_at on public.profiles;
create trigger trg_profiles_updated_at before update on public.profiles
for each row execute function public.set_updated_at();

-- ===========================================================================
-- PLAYER STATISTICS — extensible progression metrics
-- ===========================================================================
create table if not exists public.player_statistics (
    user_id uuid primary key references auth.users(id) on delete cascade,
    total_simulation_time double precision not null default 0,
    exploration_distance double precision not null default 0,
    discovered_objects integer not null default 0,
    scenarios_completed integer not null default 0,
    experiments_performed integer not null default 0,
    observations_performed integer not null default 0,
    travel_distance double precision not null default 0,
    destruction_experiments integer not null default 0,
    -- extensible JSONB for future ASTRA metrics
    metrics jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.player_statistics enable row level security;
drop policy if exists "player_statistics_select_own" on public.player_statistics;
create policy "player_statistics_select_own" on public.player_statistics for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_statistics_insert_own" on public.player_statistics;
create policy "player_statistics_insert_own" on public.player_statistics for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_statistics_update_own" on public.player_statistics;
create policy "player_statistics_update_own" on public.player_statistics for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_statistics_delete_own" on public.player_statistics;
create policy "player_statistics_delete_own" on public.player_statistics for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_player_statistics_updated_at on public.player_statistics;
create trigger trg_player_statistics_updated_at before update on public.player_statistics
for each row execute function public.set_updated_at();

-- ===========================================================================
-- PLAYER PROGRESSION — level / xp / rank
-- ===========================================================================
create table if not exists public.player_progression (
    user_id uuid primary key references auth.users(id) on delete cascade,
    level integer not null default 1,
    experience bigint not null default 0,
    rank text,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.player_progression enable row level security;
drop policy if exists "player_progression_select_own" on public.player_progression;
create policy "player_progression_select_own" on public.player_progression for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_progression_insert_own" on public.player_progression;
create policy "player_progression_insert_own" on public.player_progression for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_progression_update_own" on public.player_progression;
create policy "player_progression_update_own" on public.player_progression for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_progression_delete_own" on public.player_progression;
create policy "player_progression_delete_own" on public.player_progression for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_player_progression_updated_at on public.player_progression;
create trigger trg_player_progression_updated_at before update on public.player_progression
for each row execute function public.set_updated_at();

-- ===========================================================================
-- PLAYER PREFERENCES — product preferences, extensible jsonb
-- ===========================================================================
create table if not exists public.player_preferences (
    user_id uuid primary key references auth.users(id) on delete cascade,
    graphics_quality text,
    audio_settings jsonb not null default '{}'::jsonb,
    ui_preferences jsonb not null default '{}'::jsonb,
    scientific_display_preferences jsonb not null default '{}'::jsonb,
    simulation_preferences jsonb not null default '{}'::jsonb,
    accessibility_settings jsonb not null default '{}'::jsonb,
    preferred_units text,
    observer_settings jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table public.player_preferences enable row level security;
drop policy if exists "player_preferences_select_own" on public.player_preferences;
create policy "player_preferences_select_own" on public.player_preferences for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_preferences_insert_own" on public.player_preferences;
create policy "player_preferences_insert_own" on public.player_preferences for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_preferences_update_own" on public.player_preferences;
create policy "player_preferences_update_own" on public.player_preferences for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_preferences_delete_own" on public.player_preferences;
create policy "player_preferences_delete_own" on public.player_preferences for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_player_preferences_updated_at on public.player_preferences;
create trigger trg_player_preferences_updated_at before update on public.player_preferences
for each row execute function public.set_updated_at();

-- ===========================================================================
-- PLAYER ACHIEVEMENTS
-- ===========================================================================
create table if not exists public.player_achievements (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    achievement_id text not null,
    unlocked_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb,
    unique(user_id, achievement_id)
);
alter table public.player_achievements enable row level security;
drop policy if exists "player_achievements_select_own" on public.player_achievements;
create policy "player_achievements_select_own" on public.player_achievements for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_achievements_insert_own" on public.player_achievements;
create policy "player_achievements_insert_own" on public.player_achievements for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_achievements_update_own" on public.player_achievements;
create policy "player_achievements_update_own" on public.player_achievements for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_achievements_delete_own" on public.player_achievements;
create policy "player_achievements_delete_own" on public.player_achievements for delete to authenticated using (auth.uid() = user_id);
create index if not exists idx_player_achievements_user on public.player_achievements(user_id);
create index if not exists idx_player_achievements_achievement on public.player_achievements(achievement_id);

-- ===========================================================================
-- PLAYER UNLOCKS — features / scenarios / objects / visual capabilities
-- ===========================================================================
create table if not exists public.player_unlocks (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    unlock_type text not null,
    unlock_id text not null,
    unlocked_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb,
    unique(user_id, unlock_type, unlock_id)
);
alter table public.player_unlocks enable row level security;
drop policy if exists "player_unlocks_select_own" on public.player_unlocks;
create policy "player_unlocks_select_own" on public.player_unlocks for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_unlocks_insert_own" on public.player_unlocks;
create policy "player_unlocks_insert_own" on public.player_unlocks for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_unlocks_update_own" on public.player_unlocks;
create policy "player_unlocks_update_own" on public.player_unlocks for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_unlocks_delete_own" on public.player_unlocks;
create policy "player_unlocks_delete_own" on public.player_unlocks for delete to authenticated using (auth.uid() = user_id);
create index if not exists idx_player_unlocks_user on public.player_unlocks(user_id);

-- ===========================================================================
-- PLAYER SESSIONS — session metadata, NOT passwords
-- ===========================================================================
create table if not exists public.player_sessions (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    device_info jsonb not null default '{}'::jsonb,
    metadata jsonb not null default '{}'::jsonb
);
alter table public.player_sessions enable row level security;
drop policy if exists "player_sessions_select_own" on public.player_sessions;
create policy "player_sessions_select_own" on public.player_sessions for select to authenticated using (auth.uid() = user_id);
drop policy if exists "player_sessions_insert_own" on public.player_sessions;
create policy "player_sessions_insert_own" on public.player_sessions for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "player_sessions_update_own" on public.player_sessions;
create policy "player_sessions_update_own" on public.player_sessions for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "player_sessions_delete_own" on public.player_sessions;
create policy "player_sessions_delete_own" on public.player_sessions for delete to authenticated using (auth.uid() = user_id);
create index if not exists idx_player_sessions_user on public.player_sessions(user_id);

-- ===========================================================================
-- SAVED SIMULATIONS — metadata, large artifact in Storage
-- ===========================================================================
create table if not exists public.saved_simulations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    description text,
    storage_path text,
    simulation_version text,
    engine_version text,
    schema_version text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);
alter table public.saved_simulations enable row level security;
drop policy if exists "saved_simulations_select_own" on public.saved_simulations;
create policy "saved_simulations_select_own" on public.saved_simulations for select to authenticated using (auth.uid() = user_id);
drop policy if exists "saved_simulations_insert_own" on public.saved_simulations;
create policy "saved_simulations_insert_own" on public.saved_simulations for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "saved_simulations_update_own" on public.saved_simulations;
create policy "saved_simulations_update_own" on public.saved_simulations for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "saved_simulations_delete_own" on public.saved_simulations;
create policy "saved_simulations_delete_own" on public.saved_simulations for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_saved_simulations_updated_at on public.saved_simulations;
create trigger trg_saved_simulations_updated_at before update on public.saved_simulations
for each row execute function public.set_updated_at();
create index if not exists idx_saved_simulations_user on public.saved_simulations(user_id);

-- ===========================================================================
-- SAVED SCENARIOS — reusable scenario metadata
-- ===========================================================================
create table if not exists public.saved_scenarios (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    description text,
    storage_path text,
    scenario_type text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);
alter table public.saved_scenarios enable row level security;
drop policy if exists "saved_scenarios_select_own" on public.saved_scenarios;
create policy "saved_scenarios_select_own" on public.saved_scenarios for select to authenticated using (auth.uid() = user_id);
drop policy if exists "saved_scenarios_insert_own" on public.saved_scenarios;
create policy "saved_scenarios_insert_own" on public.saved_scenarios for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "saved_scenarios_update_own" on public.saved_scenarios;
create policy "saved_scenarios_update_own" on public.saved_scenarios for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "saved_scenarios_delete_own" on public.saved_scenarios;
create policy "saved_scenarios_delete_own" on public.saved_scenarios for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_saved_scenarios_updated_at on public.saved_scenarios;
create trigger trg_saved_scenarios_updated_at before update on public.saved_scenarios
for each row execute function public.set_updated_at();

-- ===========================================================================
-- SAVED OBSERVERS — observer configurations
-- ===========================================================================
create table if not exists public.saved_observers (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    observer_config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);
alter table public.saved_observers enable row level security;
drop policy if exists "saved_observers_select_own" on public.saved_observers;
create policy "saved_observers_select_own" on public.saved_observers for select to authenticated using (auth.uid() = user_id);
drop policy if exists "saved_observers_insert_own" on public.saved_observers;
create policy "saved_observers_insert_own" on public.saved_observers for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "saved_observers_update_own" on public.saved_observers;
create policy "saved_observers_update_own" on public.saved_observers for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "saved_observers_delete_own" on public.saved_observers;
create policy "saved_observers_delete_own" on public.saved_observers for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_saved_observers_updated_at on public.saved_observers;
create trigger trg_saved_observers_updated_at before update on public.saved_observers
for each row execute function public.set_updated_at();

-- ===========================================================================
-- SAVED CONFIGURATIONS — user configuration presets
-- ===========================================================================
create table if not exists public.saved_configurations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    config jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb
);
alter table public.saved_configurations enable row level security;
drop policy if exists "saved_configurations_select_own" on public.saved_configurations;
create policy "saved_configurations_select_own" on public.saved_configurations for select to authenticated using (auth.uid() = user_id);
drop policy if exists "saved_configurations_insert_own" on public.saved_configurations;
create policy "saved_configurations_insert_own" on public.saved_configurations for insert to authenticated with check (auth.uid() = user_id);
drop policy if exists "saved_configurations_update_own" on public.saved_configurations;
create policy "saved_configurations_update_own" on public.saved_configurations for update to authenticated using (auth.uid() = user_id) with check (auth.uid() = user_id);
drop policy if exists "saved_configurations_delete_own" on public.saved_configurations;
create policy "saved_configurations_delete_own" on public.saved_configurations for delete to authenticated using (auth.uid() = user_id);
drop trigger if exists trg_saved_configurations_updated_at on public.saved_configurations;
create trigger trg_saved_configurations_updated_at before update on public.saved_configurations
for each row execute function public.set_updated_at();

-- ===========================================================================
-- STORAGE BUCKETS — minimum required, private, <user_uuid>/... paths
-- ===========================================================================
insert into storage.buckets (id, name, public) values
  ('avatars', 'avatars', false),
  ('simulation-assets', 'simulation-assets', false),
  ('simulation-saves', 'simulation-saves', false),
  ('replays', 'replays', false),
  ('screenshots', 'screenshots', false),
  ('recordings', 'recordings', false),
  ('exports', 'exports', false)
on conflict (id) do nothing;

-- Storage RLS: user can only access own folder <user_uuid>/...
-- avatars: allow authenticated to read own, public read maybe? Keep private per spec, enforce ownership.

-- Helper function to check owner path: (storage.foldername(name))[1] = auth.uid()::text
-- Note: foldername splits by '/'

-- AVATARS bucket policies
drop policy if exists "avatars_insert_own" on storage.objects;
create policy "avatars_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "avatars_select_own" on storage.objects;
create policy "avatars_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "avatars_update_own" on storage.objects;
create policy "avatars_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "avatars_delete_own" on storage.objects;
create policy "avatars_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

-- SIMULATION-SAVES bucket
drop policy if exists "simulation_saves_insert_own" on storage.objects;
create policy "simulation_saves_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'simulation-saves' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_saves_select_own" on storage.objects;
create policy "simulation_saves_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'simulation-saves' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_saves_update_own" on storage.objects;
create policy "simulation_saves_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'simulation-saves' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_saves_delete_own" on storage.objects;
create policy "simulation_saves_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'simulation-saves' and (storage.foldername(name))[1] = auth.uid()::text);

-- simulation-assets
drop policy if exists "simulation_assets_insert_own" on storage.objects;
create policy "simulation_assets_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'simulation-assets' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_assets_select_own" on storage.objects;
create policy "simulation_assets_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'simulation-assets' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_assets_update_own" on storage.objects;
create policy "simulation_assets_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'simulation-assets' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "simulation_assets_delete_own" on storage.objects;
create policy "simulation_assets_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'simulation-assets' and (storage.foldername(name))[1] = auth.uid()::text);

-- replays
drop policy if exists "replays_insert_own" on storage.objects;
create policy "replays_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'replays' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "replays_select_own" on storage.objects;
create policy "replays_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'replays' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "replays_update_own" on storage.objects;
create policy "replays_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'replays' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "replays_delete_own" on storage.objects;
create policy "replays_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'replays' and (storage.foldername(name))[1] = auth.uid()::text);

-- screenshots
drop policy if exists "screenshots_insert_own" on storage.objects;
create policy "screenshots_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'screenshots' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "screenshots_select_own" on storage.objects;
create policy "screenshots_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'screenshots' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "screenshots_update_own" on storage.objects;
create policy "screenshots_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'screenshots' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "screenshots_delete_own" on storage.objects;
create policy "screenshots_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'screenshots' and (storage.foldername(name))[1] = auth.uid()::text);

-- recordings
drop policy if exists "recordings_insert_own" on storage.objects;
create policy "recordings_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'recordings' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "recordings_select_own" on storage.objects;
create policy "recordings_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'recordings' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "recordings_update_own" on storage.objects;
create policy "recordings_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'recordings' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "recordings_delete_own" on storage.objects;
create policy "recordings_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'recordings' and (storage.foldername(name))[1] = auth.uid()::text);

-- exports
drop policy if exists "exports_insert_own" on storage.objects;
create policy "exports_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "exports_select_own" on storage.objects;
create policy "exports_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "exports_update_own" on storage.objects;
create policy "exports_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "exports_delete_own" on storage.objects;
create policy "exports_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'exports' and (storage.foldername(name))[1] = auth.uid()::text);

-- Ensure RLS is enabled on storage.objects (already enabled by Supabase, but ensure)
-- alter table storage.objects enable row level security; -- managed by Supabase, skip

-- ===========================================================================
-- REALTIME — enable for product metadata only, NOT physics ticks
-- ===========================================================================
-- publication supabase_realtime is auto-managed, we add tables we want realtime for:
-- Keep realtime for lobby presence / notifications: profiles, player_sessions
-- Supabase uses: alter publication supabase_realtime add table ...
-- Use conditional: only if not already added
do $$
begin
  if not exists (select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename='profiles') then
    alter publication supabase_realtime add table public.profiles;
  end if;
  if not exists (select 1 from pg_publication_tables where pubname='supabase_realtime' and schemaname='public' and tablename='player_sessions') then
    alter publication supabase_realtime add table public.player_sessions;
  end if;
exception when others then null;
end $$;

-- ===========================================================================
-- AUTO-PROFILE on signup — optional trigger to create profile row
-- ===========================================================================
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id, username, display_name)
  values (new.id, new.email, new.email)
  on conflict (id) do nothing;
  insert into public.player_statistics (user_id) values (new.id) on conflict (user_id) do nothing;
  insert into public.player_progression (user_id) values (new.id) on conflict (user_id) do nothing;
  insert into public.player_preferences (user_id) values (new.id) on conflict (user_id) do nothing;
  return new;
end; $$ language plpgsql security definer;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
