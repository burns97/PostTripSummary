"""Shared utilities for geo modules."""
import time


def interruptible_sleep(seconds: float, step: float = 0.1) -> None:
    """Sleep in small increments so KeyboardInterrupt is handled promptly on Windows."""
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(remaining, step))


# ---------------------------------------------------------------------------
# Shared LocationIQ rate limiter (2 req/sec across all endpoints)
# ---------------------------------------------------------------------------
_liq_last_request = 0.0
_LIQ_INTERVAL = 0.5  # 2 requests per second


def locationiq_throttle() -> None:
    """Wait if needed to stay within LocationIQ's 2 req/sec rate limit.

    Shared across reverse geocoding and Nearby POI calls so they don't
    step on each other's rate limit.
    """
    global _liq_last_request
    elapsed = time.monotonic() - _liq_last_request
    if elapsed < _LIQ_INTERVAL:
        interruptible_sleep(_LIQ_INTERVAL - elapsed)
    _liq_last_request = time.monotonic()
