"""Локальний мозок через Ollama (https://ollama.com) — працює без інтернету й безкоштовно.

Потрібно: встановити Ollama і завантажити модель (напр. `ollama pull qwen3:4b`),
назву моделі вказати в settings.json -> local_model.
"""
import json
import re
import time
import urllib.error
import urllib.request
from typing import Callable

from jarvis.brains.prompt import SYSTEM_PROMPT, timestamp
from jarvis.core import registry
from jarvis.settings import Settings

MAX_STEPS = 8


class LocalBrain:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.messages: list[dict] = []
        self.last_activity = 0.0
        self._available = (0.0, False)

    def reset(self) -> None:
        self.messages = []

    def available(self) -> bool:
        checked_at, ok = self._available
        if time.time() - checked_at < 10:
            return ok
        try:
            tags = self._request("/api/tags", None, timeout=0.5)
            names = {m["name"] for m in tags.get("models", [])}
            model = self.settings.local_model
            ok = model in names or f"{model}:latest" in names
        except (OSError, ValueError):
            ok = False
        self._available = (time.time(), ok)
        return ok

    def ask(self, text: str, on_text: Callable[[str], None]) -> None:
        if time.time() - self.last_activity > self.settings.idle_reset_minutes * 60 or len(self.messages) > 60:
            self.reset()
        self.last_activity = time.time()
        self.messages.append({"role": "user", "content": f"{timestamp()} {text}"})

        tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in registry.TOOLS.values()
        ]
        try:
            for _ in range(MAX_STEPS):
                response = self._request("/api/chat", {
                    "model": self.settings.local_model,
                    "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *self.messages],
                    "tools": tools,
                    "stream": False,
                }, timeout=180)
                message = response["message"]
                self.messages.append(message)
                content = re.sub(r"<think>.*?</think>", "", message.get("content") or "", flags=re.S).strip()
                if content:
                    on_text(content)
                calls = message.get("tool_calls") or []
                if not calls:
                    return
                for call in calls:
                    fn = call["function"]
                    args = fn.get("arguments") or {}
                    if isinstance(args, str):
                        args = json.loads(args)
                    result = registry.call_tool(fn["name"], args)
                    self.messages.append({"role": "tool", "tool_name": fn["name"], "content": result})
        except (OSError, ValueError, KeyError) as e:
            print(f"[локальна модель: {e}]")
            on_text("Локальна модель не відповідає.")
        finally:
            self.last_activity = time.time()

    def _request(self, path: str, payload: dict | None, timeout: float) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            self.settings.ollama_url + path, data=data, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
