"""Texture manager for loading, caching, and managing textures.

Provides lazy loading and reference-counted caching to minimize
memory usage on VRAM-constrained systems.
"""

from __future__ import annotations

import hashlib
from typing import Any, Callable, Dict, List, Optional

from .texture import Texture, TextureType


class TextureManager:
    """Manages texture lifecycle with lazy loading and caching.

    Textures are loaded on first use and cached by path hash.
    Reference counting allows safe deallocation.
    """

    def __init__(self) -> None:
        self._cache: Dict[str, Texture] = {}
        self._data_cache: Dict[str, Any] = {}
        self._ref_counts: Dict[str, int] = {}
        self._loader: Optional[Callable[[str], Any]] = None
        self._max_cache_bytes: int = 512 * 1024 * 1024
        self._current_cache_bytes: int = 0

    def set_loader(self, loader: Callable[[str], Any]) -> None:
        """Set the backend texture loading function."""
        self._loader = loader

    def acquire(self, texture: Texture) -> Any:
        """Acquire a texture, loading it if necessary."""
        key = texture.compute_hash()
        key_str = str(key)
        if key_str in self._data_cache:
            self._ref_counts[key_str] = self._ref_counts.get(key_str, 0) + 1
            return self._data_cache[key_str]
        data = None
        if self._loader and texture.path:
            data = self._loader(texture.path)
        self._data_cache[key_str] = data
        self._ref_counts[key_str] = 1
        texture.loaded = True
        return data

    def release(self, texture: Texture) -> None:
        """Release a reference to a texture."""
        key_str = str(texture.compute_hash())
        if key_str in self._ref_counts:
            self._ref_counts[key_str] -= 1
            if self._ref_counts[key_str] <= 0:
                self._evict(key_str)

    def _evict(self, key_str: str) -> None:
        self._data_cache.pop(key_str, None)
        self._ref_counts.pop(key_str, None)

    def evict_all(self) -> None:
        """Clear all cached texture data."""
        self._data_cache.clear()
        self._ref_counts.clear()
        self._current_cache_bytes = 0

    @property
    def cache_size(self) -> int:
        return len(self._data_cache)

    @property
    def cache_bytes(self) -> int:
        return self._current_cache_bytes

    def generate_procedural(
        self,
        name: str,
        width: int,
        height: int,
        generator: Callable[[int, int], List[float]],
        channels: int = 4,
    ) -> Texture:
        """Generate a procedural texture using a callback."""
        tex = Texture(
            name=name,
            texture_type=TextureType.PROCEDURAL,
            size=(width, height),
            channels=channels,
        )
        data = []
        for y in range(height):
            row = []
            for x in range(width):
                pixel = generator(x, y)
                row.append(pixel)
            data.append(row)
        key_str = str(tex.compute_hash())
        self._data_cache[key_str] = data
        self._ref_counts[key_str] = 1
        tex.loaded = True
        return tex

    def create_starfield_texture(
        self,
        name: str,
        width: int = 2048,
        height: int = 1024,
        star_count: int = 5000,
        seed: int = 42,
    ) -> Texture:
        """Generate a procedural starfield texture deterministically."""
        import random
        rng = random.Random(seed)

        def gen(x, y):
            return [0.0, 0.0, 0.0, 1.0]

        tex = Texture(
            name=name,
            texture_type=TextureType.PROCEDURAL,
            size=(width, height),
            channels=4,
        )
        data = [[gen(x, y) for x in range(width)] for y in range(height)]

        for _ in range(star_count):
            sx = rng.randint(0, width - 1)
            sy = rng.randint(0, height - 1)
            brightness = rng.uniform(0.5, 1.0)
            tint = (
                rng.uniform(0.8, 1.0),
                rng.uniform(0.8, 1.0),
                rng.uniform(0.9, 1.0),
            )
            data[sy][sx] = [
                brightness * tint[0],
                brightness * tint[1],
                brightness * tint[2],
                1.0,
            ]

        key_str = str(tex.compute_hash())
        self._data_cache[key_str] = data
        self._ref_counts[key_str] = 1
        tex.loaded = True
        return tex
