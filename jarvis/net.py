"""Перевірка інтернету (з кешем, щоб не перевіряти щоразу)."""
import socket
import time

_checked_at = 0.0
_online = False


def is_online() -> bool:
    global _checked_at, _online
    if time.time() - _checked_at > 15:
        try:
            socket.create_connection(("1.1.1.1", 443), timeout=1).close()
            _online = True
        except OSError:
            _online = False
        _checked_at = time.time()
    return _online
