"""RealtimeService — product metadata only, NEVER physics ticks.

Allowed:
  lobby presence / player presence / notifications / account state
Forbidden:
  every physics tick / particle / N-body / renderer frame / GPU state
"""
from __future__ import annotations
from typing import Callable, Optional, Any
from .client import get_client

class RealtimeService:
    def __init__(self):
        self.client = get_client()

    def subscribe_profiles(self, callback: Callable[[Any], None]):
        if not self.client.is_available:
            raise RuntimeError("Realtime unavailable offline")
        # supabase-py realtime: client.realtime.channel(...).on_postgres_changes(...).subscribe
        try:
            channel = self.client.native.channel("profiles")
            channel.on_postgres_changes(event="*", schema="public", table="profiles", callback=callback).subscribe()
            return channel
        except Exception as e:
            raise RuntimeError(str(e)) from e

    def subscribe_sessions(self, callback: Callable[[Any], None]):
        if not self.client.is_available:
            raise RuntimeError("Realtime unavailable offline")
        try:
            channel = self.client.native.channel("player_sessions")
            channel.on_postgres_changes(event="*", schema="public", table="player_sessions", callback=callback).subscribe()
            return channel
        except Exception as e:
            raise RuntimeError(str(e)) from e

    @staticmethod
    def forbidden_warning() -> str:
        return "Realtime MUST NOT be used for physics ticks / particles / N-body / renderer frames / GPU state"
