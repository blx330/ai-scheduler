from app.infrastructure.demo_guard import SlidingWindowRateLimiter


def test_sliding_window_rate_limiter_allows_up_to_the_limit() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    now = 1000.0
    assert limiter.allow("ip-1", now) is True
    assert limiter.allow("ip-1", now) is True
    assert limiter.allow("ip-1", now) is True
    assert limiter.allow("ip-1", now) is False


def test_sliding_window_rate_limiter_tracks_keys_independently() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    now = 1000.0
    assert limiter.allow("ip-1", now) is True
    assert limiter.allow("ip-2", now) is True
    assert limiter.allow("ip-1", now) is False


def test_sliding_window_rate_limiter_forgets_hits_outside_the_window() -> None:
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.allow("ip-1", 1000.0) is True
    assert limiter.allow("ip-1", 1005.0) is False
    assert limiter.allow("ip-1", 1011.0) is True
