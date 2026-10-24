"""Telegram Desktop голосом: перейти в чат за іменем або номером, наступний/попередній чат.

Працює через клавіатуру Telegram Desktop:
  Esc — закрити відкритий чат; Ctrl+F — поле пошуку над списком чатів;
  у полі пошуку стрілка ↓ вибирає чати по черзі, Enter — відкриває вибраний (або перший знайдений);
  Alt+↓ / Alt+↑ — наступний / попередній чат.
Писати повідомлення — звичайною командою "напиши ...": у месенджері Джарвіс перепитає, чи відправляти.
"""
import time

from jarvis.core.desktop import bring_to_front, find_window_by_process, paste_text, press
from jarvis.core.registry import CLOSE, command, tool
from jarvis.core.text import ORDINAL, name_stem, parse_ordinal
from jarvis.skills.apps import open_app

PROCESS = "telegram.exe"
CHAT = r"(?:чат\w*|діалог\w*|переписк\w*)"
IN_TG = r"(?: (?:в|у) (?:телеграм\w*|telegram))?"


def focus_telegram() -> bool:
    """Виводить Telegram на передній план; якщо він закритий — запускає."""
    win = find_window_by_process(PROCESS)
    if win is None:
        open_app("telegram")
        for _ in range(40):
            time.sleep(0.25)
            win = find_window_by_process(PROCESS)
            if win is not None:
                break
        else:
            return False
        time.sleep(1.5)  # даємо Telegram завантажити список чатів
    return bring_to_front(win)


@tool
def telegram_open_chat(name: str) -> str:
    """Відкрити в Telegram чат з людиною, групою чи каналом за іменем.

    Args:
        name: Ім'я співрозмовника або назва чату, напр. "Богдан".
    """
    if not _open_search():
        return "Не вдалося відкрити Telegram."
    paste_text(name)
    time.sleep(1.2)  # Telegram шукає не миттєво
    press("enter")
    return f"Відкриваю чат {name}."


def _open_search() -> bool:
    """Telegram спереду, відкритий чат закрито, курсор у порожньому полі пошуку над списком чатів."""
    if not focus_telegram():
        return False
    for _ in range(2):
        press("esc")
        time.sleep(0.15)
    press("ctrl", "f")
    time.sleep(0.3)
    press("ctrl", "a")  # якщо в полі пошуку вже щось було
    press("delete")
    return True


@tool
def telegram_open_chat_number(number: int) -> str:
    """Відкрити в Telegram чат за його номером у списку чатів (1 — найвищий).

    Args:
        number: Номер чату в списку, починаючи з 1.
    """
    if not _open_search():
        return "Не вдалося відкрити Telegram."
    for _ in range(max(1, number)):
        press("down")
        time.sleep(0.1)
    press("enter")
    return ""


def _chat_keys(*keys: str):
    if not focus_telegram():
        return "Не вдалося відкрити Telegram."
    press(*keys)


@command(rf"(?:зайди|перейди|відкрий)(?: в| у| на)? (?P<n>{ORDINAL}) {CHAT}{IN_TG}", priority=6)
def _chat_number(n):
    number = parse_ordinal(n)
    return telegram_open_chat_number(number) if number else None


@command(
    rf"(?:зайди|перейди|відкрий)(?: в| у)? {CHAT} (?:з |із |до |зі )?(?P<name>.+?){IN_TG}",
    rf"зайди до (?P<name>.+?)(?: в {CHAT})?{IN_TG}",
    rf"перейди до (?P<name>.+?) в {CHAT}{IN_TG}",
    priority=5,
)
def _chat_by_name(name):
    return telegram_open_chat(name_stem(name).title())


@command(rf"наступн\w* {CHAT}", priority=5)
def _next_chat():
    return _chat_keys("alt", "down")


@command(rf"попередн\w* {CHAT}", priority=5)
def _previous_chat():
    return _chat_keys("alt", "up")


@command(rf"(?:{CLOSE}|вийди з) {CHAT}", priority=5)
def _close_chat():
    return _chat_keys("esc")
