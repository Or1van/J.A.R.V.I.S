"""Файли й програми на комп'ютері: знайти файл, видалити файл (у Кошик), видалити програму.

Правило: перед будь-яким видаленням Джарвіс розповідає, ЩО саме знайшов і ЯК видалятиме,
і робить це лише після вашого "так". Файли йдуть у Кошик (їх можна відновити),
програми видаляються їхнім власним деінсталятором (з вікном, де теж можна скасувати).
"""
import ctypes
import os
import re
import subprocess
import winreg
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

from jarvis.core import runtime
from jarvis.core.registry import command, tool
from jarvis.core.text import best_match, normalize, translit

SEARCH_DIRS = {
    "робочий стіл": Path.home() / "OneDrive" / "Рабочий стол",
    "завантаження": Path.home() / "Downloads",
    "документи": Path.home() / "Documents",
    "зображення": Path.home() / "Pictures",
    "відео": Path.home() / "Videos",
    "музика": Path.home() / "Music",
}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "AppData"}
UNINSTALL_KEYS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]
# Компоненти, від яких залежать інші програми — видаляти їх зазвичай не варто
SYSTEM_PARTS = ("microsoft visual c++", ".net", "windows", "driver", "драйвер", "nvidia", "amd", "realtek",
                "intel", "runtime", "redistributable", "python")


# ---------- файли ----------

def find_files(name: str, limit: int = 3000) -> list[Path]:
    """Файли й папки, в назві яких є name (кирилицею чи латиницею), у звичних папках користувача."""
    key = normalize(name)
    variants = {v for v in (key, translit(key), key.replace(" ", "_"), key.replace(" ", "-")) if len(v) >= 2}
    found, seen = [], 0
    for root_dir in SEARCH_DIRS.values():
        if not root_dir.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
            for entry in dirnames + filenames:
                seen += 1
                if any(v in entry.lower() for v in variants):
                    found.append(Path(dirpath) / entry)
            if seen > limit * 20:
                break
    # Точніший збіг і коротша назва — вище
    return sorted(found, key=lambda p: (normalize(p.stem) != key, len(p.name)))[:5]


def _where(path: Path) -> str:
    for label, folder in SEARCH_DIRS.items():
        if folder in path.parents:
            rel = path.parent.relative_to(folder)
            return f"у папці «{label}»" + (f", {rel}" if str(rel) != "." else "")
    return f"у {path.parent}"


def _size(path: Path) -> str:
    if path.is_dir():
        return "папка"
    size = path.stat().st_size
    for unit in ("байт", "КБ", "МБ", "ГБ"):
        if size < 1024 or unit == "ГБ":
            return f"{size:.0f} {unit}" if unit == "байт" else f"{size:.1f} {unit}"
        size /= 1024


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR),
        ("pTo", wintypes.LPCWSTR), ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", wintypes.BOOL),
        ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def move_to_recycle_bin(path: Path) -> bool:
    """Переміщує файл або папку в Кошик (як клавіша Delete у провіднику)."""
    FO_DELETE, FOF_ALLOWUNDO, FOF_NOCONFIRMATION, FOF_SILENT, FOF_NOERRORUI = 3, 0x40, 0x10, 0x4, 0x400
    op = _SHFILEOPSTRUCTW(
        wFunc=FO_DELETE, pFrom=str(path) + "\0",  # список шляхів має закінчуватись подвійним нулем
        fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI,
    )
    return ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op)) == 0 and not path.exists()


@tool
def find_file(name: str) -> str:
    """Знайти файл або папку на комп'ютері (робочий стіл, завантаження, документи, зображення, відео, музика).

    Args:
        name: Назва або частина назви файлу.
    """
    found = find_files(name)
    if not found:
        return f"Не знайшов файлу «{name}»."
    first = found[0]
    more = f" Ще схожих: {len(found) - 1}." if len(found) > 1 else ""
    return f"Знайшов {first.name} {_where(first)}.{more}"


