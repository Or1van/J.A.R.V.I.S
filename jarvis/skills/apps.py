"""Програми та вікна: відкрити, закрити, перемкнутися, згорнути."""
import os
import re
from pathlib import Path

import psutil
import pygetwindow

from jarvis.core import runtime
from jarvis.core.desktop import bring_to_front, find_window, press, user_window
from jarvis.core.registry import CLOSE, OPEN, command, tool
from jarvis.core.text import best_match, translit

# Вбудовані програми Windows.
SYSTEM_APPS = {
    "блокнот": "notepad", "notepad": "notepad",
    "калькулятор": "calc", "calculator": "calc",
    "провідник": "explorer", "explorer": "explorer",
    "диспетчер завдань": "taskmgr", "task manager": "taskmgr",
    "налаштування": "ms-settings:", "параметри": "ms-settings:", "settings": "ms-settings:",
    "панель керування": "control",
    "paint": "mspaint", "пейнт": "mspaint",
    "командний рядок": "cmd", "cmd": "cmd",
    "powershell": "powershell", "павершел": "powershell",
    "термінал": "wt", "terminal": "wt",
}
# Як назви програм звучать українською -> як вони називаються в меню Пуск.
SPOKEN_NAMES = {
    "хром": "google chrome", "гугл хром": "google chrome", "телеграм": "telegram", "стім": "steam",
    "діскорд": "discord", "дискорд": "discord", "спотіфай": "spotify", "ворд": "word",
    "ексель": "excel", "павер поінт": "powerpoint", "фотошоп": "photoshop",
    **dict.fromkeys([
        "vs code", "vscode", "vs код", "віс код", "вс код", "в с код", "ві ес код", "візуал студіо код",
        "візуал студіо", "visual studio", "vs", "код", "code",
    ], "visual studio code"),
    "клод десктоп": "claude", "claude desktop": "claude",
    "опера": "opera", "файрфокс": "firefox", "едж": "microsoft edge", "вайбер": "viber",
    "зум": "zoom", "обс": "obs studio", "епік геймс": "epic games launcher",
}
START_MENU_DIRS = [
    Path(os.environ.get("ProgramData", r"C:\ProgramData")) / r"Microsoft\Windows\Start Menu\Programs",
    Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs",
    Path.home() / "Desktop",
    Path.home() / "OneDrive" / "Desktop",
    Path.home() / "OneDrive" / "Рабочий стол",
]
UNINSTALL_WORDS = ("uninstall", "видалити", "удалить", "удаление")
# Процеси, які не можна вбивати, щоб не "покласти" Windows. Вікна провідника закриваються як вікна.
PROTECTED_PROCESSES = {
    "system", "csrss.exe", "wininit.exe", "winlogon.exe", "lsass.exe", "services.exe",
    "smss.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "registry", "explorer.exe",
}
JARVIS_WINDOW = "J.A.R.V.I.S."


def shortcuts() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for folder in START_MENU_DIRS:
        if folder.is_dir():
            for lnk in folder.rglob("*.lnk"):
                name = lnk.stem.lower()
                if not any(w in name for w in UNINSTALL_WORDS):
                    found.setdefault(name, lnk)
    return found


@tool
def open_app(name: str) -> str:
    """Відкрити програму на комп'ютері (Telegram, Steam, Chrome, блокнот, калькулятор тощо).
    Шукає вбудовані програми Windows і ярлики в меню Пуск та на робочому столі.

    Args:
        name: Назва програми, бажано як у меню Пуск, напр. "Google Chrome", "Telegram", "блокнот".
    """
    key = name.lower().strip()
    try:
        custom = runtime.settings().apps
    except RuntimeError:
        custom = {}
    if key in custom:
        os.startfile(custom[key])
        return f"Відкриваю {name}."
    if key in SYSTEM_APPS:
        os.startfile(SYSTEM_APPS[key])
        return f"Відкриваю {name}."

    links = shortcuts()
    found = best_match(SPOKEN_NAMES.get(key, key), list(links))
    if found:
        os.startfile(links[found])
        return f"Відкриваю {links[found].stem}."
    return f"Не знайшов програму «{name}» на комп'ютері."


def _windows_titled(name: str) -> list:
    """Вікна, в заголовку яких є ця назва (кирилицею, латиницею або як у меню Пуск)."""
    key = name.lower().strip()
    variants = {v for v in (key, translit(key), SPOKEN_NAMES.get(key, key)) if len(v) >= 3}
    return [
        w for w in pygetwindow.getAllWindows()
        if w.title.strip() and w.title != JARVIS_WINDOW and any(v in w.title.lower() for v in variants)
    ]


