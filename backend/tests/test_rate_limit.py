"""Tests for public chat request limiting."""

from src.core.rate_limit import SlidingWindowRateLimiter


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)

    assert limiter.allow("198.51.100.10")[0]
    assert limiter.allow("198.51.100.10")[0]
    allowed, retry_after = limiter.allow("198.51.100.10")

    assert not allowed
    assert retry_after >= 1


def test_rate_limiter_keeps_sources_separate() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)

    assert limiter.allow("198.51.100.10")[0]
    assert limiter.allow("198.51.100.11")[0]
