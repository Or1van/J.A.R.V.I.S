"""Інтернет і браузер: пошуковик, сайти, адресний рядок, вкладки (і за назвою), головна сторінка, гортання."""
import os
import re
import subprocess
import time
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pygetwindow
import pyperclip

from jarvis.core import runtime
from jarvis.core.desktop import (
    _user32, bring_to_front, find_window_by_process, hotkey, paste_text, press, user_window, window_process,
)
from jarvis.core.registry import CLOSE, OPEN, command, tool
from jarvis.core.text import ORDINAL, name_stem, normalize, parse_ordinal, translit

CHROME_PATHS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / r"Google\Chrome\Application\chrome.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / r"Google\Chrome\Application\chrome.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe",
]
BROWSERS = ("chrome.exe", "msedge.exe", "firefox.exe", "opera.exe", "brave.exe")

# Пошуковики: назва, головна сторінка, адреса пошуку
ENGINES = {
    "google": ("Google", "https://www.google.com", "https://www.google.com/search?q="),
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com", "https://duckduckgo.com/?q="),
}
ENGINE_WORDS = r"(?:гугл\w*|google|дак ?дак ?го|дак дак|duck ?duck ?go|дакдакго)"
# "Відкрий гугл / інтернет / браузер" — відкриває обраний пошуковик
WEB = r"(?:браузер\w*|інтернет|пошуковик|пошук|гугл|google)"

SITES = {
    "ютуб": "https://www.youtube.com", "youtube": "https://www.youtube.com",
    "пошту": "https://mail.google.com", "пошта": "https://mail.google.com", "gmail": "https://mail.google.com",
    "вікіпедію": "https://uk.wikipedia.org", "вікіпедія": "https://uk.wikipedia.org",
    "гітхаб": "https://github.com", "github": "https://github.com",
    "перекладач": "https://translate.google.com",
    "карти": "https://maps.google.com", "мапи": "https://maps.google.com",
    "дак дак го": "https://duckduckgo.com", "duckduckgo": "https://duckduckgo.com",
}
SITE_RE = "|".join(SITES)
# Як сайти звучать українською -> що є в заголовку вкладки
SPOKEN_SITES = {
    "ютуб": "youtube", "гугл": "google", "гітхаб": "github", "телеграм": "telegram", "пошта": "gmail",
    "пошту": "gmail", "вікіпедія": "wikipedia", "клод": "claude", "дак дак го": "duckduckgo", "чат gpt": "chatgpt",
}
YOUTUBE = r"(?:ютубі|ютуб|youtube)"
DOMAIN = re.compile(r"[\w-]+(?:\.[\w-]+)+", re.I)
TAB = r"(?:вкладк\w*|сторінк\w*)"  # "наступна сторінка" = наступна вкладка
# Куди "написати" в браузері: "напиши в гуглі ...", "введи в адресний рядок ..."
ADDRESS_BAR = r"(?:гугл\w*|google|пошук\w*|адресн\w* рядок\w*|рядок\w*|браузер\w*|хром\w*|chrome)"


def browse(url: str) -> None:
    """Відкриває адресу в браузері з налаштувань (за замовчуванням — Chrome)."""
    try:
        choice = runtime.settings().browser
    except RuntimeError:
        choice = "chrome"
    exe = None
    if choice == "chrome":
        exe = next((p for p in CHROME_PATHS if p.exists()), None)
    elif choice != "default" and Path(choice).exists():
        exe = Path(choice)
    if exe:
        subprocess.Popen([str(exe), url])
    else:
        webbrowser.open(url)


def focus_browser() -> bool:
    """Переводить фокус у браузер: той, з яким ви працюєте, або будь-який відкритий."""
    win = user_window()
    if win is None or window_process(win._hWnd) not in BROWSERS:
        win = next((w for b in BROWSERS if (w := find_window_by_process(b))), None)
    return win is not None and bring_to_front(win)


def _engine_from(text: str) -> str | None:
    text = normalize(text)
    if re.search(r"дак|duck", text):
        return "duckduckgo"
    if re.search(r"гугл|google", text):
        return "google"
    return None


def search_engine() -> str:
    """Обраний пошуковик. Першого разу питає і запам'ятовує відповідь."""
    try:
        settings = runtime.settings()
    except RuntimeError:
        return "google"
    if settings.search_engine in ENGINES:
        return settings.search_engine
    runtime.say("Яким пошуковиком користуватись: Google чи DuckDuckGo?")
    engine = _engine_from(runtime.listen(10) or "")
    if engine is None:
        runtime.say("Не розчув, поки відкрию Google. Щоб вибрати, скажіть «зміни пошуковик».")
        return "google"
    settings.search_engine = engine
    settings.save()
    runtime.say(f"Запам'ятав: {ENGINES[engine][0]}.")
    return engine