@tool
def close_app(name: str) -> str:
    """Закрити вікно або програму: спершу шукає вікна з такою назвою в заголовку
    (напр. папку "Завантаження" в провіднику), інакше завершує процес програми.

    Args:
        name: Назва вікна, папки або програми, напр. "завантаження", "провідник", "chrome", "telegram".
    """
    windows = _windows_titled(name)
    if windows:
        for win in windows:
            win.close()
        return "Закрив." if len(windows) == 1 else f"Закрив {len(windows)} вікна."

    key = SPOKEN_NAMES.get(name.lower().strip(), name.lower().strip())
    names = {(p.info["name"] or "").lower() for p in psutil.process_iter(["name"])}
    target = best_match(key.removesuffix(".exe"), [n.removesuffix(".exe") for n in names if n], cutoff=0.7)
    if target is None:
        return f"Не знайшов вікна чи програми «{name}»."
    closed = 0
    for proc in psutil.process_iter(["name", "pid"]):
        pname = (proc.info["name"] or "").lower()
        if pname.removesuffix(".exe") == target and pname not in PROTECTED_PROCESSES and proc.info["pid"] != os.getpid():
            try:
                proc.terminate()
                closed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    return f"Закрив {target}." if closed else f"Не вдалося закрити {target}."


@tool
def list_windows() -> str:
    """Список відкритих вікон (заголовки). Корисно, щоб зрозуміти, що зараз відкрито."""
    titles = [t for t in pygetwindow.getAllTitles() if t.strip()]
    return "\n".join(titles) or "Немає відкритих вікон."


@tool
def focus_window(title: str) -> str:
    """Перейти до відкритого вікна (вивести його на передній план).

    Args:
        title: Частина заголовка вікна, напр. "Chrome", "Telegram".
    """
    win = find_window(title)
    if win is None:
        titles = [t for t in pygetwindow.getAllTitles() if t.strip()]
        match = best_match(title, titles, cutoff=0.5)
        win = find_window(match) if match else None
    if win is None:
        return f"Не знайшов вікна «{title}»."
    bring_to_front(win)
    return "Готово."


# Правило: "відкрий програму / додаток X" і "запусти X" — шукати на комп'ютері;
# просто "відкрий X" — в інтернеті (окрім вбудованих програм Windows: блокнот, калькулятор...).
APP_WORD = r"(?:програму|програма|додаток|застосунок|прогу|аплікацію)"


@command(rf"{OPEN} {APP_WORD} (?P<name>.+)", r"запуст\w* (?:програму |додаток |застосунок )?(?P<name>.+)", priority=1)
def _open_app(name):
    return open_app(name)


@command(r"відкри\w* (?P<name>.+)", priority=0)
def _open(name):
    if name in SYSTEM_APPS:
        return open_app(name)
    from jarvis.skills.web import open_site_named
    raw = re.sub(r"^\s*відкри\w*\s*", "", runtime.command_text(), flags=re.I)
    return open_site_named(raw or name)


@command(rf"{CLOSE} (?:це |поточне |активне )?вікно|{CLOSE} це", priority=5)
def _close_window():
    win = user_window()
    if win is None:
        return "Не бачу, яке вікно закрити. Назвіть його, напр. «закрий завантаження»."
    win.close()
    return "Закрив."


@command(rf"{CLOSE} (?:програму )?(?P<name>.+)", priority=0)
def _close(name):
    return close_app(name)


@command(r"(?:перейди|переключись|перемкнись|покажи) (?:на |в |до )?(?:вікно )?(?P<title>.+)", priority=-1)
def _focus(title):
    return focus_window(title)


@command(r"(?:згорни|сховай) (?:все|усе|всі вікна|усі вікна)|покажи робочий стіл", priority=5)
def _minimize_all():
    press("win", "d")


@command(r"згорни(?: це)?(?: вікно)?", priority=5)
def _minimize():
    win = user_window()
    if win:
        win.minimize()


@command(r"розгорни(?: це)?(?: вікно)?(?: на весь екран)?", priority=5)
def _maximize():
    win = user_window()
    if win:
        win.maximize()


@command(r"(?:переключи|перемкни|зміни) вікно|наступне вікно|попереднє вікно", priority=5)
def _switch_window():
    press("alt", "tab")
