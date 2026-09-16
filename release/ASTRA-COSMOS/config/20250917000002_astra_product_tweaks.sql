-- 20250917000002 — ASTRA product layer tweaks, indexes already covered, no-op for idempotence
-- Add helpful comments for documentation

comment on table public.profiles is 'ASTRA player profiles, id references auth.users(id), RLS auth.uid()=id';
comment on table public.player_statistics is 'ASTRA progression metrics, extensible via metrics jsonb';
comment on table public.player_progression is 'level/xp/rank, RLS owner only';
comment on table public.saved_simulations is 'metadata for simulation saves, large artifact in storage bucket simulation-saves/<user_uuid>/...';
