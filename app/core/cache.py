import asyncio
import time
from typing import Any, Dict, NamedTuple


class CacheEntry(NamedTuple):
    value: Any
    expires_at: float


class AsyncTTLCache:
    """
    Caché en memoria asíncrono con TTL individual por entrada y soporte
    para invalidación y limpieza preventiva de expirados.
    """

    def __init__(self, default_ttl_seconds: int = 86400):
        self.default_ttl_seconds = default_ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Any | None:
        """
        Recupera un valor de la caché. Si expiró, lo elimina y retorna None.
        """
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None

            now = time.monotonic()
            if now >= entry.expires_at:
                del self._cache[key]
                return None

            return entry.value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """
        Guarda un valor en la caché con un TTL específico o el default.
        """
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds
        expires_at = time.monotonic() + ttl
        async with self._lock:
            self._cache[key] = CacheEntry(value=value, expires_at=expires_at)

    async def clear(self) -> None:
        """
        Vacía toda la caché.
        """
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> None:
        """
        Elimina todas las claves que hayan superado su TTL.
        """
        now = time.monotonic()
        async with self._lock:
            expired_keys = [
                k for k, entry in self._cache.items() if now >= entry.expires_at
            ]
            for k in expired_keys:
                del self._cache[k]

    @property
    def size(self) -> int:
        return len(self._cache)