@tool
def open_url(url: str) -> str:
    """Відкрити сайт у браузері.

    Args:
        url: Адреса сайту, напр. "https://youtube.com".
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    browse(url)
    return "Відкриваю."


@tool
def open_site_named(name: str) -> str:
    """Відкрити сайт за назвою або адресою, коли точна адреса невідома (напр. "розетка", "olx.ua").

    Args:
        name: Назва сайту або адреса.
    """
    domain = DOMAIN.search(name)
    if domain:
        return open_url(domain.group())
    # "\запит" у DuckDuckGo одразу переходить на перший результат пошуку
    browse("https://duckduckgo.com/?q=" + quote_plus("\\" + name))
    return f"Відкриваю сайт {name}."


@tool
def search_web(query: str, site: str = "web") -> str:
    """Знайти щось в інтернеті — відкриває результати пошуку в браузері.

    Args:
        query: Пошуковий запит.
        site: Де шукати: "web" (обраний пошуковик), "youtube" або "wikipedia".
    """
    urls = {
        "youtube": "https://www.youtube.com/results?search_query=",
        "wikipedia": "https://uk.wikipedia.org/w/index.php?search=",
    }
    base = urls[site] if site in urls else ENGINES[search_engine()][2]
    browse(base + quote_plus(query))
    return f"Шукаю «{query}»."


@tool
def browser_go(text: str) -> str:
    """Ввести адресу сайту або пошуковий запит в адресний рядок браузера і перейти (у поточній вкладці).

    Args:
        text: Адреса (напр. "duckduckgo.com") або пошуковий запит.
    """
    if not focus_browser():
        return open_url(text) if DOMAIN.fullmatch(text.strip()) else search_web(text)
    press("ctrl", "l")
    time.sleep(0.15)
    paste_text(text)
    press("enter")
    return "Готово."


@tool
def browser_tab(name: str, close: bool = False) -> str:
    """Знайти відкриту вкладку браузера за назвою (напр. "YouTube") і перейти на неї або закрити її.

    Args:
        name: Назва сайту чи частина заголовка вкладки.
        close: True — закрити знайдену вкладку, False — перейти на неї.
    """
    if not focus_browser():
        return "Браузер не відкритий."
    spoken = normalize(name)
    stem = name_stem(spoken)  # "ютубом" -> "ютуб"
    variants = {v for v in (spoken, stem, translit(stem), SPOKEN_SITES.get(spoken, ""), SPOKEN_SITES.get(stem, ""))
                if len(v) >= 3}
    # Спершу поточне вікно браузера, потім решта (у кожного вікна свої вкладки)
    current = user_window()
    others = [w for w in pygetwindow.getAllWindows()
              if w.title.strip() and w._hWnd != current._hWnd and _user32.IsWindowVisible(w._hWnd)
              and window_process(w._hWnd) in BROWSERS]
    for win in [current, *others]:
        if win is not current and not bring_to_front(win):
            continue
        start = user_window().title
        for _ in range(40):  # перебираємо вкладки по колу (Ctrl+Tab), доки заголовок не збігся
            if any(v in user_window().title.lower() for v in variants):
                if close:
                    press("ctrl", "w")
                    return "Закрив вкладку."
                return ""
            press("ctrl", "tab")
            time.sleep(0.25)
            if user_window().title == start:
                break
    return f"Не знайшов вкладку {name}."


@tool
def browser_home() -> str:
    """Перейти на головну сторінку сайту, відкритого в поточній вкладці (напр. з відео на головну YouTube)."""
    if not focus_browser():
        return "Браузер не відкритий."
    try:
        clipboard = pyperclip.paste()
    except pyperclip.PyperclipException:
        clipboard = None
    press("ctrl", "l")
    time.sleep(0.15)
    press("ctrl", "c")  # копіюємо адресу поточної сторінки
    time.sleep(0.2)
    url = pyperclip.paste().strip()
    parsed = urlparse(url if "://" in url else "https://" + url)
    if not parsed.netloc:
        press("esc")
        return "Не бачу адреси сторінки."
    paste_text(f"{parsed.scheme}://{parsed.netloc}/")
    press("enter")
    if clipboard is not None:
        pyperclip.copy(clipboard)
    return ""


def _raw_after(pattern: str) -> str:
    """Точний текст команди після службових слів (напр. після "напиши в гуглі")."""
    return re.sub(rf"^.*?{pattern}[\s,:]*", "", runtime.command_text(), count=1, flags=re.I).strip()


def _browser_keys(*keys: str):
    if not focus_browser():
        return "Браузер не відкритий."
    press(*keys)


# ---------- пошуковик, сайти й пошук ----------

@command(rf"{OPEN} (?:мені )?{WEB}", priority=3)
def _open_web():
    return open_url(ENGINES[search_engine()][1])


@command(
    r"(?:зміни|змінити|вибери|інший) (?:пошуковик|пошукову систему|пошуковий сервіс)",
    rf"(?:пошуковик|використовуй|шукай через|шукай в) (?P<engine>{ENGINE_WORDS})",
    priority=6,
)
def _change_engine(engine=None):
    settings = runtime.settings()
    settings.search_engine = (_engine_from(engine) if engine else "") or ""
    settings.save()
    if not settings.search_engine:
        search_engine()  # спитає
        return None
    return f"Тепер шукаю через {ENGINES[settings.search_engine][0]}."


@command(rf"{OPEN} (?:сайт )?(?P<site>{SITE_RE})", priority=3)
def _open_site(site):
    return open_url(SITES[site])


@command(rf"{OPEN} сайт (?P<name>.+)", priority=2)
def _open_named_site(name):
    return open_site_named(_raw_after(r"сайт") or name)


@command(
    rf"(?:знайди|пошукай|увімкни|включи) (?:на |в )?{YOUTUBE} (?P<query>.+)",
    rf"(?:знайди|пошукай|увімкни|включи) (?P<query>.+?) (?:на|в) {YOUTUBE}",
    priority=3,
)
def _search_youtube(query):
    return search_web(query, "youtube")


@command(r"(?:знайди|пошукай|загугли) (?:в інтернеті |в гуглі |в google )?(?P<query>.+)", priority=1)
def _search_web(query):
    return search_web(query)


@command(rf"(?:напиши|введи|вбий|набери|пошукай) (?:в |у )?{ADDRESS_BAR} (?P<text>.+)", priority=4)
def _address_bar(text):
    return browser_go(_raw_after(ADDRESS_BAR) or text)


@command(r"знайди на сторінці (?P<text>.+)", priority=4)
def _find_on_page(text):
    if not focus_browser():
        return "Браузер не відкритий."
    press("ctrl", "f")
    time.sleep(0.15)
    paste_text(_raw_after(r"сторінці") or text)


@command(
    r"(?:зайди |перейди |повернись |відкрий )?на головну(?: сторінку)?(?: сайту)?|головна сторінка|додому",
    priority=5,
)
def _home():
    return browser_home()


# ---------- вкладки ----------

@command(rf"(?:нова|відкрий нову) {TAB}", priority=4)
def _new_tab():
    return _browser_keys("ctrl", "t")


@command(rf"{CLOSE} {TAB}|{CLOSE} цю {TAB}|{CLOSE} поточну {TAB}", priority=4)
def _close_tab():
    return _browser_keys("ctrl", "w")


@command(rf"{CLOSE} {TAB} (?:з |із )?(?P<name>.+)", rf"{CLOSE} (?P<name>.+?) {TAB}", priority=5)
def _close_named_tab(name):
    return browser_tab(name, close=True)


@command(rf"(?:перейди|переключись|перемкнись|відкрий|покажи)(?: на)? {TAB} (?P<name>.+)", priority=5)
def _go_named_tab(name):
    if parse_ordinal(name) is not None:
        return _tab_number(name)
    return browser_tab(name)


@command(rf"(?:поверни|відкрий) закриту {TAB}", priority=4)
def _reopen_tab():
    return _browser_keys("ctrl", "shift", "t")


@command(rf"наступна {TAB}|(?:переключи|перемкни|зміни|гортай) (?:вкладку|сторінку)", priority=4)
def _next_tab():
    return _browser_keys("ctrl", "tab")


@command(rf"попередня {TAB}", priority=4)
def _previous_tab():
    return _browser_keys("ctrl", "shift", "tab")


@command(rf"(?:перейди на|відкрий|перемкнись на|переключись на) (?P<n>{ORDINAL}|останн\w*) {TAB}", priority=4)
def _tab_number(n):
    number = 9 if n.startswith("останн") else parse_ordinal(n)
    if number is None:
        return None
    return _browser_keys("ctrl", str(min(number, 9)))


# ---------- навігація й перегляд (працює і в інших програмах) ----------

@command(r"назад|повернись назад|сторінка назад", priority=4)
def _back():
    hotkey("alt", "left")


@command(r"вперед|сторінка вперед", priority=4)
def _forward():
    hotkey("alt", "right")


@command(r"(?:онови|оновити|перезавантаж)(?: сторінку)?", priority=4)
def _reload():
    hotkey("f5")


SCROLL = r"(?:прокрути\w*|гортай|покрути|скрол\w*|листай|спусти\w*|опусти\w*|підніми\w*|підійми\w*|йди|перейди)"


@command(
    rf"{SCROLL}(?: сторінку)?(?: ще)?(?: трохи)?(?: нижче| вниз| донизу)?(?: ще)?",
    r"(?:ще )?(?:трохи )?нижче",
    priority=4,
)
def _scroll_down():
    hotkey("pagedown")


@command(
    rf"{SCROLL}(?: сторінку)?(?: ще)?(?: трохи)? (?:вгору|догори|вище|нагору)(?: ще)?",
    r"(?:підніми\w*|підійми\w*)(?: сторінку)?(?: ще)?(?: трохи)?",
    r"(?:ще )?(?:трохи )?вище",
    priority=4,
)
def _scroll_up():
    hotkey("pageup")


@command(
    rf"(?:{SCROLL} )?(?:в |у |на |до )?(?:самий |самого )?(?:верх\w*|поч\w*|вгору|догори) сторінки",
    rf"(?:{SCROLL} )?(?:на початок|на самий верх|до самого верху|на самий початок)",
    priority=4,
)
def _top():
    hotkey("home")


@command(
    rf"(?:{SCROLL} )?(?:в |у |на |до )?(?:самий |самого )?(?:низ\w*|кін\w*|вниз|донизу) сторінки",
    rf"(?:{SCROLL} )?(?:в кінець|на самий низ|до самого низу|до кінця|в самий низ)",
    priority=4,
)
def _bottom():
    hotkey("end")


# ---------- відео на сайті (YouTube — його гарячими клавішами, інші сайти — медіаклавішами) ----------

VIDEO = r"(?:відео|ролик\w*|кліп\w*)"


def _video(youtube_keys: tuple, other_keys: tuple | None = None):
    if not focus_browser():
        return "Браузер не відкритий."
    if "youtube" in user_window().title.lower():
        press(*youtube_keys)
    elif other_keys:
        press(*other_keys)
    else:
        return "Це вмію лише на YouTube."


@command(
    rf"(?:запусти|увімкни|включи|постав|продовж\w*|відтвори|грай) {VIDEO}",
    rf"(?:зупини|призупини|пауза|постав на паузу) {VIDEO}|(?:постав )?{VIDEO} на паузу|пауза на {VIDEO}",
    priority=5,
)
def _video_play_pause():
    if not focus_browser():
        return "Браузер не відкритий."
    if "youtube" in user_window().title.lower():
        press("k")
    else:
        from jarvis.core.desktop import press_vk
        press_vk(0xB3)  # медіаклавіша "відтворити/пауза" — Chrome передає її відео на сторінці


@command(rf"(?:перемотай|промотай|мотай) (?:{VIDEO} )?вперед", rf"(?:перемотай|промотай|мотай) (?:{VIDEO} )?далі", priority=5)
def _video_forward():
    return _video(("l",), ("right",))


@command(rf"(?:перемотай|промотай|мотай) (?:{VIDEO} )?назад", priority=5)
def _video_back():
    return _video(("j",), ("left",))


@command(rf"{VIDEO} на весь екран|розгорни {VIDEO}|(?:вийди з|згорни) (?:повноекранного )?{VIDEO}", priority=5)
def _video_fullscreen():
    return _video(("f",))


@command(rf"(?:вимкни|увімкни) (?:звук (?:на |у )?{VIDEO}|{VIDEO} без звуку)", priority=5)
def _video_mute():
    return _video(("m",))


@command(r"(?:увімкни|вимкни|включи) субтитри", priority=5)
def _video_subtitles():
    return _video(("c",))


@command(r"(?:збільш|наблиз)\w*(?: масштаб| сторінку| текст)?", priority=4)
def _zoom_in():
    hotkey("ctrl", "=")


@command(r"(?:зменш|віддал)\w*(?: масштаб| сторінку| текст)?", priority=4)
def _zoom_out():
    hotkey("ctrl", "-")


@command(r"(?:звичайний|нормальний) масштаб", priority=4)
def _zoom_reset():
    hotkey("ctrl", "0")


@command(r"на весь екран|повноекранний режим|вийди з повноекранного режиму", priority=4)
def _fullscreen():
    hotkey("f11")
