"""Small in-process rate limiter for high-cost public endpoints."""

from collections import defaultdict, deque
from threading import Lock
from time import monotonic


class SlidingWindowRateLimiter:
    """Allow a bounded number of requests per key in a rolling time window.

    This is intentionally process-local. Deployments with multiple workers or
    replicas should enforce the same policy at the reverse proxy or Redis.
    """

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """Return whether a request is allowed and seconds until retry."""
        now = monotonic()
        with self._lock:
            timestamps = self._requests[key]
            cutoff = now - self.window_seconds
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            if len(timestamps) >= self.limit:
                retry_after = max(1, int(timestamps[0] + self.window_seconds - now + 0.999))
                return False, retry_after

            timestamps.append(now)
            return True, 0
