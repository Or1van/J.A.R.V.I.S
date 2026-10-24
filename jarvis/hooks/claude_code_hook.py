"""Хук Claude Code: передає подію (закінчив роботу / просить дозволу) Джарвісу.

Claude Code запускає цей скрипт сам, коли його відкрив Джарвіс. Лише стандартна бібліотека Python,
щоб скрипт працював будь-яким інтерпретатором.
Використання: python claude_code_hook.py <stop|notification> <порт>
"""
import json
import sys
import urllib.request


def main() -> None:
    kind, port = sys.argv[1], sys.argv[2]
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    except ValueError:
        payload = {}
    body = json.dumps({"type": f"claude_code.{kind}", "payload": payload}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/event", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        urllib.request.urlopen(req, timeout=2).close()
    except OSError:
        pass  # Джарвіс не запущений — нічого страшного


if __name__ == "__main__":
    main()
