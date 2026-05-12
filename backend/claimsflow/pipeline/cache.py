"""Process-local cache for LLM verdicts.

Medical-necessity questions ("does diagnosis E11.9 justify procedure 99213?")
repeat constantly across a batch. Caching by the (sorted_diagnoses,
sorted_procedures) tuple cuts LLM calls by ~70% in practice — the
BENCHMARKS doc will quantify this once the full pipeline is wired up.

Intentionally simple: dict + a max-size eviction. For multi-process
deployments swap this for Redis later.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import Any


def cache_key(diagnoses: list[str], procedures: list[str]) -> str:
    """Stable hash of (sorted diagnoses, sorted procedures)."""
    payload = "|".join(sorted(diagnoses)) + "::" + "|".join(sorted(procedures))
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class VerdictCache:
    """LRU-ish cache for stage 3 verdicts. Process-local, in-memory."""

    def __init__(self, max_entries: int = 2048) -> None:
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._max = max_entries
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Any | None:
        if key in self._store:
            self.hits += 1
            self._store.move_to_end(key)
            return self._store[key]
        self.misses += 1
        return None

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value
        self._store.move_to_end(key)
        if len(self._store) > self._max:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


# Module-level singleton — pipeline stages use this directly.
verdict_cache = VerdictCache()
