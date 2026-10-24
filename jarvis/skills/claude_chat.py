"""Claude (десктопний застосунок): "запитай у Клода" -> відкривається новий чат.

Застосунок реєструє посилання claude://, і claude://claude.ai/new відкриває в ньому новий чат.
Працює за вашою підпискою, без API. Для роботи з кодом — навичка claude_code (термінал).
"""
import os
import re
import time

from jarvis.core import runtime
from jarvis.core.desktop import bring_to_front, find_window_by_process, paste_text
from jarvis.core.registry import OPEN, command, tool

CLAUDE = r"(?:клод\w*|клауд\w*|claude)"


@tool
def open_claude_chat(question: str = "") -> str:
    """Відкрити новий чат у десктопному застосунку Claude (для питань, де потрібна розмова текстом, а не код).

    Args:
        question: Питання, яке вставити в поле чату (не відправляється). Порожньо — лише відкрити чат.
    """
    try:
        os.startfile("claude://claude.ai/new")
    except OSError:
        return "Застосунок Claude не встановлений."
    win = None
    for _ in range(40):  # чекаємо вікно до 10 секунд (якщо застосунок ще не був запущений)
        time.sleep(0.25)
        win = find_window_by_process("claude.exe")
        if win is not None:
            break
    if win is None:
        return "Не вдалося відкрити Claude."
    time.sleep(1.5)  # новий чат завантажується
    bring_to_front(win)
    if question:
        paste_text(question)
        return "Відкрив новий чат і вставив питання. Скажіть «відправ», щоб надіслати."
    return "Відкрив новий чат у Claude."


@command(
    rf"(?:запитай|спитай|питання|запитаю|спитаю)(?: в| у)? {CLAUDE}(?: (?P<question>.+))?",
    rf"(?:{OPEN}|новий)(?: новий)?(?: чат)?(?: в| у)? {CLAUDE}(?: чат)?",
    priority=7,
)
def _ask_claude(question=None):
    raw = ""
    if question:
        raw = re.sub(rf"^.*?{CLAUDE}[\s,:]*", "", runtime.command_text(), count=1, flags=re.I).strip() or question
    return open_claude_chat(raw)
