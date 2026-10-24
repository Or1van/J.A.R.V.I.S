"""Локальний сервер подій: інші програми (Claude Code, майбутні проєкти) можуть повідомляти Джарвіса.

POST http://127.0.0.1:<порт>/event  з JSON {"type": "назва.події", "payload": {...}}
Сервер слухає лише цей комп'ютер (127.0.0.1), ззовні він недоступний.
"""
import json
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class EventServer:
    def __init__(self, port: int, sink: queue.Queue):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                    sink.put((data["type"], data.get("payload") or {}))
                    self.send_response(204)
                except (ValueError, KeyError):
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
