"""Низькорівневі дії з робочим столом Windows, спільні для різних навичок."""
import ctypes
import os
import threading
import time

import psutil
import pygetwindow
import pyperclip

_user32 = ctypes.windll.user32
# Вікна самого Джарвіса: на них не можна друкувати й натискати клавіші "для користувача".
OWN_TITLES = ("J.A.R.V.I.S.",)
OWN_TITLE_PARTS = ("jarvis.bat", "main.py")

_last_user_hwnd = 0


KEYUP, EXTENDED = 0x2, 0x1
# Коди клавіш Windows. Літери й цифри — за кодом символу ("v" -> 0x56), тому комбінації
# працюють за будь-якої розкладки (pyautogui в українській розкладці не знаходить латинських літер).
VK = {
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "enter": 0x0D, "esc": 0x1B, "tab": 0x09,
    "space": 0x20, "backspace": 0x08, "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "=": 0xBB, "-": 0xBD, **{f"f{i}": 0x6F + i for i in range(1, 13)},
}
# Клавіші, які без цього прапорця Windows сприймає як клавіші цифрового блоку.
EXTENDED_KEYS = {"delete", "insert", "home", "end", "pageup", "pagedown", "left", "up", "right", "down", "win"}


def _vk(key: str) -> int:
    key = key.lower()
    if key in VK:
        return VK[key]
    if len(key) == 1 and key.isascii() and key.isalnum():
        return ord(key.upper())
    raise ValueError(f"Невідома клавіша: {key}")


def press(*keys: str) -> None:
    """Натискає клавішу або комбінацію в активному вікні: press("ctrl", "v"), press("enter")."""
    codes = [(_vk(k), k.lower() in EXTENDED_KEYS) for k in keys]
    for code, ext in codes:
        _user32.keybd_event(code, 0, EXTENDED if ext else 0, 0)
        time.sleep(0.01)
    for code, ext in reversed(codes):
        _user32.keybd_event(code, 0, (EXTENDED if ext else 0) | KEYUP, 0)
        time.sleep(0.01)
    time.sleep(0.05)


def press_vk(code: int, times: int = 1) -> None:
    """Натискає віртуальну клавішу Windows (медіа-клавіші, гучність)."""
    for _ in range(times):
        _user32.keybd_event(code, 0, 0, 0)
        _user32.keybd_event(code, 0, KEYUP, 0)
        time.sleep(0.01)


def window_title(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(512)
    _user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def window_process(hwnd: int) -> str:
    """Назва процесу вікна в нижньому регістрі, напр. "telegram.exe"."""
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return psutil.Process(pid.value).name().lower()
    except psutil.Error:
        return ""


def _is_own(hwnd: int) -> bool:
    title = window_title(hwnd)
    if title in OWN_TITLES or any(p in title.lower() for p in OWN_TITLE_PARTS):
        return True
    pid = ctypes.c_ulong()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid() or hwnd == ctypes.windll.kernel32.GetConsoleWindow()


def start_tracking() -> None:
    """Фоном запам'ятовує останнє вікно, з яким працював користувач (не вікно Джарвіса).
    Потрібно, бо коли ви натискаєте "Говорити", фокус переходить у вікно Джарвіса."""
    def loop():
        global _last_user_hwnd
        while True:
            hwnd = _user32.GetForegroundWindow()
            if hwnd and window_title(hwnd).strip() and not _is_own(hwnd):
                _last_user_hwnd = hwnd
            time.sleep(0.3)
    threading.Thread(target=loop, daemon=True).start()


def user_window():
    """Вікно, з яким зараз працює користувач (активне або останнє активне, якщо зараз активний Джарвіс)."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd or _is_own(hwnd):
        hwnd = _last_user_hwnd
    if not hwnd or not _user32.IsWindow(hwnd):
        return None
    return pygetwindow.Win32Window(hwnd)


def focus_user_window():
    """Перед друком чи гарячими клавішами повертає фокус у вікно користувача. Повертає це вікно."""
    win = user_window()
    if win is not None and win._hWnd != _user32.GetForegroundWindow():
        bring_to_front(win)
    return win


def find_window(title_part: str):
    title_part = title_part.lower()
    for win in pygetwindow.getAllWindows():
        if win.title.strip() and title_part in win.title.lower():
            return win
    return None


def find_window_by_process(process: str):
    """Головне вікно програми за назвою процесу, напр. "telegram.exe".
    Беремо найбільше видиме: у багатьох програм є приховані службові вікна з заголовками."""
    candidates = [
        w for w in pygetwindow.getAllWindows()
        if w.title.strip() and _user32.IsWindowVisible(w._hWnd) and window_process(w._hWnd) == process
    ]
    return max(candidates, key=lambda w: w.width * w.height, default=None)


def bring_to_front(win) -> bool:
    """Виводить вікно на передній план.
    Windows не дає фоновим програмам красти фокус, тому тимчасово "приєднуємось" до потоку
    активного вікна (AttachThreadInput) — так SetForegroundWindow дозволено без натискання клавіш.
    (Натискання Alt не підходить: у Chrome та провіднику воно відкриває меню.)"""
    hwnd = win._hWnd
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    if _user32.GetForegroundWindow() != hwnd:
        foreground_thread = _user32.GetWindowThreadProcessId(_user32.GetForegroundWindow(), None)
        own_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        _user32.AttachThreadInput(own_thread, foreground_thread, True)
        _user32.SetForegroundWindow(hwnd)
        _user32.BringWindowToTop(hwnd)
        _user32.AttachThreadInput(own_thread, foreground_thread, False)
    if _user32.GetForegroundWindow() != hwnd:
        try:  # запасний спосіб
            win.minimize()
            win.restore()
        except Exception:
            return False
    time.sleep(0.25)
    return _user32.GetForegroundWindow() == hwnd


def hotkey(*keys: str) -> None:
    """Гаряча клавіша у вікні користувача (а не у вікні Джарвіса)."""
    focus_user_window()
    press(*keys)


def paste_text(text: str) -> None:
    """Вставляє текст в активне вікно через буфер обміну (працює з кирилицею)."""
    try:
        old = pyperclip.paste()
    except pyperclip.PyperclipException:
        old = None
    pyperclip.copy(text)
    time.sleep(0.05)
    press("ctrl", "v")
    time.sleep(0.3)
    if old is not None:
        pyperclip.copy(old)
