"""ASTRA Product Layer — Supabase-backed account/cloud features.

Architecture:
    ASTRA Scientific Engine (authoritative)
        ↓
    Scientific State → RenderState
        ↓
    Native Renderer (Vulkan)
        +
    ASTRA Product API (Supabase: Auth/Postgres/Storage/Realtime)
        → Player / Account Layer → Simulator Integration (save/load metadata)

Product layer NEVER touches physics ticks, N-body, orbital, relativity.
Offline fallback: simulator continues if Supabase unavailable.
"""
