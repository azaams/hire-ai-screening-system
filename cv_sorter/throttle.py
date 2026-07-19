import functools
import time

from django.core.cache import cache
from django.http import JsonResponse


def throttle_ai_endpoint(max_calls: int = 5, period: int = 60):
    """
    Decorator that rate-limits a view to `max_calls` per `period` seconds per user.

    Returns HTTP 429 Too Many Requests with a Retry-After header when the
    limit is exceeded. Relies on Django's cache backend (LocMemCache or Redis).

    Usage:
        @login_required
        @throttle_ai_endpoint(max_calls=5, period=60)
        def my_view(request, ...):
            ...
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user_id = request.user.id
            cache_key = f"throttle:{view_func.__name__}:user:{user_id}"

            call_times: list = cache.get(cache_key, [])
            now = time.time()
            window_start = now - period

            # Discard timestamps outside the current time window
            call_times = [t for t in call_times if t > window_start]

            if len(call_times) >= max_calls:
                retry_after = int(period - (now - call_times[0]))
                response = JsonResponse(
                    {"error": "Too many requests. Please wait before trying again."},
                    status=429,
                )
                response["Retry-After"] = retry_after
                return response

            call_times.append(now)
            cache.set(cache_key, call_times, timeout=period)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