@tool
def delete_file(name: str) -> str:
    """Видалити файл або папку в Кошик. Джарвіс спершу каже, що саме знайшов, і питає підтвердження.

    Args:
        name: Назва або частина назви файлу чи папки.
    """
    found = find_files(name)
    if not found:
        return f"Не знайшов файлу «{name}», нічого не видаляю."
    path = found[0]
    changed = datetime.fromtimestamp(path.stat().st_mtime)
    others = f" Є ще {len(found) - 1} схожих, їх не чіпаю." if len(found) > 1 else ""
    runtime.say(f"Знайшов {path.name} {_where(path)}: {_size(path)}, змінено {changed:%d.%m.%Y}.{others} "
                "Я переміщу його в Кошик — звідти його можна буде відновити.")
    print(f"[видалення] {path}")
    if not runtime.confirm("Видаляти?"):
        return "Добре, нічого не видаляю."
    return "Перемістив у Кошик." if move_to_recycle_bin(path) else "Не вдалося видалити — можливо, файл відкритий."


# ---------- програми ----------

def installed_programs() -> dict[str, dict]:
    """Встановлені програми з реєстру Windows: назва -> {uninstall, publisher}."""
    programs = {}
    for hive, path in UNINSTALL_KEYS:
        try:
            root = winreg.OpenKey(hive, path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(root)[0]):
            try:
                key = winreg.OpenKey(root, winreg.EnumKey(root, i))
                values = {}
                for field in ("DisplayName", "UninstallString", "Publisher", "SystemComponent"):
                    try:
                        values[field] = winreg.QueryValueEx(key, field)[0]
                    except OSError:
                        pass
            except OSError:
                continue
            if values.get("DisplayName") and values.get("UninstallString") and not values.get("SystemComponent"):
                programs[values["DisplayName"]] = {
                    "uninstall": values["UninstallString"], "publisher": values.get("Publisher", ""),
                }
    return programs


@tool
def uninstall_program(name: str) -> str:
    """Видалити встановлену програму її власним деінсталятором. Джарвіс спершу каже, що знайшов, і питає підтвердження.

    Args:
        name: Назва програми, напр. "Telegram", "Steam".
    """
    from jarvis.skills.apps import SPOKEN_NAMES

    programs = installed_programs()
    key = normalize(name)
    found = best_match(SPOKEN_NAMES.get(key, key), list(programs), cutoff=0.6)
    if found is None:
        return f"Не знайшов встановленої програми «{name}». Нічого не видаляю."
    info = programs[found]
    publisher = f" від {info['publisher']}" if info["publisher"] else ""
    warning = (" Увага: це схоже на системний компонент, від нього можуть залежати інші програми."
               if any(part in found.lower() for part in SYSTEM_PARTS) else "")
    runtime.say(f"Знайшов програму {found}{publisher}. Я запущу її стандартний деінсталятор — "
                f"далі у вікні видалення треба буде ще раз підтвердити. Ваші файли я не чіпаю.{warning}")
    print(f"[видалення програми] {found}: {info['uninstall']}")
    if not runtime.confirm("Видаляти?"):
        return "Добре, програму не видаляю."
    subprocess.Popen(info["uninstall"], shell=True)
    return "Запустив деінсталятор. Підтвердіть видалення в його вікні."


@command(r"(?:знайди|пошукай|де) (?:файл|папку|документ) (?P<name>.+)", priority=6)
def _find(name):
    return find_file(name)


@command(r"(?:видали|зітри|прибери|викинь) (?:файл|папку|документ) (?P<name>.+)", priority=7)
def _delete(name):
    return delete_file(name)


@command(
    r"(?:видали|деінсталюй|знеси|зніми|прибери) (?:програму|додаток|застосунок|гру) (?P<name>.+)",
    r"(?:видали|знеси) (?P<name>.+?) з (?:комп'ютера|компютера|пк|ноутбука)",
    priority=7,
)
def _uninstall(name):
    return uninstall_program(re.sub(r"\s+повністю$", "", name))
