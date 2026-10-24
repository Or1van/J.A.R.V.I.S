"""Система: стан ПК, живлення, папки, час і дата, PowerShell."""
import ctypes
import subprocess
from datetime import datetime
from pathlib import Path

import psutil

from jarvis.core import runtime
from jarvis.core.registry import OPEN, command, tool

SHELL_FOLDERS = {
    "desktop": "shell:Desktop", "downloads": "shell:Downloads", "documents": "shell:Personal",
    "pictures": "shell:My Pictures", "music": "shell:My Music", "videos": "shell:My Video",
    "recycle_bin": "shell:RecycleBinFolder",
}
SPOKEN_FOLDERS = {
    "робочий стіл": "desktop", "завантаження": "downloads", "документи": "documents",
    "зображення": "pictures", "картинки": "pictures", "фото": "pictures", "музику": "music",
    "музика": "music", "відео": "videos", "кошик": "recycle_bin",
}
MONTHS = ("січня", "лютого", "березня", "квітня", "травня", "червня", "липня", "серпня",
          "вересня", "жовтня", "листопада", "грудня")
WEEKDAYS = ("понеділок", "вівторок", "середа", "четвер", "п'ятниця", "субота", "неділя")
PC = r"(?:комп'ютер|компютер|пк|ноутбук)"


@tool
def open_folder(folder: str) -> str:
    """Відкрити папку в провіднику.

    Args:
        folder: "desktop", "downloads", "documents", "pictures", "music", "videos", "recycle_bin" — або повний шлях.
    """
    target = SHELL_FOLDERS.get(folder.lower())
    if target is None:
        if not Path(folder).exists():
            return f"Папку {folder} не знайдено."
        target = folder
    subprocess.Popen(["explorer", target])
    return "Відкриваю."


@tool
def system_status() -> str:
    """Стан комп'ютера: завантаження процесора, пам'ять, батарея, вільне місце на диску C."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    parts = [
        f"Процесор завантажений на {psutil.cpu_percent(interval=0.5):.0f} відсотків",
        f"пам'ять на {mem.percent:.0f}",
        f"на диску C вільно {disk.free / 2**30:.0f} гігабайт",
    ]
    battery = psutil.sensors_battery()
    if battery:
        parts.append(f"батарея {battery.percent:.0f} відсотків{', заряджається' if battery.power_plugged else ''}")
    return ", ".join(parts) + "."


@tool
def power(action: str) -> str:
    """Керування живленням комп'ютера. Перед сном/перезавантаженням/вимкненням користувач підтверджує дію.

    Args:
        action: "lock" (заблокувати), "sleep" (сон), "restart" (перезавантажити), "shutdown" (вимкнути).
    """
    if action == "lock":
        ctypes.windll.user32.LockWorkStation()
        return ""
    commands = {
        "sleep": ("перевести комп'ютер у сон", ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]),
        "restart": ("перезавантажити комп'ютер", ["shutdown", "/r", "/t", "5"]),
        "shutdown": ("вимкнути комп'ютер", ["shutdown", "/s", "/t", "5"]),
    }
    if action not in commands:
        return f"Невідома дія {action}."
    label, cmd = commands[action]
    if not runtime.confirm(f"Точно {label}?"):
        return "Скасовано."
    subprocess.Popen(cmd)
    return f"Виконую: {label}."


@tool
def run_powershell(command: str, explanation: str) -> str:
    """Виконати команду PowerShell. Використовуй, коли жоден інший інструмент не підходить
    (дізнатися IP, створити папку тощо). Джарвіс озвучує пояснення і виконує лише після "так" користувача.

    Args:
        command: Команда PowerShell.
        explanation: Коротко українською, що саме зробить команда і що зміниться на комп'ютері.
    """
    print(f"[PowerShell] {command}")
    runtime.say(f"Хочу виконати команду: {explanation}")
    if not runtime.confirm("Виконувати?"):
        return "Користувач скасував виконання команди."
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", f"[Console]::OutputEncoding=[Text.Encoding]::UTF8; {command}"],
            capture_output=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return "Команда не завершилась за 60 секунд."
    out = result.stdout.decode("utf-8", errors="replace")
    err = result.stderr.decode("utf-8", errors="replace")
    text = (out + ("\nПОМИЛКИ:\n" + err if err.strip() else "")).strip() or "(порожній вивід)"
    return text[:4000]


@command(rf"{OPEN} (?:папку )?(?P<folder>{'|'.join(SPOKEN_FOLDERS)})", priority=4)
def _open_folder(folder):
    return open_folder(SPOKEN_FOLDERS[folder])


@command(rf"(?:заблокуй|блокуй) (?:{PC}|екран)", priority=5)
def _lock():
    return power("lock")


@command(rf"(?:вимкни|виключи) {PC}", priority=5)
def _shutdown():
    return power("shutdown")


@command(rf"(?:перезавантаж\w*|перезапусти) {PC}", priority=5)
def _restart():
    return power("restart")


@command(rf"(?:переведи|відправ) (?:{PC} )?(?:в|у) (?:сон|режим сну)|режим сну|присипи {PC}", priority=5)
def _sleep():
    return power("sleep")


@command(
    rf"(?:стан|статус) (?:системи|{PC}а?)|як (?:там )?(?:{PC}|система)|скільки (?:заряду|батареї)|заряд|батарея",
    priority=4,
)
def _status():
    return system_status()


@command(r"котра (?:зараз )?година|скільки (?:зараз )?(?:часу|годин)", priority=4)
def _time():
    return f"Зараз {datetime.now():%H:%M}."


@command(r"яке (?:сьогодні )?число|яка (?:сьогодні )?дата|який сьогодні день", priority=4)
def _date():
    now = datetime.now()
    return f"Сьогодні {WEEKDAYS[now.weekday()]}, {now.day} {MONTHS[now.month - 1]}."
