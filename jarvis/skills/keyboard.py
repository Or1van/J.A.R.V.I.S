"""Клавіатура: надрукувати текст, натиснути клавіші, стандартні комбінації.
Усе відбувається у вікні, з яким ви працюєте, навіть якщо щойно натискали кнопку у вікні Джарвіса."""
import re


from jarvis.core import runtime
from jarvis.core.desktop import focus_user_window, hotkey, paste_text, press, window_process
from jarvis.core.registry import NotHandled, command, tool

# У месенджерах перед відправленням Джарвіс перепитує — щоб помилка розпізнавання не пішла людям.
MESSENGERS = {"telegram.exe", "viber.exe", "discord.exe", "whatsapp.exe", "signal.exe", "slack.exe"}

SPOKEN_KEYS = {
    "ентер": "enter", "інтер": "enter", "enter": "enter", "пробіл": "space", "таб": "tab",
    "ескейп": "esc", "escape": "esc", "есц": "esc", "делит": "delete", "видалити": "delete",
    "бекспейс": "backspace", "вгору": "up", "вниз": "down", "вліво": "left", "ліворуч": "left",
    "вправо": "right", "праворуч": "right", "home": "home", "енд": "end",
}
SHORTCUTS = {
    r"(?:скопіюй|копіюй|копіювати)": ("ctrl", "c"),
    r"(?:встав|вставити|встав текст)": ("ctrl", "v"),
    r"(?:виріж|вирізати)": ("ctrl", "x"),
    r"(?:виділи|виділити) (?:все|усе)": ("ctrl", "a"),
    r"(?:відміни|скасуй) (?:дію|останню дію)": ("ctrl", "z"),
    r"(?:збережи|зберегти)(?: файл)?": ("ctrl", "s"),
    r"(?:видали|стери) (?:слово|останнє слово)": ("ctrl", "backspace"),
}
SEND_SUFFIX = re.compile(r"[\s,]*(?:і|та|й)\s+(?:відправ|надішли)\w*[.!]?\s*$", re.I)


@tool
def type_text(text: str, send: bool = False) -> str:
    """Надрукувати текст у вікні, з яким працює користувач (там, де стоїть курсор). Підтримує кирилицю.

    Args:
        text: Текст, який треба надрукувати.
        send: Чи натиснути Enter після друку (відправити повідомлення, виконати пошук).
    """
    win = focus_user_window()
    paste_text(text)
    if send:
        press("enter")
        return "Відправив."
    if win is not None and window_process(win._hWnd) in MESSENGERS:
        if runtime.confirm("Написав. Відправити?"):
            focus_user_window()
            press("enter")
            return "Відправив."
        return "Добре, не відправляю."
    return "Надрукував."


@tool
def press_keys(keys: str) -> str:
    """Натиснути клавішу або комбінацію клавіш у вікні користувача.
    Приклади: "enter", "ctrl+c", "alt+tab", "alt+f4", "win+d" (згорнути все), "ctrl+shift+esc", "f5".

    Args:
        keys: Клавіші через "+", як у прикладах.
    """
    parts = [k.strip().lower() for k in keys.split("+") if k.strip()]
    if not parts:
        return "Не вказано клавіш."
    hotkey(*parts)
    return ""


@command(r"(?:надрукуй|напиши|введи) (?P<text>.+)", priority=1)
def _type(text):
    # Беремо точний текст (з великими літерами й розділовими знаками), без слова "напиши"
    raw = re.sub(r"^\s*(?:надрукуй|напиши|введи)\w*[\s,:]*", "", runtime.command_text(), flags=re.I) or text
    send = bool(SEND_SUFFIX.search(raw))
    return type_text(SEND_SUFFIX.sub("", raw), send=send)


@command(r"(?:відправ|надішли)(?: повідомлення| це| його)?", priority=3)
def _send():
    hotkey("enter")
    return "Відправив."


@command(r"натисни (?P<key>.+)", priority=1)
def _press(key):
    if key not in SPOKEN_KEYS:
        raise NotHandled
    return press_keys(SPOKEN_KEYS[key])


def _register_shortcuts():
    for pattern, keys in SHORTCUTS.items():
        command(pattern, priority=4)(lambda keys=keys: hotkey(*keys))


_register_shortcuts()
