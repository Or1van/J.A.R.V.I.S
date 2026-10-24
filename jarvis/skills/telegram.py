"""Telegram Desktop голосом: перейти в чат за іменем або номером, наступний/попередній чат.

Працює через клавіші Telegram Desktop (перевірено):
  Esc — закрити відкритий чат; Ctrl+F — поле пошуку над списком чатів; Enter — відкрити перший знайдений;
  Ctrl+Alt+Home — перший чат у списку; Alt+↓ / Alt+↑ — наступний / попередній чат; Ctrl+0 — Збережене.
Заголовок вікна Telegram — "Чат @ Акаунт", тож за ним видно, чи відкрився чат і який.
Писати повідомлення — звичайною командою "напиши ...": у месенджері Джарвіс перепитає, чи відправляти.
"""
import time

from jarvis.core.desktop import bring_to_front, find_window_by_process, paste_text, press, user_window
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
        time.sleep(2)  # даємо Telegram завантажити список чатів
    return bring_to_front(win)


def current_chat() -> str | None:
    """Назва відкритого чату із заголовка вікна або None, якщо чат не відкрито."""
    win = user_window()
    title = (win.title if win else "").replace("‎", "")
    return title.split(" @ ")[0].strip() if " @ " in title else None


def _close_chat() -> None:
    for _ in range(2):
        press("esc")
        time.sleep(0.4)


@tool
def telegram_open_chat(name: str) -> str:
    """Відкрити в Telegram чат з людиною, групою чи каналом за іменем.

    Args:
        name: Ім'я співрозмовника або назва чату в називному відмінку, напр. "Максим".
    """
    if not focus_telegram():
        return "Не вдалося відкрити Telegram."
    _close_chat()
    press("ctrl", "f")
    time.sleep(0.8)  # поле пошуку отримує фокус не миттєво
    press("ctrl", "a")
    press("delete")
    paste_text(name)
    time.sleep(1.5)  # Telegram шукає не миттєво
    press("enter")
    time.sleep(0.8)
    chat = current_chat()
    if chat is None:
        press("esc")
        return f"Не знайшов чат {name}."
    return f"Відкрив чат {chat}."


@tool
def telegram_open_chat_number(number: int) -> str:
    """Відкрити в Telegram чат за його номером у списку чатів (1 — найвищий).

    Args:
        number: Номер чату в списку, починаючи з 1.
    """
    if not focus_telegram():
        return "Не вдалося відкрити Telegram."
    _close_chat()
    press("ctrl", "alt", "home")
    for _ in range(max(0, number - 1)):
        time.sleep(0.35)
        press("alt", "down")
    time.sleep(0.5)
    chat = current_chat()
    return f"Відкрив чат {chat}." if chat else "Не вдалося відкрити чат."


def _chat_keys(*keys: str) -> str:
    if not focus_telegram():
        return "Не вдалося відкрити Telegram."
    press(*keys)
    time.sleep(0.5)
    chat = current_chat()
    return chat or ""


@command(rf"(?:зайди|перейди|відкрий)(?: в| у| на)? (?P<n>{ORDINAL}) {CHAT}{IN_TG}", priority=6)
def _chat_number(n):
    number = parse_ordinal(n)
    return telegram_open_chat_number(number) if number else None


@command(
    rf"(?:зайди|перейди|відкрий)(?: в| у)? {CHAT} (?:з |із |до |зі )?(?P<name>.+?){IN_TG}",
    rf"зайди до (?P<name>.+?)(?: в {CHAT})?{IN_TG}",
    rf"перейди до (?P<name>.+?) в {CHAT}{IN_TG}",
    r"(?:відкрий|покажи) (?:мої )?(?:збережене|збережені|обране|saved messages)",
    priority=5,
)
def _chat_by_name(name=None):
    if name is None:  # "Збережене"
        return _chat_keys("ctrl", "0") and "Відкрив Збережене."
    return telegram_open_chat(name_stem(name).title())


@command(rf"наступн\w* {CHAT}", priority=5)
def _next_chat():
    return _chat_keys("alt", "down")


@command(rf"попередн\w* {CHAT}", priority=5)
def _previous_chat():
    return _chat_keys("alt", "up")


@command(rf"(?:{CLOSE}|вийди з) {CHAT}", priority=5)
def _close_chat_command():
    if focus_telegram():
        _close_chat()
