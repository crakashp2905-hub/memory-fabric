"""Process-local guard for running a flow without network access.

Use :func:`offline_mode` around an operation that must stay local. It blocks
Python socket connections, datagrams and DNS lookups for the duration of the
context, then restores the previous socket behavior. It is an accidental
network-dependency guard, not an OS sandbox for subprocesses or native code.
"""
from __future__ import annotations

__stability__ = "beta"

import socket
from contextlib import ExitStack, contextmanager
from typing import Any, Callable, Iterator
from unittest.mock import patch


class NetworkAccessDenied(RuntimeError):
    """Raised when an operation tries to use a socket inside offline mode."""


def _deny(*args: Any, **kwargs: Any) -> Any:
    del args, kwargs
    raise NetworkAccessDenied("network access is disabled inside offline_mode()")


@contextmanager
def offline_mode() -> Iterator[None]:
    """Block Python DNS and socket network operations until the context exits.

    The context is process-wide while active, so do not overlap it with work
    that intentionally uses networking in another thread.
    """
    with ExitStack() as stack:
        stack.enter_context(patch("socket.create_connection", side_effect=_deny))
        stack.enter_context(patch("socket.getaddrinfo", side_effect=_deny))
        for name in ("connect", "connect_ex", "send", "sendall", "sendto"):
            original: Callable[..., Any] = getattr(socket.socket, name)

            def guarded(sock: socket.socket, *args: Any, _original: Callable[..., Any] = original,
                        **kwargs: Any) -> Any:
                if sock.family in (socket.AF_INET, socket.AF_INET6):
                    raise NetworkAccessDenied(
                        "network access is disabled inside offline_mode()")
                return _original(sock, *args, **kwargs)

            stack.enter_context(patch.object(socket.socket, name, guarded))
        yield
