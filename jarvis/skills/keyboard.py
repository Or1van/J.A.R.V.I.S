"""Клавіатура: надрукувати текст, натиснути клавіші, стандартні комбінації.
Усе відбувається у вікні, з яким ви працюєте, навіть якщо щойно натискали кнопку у вікні Джарвіса."""
import re


from jarvis.core import runtime
from jarvis.core.desktop import focus_user_window, hotkey, paste_text, press, window_process
from jarvis.core.registry import NotHandled, command, tool

# У месенджерах перед відправленням Джарвіс перепитує — щоб помилка розпізнавання не пішла людям.
MESSENGERS = {"telegram.exe", "viber.exe", "discord.exe", "whatsapp.exe", "signal.exe", "slack.exe"}

SPOKEN_KEYS = {
    "ентер": "enter", "інтер": "enter", "enter": "enter", "пробіл": "space", "space": "space",
    "таб": "tab", "tab": "tab", "табуляція": "tab",
    "ескейп": "esc", "escape": "esc", "esc": "esc", "есц": "esc", "ескейв": "esc",
    "делит": "delete", "деліт": "delete", "delete": "delete", "видалити": "delete",
    "бекспейс": "backspace", "backspace": "backspace", "вгору": "up", "вниз": "down", "вліво": "left",
    "ліворуч": "left", "вправо": "right", "праворуч": "right", "home": "home", "хоум": "home", "енд": "end",
    "end": "end", "пейдж даун": "pagedown", "пейдж ап": "pageup",
    # модифікатори
    "альт": "alt", "alt": "alt", "контрол": "ctrl", "контрл": "ctrl", "контроль": "ctrl", "ctrl": "ctrl",
    "control": "ctrl", "цтрл": "ctrl", "шифт": "shift", "shift": "shift", "він": "win", "win": "win",
    "віндовс": "win", "windows": "win", "вінда": "win", "пуск": "win",
}
# Як вимовляють латинські літери: "контрол сі" = Ctrl+C
SPOKEN_LETTERS = {
    "ей": "a", "бі": "b", "сі": "c", "ді": "d", "і": "e", "еф": "f", "джі": "g", "ейч": "h", "ай": "i",
    "джей": "j", "кей": "k", "ел": "l", "ем": "m", "ен": "n", "оу": "o", "пі": "p", "кʼю": "q", "к'ю": "q",
    "ар": "r", "ес": "s", "ті": "t", "ю": "u", "ві": "v", "дабл ю": "w", "ікс": "x", "уай": "y", "зет": "z",
    # кирилиця, схожа на латиницю (так інколи пише розпізнавання): "альт ф4", "контрол с"
    "а": "a", "с": "c", "в": "v", "х": "x", "з": "z", "т": "t", "ф": "f", "р": "r", "н": "n", "к": "k",
    "д": "d", "е": "e", "о": "o", "м": "m", "л": "l", "п": "p",
}


def parse_keys(spoken: str) -> list[str] | None:
    """"альт таб" -> ["alt", "tab"], "контрол шифт ескейп" -> [...], "alt f4" -> ["alt", "f4"]. None — не клавіші."""
    text = re.sub(r"\s*(?:\bплюс\b|\+|-|\bі\b|\bта\b|\bй\b)\s*", " ", spoken.lower()).strip()
    text = re.sub(r"\bф\s*(\d{1,2})\b", r"f\1", text)  # "ф 4" / "ф4" -> f4
    words, keys, i = text.split(), [], 0
    while i < len(words):
        two = " ".join(words[i:i + 2])
        if two in SPOKEN_KEYS or two in SPOKEN_LETTERS:
            keys.append(SPOKEN_KEYS.get(two) or SPOKEN_LETTERS[two])
            i += 2
            continue
        word = words[i]
        if word in SPOKEN_KEYS:
            keys.append(SPOKEN_KEYS[word])
        elif re.fullmatch(r"f(?:[1-9]|1[0-2])|[a-z0-9]", word):
            keys.append(word)
        elif word in SPOKEN_LETTERS and keys:  # окрема літера має сенс лише після модифікатора
            keys.append(SPOKEN_LETTERS[word])
        else:
            return None
        i += 1
    return keys or None
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


@command(
    r"(?:натисни|натисніть|нажми|клацни|тисни) (?:клавіш[уі] |кнопку |комбінацію )?(?P<key>.+)",
    r"(?P<key>(?:альт|alt|контрол\w*|ctrl|control|цтрл|шифт|shift|він|win|віндовс|windows)\b.+)",  # "альт таб"
    priority=2,
)
def _press(key):
    keys = parse_keys(key)
    if keys is None:
        raise NotHandled
    return press_keys("+".join(keys))


def _register_shortcuts():
    for pattern, keys in SHORTCUTS.items():
        command(pattern, priority=4)(lambda keys=keys: hotkey(*keys))


_register_shortcuts()
