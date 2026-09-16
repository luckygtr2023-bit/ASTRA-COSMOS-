"""ASTRA Supabase abstraction — centralized, not scattered raw calls."""
from .config import SupabaseConfig, get_config
from .client import SupabaseClient, get_client, is_available
from .auth import AuthService
from .profiles import ProfileService
from .storage import StorageService
from .saves import SaveService

__all__ = [
    "SupabaseConfig", "get_config",
    "SupabaseClient", "get_client", "is_available",
    "AuthService", "ProfileService", "StorageService", "SaveService",
]
