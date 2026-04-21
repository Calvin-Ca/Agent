"""Resilience patterns — retry, circuit breaker, fallback, and timeout.

Provides infrastructure-level resilience for external calls (LLM, DB, APIs).
Agent-level retry is handled by RetryMiddleware; this module covers lower-level
service calls.

Usage:
    from app.core.resilience import circuit_breaker, retry_with_backoff, with_timeout

    # Circuit breaker for LLM backend
    llm_breaker = CircuitBreaker(name="llm-vllm", failure_threshold=5, recovery_timeout=60)

    @llm_breaker
    def call_llm(prompt):
        ...

    # Retry with exponential backoff
    @retry_with_backoff(max_retries=3, base_delay=1.0)
    def fetch_data():
        ...

    # Timeout wrapper
    result = with_timeout(call_llm, timeout=30.0, args=(prompt,))
"""

from __future__ import annotations

import functools
import threading
import time
from enum import Enum
from typing import Any, Callable, TypeVar

from loguru import logger

T = TypeVar("T")


# ── Circuit Breaker ───────────────────────────────────────────────────────


class CircuitState(str, Enum):
    CLOSED = "closed"       # Normal operation, requests pass through
    OPEN = "open"           # Failures exceeded threshold, requests are rejected
    HALF_OPEN = "half_open"  # Testing recovery, limited requests allowed


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open and rejects a call."""

    def __init__(self, name: str, state: CircuitState, retry_after: float = 0):
        self.name = name
        self.state = state
        self.retry_after = retry_after
        super().__init__(f"Circuit breaker '{name}' is {state.value}")


class CircuitBreaker:
    """Circuit breaker pattern for external service calls.

    States:
        CLOSED → failures < threshold, all calls pass through
        OPEN → failures >= threshold, calls rejected for recovery_timeout seconds
        HALF_OPEN → after recovery_timeout, one trial call is allowed:
            - Success → CLOSED
            - Failure → OPEN (reset timer)

    Args:
        name: Identifier for logging and metrics.
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout: Seconds to wait before trying half-open.
        expected_exceptions: Tuple of exception types that count as failures.
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: tuple[type[Exception], ...] = (Exception,),
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("[CircuitBreaker:{}] OPEN → HALF_OPEN", self.name)
            return self._state

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state != CircuitState.CLOSED:
                logger.info("[CircuitBreaker:{}] {} → CLOSED", self.name, self._state.value)
                self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        "[CircuitBreaker:{}] {} → OPEN (failures={})",
                        self.name, self._state.value, self._failure_count,
                    )
                self._state = CircuitState.OPEN

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Use as a decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            state = self.state
            if state == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (time.time() - self._last_failure_time)
                raise CircuitBreakerError(self.name, state, max(0, retry_after))

            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except self.expected_exceptions:
                self._on_failure()
                raise

        return wrapper

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("[CircuitBreaker:{}] manually reset", self.name)


# ── Retry with Backoff ────────────────────────────────────────────────────


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 30.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator: retry a function with exponential backoff.

    Args:
        max_retries: Maximum retry attempts.
        base_delay: Initial delay in seconds.
        backoff_factor: Delay multiplier per attempt.
        max_delay: Maximum delay cap.
        retryable_exceptions: Exception types that trigger a retry.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exc = e
                    if attempt >= max_retries:
                        break
                    delay = min(base_delay * (backoff_factor ** attempt), max_delay)
                    logger.warning(
                        "[Retry:{}] attempt {}/{} failed: {} — retrying in {:.1f}s",
                        func.__name__, attempt + 1, max_retries, e, delay,
                    )
                    time.sleep(delay)
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator


# ── Timeout ───────────────────────────────────────────────────────────────


class TimeoutError(Exception):
    """Raised when a function exceeds its timeout budget."""

    def __init__(self, func_name: str, timeout: float):
        super().__init__(f"{func_name} exceeded {timeout}s timeout")


def with_timeout(func: Callable[..., T], timeout: float, args: tuple = (), kwargs: dict | None = None) -> T:
    """Execute a function with a timeout (thread-based).

    Args:
        func: The function to call.
        timeout: Maximum seconds to wait.
        args: Positional arguments.
        kwargs: Keyword arguments.

    Returns:
        The function's return value.

    Raises:
        TimeoutError: If the function doesn't complete in time.

    Note: This uses threading, so the function continues running after timeout.
          For true cancellation, use asyncio with async functions.
    """
    kwargs = kwargs or {}
    result: list[Any] = []
    exception: list[Exception] = []

    def target():
        try:
            result.append(func(*args, **kwargs))
        except Exception as e:
            exception.append(e)

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if thread.is_alive():
        raise TimeoutError(func.__name__, timeout)
    if exception:
        raise exception[0]
    return result[0]


# ── Fallback ──────────────────────────────────────────────────────────────


def with_fallback(
    primary: Callable[..., T],
    fallback: Callable[..., T],
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[..., T]:
    """Create a function that falls back to an alternative on failure.

    Args:
        primary: The preferred function to call.
        fallback: The function to call if primary fails.
        exceptions: Exception types that trigger fallback.

    Returns:
        A wrapper function that tries primary, then fallback.
    """

    @functools.wraps(primary)
    def wrapper(*args, **kwargs) -> T:
        try:
            return primary(*args, **kwargs)
        except exceptions as e:
            logger.warning("[Fallback] {} failed: {} — using fallback {}", primary.__name__, e, fallback.__name__)
            return fallback(*args, **kwargs)

    return wrapper
