"""Доступ до запущеного асистента з будь-якої навички: говорити, слухати, підтверджувати, події."""
from collections import defaultdict
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from jarvis.core.assistant import Assistant, Mode
    from jarvis.settings import Settings

# Обробники подій від зовнішніх програм (напр. "claude_code.stop" від хуків Claude Code).
EVENT_HANDLERS: dict[str, list[Callable[[dict], None]]] = defaultdict(list)

_assistant: "Assistant | None" = None


def bind(assistant: "Assistant") -> None:
    global _assistant
    _assistant = assistant


def assistant() -> "Assistant":
    if _assistant is None:
        raise RuntimeError("Асистент ще не запущений")
    return _assistant


def settings() -> "Settings":
    return assistant().settings


def say(text: str) -> None:
    assistant().say(text)


def listen(timeout: float = 8.0) -> str | None:
    return assistant().listen(timeout)


def confirm(question: str) -> bool:
    return assistant().confirm(question)


def command_text() -> str:
    """Точний текст поточної команди (з великими літерами й розділовими знаками), без "Джарвіс"."""
    return assistant().command_text()


def set_mode(mode: "Mode | None") -> None:
    assistant().mode = mode


def on_event(kind: str):
    def decorator(fn):
        EVENT_HANDLERS[kind].append(fn)
        return fn
    return decorator
