import functools
import time
from typing import Callable

# Petit cache mémoire simple pour éviter de spammer les APIs

def memoize_ttl(ttl_seconds: int = 600):
    def decorator(func: Callable):
        cache = {}
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in cache:
                ts, value = cache[key]
                if now - ts < ttl_seconds:
                    return value
            value = func(*args, **kwargs)
            cache[key] = (now, value)
            return value
        return wrapper
    return decorator
