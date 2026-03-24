from __future__ import annotations

import math
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Optional

from fastapi import HTTPException, Request


class RateLimitService:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def enforce(self, bucket: str, *, limit: int, window_seconds: int, detail: str) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[bucket]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=429,
                    detail=detail,
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)

    def client_ip(self, request: Request) -> str:
        forwarded_for = (request.headers.get("x-forwarded-for") or "").split(",", 1)[0].strip()
        if forwarded_for:
            return forwarded_for
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def auth_bucket(self, action: str, scope: str, identifier: Optional[str]) -> str:
        normalized = (identifier or "").strip().lower() or "anonymous"
        return f"auth:{action}:{scope}:{normalized}"
