"""Explicit failure categories shared by the bounded research helpers."""

from __future__ import annotations

from typing import NoReturn


def invalid(message: str, *, cause: BaseException | None = None) -> NoReturn:
    """Reject an invalid experiment value without changing the error family."""
    if cause is not None:
        raise ValueError(message) from cause
    raise ValueError(message)


def wrong_type(message: str) -> NoReturn:
    """Reject a value of the wrong type before it can authorize native work."""
    raise TypeError(message)


def unavailable(message: str, *, cause: BaseException | None = None) -> NoReturn:
    """Report missing protection or a failed invariant as a nonpass."""
    if cause is not None:
        raise RuntimeError(message) from cause
    raise RuntimeError(message)


def expired(message: str, *, cause: BaseException | None = None) -> NoReturn:
    """Preserve the timeout category while retaining a proven original cause."""
    if cause is not None:
        raise TimeoutError(message) from cause
    raise TimeoutError(message)
