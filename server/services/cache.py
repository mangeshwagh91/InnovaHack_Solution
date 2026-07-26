"""
Simple in-memory TTL cache — DCPI.
Zero external dependencies. Thread-safe via a lock.

Usage:
    from services.cache import cache

    # Set
    cache.set("dashboard_summary", data, ttl=300)

    # Get (returns None if missing or expired)
    data = cache.get("dashboard_summary")

    # Decorator
    @cache.cached("my_key", ttl=60)
    def expensive_fn(): ...
"""

import time
import threading
import logging
import hashlib
import json
from typing import Any, Optional, Callable
from functools import wraps

logger = logging.getLogger(__name__)


class TTLCache:
    """
    Thread-safe in-memory TTL cache backed by a plain dict.
    Expired entries are evicted lazily on access and periodically on sweep.
    """

    def __init__(self, default_ttl: int = 300, max_size: int = 256):
        self._store: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)
        self._lock = threading.Lock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    # ── Core API ──────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + ttl
        with self._lock:
            # Evict oldest entry if over capacity
            if len(self._store) >= self._max_size and key not in self._store:
                self._evict_oldest()
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def invalidate_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix. Returns count deleted."""
        with self._lock:
            keys_to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_delete:
                del self._store[k]
            return len(keys_to_delete)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def sweep(self) -> int:
        """Remove all expired entries. Returns count removed."""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if now > exp]
            for k in expired:
                del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": round(
                    self._hits / max(1, self._hits + self._misses) * 100, 1
                ),
            }

    # ── Decorator ─────────────────────────────────────────────────────────────

    def cached(self, key_prefix: str, ttl: Optional[int] = None):
        """
        Decorator that caches the return value of a sync function.

            @cache.cached("dashboard_summary", ttl=300)
            def get_summary(): ...
        """
        def decorator(fn: Callable):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                cache_key = f"{key_prefix}_{make_cache_key(args, kwargs)}"
                cached_val = self.get(cache_key)
                if cached_val is not None:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return cached_val
                result = fn(*args, **kwargs)
                if result is not None:
                    self.set(cache_key, result, ttl=ttl)
                return result
            return wrapper
        return decorator

    def cached_async(self, key_prefix: str, ttl: Optional[int] = None):
        """
        Decorator that caches the return value of an async function.

            @cache.cached_async("dashboard_summary", ttl=300)
            async def get_summary(): ...
        """
        def decorator(fn: Callable):
            @wraps(fn)
            async def wrapper(*args, **kwargs):
                cache_key = f"{key_prefix}_{make_cache_key(args, kwargs)}"
                cached_val = self.get(cache_key)
                if cached_val is not None:
                    logger.debug(f"Cache HIT: {cache_key}")
                    return cached_val
                result = await fn(*args, **kwargs)
                if result is not None:
                    self.set(cache_key, result, ttl=ttl)
                return result
            return wrapper
        return decorator

    # ── Internal ──────────────────────────────────────────────────────────────

    def _evict_oldest(self) -> None:
        """Evict the entry with the earliest expiry. Call with lock held."""
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]


# Shared singleton — import this everywhere
cache = TTLCache(default_ttl=300, max_size=256)


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_cache_key(*parts: Any) -> str:
    """
    Build a stable cache key from arbitrary parts by hashing their JSON repr.
    Useful for argument-dependent keys.

        key = make_cache_key("rfi_query", query_text)
        key = make_cache_key("compliance", po_id)
    """
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()
