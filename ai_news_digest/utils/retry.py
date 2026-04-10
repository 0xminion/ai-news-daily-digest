from __future__ import annotations

import functools
import logging
import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger('ai-digest')

F = TypeVar('F', bound=Callable[..., Any])


def with_retry(
    max_attempts: int = 3,
    delay: float = 5.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[F], F]:
    """Retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (default 3).
        delay: Initial delay in seconds between retries (default 5).
        backoff: Multiplier for delay after each retry (default 2).
        exceptions: Tuple of exception types to catch and retry on.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        logger.error('%s failed after %d attempts: %s', func.__name__, max_attempts, exc)
                        raise
                    logger.warning('%s attempt %d/%d failed: %s — retrying in %.1fs',
                                   func.__name__, attempt, max_attempts, exc, current_delay)
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exc  # unreachable, but keeps type checker happy
        return wrapper
    return decorator
