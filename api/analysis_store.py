"""Stockage mémoire borné des analyses nécessaires aux suivis."""

from __future__ import annotations

import secrets
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StoredAnalysis:
    response: dict[str, Any]
    request: dict[str, Any]
    expires_at: float


class AnalysisStore:
    """Cache local mono-processus; son contenu disparaît au redémarrage."""

    def __init__(self, *, max_entries: int = 100, ttl_seconds: int = 3600) -> None:
        self.max_entries = max_entries
        self.ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, StoredAnalysis] = OrderedDict()
        self._lock = threading.Lock()

    def put(self, response: dict[str, Any], request: dict[str, Any]) -> str:
        identifier = secrets.token_urlsafe(24)
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            self._entries[identifier] = StoredAnalysis(
                deepcopy(response), deepcopy(request), now + self.ttl_seconds
            )
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        return identifier

    def get(self, identifier: str) -> StoredAnalysis | None:
        now = time.monotonic()
        with self._lock:
            self._purge(now)
            item = self._entries.get(identifier)
            if item is None:
                return None
            self._entries.move_to_end(identifier)
            return StoredAnalysis(
                deepcopy(item.response), deepcopy(item.request), item.expires_at
            )

    def _purge(self, now: float) -> None:
        expired = [key for key, item in self._entries.items() if item.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
