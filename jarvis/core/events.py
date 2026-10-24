"""Локальний сервер подій: інші програми (Claude Code, майбутні проєкти) можуть повідомляти Джарвіса.

POST http://127.0.0.1:<порт>/event  з заголовком Content-Type: application/json
і тілом {"type": "назва.події", "payload": {...}}

Захист:
  - сервер слухає лише цей комп'ютер (127.0.0.1), ззовні він недоступний;
  - запити з браузера відхиляються (є заголовок Origin або не JSON) — щоб відкрита веб-сторінка
    не могла керувати Джарвісом;
  - приймаються лише події зі списку дозволених: виконати довільну команду через сервер не можна.
"""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from jarvis.core import runtime

# Події, які можна надсилати ззовні. Навички додають свої через @runtime.on_event.
BUILTIN_EVENTS = {"jarvis.show", "jarvis.activate"}


def _allowed(kind: str) -> bool:
    return kind in BUILTIN_EVENTS or kind in runtime.EVENT_HANDLERS


class EventServer:
    def __init__(self, port: int, sink: queue.Queue):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                is_json = self.headers.get("Content-Type", "").startswith("application/json")
                if self.headers.get("Origin") or not is_json:
                    self.send_response(403)
                    self.end_headers()
                    return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not _allowed(data["type"]):
                        self.send_response(403)
                    else:
                        sink.put((data["type"], data.get("payload") or {}))
                        self.send_response(204)
                except (ValueError, KeyError, TypeError):
                    self.send_response(400)
                self.end_headers()

            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"jarvis ok")

            def log_message(self, *args):
                pass

        self.port = port
        self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)

    def start(self) -> None:
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
