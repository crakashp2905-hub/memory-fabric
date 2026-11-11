"""Process-local loopback-only network guard for offline sandbox smoke tests.

This is test defense in depth, not a security boundary against native code or
direct system calls. Install it in the isolated smoke-test subprocess before
loading the code under test.
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Any

_BLOCKED: list[str] = []
_INSTALLED = False
_ORIGINAL_GETADDRINFO = socket.getaddrinfo
_ORIGINAL_CREATE_CONNECTION = socket.create_connection
_ORIGINAL_SOCKET = socket.socket


def _loopback(host: Any) -> bool:
    text = str(host).strip("[]").lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def _deny(host: Any) -> PermissionError:
    value = str(host)
    _BLOCKED.append(value)
    return PermissionError(f"offline sandbox egress denied: non-loopback host {value}")


def install() -> None:
    """Block non-loopback resolution and connection attempts in this process."""
    global _INSTALLED
    if _INSTALLED:
        return

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any):
        if not _loopback(host):
            raise _deny(host)
        rows = _ORIGINAL_GETADDRINFO(host, *args, **kwargs)
        for row in rows:
            if not _loopback(row[4][0]):
                raise _deny(row[4][0])
        return rows

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _loopback(host):
            raise _deny(host)
        return _ORIGINAL_CREATE_CONNECTION(address, *args, **kwargs)

    class LoopbackSocket(_ORIGINAL_SOCKET):
        def connect(self, address: Any) -> None:
            host = address[0] if isinstance(address, tuple) and address else address
            if not _loopback(host):
                raise _deny(host)
            return super().connect(address)

        def connect_ex(self, address: Any) -> int:
            host = address[0] if isinstance(address, tuple) and address else address
            if not _loopback(host):
                raise _deny(host)
            return super().connect_ex(address)

    socket.getaddrinfo = guarded_getaddrinfo
    socket.create_connection = guarded_create_connection
    socket.socket = LoopbackSocket
    _INSTALLED = True


def blocked_attempts() -> tuple[str, ...]:
    """Return denied destination strings for the smoke-test assertion."""
    return tuple(_BLOCKED)
